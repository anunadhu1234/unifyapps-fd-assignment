"""Build the knowledge base from the live database + the hand-written semantic layer.

Inputs
    data/company.db                        what the data CONTAINS (profiled live)
    knowledge_base/semantic_layer.yaml     what the data MEANS (written by hand)

Outputs (knowledge_base/)
    data_dictionary.json   column-level reference: type, role, meaning, synonyms, stats, enumerated values
    knowledge_graph.json   tables / columns / metrics / terms as nodes + edges, every join path,
                           validated metric SQL, and lookup indexes (values and schema terms)
    relations_graph.html   interactive picture of the graph (open in a browser)

The build FAILS when the two sources disagree: the YAML names a table, column or
value that does not exist, a database column is undocumented, an enumerated value
has no meaning, or a metric / glossary SQL snippet does not run. That is what keeps
the agent from being taught about columns that are not there.

Usage (from backend/):  python scripts/build_knowledge.py
"""

from __future__ import annotations

import json
import re
import sqlite3
import sys
from collections import deque
from datetime import date
from pathlib import Path
from typing import Any

import sqlglot
import yaml
from sqlglot import exp

from agent.knowledge.us_geography import STATE_GROUP_ALIASES, STATE_GROUPS, STATES
from utils.config import BACKEND_DIR

DB_PATH = BACKEND_DIR / "data" / "company.db"
KB_DIR = BACKEND_DIR / "knowledge_base"
SEMANTIC_PATH = KB_DIR / "semantic_layer.yaml"

ENUM_LIMIT = 60  # TEXT columns with at most this many distinct values get their values enumerated
SAMPLE_SIZE = 5


class KnowledgeBuildError(Exception):
    pass


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", str(text).strip().lower())


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


# ─── 1. introspect the database ──────────────────────────────────────────────


def introspect(con: sqlite3.Connection) -> dict[str, dict]:
    schema: dict[str, dict] = {}
    tables = [r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY rowid")]
    for t in tables:
        columns = {}
        for cid, name, ctype, notnull, default, pk in con.execute(f'PRAGMA table_info("{t}")'):
            columns[name] = {"position": cid, "type": ctype.upper(), "nullable": not notnull and not pk,
                             "primary_key": bool(pk), "default": default}
        fks = [{"column": r[3], "ref_table": r[2], "ref_column": r[4]}
               for r in con.execute(f'PRAGMA foreign_key_list("{t}")')]
        indexes = []
        for _, idx_name, unique, origin, _partial in con.execute(f'PRAGMA index_list("{t}")'):
            cols = [r[2] for r in con.execute(f'PRAGMA index_info("{idx_name}")')]
            indexes.append({"name": idx_name, "columns": cols, "unique": bool(unique),
                            "origin": {"c": "CREATE INDEX", "u": "UNIQUE constraint", "pk": "PRIMARY KEY"}[origin]})
        for name in columns:
            if columns[name]["primary_key"]:
                indexes.append({"name": "(rowid)", "columns": [name], "unique": True, "origin": "PRIMARY KEY"})
        row_count = con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
        schema[t] = {"columns": columns, "foreign_keys": fks, "indexes": indexes, "row_count": row_count}
    return schema


# ─── 2. profile every column ─────────────────────────────────────────────────


def infer_role(table: str, col: str, info: dict, fk_cols: set[str], semantic: dict) -> str:
    if info["primary_key"]:
        return "primary_key"
    if col in fk_cols:
        return "foreign_key"
    if semantic.get("semantic_type") == "us_state" or semantic.get("values"):
        return "category"
    if col.endswith("Date"):
        return "date"
    if col.startswith("Is"):
        return "flag"
    if info["type"] in ("REAL", "INTEGER", "NUMERIC"):
        return "measure"
    return "attribute"


def profile_column(con: sqlite3.Connection, table: str, col: str, role: str, row_count: int) -> dict:
    q = f'"{col}"'
    distinct, nulls = con.execute(
        f'SELECT COUNT(DISTINCT {q}), SUM(CASE WHEN {q} IS NULL THEN 1 ELSE 0 END) FROM "{table}"').fetchone()
    stats: dict[str, Any] = {"distinct": distinct, "nulls": nulls or 0,
                             "null_pct": round(100 * (nulls or 0) / row_count, 1) if row_count else 0.0}
    if role in ("date", "measure", "flag", "primary_key", "foreign_key"):
        mn, mx, avg = con.execute(f'SELECT MIN({q}), MAX({q}), AVG({q}) FROM "{table}"').fetchone()
        stats.update(min=mn, max=mx)
        if role == "measure":
            stats["avg"] = round(avg, 2) if avg is not None else None
    values = None
    if role in ("category", "flag", "attribute") and distinct <= ENUM_LIMIT:
        values = [{"value": v, "count": n} for v, n in con.execute(
            f'SELECT {q}, COUNT(*) FROM "{table}" WHERE {q} IS NOT NULL GROUP BY {q} ORDER BY COUNT(*) DESC, {q}')]
    samples = None
    if values is None and role in ("attribute", "category"):
        samples = [r[0] for r in con.execute(
            f'SELECT {q} FROM "{table}" WHERE {q} IS NOT NULL GROUP BY {q} '
            f'ORDER BY COUNT(*) DESC, {q} LIMIT {SAMPLE_SIZE}')]
    return {"stats": stats, "values": values, "samples": samples}


# ─── 3. check the semantic layer against the database ────────────────────────


TABLE_KEYS = {"description", "grain", "synonyms", "columns"}
COLUMN_KEYS = {"description", "synonyms", "unit", "semantic_type", "values"}
VALUE_KEYS = {"meaning", "synonyms"}


def check_shape(sem: dict) -> list[str]:
    """Reject unknown keys — in YAML flow style an unquoted comma silently splits a value into a new key."""
    errors = []
    for t, tdef in sem.get("tables", {}).items():
        errors += [f"table {t}: unknown key {k!r}" for k in set(tdef) - TABLE_KEYS]
        for c, cdef in (tdef.get("columns") or {}).items():
            errors += [f"{t}.{c}: unknown key {k!r} (quote values containing commas)"
                       for k in set(cdef or {}) - COLUMN_KEYS]
            for v, vdef in ((cdef or {}).get("values") or {}).items():
                if not isinstance(vdef, dict) or not vdef.get("meaning"):
                    errors.append(f"{t}.{c} = {v!r}: missing meaning")
                    continue
                errors += [f"{t}.{c} = {v!r}: unknown key {k!r} (quote values containing commas)"
                           for k in set(vdef) - VALUE_KEYS]
    return errors


def check_alignment(schema: dict, sem: dict) -> list[str]:
    errors = check_shape(sem)
    sem_tables = sem.get("tables", {})
    for t in schema:
        if t not in sem_tables:
            errors.append(f"table {t} exists in the database but is not documented")
    for t, tdef in sem_tables.items():
        if t not in schema:
            errors.append(f"semantic layer documents table {t}, which does not exist")
            continue
        for key in ("description", "grain"):
            if not tdef.get(key):
                errors.append(f"table {t} is missing a {key}")
        sem_cols = tdef.get("columns", {})
        for c in schema[t]["columns"]:
            if c not in sem_cols or not (sem_cols[c] or {}).get("description"):
                errors.append(f"column {t}.{c} has no description")
        for c in sem_cols:
            if c not in schema[t]["columns"]:
                errors.append(f"semantic layer documents column {t}.{c}, which does not exist")
    for fk_col in sem.get("relationships", {}):
        t, _, c = fk_col.partition(".")
        if not any(fk["column"] == c for fk in schema.get(t, {}).get("foreign_keys", [])):
            errors.append(f"relationship {fk_col} is not a foreign key in the database")
    return errors


# ─── 4. relationships and join paths ─────────────────────────────────────────


def build_relationships(schema: dict, sem: dict) -> list[dict]:
    rels = []
    for t, info in schema.items():
        for fk in info["foreign_keys"]:
            key = f"{t}.{fk['column']}"
            rels.append({
                "id": key,
                "from_table": t, "from_column": fk["column"],
                "to_table": fk["ref_table"], "to_column": fk["ref_column"],
                "cardinality": "many-to-one",
                "self_reference": t == fk["ref_table"],
                "nullable": info["columns"][fk["column"]]["nullable"],
                "join_condition": f"{t}.{fk['column']} = {fk['ref_table']}.{fk['ref_column']}",
                "description": sem.get("relationships", {}).get(key, ""),
            })
    return rels


def all_join_paths(tables: list[str], rels: list[dict], max_hops: int = 3) -> dict[str, list[dict]]:
    """Every simple join path (up to max_hops) between each ordered pair of distinct tables.

    More than one path between two tables (Customers → Employees directly via
    AccountManagerID, or via Orders.EmployeeID) is a real ambiguity the agent must
    resolve from the question, so all of them are kept, shortest first.
    """
    adj: dict[str, list[tuple[str, dict]]] = {t: [] for t in tables}
    for r in rels:
        if r["self_reference"]:
            continue
        adj[r["from_table"]].append((r["to_table"], r))
        adj[r["to_table"]].append((r["from_table"], r))

    paths: dict[str, list[dict]] = {}
    for src in tables:
        queue = deque([(src, [src], [])])
        while queue:
            node, visited, edges = queue.popleft()
            if node != src:
                paths.setdefault(f"{src}->{node}", []).append({
                    "hops": len(edges),
                    "tables": visited,
                    "joins": [e["join_condition"] for e in edges],
                    "via": [e["id"] for e in edges],
                    "meaning": " → ".join(e["description"] for e in edges if e["description"]),
                })
            if len(edges) >= max_hops:
                continue
            for nxt, rel in adj[node]:
                if nxt not in visited:
                    queue.append((nxt, visited + [nxt], edges + [rel]))
    for key in paths:
        paths[key].sort(key=lambda p: (p["hops"], p["via"]))
    return paths


# ─── 5. validate metric / glossary SQL ───────────────────────────────────────


def referenced_columns(sql: str, schema: dict) -> tuple[list[str], list[str]]:
    """Tables and Table.Column references in a SQL snippet, aliases resolved."""
    tree = sqlglot.parse_one(sql, read="sqlite")
    aliases: dict[str, str] = {}
    tables: set[str] = set()
    for t in tree.find_all(exp.Table):
        if t.name in schema:
            tables.add(t.name)
            aliases[t.alias_or_name] = t.name
    cols: set[str] = set()
    for c in tree.find_all(exp.Column):
        table = aliases.get(c.table) if c.table else None
        if table is None:  # unqualified: attribute to the only table that has it
            owners = [t for t in tables if c.name in schema[t]["columns"]]
            table = owners[0] if len(owners) == 1 else None
        if table and c.name in schema[table]["columns"]:
            cols.add(f"{table}.{c.name}")
    return sorted(tables), sorted(cols)


def fill(text: str, as_of: str) -> str:
    return text.replace("{as_of_date}", as_of)


def validate_metrics(con: sqlite3.Connection, schema: dict, metrics: list[dict], as_of: str) -> tuple[list, list]:
    out, errors = [], []
    for m in metrics:
        if m.get("query"):
            sql = fill(m["query"], as_of)
        else:
            where = " AND ".join(fill(f, as_of) for f in m.get("filters", []))
            sql = f"SELECT {fill(m['expression'], as_of)} AS value FROM {m['from']}"
            if where:
                sql += f" WHERE {where}"
        sql = re.sub(r"\s+", " ", sql).strip()
        try:
            value = con.execute(sql).fetchone()[0]
            tables, cols = referenced_columns(sql, schema)
        except Exception as exc:
            errors.append(f"metric '{m['name']}' does not run: {exc}\n    {sql}")
            continue
        entry = {
            "id": slugify(m["name"]),
            "name": m["name"],
            "synonyms": m.get("synonyms", []),
            "description": m["description"],
            "unit": m.get("unit"),
            "additive": m.get("additive", True),
            "tables": tables,
            "columns": cols,
            "sql": sql,
            "value_at_snapshot": round(value, 2) if isinstance(value, float) else value,
        }
        if not m.get("query"):
            entry.update(expression=fill(m["expression"], as_of), base_from=m["from"],
                         default_filters=[fill(f, as_of) for f in m.get("filters", [])])
        out.append(entry)
    return out, errors


def validate_glossary(con: sqlite3.Connection, schema: dict, glossary: list[dict], as_of: str) -> tuple[list, list]:
    out, errors = [], []
    for g in glossary:
        entry = {"id": slugify(g["term"]), "term": g["term"], "synonyms": g.get("synonyms", []),
                 "definition": fill(g["definition"], as_of), "ambiguous": bool(g.get("ambiguous"))}
        if g.get("ambiguous"):
            entry.update(default=g.get("default"), alternatives=g.get("alternatives", []))
        if g.get("sql"):
            condition = fill(g["sql"], as_of)
            # Named parameters (":period_start") are filled with a real date only for validation.
            probe = f"SELECT COUNT(*) FROM {g['applies_to']} WHERE " + re.sub(r":\w+", f"'{as_of}'", condition)
            try:
                matching = con.execute(probe).fetchone()[0]
                tables, cols = referenced_columns(probe, schema)
            except Exception as exc:
                errors.append(f"glossary term '{g['term']}' SQL does not run: {exc}\n    {probe}")
                continue
            entry.update(sql=condition, applies_to=g["applies_to"], tables=tables, columns=cols,
                         matching_rows_at_snapshot=matching)
        out.append(entry)
    return out, errors


# ─── 6. assemble the data dictionary ─────────────────────────────────────────


def build_dictionary(con, schema: dict, sem: dict, as_of: str) -> tuple[dict, list[str]]:
    errors: list[str] = []
    tables_out = {}
    for t, info in schema.items():
        tdef = sem["tables"][t]
        fk_map = {fk["column"]: fk for fk in info["foreign_keys"]}
        cols_out = {}
        for c, cinfo in info["columns"].items():
            csem = tdef["columns"].get(c) or {}
            role = infer_role(t, c, cinfo, set(fk_map), csem)
            prof = profile_column(con, t, c, role, info["row_count"])
            col = {
                "type": cinfo["type"],
                "role": role,
                "nullable": cinfo["nullable"],
                "description": csem["description"],
                "synonyms": csem.get("synonyms", []),
            }
            if csem.get("unit"):
                col["unit"] = csem["unit"]
            if csem.get("semantic_type"):
                col["semantic_type"] = csem["semantic_type"]
            if c in fk_map:
                col["references"] = f"{fk_map[c]['ref_table']}.{fk_map[c]['ref_column']}"
            col["stats"] = prof["stats"]

            sem_values = csem.get("values") or {}
            if prof["values"] is not None:
                db_values = {v["value"] for v in prof["values"]}
                for v in sem_values:
                    if v not in db_values:
                        errors.append(f"{t}.{c}: documented value {v!r} does not occur in the data")
                if sem_values:
                    for v in db_values - set(sem_values):
                        errors.append(f"{t}.{c}: value {v!r} occurs in the data but has no documented meaning")
                col["values"] = [
                    {**v, **({"meaning": sem_values[v["value"]].get("meaning")} if v["value"] in sem_values else {}),
                     **({"synonyms": sem_values[v["value"]].get("synonyms", [])} if v["value"] in sem_values else {})}
                    for v in prof["values"]
                ]
            elif sem_values:
                errors.append(f"{t}.{c}: has documented values but too many distinct values to enumerate")
            if prof["samples"]:
                col["samples"] = prof["samples"]
            cols_out[c] = col

        tables_out[t] = {
            "description": tdef["description"],
            "grain": tdef["grain"],
            "synonyms": tdef.get("synonyms", []),
            "row_count": info["row_count"],
            "primary_key": [c for c, ci in info["columns"].items() if ci["primary_key"]],
            "foreign_keys": [f"{t}.{fk['column']} → {fk['ref_table']}.{fk['ref_column']}"
                             for fk in info["foreign_keys"]],
            "referenced_by": sorted(f"{ot}.{fk['column']}" for ot, oi in schema.items()
                                    for fk in oi["foreign_keys"] if fk["ref_table"] == t),
            "indexes": info["indexes"],
            "columns": cols_out,
        }

    dictionary = {
        "meta": {
            "title": f"Data Dictionary — {sem['domain']['company']}",
            "database": DB_PATH.name,
            "dialect": sem["domain"]["dialect"],
            "currency": sem["domain"]["currency"],
            "as_of_date": as_of,
            "generated_on": date.today().isoformat(),
            "generated_from": "Live profile of the SQLite database merged with knowledge_base/semantic_layer.yaml.",
            "domain": sem["domain"]["description"],
            "row_counts": {t: i["row_count"] for t, i in schema.items()},
        },
        "conventions": [{"id": c["id"], "rule": fill(c["rule"], as_of)} for c in sem.get("conventions", [])],
        "tables": tables_out,
    }
    return dictionary, errors


# ─── 7. lookup indexes ───────────────────────────────────────────────────────


def add_index(index: dict, phrase: str, entry: dict) -> None:
    key = norm(phrase)
    if not key:
        return
    bucket = index.setdefault(key, [])
    if entry not in bucket:
        bucket.append(entry)


def build_value_index(dictionary: dict) -> dict[str, list[dict]]:
    """Phrase a user might type → the exact stored value(s) it means."""
    index: dict[str, list[dict]] = {}
    for t, tinfo in dictionary["tables"].items():
        for c, col in tinfo["columns"].items():
            if col.get("semantic_type") == "us_state":
                for s in STATES:
                    target = {"table": t, "column": c, "value": s.code}
                    add_index(index, s.code, {**target, "match": "state_code"})
                    add_index(index, s.name, {**target, "match": "state_name"})
                    for alias in s.aliases:
                        add_index(index, alias, {**target, "match": "state_alias"})
                for group, codes in STATE_GROUPS.items():
                    target = {"table": t, "column": c, "values": list(codes), "match": "state_group", "group": group}
                    add_index(index, group, target)
                    for alias in STATE_GROUP_ALIASES.get(group, ()):
                        add_index(index, alias, target)
                continue
            if col["role"] != "category" or not col.get("values"):
                continue
            for v in col["values"]:
                target = {"table": t, "column": c, "value": v["value"]}
                add_index(index, v["value"], {**target, "match": "exact"})
                for syn in v.get("synonyms", []):
                    add_index(index, syn, {**target, "match": "synonym"})
    return dict(sorted(index.items()))


def build_term_index(dictionary: dict, metrics: list[dict], glossary: list[dict]) -> dict[str, list[dict]]:
    """Phrase a user might type → the table / column / metric / glossary term it refers to."""
    index: dict[str, list[dict]] = {}
    for t, tinfo in dictionary["tables"].items():
        for phrase in [t, *tinfo["synonyms"]]:
            add_index(index, phrase, {"kind": "table", "table": t})
        for c, col in tinfo["columns"].items():
            split = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", c)  # HireDate → "Hire Date"
            for phrase in {c, split, *col["synonyms"]}:
                add_index(index, phrase, {"kind": "column", "table": t, "column": c})
    for m in metrics:
        for phrase in [m["name"], *m["synonyms"]]:
            add_index(index, phrase, {"kind": "metric", "id": m["id"]})
    for g in glossary:
        for phrase in [g["term"], *g["synonyms"]]:
            add_index(index, phrase, {"kind": "term", "id": g["id"]})
    return dict(sorted(index.items()))


# ─── 8. the graph ────────────────────────────────────────────────────────────


def build_graph(dictionary: dict, rels: list[dict], metrics: list[dict], glossary: list[dict]) -> tuple[list, list]:
    nodes, edges = [], []
    for t, tinfo in dictionary["tables"].items():
        nodes.append({"id": f"table:{t}", "kind": "table", "label": t, "description": tinfo["description"],
                      "row_count": tinfo["row_count"]})
        for c, col in tinfo["columns"].items():
            nodes.append({"id": f"column:{t}.{c}", "kind": "column", "label": f"{t}.{c}", "role": col["role"],
                          "type": col["type"], "description": col["description"]})
            edges.append({"source": f"table:{t}", "target": f"column:{t}.{c}", "kind": "has_column"})
    for r in rels:
        edges.append({"source": f"column:{r['from_table']}.{r['from_column']}",
                      "target": f"column:{r['to_table']}.{r['to_column']}", "kind": "references",
                      "label": r["description"]})
        edges.append({"source": f"table:{r['from_table']}", "target": f"table:{r['to_table']}",
                      "kind": "joins_to", "via": r["id"], "label": r["description"]})
    for m in metrics:
        nodes.append({"id": f"metric:{m['id']}", "kind": "metric", "label": m["name"], "description": m["description"]})
        edges.extend({"source": f"metric:{m['id']}", "target": f"column:{c}", "kind": "uses"} for c in m["columns"])
    for g in glossary:
        nodes.append({"id": f"term:{g['id']}", "kind": "term", "label": g["term"], "description": g["definition"]})
        edges.extend({"source": f"term:{g['id']}", "target": f"column:{c}", "kind": "uses"}
                     for c in g.get("columns", []))
    return nodes, edges


GRAPH_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Knowledge Graph — __TITLE__</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/vis-network/9.1.9/standalone/umd/vis-network.min.js"></script>
<style>
  body{margin:0;font-family:system-ui,sans-serif;background:#0f172a;color:#e2e8f0}
  header{padding:10px 16px;border-bottom:1px solid #1e293b;display:flex;gap:16px;align-items:center;flex-wrap:wrap}
  header h1{font-size:16px;margin:0} .chip{font-size:12px;display:flex;gap:6px;align-items:center}
  .dot{width:10px;height:10px;border-radius:50%} #net{height:calc(100vh - 50px)}
  label{font-size:12px;cursor:pointer}
</style></head><body>
<header><h1>__TITLE__</h1>
<span class="chip"><span class="dot" style="background:#38bdf8"></span>table</span>
<span class="chip"><span class="dot" style="background:#64748b"></span>column</span>
<span class="chip"><span class="dot" style="background:#f59e0b"></span>metric</span>
<span class="chip"><span class="dot" style="background:#a78bfa"></span>term</span>
<label><input type="checkbox" id="cols"> show columns</label></header>
<div id="net"></div>
<script>
const G = __GRAPH__;
const color = {table:'#38bdf8', column:'#64748b', metric:'#f59e0b', term:'#a78bfa'};
const shape = {table:'box', column:'dot', metric:'diamond', term:'triangle'};
function draw(showColumns){
  const keep = n => showColumns || n.kind !== 'column';
  const ids = new Set(G.nodes.filter(keep).map(n => n.id));
  const nodes = G.nodes.filter(keep).map(n => ({id:n.id, label:n.label, title:n.description,
    shape:shape[n.kind], color:color[n.kind], font:{color:'#e2e8f0', size:n.kind==='table'?18:12},
    size:n.kind==='column'?6:14}));
  const edges = [];
  for (const e of G.edges) {
    let s = e.source, t = e.target;
    if (!showColumns) {               // collapse column endpoints onto their table
      if (e.kind === 'has_column' || e.kind === 'references') continue;
      s = s.startsWith('column:') ? 'table:' + s.slice(7).split('.')[0] : s;
      t = t.startsWith('column:') ? 'table:' + t.slice(7).split('.')[0] : t;
    }
    if (ids.has(s) && ids.has(t)) edges.push({from:s, to:t, title:e.label||e.kind,
      label:e.kind==='joins_to'?e.via:undefined, arrows:e.kind==='has_column'?undefined:'to',
      color:{color:e.kind==='joins_to'?'#38bdf8':'#334155'}, font:{color:'#94a3b8', size:10, strokeWidth:0}});
  }
  new vis.Network(document.getElementById('net'), {nodes, edges},
    {physics:{solver:'forceAtlas2Based', stabilization:{iterations:300}}, interaction:{hover:true}});
}
document.getElementById('cols').onchange = e => draw(e.target.checked);
draw(false);
</script></body></html>
"""


# ─── main ────────────────────────────────────────────────────────────────────


def main() -> int:
    if not DB_PATH.exists():
        print(f"Database not found: {DB_PATH}. Run scripts/generate_data.py first.")
        return 1
    sem = yaml.safe_load(SEMANTIC_PATH.read_text(encoding="utf-8"))
    as_of = str(sem["domain"]["as_of_date"])

    con = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
    try:
        schema = introspect(con)
        errors = check_alignment(schema, sem)
        if errors:
            raise KnowledgeBuildError(errors)

        latest_order = con.execute("SELECT MAX(OrderDate) FROM Orders").fetchone()[0]
        if latest_order > as_of:
            raise KnowledgeBuildError([f"as_of_date {as_of} is earlier than the latest order ({latest_order})"])

        dictionary, errors = build_dictionary(con, schema, sem, as_of)
        rels = build_relationships(schema, sem)
        metrics, metric_errors = validate_metrics(con, schema, sem.get("metrics", []), as_of)
        glossary, glossary_errors = validate_glossary(con, schema, sem.get("glossary", []), as_of)
        errors += metric_errors + glossary_errors
        if errors:
            raise KnowledgeBuildError(errors)
    finally:
        con.close()

    nodes, edges = build_graph(dictionary, rels, metrics, glossary)
    graph = {
        "meta": {
            "title": f"Knowledge Graph — {sem['domain']['company']}",
            "dialect": sem["domain"]["dialect"],
            "as_of_date": as_of,
            "generated_on": date.today().isoformat(),
            "counts": {"tables": len(schema), "columns": sum(len(t["columns"]) for t in schema.values()),
                       "relationships": len(rels), "metrics": len(metrics), "terms": len(glossary),
                       "nodes": len(nodes), "edges": len(edges)},
            "how_to_read": [
                "relationships: every foreign key, with the exact join condition and what the link means.",
                "join_paths['A->B']: every way to join A to B (up to 3 hops), shortest first. More than one path "
                "means the question must decide which relationship it means.",
                "metrics: validated SQL for each business KPI; reuse `expression` + `default_filters` inside a "
                "larger query, or `sql` as-is for the overall value.",
                "glossary: business terms with a ready SQL condition over `applies_to` (alias included); "
                "`ambiguous` terms carry a default interpretation and alternatives.",
                "value_index: normalised phrase → the exact stored value(s), "
                "e.g. 'california' → Customers.State = 'CA'.",
                "term_index: normalised phrase → the table / column / metric / term it refers to.",
            ],
        },
        "conventions": dictionary["conventions"],
        "relationships": rels,
        "join_paths": all_join_paths(list(schema), rels),
        "metrics": metrics,
        "glossary": glossary,
        "state_groups": {g: list(codes) for g, codes in STATE_GROUPS.items()},
        "value_index": build_value_index(dictionary),
        "term_index": build_term_index(dictionary, metrics, glossary),
        "nodes": nodes,
        "edges": edges,
    }

    write_json(KB_DIR / "data_dictionary.json", dictionary)
    write_json(KB_DIR / "knowledge_graph.json", graph)
    html = GRAPH_HTML.replace("__TITLE__", graph["meta"]["title"]).replace(
        "__GRAPH__", json.dumps({"nodes": nodes, "edges": edges}))
    (KB_DIR / "relations_graph.html").write_text(html, encoding="utf-8")

    c = graph["meta"]["counts"]
    print(f"Knowledge base built (as of {as_of}):")
    print(f"  {c['tables']} tables, {c['columns']} columns, {c['relationships']} relationships, "
          f"{len(graph['join_paths'])} join-path pairs")
    print(f"  {c['metrics']} metrics, {c['terms']} glossary terms - all SQL validated against the database")
    print(f"  {len(graph['value_index'])} value phrases, {len(graph['term_index'])} schema phrases indexed")
    print(f"  graph: {c['nodes']} nodes, {c['edges']} edges -> {KB_DIR / 'relations_graph.html'}")
    return 0


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KnowledgeBuildError as exc:
        print("Knowledge base build FAILED:")
        for err in exc.args[0]:
            print(f"  - {err}")
        sys.exit(1)
