"""Node: query_planner — natural language → structured QueryPlan (no SQL yet).

Like the intelligence-assistant planner, the question is first turned into a
plan of what to read, filter, group and sort, so every part can be checked
against the real schema before SQL exists. For follow-ups the previous plan is
passed in and the model returns the full updated plan ("only those from
California" adds one filter to it).
"""

from __future__ import annotations

from langchain_core.runnables import RunnableConfig

from agent.llm_schemas import QueryPlan
from agent.supervisor.dependencies import AgentDeps
from agent.supervisor.state import AgentState
from prompt_library import get_prompt


def query_planner(state: AgentState, deps: AgentDeps, config: RunnableConfig) -> dict:
    retrieval = state["retrieval"]
    follow_up = state["intent"]["intent"] == "modify_previous"
    previous_plan = _plan_core(state.get("last_plan")) if follow_up else None
    messages = get_prompt(
        "query_planner",
        question=state["standalone_question"],
        schema_context=_with_join_notes(retrieval),
        as_of=deps.kb.meta["as_of_date"],
        previous_plan=previous_plan,
        examples=retrieval.get("examples"),
    )
    plan, call = deps.llm.structured("query_planner", messages, QueryPlan, config=config)
    return {
        "plan": plan.model_dump(),
        "llm_calls": [call.as_dict()],
        "_trace": {"restated_request": plan.restated_request, "tables": plan.tables,
                   "filters": len(plan.filters), "needs_clarification": plan.needs_clarification,
                   "follow_up": follow_up},
    }


def _with_join_notes(retrieval: dict) -> str:
    """Add the 'two ways to join' warnings to the schema text so the planner chooses deliberately."""
    text = retrieval["schema_context"]
    if retrieval.get("ambiguous_links"):
        notes = ["AMBIGUOUS LINKS (choose the one the request means, and say which in relationship_notes):"]
        for link in retrieval["ambiguous_links"]:
            a, b = link["tables"]
            for opt in link["options"]:
                notes.append(f"  {a} ↔ {b} via {' AND '.join(opt['joins'])}  — {opt['meaning'] or 'see relationships'}")
        text += "\n" + "\n".join(notes) + "\n"
    return text


def _plan_core(grounded: dict | None) -> dict | None:
    """The parts of the previous (grounded) plan the planner should see and edit."""
    if not grounded:
        return None
    keys = ("restated_request", "tables", "select", "filters", "group_by", "having", "order_by", "limit",
            "distinct", "include_unmatched", "relationship_notes", "assumptions")
    core = {k: grounded.get(k) for k in keys}
    keep = ("table", "column", "operator", "values")
    core["filters"] = [{k: f[k] for k in keep} for f in grounded.get("filters", [])]
    return core
