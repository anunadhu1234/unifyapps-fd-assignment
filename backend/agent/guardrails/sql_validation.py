"""Node: sql_validation — every SQL statement passes here before anyone sees or runs it.

Runs the deterministic SQLValidator (syntax, single statement, read-only,
tables, columns, stored values, FK joins, SQLite compile, plan conformance) on
the current SQL, whatever produced it: the generator, the repair loop, the
debugger, or the user. The routing after this node decides between repair,
debugging, optimization and refusal.
"""

from __future__ import annotations

from langchain_core.runnables import RunnableConfig

from agent.supervisor.dependencies import AgentDeps
from agent.supervisor.state import AgentState


def sql_validation(state: AgentState, deps: AgentDeps, config: RunnableConfig) -> dict:
    sql = state.get("sql") or state.get("user_sql") or ""
    origin = state.get("sql_origin") or "user"
    # Generated SQL must also honour the grounded plan's value filters.
    plan_filters = None
    if origin in ("generated", "repaired") and state.get("grounded_plan"):
        plan_filters = [{"table": f["table"], "column": f["column"], "operator": f["operator"],
                         "values": f["stored_values"]} for f in state["grounded_plan"]["filters"]]
    report = deps.validator.validate(sql, plan_filters=plan_filters)
    record = {"attempt": state.get("attempts") or 0, "origin": origin, "sql": report.sql, **report.as_dict()}
    return {
        "sql": report.sql,
        "sql_origin": origin,
        "validation": {**report.as_dict(), "formatted_sql": report.formatted_sql, "feedback": report.feedback(),
                       "blocked_write": report.blocked_write},
        "validation_history": (state.get("validation_history") or []) + [record],
        "_trace": {"ok": report.ok, "origin": origin, "attempt": record["attempt"],
                   "errors": [f.code for f in report.errors],
                   "warnings": [f.code for f in report.findings if f.severity == "warning"],
                   "checks_passed": report.checks_passed},
    }
