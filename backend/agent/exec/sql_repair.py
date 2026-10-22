"""Node: sql_repair — fix SQL that failed validation, using the validator's findings.

Self-correction loop (like intelligence-assistant's sqlRetry): the failed SQL and
every finding — code, message and fix hint — go back to the main model (repairs
always escalate to it), and the result returns to sql_validation. The router
stops the loop after MAX_SQL_FIX_ATTEMPTS.
"""

from __future__ import annotations

from langchain_core.runnables import RunnableConfig

from agent.guardrails.sql_validator import strip_sql
from agent.llm_schemas import SQLDraft
from agent.planner.plan_grounding import plan_for_sql
from agent.retrieval.swarm import schema_context_for
from agent.supervisor.dependencies import AgentDeps
from agent.supervisor.state import AgentState
from prompt_library import get_prompt


def sql_repair(state: AgentState, deps: AgentDeps, config: RunnableConfig) -> dict:
    attempt = (state.get("attempts") or 1) + 1
    grounded = state.get("grounded_plan")
    messages = get_prompt(
        "sql_repair",
        question=state["standalone_question"],
        schema_context=schema_context_for(deps.kb, state["retrieval"], grounded),
        sql=state["sql"],
        findings=state["validation"]["feedback"],
        attempt=attempt - 1,
        plan=plan_for_sql(grounded) if grounded else None,
    )
    draft, call = deps.llm.structured("sql_repair", messages, SQLDraft, attempt=attempt, config=config)
    origin = "repaired" if state.get("sql_origin") in ("generated", "repaired") else state.get("sql_origin")
    return {
        "sql": strip_sql(draft.sql),
        "sql_origin": origin,
        "attempts": attempt,
        "llm_calls": [call.as_dict()],
        "_trace": {"attempt": attempt, "fixing": [f["code"] for f in state["validation"]["findings"]
                                                   if f["severity"] == "error"]},
    }
