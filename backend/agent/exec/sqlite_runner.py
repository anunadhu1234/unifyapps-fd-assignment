"""Read-only SQLite access — the last line of defence.

Even if every check before it failed, nothing that reaches the database through
this module can change it:

  1. the file is opened with `mode=ro` (SQLite refuses writes at the file level);
  2. `PRAGMA query_only = ON` rejects any write statement;
  3. an authorizer callback allows only reading actions (SELECT, column reads,
     ordinary functions, recursive CTEs) and denies everything else — including
     ATTACH, PRAGMA, temp tables and load_extension;
  4. a progress handler aborts queries that run past the timeout;
  5. results are capped at `max_rows` (the caller is told when rows were cut).
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path

ALLOWED_ACTIONS = {
    sqlite3.SQLITE_SELECT,
    sqlite3.SQLITE_READ,
    sqlite3.SQLITE_FUNCTION,
    getattr(sqlite3, "SQLITE_RECURSIVE", 33),
}
BLOCKED_FUNCTIONS = {"load_extension", "readfile", "writefile", "edit", "fts3_tokenizer", "sqlite_compileoption_get"}


class QueryTimeout(RuntimeError):
    pass


@dataclass
class QueryResult:
    columns: list[str]
    rows: list[list]
    row_count: int  # rows returned (after the cap)
    truncated: bool  # True when more rows existed than max_rows
    ms: int
    error: str | None = None
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"columns": self.columns, "rows": self.rows, "row_count": self.row_count,
                "truncated": self.truncated, "ms": self.ms, "error": self.error}


def _authorizer(action: int, arg1, arg2, _db, _trigger) -> int:
    if action not in ALLOWED_ACTIONS:
        return sqlite3.SQLITE_DENY
    if action == sqlite3.SQLITE_FUNCTION and (arg2 or "").lower() in BLOCKED_FUNCTIONS:
        return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK


class ReadOnlyDatabase:
    def __init__(self, path: Path, *, timeout_s: float = 5.0, max_rows: int = 500):
        if not Path(path).exists():
            raise FileNotFoundError(f"database not found: {path}")
        self.path = Path(path)
        self.timeout_s = timeout_s
        self.max_rows = max_rows

    def _connect(self, deadline: float | None) -> sqlite3.Connection:
        con = sqlite3.connect(f"file:{self.path.as_posix()}?mode=ro", uri=True, check_same_thread=False)
        con.execute("PRAGMA query_only = ON")
        con.set_authorizer(_authorizer)
        if deadline is not None:
            # Returning non-zero from the handler interrupts the running statement.
            con.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, 10_000)
        return con

    def execute(self, sql: str, *, max_rows: int | None = None, timeout_s: float | None = None) -> QueryResult:
        cap = max_rows or self.max_rows
        limit_s = timeout_s or self.timeout_s
        started = time.perf_counter()
        deadline = time.monotonic() + limit_s
        con = self._connect(deadline)
        try:
            cur = con.execute(sql)
            columns = [d[0] for d in cur.description or []]
            fetched = cur.fetchmany(cap + 1)
            truncated = len(fetched) > cap
            rows = [list(r) for r in fetched[:cap]]
            return QueryResult(columns, rows, len(rows), truncated, _ms(started))
        except sqlite3.OperationalError as exc:
            if "interrupted" in str(exc).lower():
                raise QueryTimeout(f"query exceeded the {limit_s:g}s time limit") from exc
            raise
        finally:
            con.close()

    def explain(self, sql: str) -> list[dict]:
        """EXPLAIN QUERY PLAN — compiles the statement (catching any engine error) without running it."""
        con = self._connect(time.monotonic() + self.timeout_s)
        try:
            rows = con.execute(f"EXPLAIN QUERY PLAN {sql}").fetchall()
            return [{"id": r[0], "parent": r[1], "detail": r[3]} for r in rows]
        finally:
            con.close()

    def distinct_matching(self, table: str, column: str, needle: str, limit: int = 12) -> list[str]:
        """Distinct stored values containing `needle` (case-insensitive). Identifiers must come
        from the knowledge base — never from user text — and the needle is bound as a parameter."""
        con = self._connect(time.monotonic() + self.timeout_s)
        try:
            rows = con.execute(
                f'SELECT DISTINCT "{column}" FROM "{table}" WHERE "{column}" LIKE ? ESCAPE \'\\\' '
                f'ORDER BY "{column}" LIMIT ?',
                (f"%{_escape_like(needle)}%", limit)).fetchall()
            return [r[0] for r in rows]
        finally:
            con.close()


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)
