"""Node: sql_generation — grounded plan → one read-only SQLite query.

Model routing happens here: the plan's complexity score decides whether the
fast model (single table, no aggregation) or the main model (joins, grouping,
metrics) writes the SQL. For follow-ups the previous SQL is passed so the model
edits it instead of starting over.
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


def sql_generation(state: AgentState, deps: AgentDeps, config: RunnableConfig) -> dict:
    grounded = state["grounded_plan"]
    follow_up = state["intent"]["intent"] == "modify_previous"
    messages = get_prompt(
        "sql_generation",
        question=state["standalone_question"],
        schema_context=schema_context_for(deps.kb, state["retrieval"], grounded),
        plan=plan_for_sql(grounded),
        as_of=deps.kb.meta["as_of_date"],
        previous_sql=state.get("last_sql") if follow_up else None,
        # A follow-up edits the previous SQL; worked examples would pull it towards their own column choices.
        examples=None if follow_up else state["retrieval"].get("examples"),
    )
    draft, call = deps.llm.structured("sql_generation", messages, SQLDraft,
                                      complexity=grounded["complexity"], config=config)
    return {
        "sql": strip_sql(draft.sql),
        "sql_origin": "generated",
        "attempts": 1,
        "llm_calls": [call.as_dict()],
        "_trace": {"model": call.model, "route": call.route_reason, "complexity": grounded["complexity"]},
    }
