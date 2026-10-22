"""Node: receive_request — the "User Request" box of the workflow.

Starts a new turn on the conversation's thread: clears the previous turn's
working state (conversation memory is kept), applies default options, and runs
the deterministic input guard. Empty, over-long and prompt-injection messages
are refused here, before any LLM is called.
"""

from __future__ import annotations

import uuid

from langchain_core.runnables import RunnableConfig

from agent.guardrails.input_guard import check_input
from agent.intent.scope_validation import REFUSALS
from agent.supervisor.dependencies import AgentDeps
from agent.supervisor.state import RESET, TURN_KEYS, AgentState

KEEP_FROM_INPUT = {"request_id", "question", "options"}


def receive_request(state: AgentState, deps: AgentDeps, config: RunnableConfig) -> dict:
    update: dict = {key: None for key in TURN_KEYS if key not in KEEP_FROM_INPUT}
    check = check_input(state.get("question", ""), max_chars=deps.settings.max_question_chars)
    update.update(
        request_id=state.get("request_id") or uuid.uuid4().hex,
        question=check.text,
        options={"execute": True, **(state.get("options") or {})},
        input_check=check.as_dict(),
        user_sql=check.user_sql,
        attempts=0,
        optimized=False,
        debugged=False,
        validation_history=[],
        trace=RESET,
        llm_calls=RESET,
    )
    if check.blocked:
        update["refusal"] = {"reason": check.reason, "message": REFUSALS[check.reason], "signals": check.signals}
    update["_trace"] = {"blocked": check.blocked, "reason": check.reason, "signals": check.signals,
                        "has_sql": bool(check.user_sql)}
    return update
