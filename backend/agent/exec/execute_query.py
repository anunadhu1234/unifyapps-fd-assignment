"""Node: execute_query — run the validated SQL against the sample database (optional).

Only SQL that passed sql_validation reaches this node, and it runs through the
read-only connection (mode=ro, query_only, authorizer, timeout, row cap). The
user can switch execution off per request (options.execute = false) to get
SQL only. A runtime error or timeout is reported, not hidden.
"""

from __future__ import annotations

from langchain_core.runnables import RunnableConfig

from agent.exec.sqlite_runner import QueryTimeout
from agent.supervisor.dependencies import AgentDeps
from agent.supervisor.state import AgentState


def execute_query(state: AgentState, deps: AgentDeps, config: RunnableConfig) -> dict:
    if not (state.get("options") or {}).get("execute", True):
        return {"execution": None, "_trace": {"skipped": True}}
    try:
        result = deps.db.execute(state["sql"])
        execution = result.as_dict()
        execution["total_rows"] = result.row_count
        if result.truncated:  # tell the user the real size: "showing 500 of 3,000 rows"
            try:
                execution["total_rows"] = deps.db.execute(f"SELECT COUNT(*) FROM ({state['sql']})").rows[0][0]
            except Exception:
                execution["total_rows"] = None
    except QueryTimeout as exc:
        execution = {"columns": [], "rows": [], "row_count": 0, "total_rows": None, "truncated": False, "ms": None,
                     "error": str(exc)}
    except Exception as exc:
        execution = {"columns": [], "rows": [], "row_count": 0, "total_rows": None, "truncated": False, "ms": None,
                     "error": f"The database could not run the query: {exc}"}
    return {
        "execution": execution,
        "_trace": {"rows": execution["row_count"], "truncated": execution["truncated"], "ms": execution["ms"],
                   "error": execution["error"]},
    }
