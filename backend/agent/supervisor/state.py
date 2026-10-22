"""LangGraph state for the SQL agent.

The state has two lifetimes, persisted together by the checkpointer per thread:

  conversation — survives across turns: messages, compact turn history, the last
                 successful plan / SQL (what follow-ups modify), and a pending
                 clarification question.
  turn         — reset by `receive_request` at the start of every turn.

`trace` and `llm_calls` use an append reducer (each node adds its own entries)
that `receive_request` resets with RESET.
"""

from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

RESET: dict = {"__reset__": True}


def append_or_reset(left: list | None, right: Any) -> list:
    """Append the update's items; RESET (alone, or as the first item of the update) clears the list first."""
    if isinstance(right, dict) and right.get("__reset__"):
        return []
    if right is None:
        return left or []
    right = list(right)
    if right and isinstance(right[0], dict) and right[0].get("__reset__"):
        return right[1:]
    return (left or []) + right


# Per-turn keys cleared by receive_request (conversation keys are not listed).
TURN_KEYS = (
    "request_id", "question", "options", "input_check", "intent", "standalone_question", "user_sql",
    "retrieval", "plan", "grounded_plan", "sql", "sql_origin", "attempts", "validation", "validation_history",
    "debug", "optimization", "optimized", "debugged", "cost", "execution", "explanation", "suggestions", "response",
    "refusal", "clarification", "failure",
)


class AgentState(TypedDict, total=False):
    # ── conversation (persisted across turns) ──
    messages: Annotated[list[AnyMessage], add_messages]
    history: list[dict]
    last_plan: dict | None
    last_sql: str | None
    pending_clarification: dict | None

    # ── turn input ──
    request_id: str
    question: str
    options: dict  # {"execute": bool}

    # ── turn working state ──
    input_check: dict
    intent: dict  # IntentResult as dict
    standalone_question: str
    user_sql: str | None
    retrieval: dict
    plan: dict  # QueryPlan as dict
    grounded_plan: dict
    sql: str | None
    sql_origin: str  # generated | repaired | user | debugged | optimized
    attempts: int
    validation: dict
    validation_history: list[dict]
    debug: dict | None
    optimization: dict | None
    optimized: bool
    debugged: bool
    cost: dict | None
    execution: dict | None
    explanation: str | None
    suggestions: list[dict] | None
    refusal: dict | None
    clarification: dict | None
    failure: dict | None
    response: dict

    # ── observability (dev mode) ──
    trace: Annotated[list[dict], append_or_reset]
    llm_calls: Annotated[list[dict], append_or_reset]
