"""Conditional edges — every routing decision of the graph, in one place.

Each function reads the state after a node and names the next node. Any node
failure (state.failure) or refusal short-circuits to return_response.
"""

from __future__ import annotations

from agent.supervisor.state import AgentState

RESPOND = "return_response"


def _stop(state: AgentState) -> bool:
    return bool(state.get("failure") or state.get("refusal"))


def after_receive_request(state: AgentState) -> str:
    return RESPOND if _stop(state) else "intent_detection"


def after_intent_detection(state: AgentState) -> str:
    return RESPOND if _stop(state) else "scope_validation"


def after_scope_validation(state: AgentState) -> str:
    if _stop(state):
        return RESPOND
    if state.get("clarification"):
        return "ask_clarification"
    if state["intent"]["intent"] == "schema_question":
        return "schema_answer"
    return "schema_retrieval"


def after_schema_retrieval(state: AgentState) -> str:
    if _stop(state):
        return RESPOND
    if state["intent"]["intent"] in ("optimize_sql", "debug_sql", "explain_sql"):
        return "sql_validation"  # validate the user's own SQL first
    return "query_planner"


def after_query_planner(state: AgentState) -> str:
    return RESPOND if _stop(state) else "plan_grounding"


def after_plan_grounding(state: AgentState) -> str:
    if _stop(state):
        return RESPOND
    return "ask_clarification" if state.get("clarification") else "sql_generation"


def after_sql_generation(state: AgentState) -> str:
    return RESPOND if _stop(state) else "sql_validation"


def make_after_sql_validation(max_attempts: int):
    def after_sql_validation(state: AgentState) -> str:
        if state.get("failure"):
            return RESPOND
        intent = state["intent"]["intent"]
        validation = state["validation"]
        user_sql_path = intent in ("optimize_sql", "debug_sql", "explain_sql")
        if validation["ok"]:
            # Debugging always reviews the user's query once, even when it validates (logic errors).
            if intent == "debug_sql" and not state.get("debugged"):
                return "sql_debugging"
            if not state.get("optimized"):
                return "sql_optimization"
            return "execute_query"
        # Invalid SQL. A user's query is corrected by the debugger first; then the repair loop.
        if user_sql_path and not state.get("debugged"):
            return "sql_debugging"
        if (state.get("attempts") or 0) < max_attempts:
            return "sql_repair"
        return RESPOND

    return after_sql_validation


def after_sql_repair(state: AgentState) -> str:
    return RESPOND if _stop(state) else "sql_validation"


def after_sql_debugging(state: AgentState) -> str:
    return RESPOND if _stop(state) else "sql_validation"


def after_sql_optimization(state: AgentState) -> str:
    return RESPOND if _stop(state) else "execute_query"


def after_execute_query(state: AgentState) -> str | list[str]:
    if _stop(state):
        return RESPOND
    # New and follow-up queries fan out: the explanation and the "Dive deeper"
    # suggestions are produced in parallel, then joined at return_response.
    if state["intent"]["intent"] in ("generate_sql", "modify_previous"):
        return ["generate_explanation", "suggest_follow_ups"]
    return "generate_explanation"
