"""Node: intent_detection — what kind of request is this, and what does it mean in context?

One fast-model call (structured output: IntentResult) that classifies the
message into generate / modify / optimize / debug / explain / schema question /
destructive / out-of-scope, and rewrites follow-ups into a standalone question
using the conversation history ("Only those from California" → "Show all
customers who are from California").

Deterministic corrections after the call:
  * SQL pasted by the user is taken from the input guard's extraction when found;
  * a pasted write statement is always "destructive", whatever the model said;
  * "modify_previous" with no previous turn becomes "generate_sql".
"""

from __future__ import annotations

from langchain_core.runnables import RunnableConfig

from agent.guardrails.sql_validator import strip_sql
from agent.llm_schemas import IntentResult
from agent.supervisor.dependencies import AgentDeps
from agent.supervisor.state import AgentState
from prompt_library import get_prompt


def intent_detection(state: AgentState, deps: AgentDeps, config: RunnableConfig) -> dict:
    history = (state.get("history") or [])[-deps.settings.history_turns:]
    messages = get_prompt(
        "intent_detection",
        message=state["question"],
        history=history,
        database_summary=deps.kb.meta["domain"],
        tables=list(deps.kb.tables),
        pending_clarification=state.get("pending_clarification"),
    )
    result, call = deps.llm.structured("intent_detection", messages, IntentResult, config=config)

    intent = result.intent
    user_sql = state.get("user_sql") or (strip_sql(result.user_sql) if result.user_sql else None)
    corrections = []
    if state.get("input_check", {}).get("user_sql_is_write") and intent != "destructive":
        corrections.append(f"{intent} → destructive (the pasted SQL writes to the database)")
        intent = "destructive"
    if intent == "modify_previous" and not history:
        corrections.append("modify_previous → generate_sql (no previous turn)")
        intent = "generate_sql"

    detected = result.model_dump() | {"intent": intent, "model_intent": result.intent, "corrections": corrections}
    return {
        "intent": detected,
        "standalone_question": (result.standalone_question or state["question"]).strip(),
        "user_sql": user_sql,
        "llm_calls": [call.as_dict()],
        "_trace": {"intent": intent, "standalone_question": result.standalone_question, "reason": result.reason,
                   "corrections": corrections},
    }
