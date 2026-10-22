"""Node: ask_clarification — ask one focused question instead of guessing.

Reached when the planner cannot answer without more information, when grounding
finds something that does not exist (an unknown field, an impossible value, a
misspelt product), or when the user asks to optimize / debug / explain a query
without pasting it. The question and its options are stored as a pending
clarification, so the user's next message is read as the answer to it.
"""

from __future__ import annotations

from langchain_core.runnables import RunnableConfig

from agent.supervisor.dependencies import AgentDeps
from agent.supervisor.state import AgentState


def ask_clarification(state: AgentState, deps: AgentDeps, config: RunnableConfig) -> dict:
    c = dict(state.get("clarification") or {})
    question = (c.get("question") or "Could you tell me a bit more about what you need?").strip()
    options = [o for o in dict.fromkeys(c.get("options") or []) if o][:6]
    return {
        "clarification": {"question": question, "options": options,
                          "request": c.get("request") or state.get("standalone_question")},
        "_trace": {"question": question, "options": options},
    }
