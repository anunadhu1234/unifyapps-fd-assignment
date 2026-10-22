"""Deterministic SQL validator — no LLM involved.

Checks, in order (later checks run only when earlier ones pass):

  sql.syntax               parses as SQLite (sqlglot)
  sql.multiple_statements  exactly one statement
  sql.not_read_only        only SELECT / WITH / set operations; any write or DDL node anywhere → blocked
  sql.table.unknown        every table exists
  sql.column.unknown       every column exists on the table it is read from
  sql.value.unknown        string literals compared to categorical columns are real stored values
                           ('California' → use 'CA'; 'Canceled' → use 'Cancelled')
  sql.join.invalid         key-to-key joins follow a real foreign key
  sql.join.non_fk          (warning) join on non-key columns
  sql.join.cartesian       (warning) a join without a condition
  sql.engine               SQLite itself compiles the statement (EXPLAIN QUERY PLAN)
  sql.plan.filter_missing  the SQL applies every value filter of the grounded plan

Every finding carries a precise message and, where possible, a fix hint; the
repair node feeds them back to the LLM verbatim.
"""

from __future__ import annotations

import difflib
import re
import sqlite3
from dataclasses import asdict, dataclass, field
from typing import Literal

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError, TokenError
from sqlglot.optimizer.qualify import qualify
from sqlglot.optimizer.scope import traverse_scope

from agent.exec.sqlite_runner import ReadOnlyDatabase
from agent.knowledge.kb_resolver import KnowledgeBase

Severity = Literal["error", "warning"]

_WRITE_NODES = tuple(t for t in (
    getattr(exp, name, None) for name in (
        "Insert", "Update", "Delete", "Merge", "Drop", "Create", "Alter", "AlterTable", "TruncateTable",
        "Command", "Pragma", "Attach", "Detach", "Transaction", "Commit", "Rollback", "Into", "Analyze",
        "Use", "Set", "LoadData", "Copy")
) if t is not None)
_READ_ROOTS = tuple(t for t in (getattr(exp, n, None) for n in ("Select", "Union", "Intersect", "Except",
                                                                 "SetOperation")) if t is not None)


@dataclass
class Finding:
    severity: Severity
    code: str
    message: str
    hint: str | None = None

    def as_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class ValidationReport:
    sql: str
    findings: list[Finding] = field(default_factory=list)
    tables: list[str] = field(default_factory=list)
    columns: list[str] = field(default_factory=list)
    formatted_sql: str | None = None
    checks_passed: list[str] = field(default_factory=list)

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "error"]

    @property
    def ok(self) -> bool:
        return not self.errors

    @property
    def blocked_write(self) -> bool:
        return any(f.code == "sql.not_read_only" for f in self.findings)

    def feedback(self) -> str:
        """Findings as a numbered list, the way the repair prompt receives them."""
        return "\n".join(f"{i}. [{f.code}] {f.message}" + (f" Fix: {f.hint}" if f.hint else "")
                         for i, f in enumerate(self.findings, 1))

    def as_dict(self) -> dict:
        return {"ok": self.ok, "findings": [f.as_dict() for f in self.findings], "tables": self.tables,
                "columns": self.columns, "checks_passed": self.checks_passed}


class SQLValidator:
    def __init__(self, kb: KnowledgeBase, db: ReadOnlyDatabase | None = None, dialect: str = "sqlite"):
        self.kb = kb
        self.db = db
        self.dialect = dialect
        self.schema = {t: {c: col["type"] for c, col in info["columns"].items()} for t, info in kb.tables.items()}
        self._fk_pairs = {frozenset({(r["from_table"], r["from_column"]), (r["to_table"], r["to_column"])})
                          for r in kb.relationships}

    # ── public API ───────────────────────────────────────────────────────

    def validate(self, sql: str, *, plan_filters: list[dict] | None = None) -> ValidationReport:
        sql = strip_sql(sql)
        report = ValidationReport(sql=sql)
        if not sql:
            report.findings.append(Finding("error", "sql.syntax", "The SQL statement is empty."))
            return report

        tree = self._parse(sql, report)
        if tree is None:
            return report
        report.checks_passed.append("syntax")
        if not self._check_read_only(tree, report):
            return report
        report.checks_passed.append("read_only")
        if not self._check_tables(tree, report):
            return report
        report.checks_passed.append("tables")

        qualified = self._qualify(tree, report)
        if qualified is None:
            return report
        # qualify() lowercases identifiers; keep the user's spelling for messages.
        original = {i.name.lower(): i.name for i in tree.find_all(exp.Identifier)}
        self._check_columns(qualified, report, original)
        if not report.errors:
            report.checks_passed.append("columns")
            self._check_values(qualified, report)
            if not report.errors:
                report.checks_passed.append("values")
            self._check_joins(qualified, report)
            if not any(f.code.startswith("sql.join") and f.severity == "error" for f in report.findings):
                report.checks_passed.append("joins")
        if not report.errors and self.db is not None:
            self._check_engine(sql, report)
        if not report.errors and plan_filters:
            self._check_plan(sql, plan_filters, report)
        report.formatted_sql = format_sql(sql, self.dialect)
        return report

    # ── individual checks ────────────────────────────────────────────────

    def _parse(self, sql: str, report: ValidationReport) -> exp.Expression | None:
        try:
            statements = [s for s in sqlglot.parse(sql, read=self.dialect) if s is not None]
        except (ParseError, TokenError) as exc:
            report.findings.append(Finding("error", "sql.syntax", f"Syntax error: {_clean_parse_error(exc)}"))
            return None
        if len(statements) != 1:
            kinds = ", ".join(type(s).__name__.upper() for s in statements)
            report.findings.append(Finding(
                "error", "sql.multiple_statements",
                f"Expected exactly one statement, found {len(statements)} ({kinds}).",
                "Return a single SELECT statement."))
            if any(isinstance(s, _WRITE_NODES) or s.find(*_WRITE_NODES) for s in statements):
                report.findings.append(Finding("error", "sql.not_read_only",
                                               "The input contains a statement that modifies the database."))
            return None
        return statements[0]

    def _check_read_only(self, tree: exp.Expression, report: ValidationReport) -> bool:
        offender = tree if isinstance(tree, _WRITE_NODES) else tree.find(*_WRITE_NODES)
        if offender is not None or not isinstance(tree, _READ_ROOTS):
            kind = type(offender or tree).__name__.upper()
            report.findings.append(Finding(
                "error", "sql.not_read_only",
                f"Only read-only queries are allowed; this statement contains {kind}.",
                "Use a SELECT statement. DELETE, UPDATE, INSERT, DROP, ALTER, TRUNCATE, PRAGMA and ATTACH "
                "are never generated."))
            return False
        return True

    def _check_tables(self, tree: exp.Expression, report: ValidationReport) -> bool:
        ctes = {c.alias_or_name.lower() for c in tree.find_all(exp.CTE)}
        known = {t.lower(): t for t in self.schema}
        found, ok = [], True
        for t in tree.find_all(exp.Table):
            name = t.name
            if not name or name.lower() in ctes:
                continue
            if name.lower() not in known:
                ok = False
                suggestion = self.kb.resolve_table(name) or _closest(name, list(self.schema))
                report.findings.append(Finding(
                    "error", "sql.table.unknown", f"Table '{name}' does not exist.",
                    f"Use {suggestion}." if suggestion else f"Available tables: {', '.join(self.schema)}."))
            elif known[name.lower()] not in found:
                found.append(known[name.lower()])
        report.tables = found
        return ok

    def _qualify(self, tree: exp.Expression, report: ValidationReport) -> exp.Expression | None:
        try:
            return qualify(tree.copy(), schema=self.schema, dialect=self.dialect,
                           validate_qualify_columns=False, quote_identifiers=False, identify=False)
        except Exception as exc:  # sqlglot raises OptimizeError for unknown / ambiguous columns
            unknown = re.search(r"Unknown column: ['\"]?(\w+)", str(exc))
            if unknown:
                original = {i.name.lower(): i.name for i in tree.find_all(exp.Identifier)}
                report.findings.append(self._unknown_column(None, original.get(unknown.group(1), unknown.group(1))))
            else:
                report.findings.append(Finding("error", "sql.column.unresolved", f"Could not resolve columns: {exc}",
                                               "Qualify every column with its table alias."))
            return None

    def _sources(self, scope) -> dict[str, str]:
        """Scope alias → real table name, for sources that are base tables."""
        lower = {t.lower(): t for t in self.schema}
        out = {}
        for alias, source in scope.sources.items():
            if isinstance(source, exp.Table) and source.name.lower() in lower:
                out[alias] = lower[source.name.lower()]
        return out

    def _check_columns(self, qualified: exp.Expression, report: ValidationReport, original: dict[str, str]) -> None:
        seen: list[str] = []
        for scope in traverse_scope(qualified):
            base = self._sources(scope)
            select = scope.expression
            aliases = {p.alias.lower() for p in getattr(select, "expressions", []) if isinstance(p, exp.Alias)}
            for col in scope.columns:
                name = original.get(col.name.lower(), col.name)
                if not name or name == "*":
                    continue
                if col.table and col.table in base:
                    table = base[col.table]
                    real = _case_lookup(name, self.schema[table])
                    if real is None:
                        report.findings.append(self._unknown_column(table, name))
                    elif f"{table}.{real}" not in seen:
                        seen.append(f"{table}.{real}")
                elif not col.table:
                    # ORDER BY / GROUP BY / HAVING may reference a SELECT alias.
                    if name.lower() in aliases and not _in_projection(col, select):
                        continue
                    tables = list(base.values())
                    if not any(_case_lookup(name, self.schema[t]) for t in tables):
                        report.findings.append(self._unknown_column(tables[0] if len(tables) == 1 else None, name))
        report.columns = seen

    def _unknown_column(self, table: str | None, name: str) -> Finding:
        scope = [table] if table else list(self.schema)
        candidates = [f"{t}.{c}" for t, c in self.kb.resolve_column(name, scope)]
        if not candidates:
            pool = {f"{t}.{c}": c for t in scope for c in self.schema[t]}
            close = difflib.get_close_matches(name.lower(), [c.lower() for c in pool.values()], n=3, cutoff=0.6)
            candidates = [k for k, v in pool.items() if v.lower() in close]
        where = f" on table {table}" if table else ""
        hint = f"Did you mean {', '.join(candidates)}?" if candidates else (
            f"Columns of {table}: {', '.join(self.schema[table])}." if table else None)
        return Finding("error", "sql.column.unknown", f"Column '{name}' does not exist{where}.", hint)

    def _check_values(self, qualified: exp.Expression, report: ValidationReport) -> None:
        for scope in traverse_scope(qualified):
            base = self._sources(scope)
            for node in scope.expression.find_all(exp.EQ, exp.NEQ, exp.In):
                column, literals = _column_and_literals(node)
                if column is None or not column.table or column.table not in base:
                    continue
                table = base[column.table]
                real = _case_lookup(column.name, self.schema[table])
                meta = self.kb.column(table, real) if real else None
                if not meta or meta["role"] != "category" or not meta.get("values"):
                    continue
                allowed = [v["value"] for v in meta["values"]]
                for lit in literals:
                    if lit in allowed:
                        continue
                    report.findings.append(Finding(
                        "error", "sql.value.unknown",
                        f"{table}.{real} has no value '{lit}'.",
                        self._value_hint(table, real, lit, allowed)))

    def _value_hint(self, table: str, column: str, literal: str, allowed: list[str]) -> str:
        mapped = sorted({e.get("value") or ", ".join(e.get("values", []))
                         for m in self.kb.match_values(literal) for e in m.entries
                         if e["table"] == table and e["column"] == column})
        if mapped:
            return f"'{literal}' is stored as {' / '.join(repr(v) for v in mapped)}."
        exact_ci = [v for v in allowed if v.lower() == literal.lower()]
        if exact_ci:
            return f"Values are case-sensitive: use '{exact_ci[0]}'."
        if len(allowed) <= 15:
            return f"Valid values: {', '.join(repr(v) for v in allowed)}."
        return f"Valid values include: {', '.join(repr(v) for v in allowed[:10])}, …"

    def _check_joins(self, qualified: exp.Expression, report: ValidationReport) -> None:
        for scope in traverse_scope(qualified):
            base = self._sources(scope)
            select = scope.expression
            if not isinstance(select, exp.Select):
                continue
            for join in select.args.get("joins") or []:
                on = join.args.get("on")
                if on is None and not join.args.get("using"):
                    target = join.this.alias_or_name if isinstance(join.this, exp.Table) else "subquery"
                    if not _where_links(select, target):
                        report.findings.append(Finding(
                            "warning", "sql.join.cartesian",
                            f"The join to '{target}' has no join condition (every row pairs with every row).",
                            "Add an ON clause on the foreign key."))
                    continue
                for eq in (on.find_all(exp.EQ) if on is not None else []):
                    left, right = eq.this, eq.expression
                    if not (isinstance(left, exp.Column) and isinstance(right, exp.Column)):
                        continue
                    lt, rt = base.get(left.table), base.get(right.table)
                    if not lt or not rt or lt == rt and left.table == right.table:
                        continue
                    lc = _case_lookup(left.name, self.schema[lt])
                    rc = _case_lookup(right.name, self.schema[rt])
                    if not lc or not rc:
                        continue
                    if frozenset({(lt, lc), (rt, rc)}) in self._fk_pairs:
                        continue
                    lrole = self.kb.column(lt, lc)["role"]
                    rrole = self.kb.column(rt, rc)["role"]
                    valid = self._valid_joins(lt, rt)
                    if lrole in ("primary_key", "foreign_key") and rrole in ("primary_key", "foreign_key"):
                        report.findings.append(Finding(
                            "error", "sql.join.invalid",
                            f"{lt}.{lc} = {rt}.{rc} is not a real relationship between these tables.",
                            f"Valid joins: {'; '.join(valid)}." if valid else
                            f"{lt} and {rt} are not directly related; join through the tables between them."))
                    else:
                        report.findings.append(Finding(
                            "warning", "sql.join.non_fk",
                            f"{lt}.{lc} = {rt}.{rc} joins on non-key columns; check this is intended.",
                            f"Foreign-key joins: {'; '.join(valid)}." if valid else None))

    def _valid_joins(self, a: str, b: str) -> list[str]:
        return [r["join_condition"] for r in self.kb.relationships
                if {r["from_table"], r["to_table"]} == {a, b}]

    def _check_engine(self, sql: str, report: ValidationReport) -> None:
        try:
            self.db.explain(sql)
            report.checks_passed.append("engine")
        except sqlite3.DatabaseError as exc:
            message = str(exc)
            if "not authorized" in message.lower():
                report.findings.append(Finding("error", "sql.not_read_only",
                                               "The database refused this statement (read-only access)."))
            else:
                report.findings.append(Finding("error", "sql.engine", f"SQLite rejected the query: {message}."))

    def _check_plan(self, sql: str, plan_filters: list[dict], report: ValidationReport) -> None:
        for f in plan_filters:
            for v in f.get("values", []):
                if isinstance(v, str) and f.get("operator", "=") not in ("LIKE", "NOT LIKE") and \
                        f"'{v.replace(chr(39), chr(39) * 2)}'" not in sql:
                    report.findings.append(Finding(
                        "error", "sql.plan.filter_missing",
                        f"The plan filters {f['table']}.{f['column']} on '{v}', but the SQL does not use that value.",
                        f"Apply the filter {f['table']}.{f['column']} {f.get('operator', '=')} '{v}'."))
        if not report.errors:
            report.checks_passed.append("plan")


# ── helpers ──────────────────────────────────────────────────────────────────


def strip_sql(sql: str) -> str:
    """Remove markdown fences, surrounding prose markers and a trailing semicolon."""
    text = str(sql or "").strip()
    fenced = re.search(r"```(?:sql)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    if fenced:
        text = fenced.group(1).strip()
    return text.rstrip().rstrip(";").strip()


def format_sql(sql: str, dialect: str = "sqlite") -> str:
    try:
        return sqlglot.transpile(sql, read=dialect, write=dialect, pretty=True)[0]
    except Exception:
        return sql


def transpile(sql: str, target: str, source: str = "sqlite") -> str | None:
    try:
        return sqlglot.transpile(sql, read=source, write=target, pretty=True)[0]
    except Exception:
        return None


def _clean_parse_error(exc: Exception) -> str:
    msg = str(exc).split("\n")[0]
    return re.sub(r"\s+", " ", msg)[:240]


def _case_lookup(name: str, columns: dict[str, str]) -> str | None:
    lower = name.lower()
    for c in columns:
        if c.lower() == lower:
            return c
    return None


def _closest(name: str, options: list[str]) -> str | None:
    match = difflib.get_close_matches(name.lower(), [o.lower() for o in options], n=1, cutoff=0.6)
    return next((o for o in options if match and o.lower() == match[0]), None)


def _column_and_literals(node: exp.Expression) -> tuple[exp.Column | None, list[str]]:
    if isinstance(node, exp.In):
        column = node.this if isinstance(node.this, exp.Column) else None
        literals = [e.this for e in node.expressions if isinstance(e, exp.Literal) and e.is_string]
        return column, literals
    left, right = node.this, node.expression
    if isinstance(left, exp.Column) and isinstance(right, exp.Literal) and right.is_string:
        return left, [right.this]
    if isinstance(right, exp.Column) and isinstance(left, exp.Literal) and left.is_string:
        return right, [left.this]
    return None, []


def _in_projection(col: exp.Column, select: exp.Expression) -> bool:
    node = col
    while node.parent is not None and node.parent is not select:
        node = node.parent
    return node.parent is select and node.arg_key == "expressions"


def _where_links(select: exp.Select, alias: str) -> bool:
    """A comma/implicit join is fine when the WHERE clause links the table to another one."""
    where = select.args.get("where")
    if where is None:
        return False
    for eq in where.find_all(exp.EQ):
        tables = {c.table for c in (eq.this, eq.expression) if isinstance(c, exp.Column)}
        if alias in tables and len(tables) == 2:
            return True
    return False
