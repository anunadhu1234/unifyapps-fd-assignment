"""Query cost estimation and index recommendations from SQLite's own query plan.

SQLite has no numeric cost model exposed, so the estimate is built from
EXPLAIN QUERY PLAN plus table sizes:

  SCAN t              full table read           → cost += rows(t)
  SEARCH t USING ...  index / rowid lookup      → cost += log2(rows(t)) per outer row
  USE TEMP B-TREE     sort / group / distinct   → cost += 20% of the rows feeding it

The result is a relative level (low / medium / high) plus the plan steps in
plain words. Index recommendations come from full scans whose table is
filtered, joined or sorted on a column that has no index.
"""

from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass, field

import sqlglot
from sqlglot import exp

from agent.exec.sqlite_runner import ReadOnlyDatabase
from agent.knowledge.kb_resolver import KnowledgeBase

LOW, MEDIUM = 5_000, 50_000


@dataclass
class IndexRecommendation:
    table: str
    columns: list[str]
    reason: str
    ddl: str


@dataclass
class CostEstimate:
    level: str  # low | medium | high
    score: int
    full_scans: list[str]
    index_lookups: list[str]
    temp_sorts: int
    plan: list[str]
    recommendations: list[IndexRecommendation] = field(default_factory=list)

    def as_dict(self) -> dict:
        return asdict(self)


class CostEstimator:
    def __init__(self, kb: KnowledgeBase, db: ReadOnlyDatabase):
        self.kb = kb
        self.db = db
        self.row_counts = {t: info["row_count"] for t, info in kb.tables.items()}
        self.indexed_leading = {
            t: {ix["columns"][0].lower() for ix in info["indexes"] if ix["columns"]}
            for t, info in kb.tables.items()
        }

    def estimate(self, sql: str) -> CostEstimate:
        steps = self.db.explain(sql)
        aliases = _alias_map(sql, set(self.kb.tables))
        score, outer_rows = 0.0, 1.0
        full_scans, lookups, temp_sorts, readable = [], [], 0, []
        for step in steps:
            detail = step["detail"]
            scan = re.match(r"SCAN (\w+)(?: USING (?:COVERING )?INDEX (\w+))?", detail)
            search = re.match(r"SEARCH (\w+) USING (?:(?:COVERING )?INDEX (\w+)|INTEGER PRIMARY KEY)", detail)
            if scan and scan.group(1) in aliases:
                table = aliases[scan.group(1)]
                rows = self.row_counts.get(table, 1000)
                score += rows * max(outer_rows, 1)
                outer_rows = max(outer_rows, rows)
                full_scans.append(table)
                readable.append(f"Read every row of {table} ({rows:,} rows)"
                                + (f" via index {scan.group(2)}" if scan.group(2) else ""))
            elif search and search.group(1) in aliases:
                table = aliases[search.group(1)]
                rows = self.row_counts.get(table, 1000)
                score += math.log2(rows + 1) * max(outer_rows, 1)
                lookups.append(table)
                how = f"index {search.group(2)}" if search.group(2) else "primary key"
                readable.append(f"Look up {table} by {how}")
            elif detail.startswith("USE TEMP B-TREE"):
                temp_sorts += 1
                score += 0.2 * max(outer_rows, 1)
                purpose = detail[len("USE TEMP B-TREE "):].lower()
                readable.append(f"Sort / group rows in a temporary B-tree ({purpose})")
            else:
                readable.append(detail)
        level = "low" if score < LOW else "medium" if score < MEDIUM else "high"
        estimate = CostEstimate(level, int(score), full_scans, lookups, temp_sorts, readable)
        estimate.recommendations = self.recommend_indexes(sql, full_scans)
        return estimate

    def recommend_indexes(self, sql: str, scanned_tables: list[str]) -> list[IndexRecommendation]:
        """Suggest an index for a scanned table filtered / joined / sorted on an unindexed column."""
        try:
            tree = sqlglot.parse_one(sql, read="sqlite")
        except Exception:
            return []
        aliases = _alias_map(sql, set(self.kb.tables))
        wanted: dict[tuple[str, str], str] = {}

        def note(col: exp.Column, why: str) -> None:
            table = aliases.get(col.table) if col.table else None
            if table is None:
                owners = [t for t in scanned_tables if _has_column(self.kb, t, col.name)]
                table = owners[0] if len(owners) == 1 else None
            if table is None or table not in scanned_tables:
                return
            real = _real_column(self.kb, table, col.name)
            if real and real.lower() not in self.indexed_leading.get(table, set()):
                wanted.setdefault((table, real), why)

        for where in tree.find_all(exp.Where):
            for cmp in where.find_all(exp.EQ, exp.GT, exp.GTE, exp.LT, exp.LTE, exp.In, exp.Between, exp.Like):
                for col in cmp.find_all(exp.Column):
                    note(col, "filtered in WHERE")
        for join in tree.find_all(exp.Join):
            on = join.args.get("on")
            for col in (on.find_all(exp.Column) if on is not None else []):
                note(col, "used as a join key")
        for order in tree.find_all(exp.Order):
            for col in order.find_all(exp.Column):
                note(col, "used for sorting")

        recs = []
        for (table, column), why in wanted.items():
            rows = self.row_counts.get(table, 0)
            if rows < 1_000 or (why == "used for sorting" and rows < 10_000):  # cheap to scan / sort in memory
                continue
            reason = (f"{table} is read in full and {column} is {why}; an index lets SQLite seek instead of "
                      f"scanning {self.row_counts[table]:,} rows.")
            distinct = self.kb.tables[table]["columns"][column]["stats"].get("distinct", 0)
            if 0 < distinct <= 10:
                reason += f" {column} has only {distinct} distinct values, so this helps mainly for rare values."
            recs.append(IndexRecommendation(
                table, [column], reason, f"CREATE INDEX idx_{table.lower()}_{column.lower()} ON {table} ({column});"))
        return recs


def _alias_map(sql: str, tables: set[str]) -> dict[str, str]:
    """Alias (and bare name) → real table, as EXPLAIN QUERY PLAN prints aliases."""
    lower = {t.lower(): t for t in tables}
    out = {t: t for t in tables}
    try:
        tree = sqlglot.parse_one(sql, read="sqlite")
    except Exception:
        return out
    for t in tree.find_all(exp.Table):
        real = lower.get(t.name.lower())
        if real:
            out[t.alias_or_name] = real
            out[t.name] = real
    return out


def _has_column(kb: KnowledgeBase, table: str, column: str) -> bool:
    return _real_column(kb, table, column) is not None


def _real_column(kb: KnowledgeBase, table: str, column: str) -> str | None:
    return next((c for c in kb.tables[table]["columns"] if c.lower() == column.lower()), None)
