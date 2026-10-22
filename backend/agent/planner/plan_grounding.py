"""Node: plan_grounding — make the plan true to the real schema and data, deterministically.

The intelligence-assistant planner snaps every metric name the LLM wrote back to
the exact menu string before anything resolves it. This is the same idea for a
relational schema:

  tables    "customer" → Customers; unknown tables become a clarification
  columns   "hire_date" → Employees.HireDate; a column on the wrong table moves
            to the right one; a column that exists nowhere → clarification with
            the closest real columns
  values    "California" → 'CA', "west coast" → IN ('CA','OR','WA'),
            "canceled" → 'Cancelled', "standing desks" → the matching ProductName
            values found in the database; an impossible value for a closed set →
            clarification listing the valid values
  metrics   "revenue" → the validated Net Revenue definition
  joins     the FK join tree connecting every table (bridge tables added),
            honouring the relationship the planner chose when two exist
  complexity  a score that model routing uses for SQL generation

Anything that cannot be resolved without guessing becomes a clarifying question
instead of SQL.
"""

from __future__ import annotations

import difflib
import re

from langchain_core.runnables import RunnableConfig

from agent.exec.sqlite_runner import ReadOnlyDatabase
from agent.knowledge.kb_resolver import KnowledgeBase, _norm
from agent.supervisor.dependencies import AgentDeps
from agent.supervisor.state import AgentState

_TRUE = {"true", "yes", "1", "y", "discontinued"}
_FALSE = {"false", "no", "0", "n", "active", "not discontinued"}
_LIST_OPS = {"=": "IN", "!=": "NOT IN"}


def plan_grounding(state: AgentState, deps: AgentDeps, config: RunnableConfig) -> dict:
    plan = state["plan"]
    grounded = ground_plan(plan, deps.kb, deps.db)
    update = {
        "grounded_plan": grounded,
        "_trace": {"tables": grounded["tables"], "joins": grounded["joins"], "mappings": grounded["mappings"],
                   "issues": grounded["issues"], "complexity": grounded["complexity"]},
    }
    if plan.get("needs_clarification") or grounded["issues"]:
        question = plan.get("clarification_question") if plan.get("needs_clarification") else None
        update["clarification"] = {
            "question": question or " ".join(grounded["issues"]),
            "options": plan.get("clarification_options") or grounded["options"],
            "request": state["standalone_question"],
        }
    return update


def ground_plan(plan: dict, kb: KnowledgeBase, db: ReadOnlyDatabase) -> dict:
    g = _Grounder(kb, db)
    return g.run(plan)


class _Grounder:
    def __init__(self, kb: KnowledgeBase, db: ReadOnlyDatabase):
        self.kb, self.db = kb, db
        self.issues: list[str] = []
        self.options: list[str] = []
        self.mappings: list[str] = []
        self.assumptions: list[str] = []
        self.tables: list[str] = []

    # ── entry ────────────────────────────────────────────────────────────

    def run(self, plan: dict) -> dict:
        self.assumptions = list(plan.get("assumptions") or [])
        for name in plan.get("tables") or []:
            real = self.kb.resolve_table(name)
            if real:
                self._add_table(real)
            else:
                self.issues.append(f"The database has no '{name}' table (available: {', '.join(self.kb.tables)}).")

        select = [self._ground_select(item) for item in plan.get("select") or []]
        filters = [f for f in (self._ground_filter(f) for f in plan.get("filters") or []) if f]
        group_by = [self._ground_ref(g) for g in plan.get("group_by") or []]
        metrics = [s["metric_definition"] for s in select if s.get("metric_definition")]

        preferred = set(re.findall(r"\b([A-Z]\w+\.[A-Z]\w+)\b", " ".join(plan.get("relationship_notes") or [])))
        preferred |= {f"{s['table']}.{s['column']}" for s in select if s.get("table") and s.get("column")}
        tables, joins = self.kb.connect(self.tables, preferred)
        for link in self.kb.ambiguous_links(tables):
            used = [o for o in link["options"] if all(j in joins for j in o["joins"])]
            if used and not plan.get("relationship_notes"):
                a, b = link["tables"]
                how = (used[0]["meaning"] or used[0]["joins"][0]).rstrip(".")
                self.assumptions.append(f"Linked {a} to {b} through: {how}.")

        grounded = {
            "restated_request": plan.get("restated_request"),
            "tables": tables,
            "joins": joins,
            "select": select,
            "filters": filters,
            "group_by": group_by,
            "having": plan.get("having") or [],
            "order_by": plan.get("order_by") or [],
            "limit": plan.get("limit"),
            "distinct": bool(plan.get("distinct")),
            "include_unmatched": bool(plan.get("include_unmatched")),
            "relationship_notes": plan.get("relationship_notes") or [],
            "metrics": metrics,
            "mappings": self.mappings,
            "assumptions": self.assumptions,
            "issues": self.issues,
            "options": self.options[:6],
        }
        grounded["complexity"] = complexity(grounded)
        return grounded

    # ── pieces ───────────────────────────────────────────────────────────

    def _add_table(self, table: str) -> None:
        if table not in self.tables:
            self.tables.append(table)

    def _resolve(self, table: str | None, column: str) -> tuple[str, str] | None:
        stated = self.kb.resolve_table(table) if table else None
        if stated:
            hits = self.kb.resolve_column(column, [stated])
            if hits:
                return hits[0]
        in_plan = self.kb.resolve_column(column, self.tables or None)
        if len(in_plan) == 1:
            return in_plan[0]
        anywhere = self.kb.resolve_column(column)
        if len(anywhere) == 1:
            return anywhere[0]
        return (in_plan or anywhere or [None])[0]

    def _unknown_column(self, table: str | None, column: str) -> None:
        pool = [f"{t}.{c}" for t, info in self.kb.tables.items() for c in info["columns"]]
        close = difflib.get_close_matches(column.lower(), [p.split(".")[1].lower() for p in pool], n=3, cutoff=0.5)
        suggestions = [p for p in pool if p.split(".")[1].lower() in close][:3]
        where = f"{table}." if table else ""
        msg = f"The data has no '{where}{column}' field."
        if suggestions:
            msg += f" Closest available: {', '.join(suggestions)}."
            self.options.extend(suggestions)
        self.issues.append(msg)

    def _ground_ref(self, ref: str) -> str:
        m = re.fullmatch(r"\s*(\w+)\.(\w+)\s*", ref or "")
        if not m:
            return ref
        hit = self._resolve(m.group(1), m.group(2))
        if hit:
            self._add_table(hit[0])
            return f"{hit[0]}.{hit[1]}"
        return ref

    def _ground_select(self, item: dict) -> dict:
        out = dict(item)
        kind = item.get("kind")
        if kind == "metric":
            metric = self._find_metric(item.get("metric") or item.get("alias") or "")
            if metric:
                out["metric"] = metric["name"]
                out["metric_definition"] = {k: metric.get(k) for k in
                                            ("name", "expression", "base_from", "default_filters", "sql", "unit")}
                for t in metric["tables"]:
                    self._add_table(t)
            else:
                self.assumptions.append(f"'{item.get('metric')}' is not a defined business metric; "
                                        "it is computed from its plain meaning.")
            return out
        if kind == "all_columns":
            real = self.kb.resolve_table(item.get("table") or "")
            if real:
                out["table"] = real
                self._add_table(real)
            return out
        if item.get("column"):
            hit = self._resolve(item.get("table"), item["column"])
            if hit:
                out["table"], out["column"] = hit
                self._add_table(hit[0])
            else:
                self._unknown_column(item.get("table"), item["column"])
        return out

    def _find_metric(self, name: str) -> dict | None:
        key = _norm(name)
        for m in self.kb.metrics.values():
            if _norm(m["name"]) == key or key in (_norm(s) for s in m["synonyms"]):
                return m
        hits = [e for e in self.kb.graph["term_index"].get(key, []) if e["kind"] == "metric"]
        return self.kb.metrics[hits[0]["id"]] if hits else None

    def _ground_filter(self, f: dict) -> dict | None:
        hit = self._resolve(f.get("table"), f.get("column") or "")
        if not hit:
            self._unknown_column(f.get("table"), f.get("column") or "?")
            return None
        table, column = hit
        self._add_table(table)
        operator = f.get("operator", "=")
        values = [str(v) for v in f.get("values") or []]
        stored = self._ground_values(table, column, operator, values)
        if len(stored) > 1 and operator in _LIST_OPS:
            operator = _LIST_OPS[operator]
        return {"table": table, "column": column, "operator": operator, "values": values, "stored_values": stored}

    def _ground_values(self, table: str, column: str, operator: str, values: list[str]) -> list[str]:
        meta = self.kb.column(table, column)
        if operator in ("IS NULL", "IS NOT NULL") or not values:
            return []
        role = meta["role"]
        if role == "flag":
            return ["1" if v.lower() in _TRUE else "0" if v.lower() in _FALSE else v for v in values]
        if role in ("date", "measure", "primary_key", "foreign_key"):
            return values
        if operator in ("LIKE", "NOT LIKE"):
            return [v if "%" in v or "_" in v else f"%{v}%" for v in values]

        enumerated = [v["value"] for v in meta.get("values") or []]
        out: list[str] = []
        for v in values:
            if v in enumerated:
                out.append(v)
                continue
            mapped = self._from_value_index(table, column, v, enumerated)
            if mapped:
                out.extend(mapped)
                continue
            if role == "category":  # closed set and nothing matched: ask
                listed = ", ".join(enumerated[:12]) + (" …" if len(enumerated) > 12 else "")
                self.issues.append(f"'{v}' is not a valid {column} value (valid: {listed}).")
                self.options.extend(enumerated[:6])
                continue
            found = self._search_database(table, column, v, operator)
            out.extend(found)
        return list(dict.fromkeys(out))

    def _from_value_index(self, table: str, column: str, v: str, enumerated: list[str]) -> list[str]:
        ci = [e for e in enumerated if e.lower() == v.lower()]
        if ci:
            if ci[0] != v:
                self.mappings.append(f"'{v}' → {table}.{column} = '{ci[0]}'")
            return ci[:1]
        entries = [e for e in self.kb.graph["value_index"].get(_norm(v), [])
                   if e["table"] == table and e["column"] == column]
        if not entries:  # phrase inside the value ("the West Coast region")
            entries = [e for m in self.kb.match_values(v) for e in m.entries
                       if e["table"] == table and e["column"] == column]
        if not entries:
            return []
        e = entries[0]
        if "values" in e:
            self.mappings.append(f"'{v}' → {table}.{column} IN ({', '.join(repr(x) for x in e['values'])})")
            return list(e["values"])
        self.mappings.append(f"'{v}' → {table}.{column} = '{e['value']}'")
        return [e["value"]]

    def _search_database(self, table: str, column: str, v: str, operator: str) -> list[str]:
        """Open-ended text column (product names, cities, companies): look for stored values containing v."""
        candidates = [v]
        if v.lower().endswith("es"):
            candidates.append(v[:-2])
        if v.lower().endswith("s"):
            candidates.append(v[:-1])
        for needle in candidates:
            matches = self.db.distinct_matching(table, column, needle.strip())
            if matches:
                exact = [m for m in matches if m.lower() == needle.lower()]
                chosen = exact or matches
                if chosen != [v]:
                    shown = ", ".join(repr(m) for m in chosen[:5]) + (", …" if len(chosen) > 5 else "")
                    target = f"= {shown}" if len(chosen) == 1 else f"IN ({shown})"
                    self.mappings.append(f"'{v}' → {table}.{column} {target}")
                return chosen
        pool = self.db.distinct_matching(table, column, "", limit=500)
        close = difflib.get_close_matches(v, pool, n=4, cutoff=0.6)
        if close:
            self.issues.append(f"No {table}.{column} matches '{v}'. Did you mean {', '.join(repr(c) for c in close)}?")
            self.options.extend(close)
            return []
        self.assumptions.append(f"No {table}.{column} value matches '{v}', so the query may return no rows.")
        return [v]


def complexity(grounded: dict) -> int:
    """Rough difficulty score used by model routing: 0–1 simple, 2+ needs the main model."""
    select = grounded["select"]
    score = max(0, len(grounded["tables"]) - 1)
    score += any(s.get("kind") in ("aggregate", "metric") for s in select)
    score += bool(grounded["group_by"])
    score += bool(grounded["having"])
    score += grounded["include_unmatched"]
    score += any(s.get("kind") == "expression" for s in select)
    score += any((m.get("sql") and not m.get("expression")) for m in grounded["metrics"])
    return score


def plan_for_sql(grounded: dict) -> dict:
    """The grounded plan as the SQL writer should see it (no bookkeeping fields)."""
    hidden = {"issues", "options", "complexity"}
    out = {k: v for k, v in grounded.items() if k not in hidden}
    out["select"] = [{k: v for k, v in s.items() if v not in (None, [], "")} for s in grounded["select"]]
    return out
