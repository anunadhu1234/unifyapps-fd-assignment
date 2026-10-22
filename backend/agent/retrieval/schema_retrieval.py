"""Node: schema_retrieval — gather only the schema and knowledge this request needs.

Runs the retrieval swarm on the standalone question (plus any pasted SQL and,
for follow-ups, the previous plan's tables) and stores the merged result:
selected tables, FK joins between them, ambiguous links, matched values /
metrics / terms, similar examples, and the prompt-ready schema context.
"""

from __future__ import annotations

from langchain_core.runnables import RunnableConfig

from agent.retrieval.swarm import run_swarm
from agent.supervisor.dependencies import AgentDeps
from agent.supervisor.state import AgentState


def schema_retrieval(state: AgentState, deps: AgentDeps, config: RunnableConfig) -> dict:
    intent = state["intent"]["intent"]
    previous = (state.get("last_plan") or {}).get("tables") if intent == "modify_previous" else None
    retrieval = run_swarm(
        deps.kb, deps.examples, state["standalone_question"],
        user_sql=state.get("user_sql") if intent in ("optimize_sql", "debug_sql", "explain_sql") else None,
        previous_tables=previous,
        include_indexes=intent == "optimize_sql",
    )
    return {
        "retrieval": retrieval,
        "_trace": {"tables": retrieval["tables"], "joins": retrieval["joins"], "metrics": retrieval["metrics"],
                   "glossary": retrieval["glossary"], "examples": len(retrieval["examples"]),
                   "ambiguous_links": len(retrieval["ambiguous_links"])},
    }
