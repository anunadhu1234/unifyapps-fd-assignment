"""Node: schema_answer — answer questions about the database (or SQL concepts) without querying it.

"What tables are there?", "What does LoyaltyTier mean?", "How are orders linked to
products?", "What's the difference between WHERE and HAVING?". The fast model
answers from the knowledge-base documentation only (streamed as text), so it can
describe the schema but never invent a table, column or metric.
"""

from __future__ import annotations

from langchain_core.runnables import RunnableConfig

from agent.supervisor.dependencies import AgentDeps
from agent.supervisor.state import AgentState
from prompt_library import get_prompt


def schema_answer(state: AgentState, deps: AgentDeps, config: RunnableConfig) -> dict:
    kb = deps.kb
    documentation = kb.schema_context(list(kb.tables), metrics=list(kb.metrics.values()),
                                      glossary=list(kb.glossary.values()))
    messages = get_prompt("schema_answer", question=state["standalone_question"], documentation=documentation)
    text, call = deps.llm.text("schema_answer", messages, config=config)
    return {"explanation": text.strip(), "llm_calls": [call.as_dict()], "_trace": {"chars": len(text)}}
