"""Node: sql_debugging — find what is wrong with a user's query and correct it.

Requirement 3.5: identify the issue, explain why it is incorrect, return a
corrected version. The validator has already checked the user's SQL against the
real schema and stored values; its findings are given to the model as confirmed
problems, and the model adds logic issues the validator cannot see. The
corrected SQL then goes back through sql_validation like any other SQL.

Also used before optimizing / explaining a query that does not validate.
"""

from __future__ import annotations

from langchain_core.runnables import RunnableConfig

from agent.guardrails.sql_validator import strip_sql
from agent.llm_schemas import DebugResult
from agent.supervisor.dependencies import AgentDeps
from agent.supervisor.state import AgentState
from prompt_library import get_prompt


def sql_debugging(state: AgentState, deps: AgentDeps, config: RunnableConfig) -> dict:
    original = state.get("user_sql") or state.get("sql") or ""
    validation = state.get("validation") or {}
    messages = get_prompt(
        "sql_debugging",
        question=state["standalone_question"],
        schema_context=state["retrieval"]["schema_context"],
        sql=original,
        findings=validation.get("feedback", ""),
    )
    result, call = deps.llm.structured("sql_debugging", messages, DebugResult, config=config)
    corrected = strip_sql(result.corrected_sql)
    return {
        "debug": {
            "original_sql": original,
            "issues": [i.model_dump() for i in result.issues],
            "summary": result.summary,
            "validator_findings": validation.get("findings", []),
            "changed": " ".join(corrected.split()) != " ".join(strip_sql(original).split()),
        },
        "sql": corrected,
        "sql_origin": "debugged",
        "debugged": True,
        "attempts": (state.get("attempts") or 0) + 1,
        "llm_calls": [call.as_dict()],
        "_trace": {"issues": len(result.issues), "validator_errors": sum(
            1 for f in validation.get("findings", []) if f["severity"] == "error")},
    }
