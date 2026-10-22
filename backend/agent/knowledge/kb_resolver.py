"""Knowledge-base resolver — the agent's read API over the knowledge graph.

Loads knowledge_base/{data_dictionary,knowledge_graph}.json once and answers
the questions every pipeline stage needs:

    match_terms(text)     which tables / columns / metrics / business terms a question mentions
    match_values(text)    which stored values a question means ("California" → State = 'CA')
    relevant_tables(text) which tables a question needs (schema retrieval)
    connect(tables)       the joins that connect a set of tables (shortest paths, FK-based)
    resolve_table/column  snap an LLM-written identifier to the real one (case / synonym tolerant)
    schema_context(...)   compact, prompt-ready description of the selected schema

Everything here is deterministic: no LLM calls.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from itertools import combinations
from pathlib import Path

from utils.config import get_settings

_WORD = r"[a-z0-9]"


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", str(text).strip().lower())


@dataclass(frozen=True)
class PhraseMatch:
    phrase: str  # the index key that matched
    text: str  # the exact span in the user's text
    start: int
    end: int
    entries: tuple[dict, ...]


@dataclass
class Retrieval:
    tables: list[str]
    joins: list[str]
    term_matches: list[PhraseMatch] = field(default_factory=list)
    value_matches: list[PhraseMatch] = field(default_factory=list)
    metrics: list[dict] = field(default_factory=list)
    glossary: list[dict] = field(default_factory=list)
    scores: dict[str, float] = field(default_factory=dict)


class KnowledgeBase:
    def __init__(self, dictionary: dict, graph: dict):
        self.dictionary = dictionary
        self.graph = graph
        self.meta = dictionary["meta"]
        self.tables: dict[str, dict] = dictionary["tables"]
        self.metrics: dict[str, dict] = {m["id"]: m for m in graph["metrics"]}
        self.glossary: dict[str, dict] = {g["id"]: g for g in graph["glossary"]}
        self.relationships: list[dict] = graph["relationships"]
        self.join_paths_index: dict[str, list[dict]] = graph["join_paths"]
        self._term_re = self._compile(graph["term_index"])
        self._value_re = self._compile(graph["value_index"])
        self._table_lc = {t.lower(): t for t in self.tables}
        self._column_lc = {t: {c.lower(): c for c in info["columns"]} for t, info in self.tables.items()}

    @classmethod
    def load(cls, directory: Path) -> KnowledgeBase:
        dictionary = json.loads((directory / "data_dictionary.json").read_text(encoding="utf-8"))
        graph = json.loads((directory / "knowledge_graph.json").read_text(encoding="utf-8"))
        return cls(dictionary, graph)

    # ── phrase matching ──────────────────────────────────────────────────

    @staticmethod
    def _compile(index: dict[str, list[dict]]) -> tuple[re.Pattern, dict[str, list[dict]]]:
        # A zero-width lookahead finds a candidate at EVERY position (overlaps included);
        # at each position the longest key wins because keys are tried longest-first.
        keys = sorted(index, key=len, reverse=True)
        alternation = "|".join(re.escape(k) for k in keys)
        pattern = re.compile(rf"(?<!{_WORD})(?=(({alternation})(?:s|es)?)(?!{_WORD}))")
        return pattern, index

    @staticmethod
    def _entries(index: dict[str, list[dict]], key: str) -> list[dict]:
        """Entries for a key plus its singular form ("sales reps" also means the "sales rep" column)."""
        entries = list(index[key])
        if key.endswith("s") and key[:-1] in index:
            entries += [e for e in index[key[:-1]] if e not in entries]
        return entries

    def _scan(self, compiled: tuple[re.Pattern, dict], text: str, keep=None) -> list[PhraseMatch]:
        """Longest non-overlapping phrase matches, chosen across the whole text (not leftmost-first)."""
        pattern, index = compiled
        candidates = []
        for m in pattern.finditer(text.lower()):
            start, span, key = m.start(), m.group(1), m.group(2)
            original = text[start:start + len(span)]
            entries = [e for e in self._entries(index, key) if keep is None or keep(e, original)]
            if entries:
                candidates.append(PhraseMatch(key, original, start, start + len(span), tuple(entries)))
        chosen: list[PhraseMatch] = []
        for c in sorted(candidates, key=lambda c: (-(c.end - c.start), c.start)):
            if all(c.end <= o.start or c.start >= o.end for o in chosen):
                chosen.append(c)
        return sorted(chosen, key=lambda c: c.start)

    def match_terms(self, text: str) -> list[PhraseMatch]:
        return self._scan(self._term_re, text)

    def match_values(self, text: str) -> list[PhraseMatch]:
        # A bare state code only counts when written in capitals: "IN" is Indiana, "in" is a word.
        def keep(entry: dict, original: str) -> bool:
            return entry.get("match") != "state_code" or original.rstrip("sS").isupper()

        return self._scan(self._value_re, text, keep)

    # ── identifier resolution ────────────────────────────────────────────

    def resolve_table(self, name: str) -> str | None:
        """Exact (case-insensitive) table name, else a table synonym ("customer" → Customers)."""
        key = _norm(name).strip('"`[]')
        if key in self._table_lc:
            return self._table_lc[key]
        hits = {e["table"] for e in self.graph["term_index"].get(key, []) if e["kind"] == "table"}
        return hits.pop() if len(hits) == 1 else None

    def resolve_column(self, name: str, tables: list[str] | None = None) -> list[tuple[str, str]]:
        """All (table, column) pairs a name can mean, restricted to `tables` when given."""
        key = _norm(name).strip('"`[]')
        scope = tables or list(self.tables)
        exact = [(t, self._column_lc[t][key]) for t in scope if key in self._column_lc[t]]
        if exact:
            return exact
        squashed = key.replace(" ", "").replace("_", "")
        exact = [(t, self._column_lc[t][squashed]) for t in scope if squashed in self._column_lc[t]]
        if exact:
            return exact
        return [(e["table"], e["column"]) for e in self.graph["term_index"].get(key, [])
                if e["kind"] == "column" and e["table"] in scope]

    def column(self, table: str, column: str) -> dict | None:
        return self.tables.get(table, {}).get("columns", {}).get(column)

    # ── joins ────────────────────────────────────────────────────────────

    def join_paths(self, a: str, b: str) -> list[dict]:
        return self.join_paths_index.get(f"{a}->{b}", [])

    def connect(self, tables: list[str], prefer_columns: set[str] | frozenset = frozenset()
                ) -> tuple[list[str], list[str]]:
        """Smallest set of FK joins that connects `tables` (bridge tables added as needed).

        The schema is small, so this enumerates relationship subsets by size and
        takes the first size that connects everything (an exact Steiner tree).
        Ties — e.g. Customers↔Employees via AccountManagerID or via Orders — go to
        joins on FK columns the question mentioned (`prefer_columns`), then to
        NOT NULL foreign keys. Returns (tables incl. bridges, join conditions).
        """
        wanted = list(dict.fromkeys(t for t in tables if t in self.tables))
        if len(wanted) <= 1:
            return wanted, []
        rels = [r for r in self.relationships if not r["self_reference"]]
        for size in range(1, len(rels) + 1):
            best, best_score = None, None
            for subset in combinations(rels, size):
                if not self._connects(subset, wanted):
                    continue
                score = sum(2 * (r["id"] in prefer_columns) + (not r["nullable"]) for r in subset)
                if best_score is None or score > best_score:
                    best, best_score = subset, score
            if best is not None:
                extra = [t for r in best for t in (r["from_table"], r["to_table"]) if t not in wanted]
                return wanted + list(dict.fromkeys(extra)), [r["join_condition"] for r in best]
        return wanted, []

    @staticmethod
    def _connects(rels: tuple[dict, ...], wanted: list[str]) -> bool:
        adj: dict[str, set[str]] = {}
        for r in rels:
            adj.setdefault(r["from_table"], set()).add(r["to_table"])
            adj.setdefault(r["to_table"], set()).add(r["from_table"])
        if any(t not in adj for t in wanted):
            return False
        seen, stack = {wanted[0]}, [wanted[0]]
        while stack:
            for nxt in adj[stack.pop()] - seen:
                seen.add(nxt)
                stack.append(nxt)
        # every wanted table reachable, and no dangling edges outside the connected tree
        return all(t in seen for t in wanted) and all(t in seen for t in adj)

    @property
    def hub_tables(self) -> set[str]:
        """Fact tables: two or more foreign keys to other tables (Orders, OrderItems)."""
        outgoing: dict[str, int] = {}
        for r in self.relationships:
            if not r["self_reference"]:
                outgoing[r["from_table"]] = outgoing.get(r["from_table"], 0) + 1
        return {t for t, n in outgoing.items() if n >= 2}

    def ambiguous_links(self, tables: list[str]) -> list[dict]:
        """Table pairs in `tables` that can be joined in more than one MEANINGFUL way.

        An alternative path only counts when every table it passes through is a
        fact table linking both sides — Customers ↔ Employees directly (account
        manager) or through Orders (the rep who booked the order). A detour through
        a lookup table (Customers → Employees → Orders) is not a real alternative.
        """
        hubs, out = self.hub_tables, []
        for i, a in enumerate(tables):
            for b in tables[i + 1:]:
                paths = self.join_paths(a, b)
                if not paths:
                    continue
                shortest = paths[0]["hops"]
                options = [p for p in paths if p["hops"] <= shortest + 1
                           and all(t in hubs for t in p["tables"][1:-1])]
                if len(options) > 1:
                    out.append({"tables": [a, b], "options": [
                        {"joins": p["joins"], "meaning": p["meaning"]} for p in options[:2]]})
        return out

    # ── retrieval ────────────────────────────────────────────────────────

    def relevant_tables(self, text: str) -> Retrieval:
        """Score tables by what the question mentions, keep the clear hits, then add bridge tables."""
        terms = self.match_terms(text)
        # A value match inside a longer schema phrase is explained by that phrase ("product
        # category" is Products.Category, not the 'Product' department), and a word that names
        # a table is a table reference ("products" is the Products table, not that department).
        def explained(v: PhraseMatch) -> bool:
            for t in terms:
                if t.start <= v.start and v.end <= t.end:
                    longer = (t.end - t.start) > (v.end - v.start)
                    if longer or any(e["kind"] == "table" for e in t.entries):
                        return True
            return False

        def beside_its_column(v: PhraseMatch) -> bool:
            # "Product department": the value sits right next to the name of its own column.
            own = {(e["table"], e["column"]) for e in v.entries}
            for t in terms:
                adjacent = 0 <= t.start - v.end <= 3 or 0 <= v.start - t.end <= 3
                if adjacent and any(e["kind"] == "column" and (e["table"], e["column"]) in own for e in t.entries):
                    return True
            return False

        values, value_words = [], set()
        for v in self.match_values(text):
            if beside_its_column(v):
                values.append(v)
                value_words.add((v.start, v.end))
            elif not explained(v):
                values.append(v)
        # A word read as a value is not also a table reference.
        terms = [t for t in terms if (t.start, t.end) not in value_words]
        mentioned = {f"{e['table']}.{e['column']}" for m in terms for e in m.entries if e["kind"] == "column"}
        scores = {t: 0.0 for t in self.tables}
        metrics, glossary = {}, {}

        def credit(tables: set[str], strong: float, shared: float) -> None:
            for t in tables:
                scores[t] += strong if len(tables) == 1 else shared

        for m in terms:
            for e in m.entries:
                if e["kind"] == "table":
                    scores[e["table"]] += 3
                elif e["kind"] == "metric":
                    metric = self.metrics[e["id"]]
                    metrics[metric["id"]] = metric
                    credit(set(metric["tables"]), 2, 2)
                elif e["kind"] == "term":
                    term = self.glossary[e["id"]]
                    glossary[term["id"]] = term
                    credit(set(term.get("tables", [])), 2, 2)
            columns = [e for e in m.entries if e["kind"] == "column"]
            credit({e["table"] for e in columns}, 2, 0.5)
            # Naming a foreign key ("account manager", "sales rep") means the row it points to.
            for e in columns:
                ref = self.column(e["table"], e["column"]).get("references")
                if ref and len(columns) == 1:
                    scores[ref.split(".")[0]] += 2
        for m in values:
            credit({e["table"] for e in m.entries}, 2, 0.5)

        chosen = [t for t, s in sorted(scores.items(), key=lambda kv: -kv[1]) if s >= 2]
        if not chosen:
            best = max(scores.values())
            chosen = [t for t, s in scores.items() if s == best and s > 0] or list(self.tables)
        tables, joins = self.connect(chosen, mentioned)
        return Retrieval(tables, joins, terms, values, list(metrics.values()), list(glossary.values()), scores)

    # ── prompt rendering ─────────────────────────────────────────────────

    def schema_context(self, tables: list[str] | None = None, *, metrics: list[dict] | None = None,
                       glossary: list[dict] | None = None, include_conventions: bool = True,
                       include_indexes: bool = False) -> str:
        """Prompt-ready description: full detail for `tables`, a one-line summary for the rest."""
        detail = tables or list(self.tables)
        lines = [f"DATABASE: {self.meta['domain']}",
                 f"Dialect: {self.meta['dialect']}. Data snapshot date: {self.meta['as_of_date']}.", ""]
        for t in detail:
            lines.extend(self._render_table(t))
            if include_indexes:
                idx = [f"{i['name']} ({', '.join(i['columns'])})" for i in self.tables[t]["indexes"]]
                lines.append(f"  INDEXES: {'; '.join(idx) or 'none'}")
            lines.append("")
        others = [t for t in self.tables if t not in detail]
        if others:
            lines.append("OTHER TABLES (ask for them only if needed):")
            lines.extend(f"  {t} — {self.tables[t]['description']}" for t in others)
            lines.append("")
        rels = [r for r in self.relationships if r["from_table"] in detail and r["to_table"] in detail]
        if rels:
            lines.append("RELATIONSHIPS (the only valid joins):")
            lines.extend(f"  {r['join_condition']}  -- {r['description']}" for r in rels)
            lines.append("")
        if include_conventions:
            lines.append("CONVENTIONS:")
            lines.extend(f"  - {c['rule']}" for c in self.dictionary["conventions"])
            lines.append("")
        if metrics:
            lines.append("BUSINESS METRICS (validated definitions — reuse them):")
            for m in metrics:
                if m.get("expression"):
                    filters = " AND ".join(m["default_filters"]) or "none"
                    lines.append(f"  {m['name']}: {m['expression']}  FROM {m['base_from']}  WHERE {filters}")
                else:
                    lines.append(f"  {m['name']}: {m['sql']}")
            lines.append("")
        if glossary:
            lines.append("BUSINESS TERMS:")
            for g in glossary:
                line = f"  {g['term']}: {g['definition']}"
                if g.get("sql"):
                    line += f"  SQL over {g['applies_to']}: {g['sql']}"
                if g.get("ambiguous"):
                    line += f"  (default: {g['default']}; alternatives: {', '.join(g['alternatives'])})"
                lines.append(line)
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    def _render_table(self, t: str) -> list[str]:
        info = self.tables[t]
        out = [f"TABLE {t} — {info['description']} Grain: {info['grain']} ({info['row_count']:,} rows)"]
        for c, col in info["columns"].items():
            flags = []
            if col["role"] == "primary_key":
                flags.append("PK")
            if col.get("references"):
                flags.append(f"FK → {col['references']}")
            if col["nullable"]:
                flags.append("nullable")
            head = f"  {c} {col['type']}" + (f" [{', '.join(flags)}]" if flags else "")
            out.append(f"{head} — {col['description']}{self._render_values(col)}")
        return out

    @staticmethod
    def _render_values(col: dict) -> str:
        if col.get("semantic_type") == "us_state":
            top = ", ".join(f"'{v['value']}'" for v in (col.get("values") or [])[:3]) or "'CA', 'TX', 'NY'"
            return f" Values are 2-letter state codes, e.g. {top}."
        values = col.get("values")
        if values and col["role"] in ("category", "flag", "attribute"):
            if len(values) <= 12 and any(v.get("meaning") for v in values):
                listed = "; ".join(f"'{v['value']}' = {v['meaning']}" if v.get("meaning") else f"'{v['value']}'"
                                   for v in values)
                return f" Values: {listed}"
            return " Values: " + ", ".join(f"'{v['value']}'" for v in values)
        if col["role"] == "date" and col["stats"].get("min"):
            return f" Range {col['stats']['min']} to {col['stats']['max']}."
        if col["role"] == "measure" and col["stats"].get("min") is not None:
            return f" Range {col['stats']['min']} to {col['stats']['max']}."
        if col.get("samples"):
            return " e.g. " + ", ".join(f"'{s}'" for s in col["samples"][:3])
        return ""


@lru_cache
def get_kb() -> KnowledgeBase:
    return KnowledgeBase.load(get_settings().knowledge_dir)
