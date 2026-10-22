"""Node: scope_validation — the gate between "understood" and "allowed".

Deterministic. Combines the input guard, the classified intent and any SQL the
user pasted, and decides whether the turn continues:

    out_of_scope                      → refuse (the assignment's exact wording)
    destructive request / pasted write → refuse politely, offer a read-only alternative
    optimize / debug / explain w/o SQL → ask the user to paste the query
    anything else                      → continue
"""

from __future__ import annotations

from langchain_core.runnables import RunnableConfig

from agent.supervisor.dependencies import AgentDeps
from agent.supervisor.state import AgentState

SQL_INPUT_INTENTS = {"optimize_sql", "debug_sql", "explain_sql"}

REFUSALS = {
    "out_of_scope": "I'm designed to assist only with SQL and database-related tasks. Please ask a question related "
                    "to the provided database schema.",
    "destructive": "I can't help with that — I only work with read-only queries, so I never generate DELETE, UPDATE, "
                   "INSERT, DROP, ALTER or TRUNCATE statements. If it helps, I can write a SELECT that shows the rows "
                   "that would be affected.",
    "prompt_injection": "I can't follow instructions that try to change how I work. I can help you query the "
                        "Summit Supply Co. database — what would you like to know?",
    "too_long": "That message is too long for me to process. Please shorten it and try again.",
    "empty": "Please type a question about the database, or paste a SQL query.",
}

PASTE_SQL = {
    "optimize_sql": "Please paste the SQL query you'd like me to optimize.",
    "debug_sql": "Please paste the SQL query that isn't working, and I'll find the problem.",
    "explain_sql": "Please paste the SQL query you'd like me to explain.",
}


def scope_validation(state: AgentState, deps: AgentDeps, config: RunnableConfig) -> dict:
    intent = state["intent"]["intent"]
    if intent == "out_of_scope":
        return _refuse("out_of_scope")
    if intent == "destructive" or state.get("input_check", {}).get("user_sql_is_write"):
        return _refuse("destructive")
    if intent in SQL_INPUT_INTENTS and not state.get("user_sql"):
        return {"clarification": {"question": PASTE_SQL[intent], "options": [],
                                  "request": state.get("standalone_question")},
                "_trace": {"decision": "needs_sql"}}
    return {"_trace": {"decision": "allowed", "intent": intent}}


def _refuse(reason: str) -> dict:
    return {"refusal": {"reason": reason, "message": REFUSALS[reason]}, "_trace": {"decision": f"refused:{reason}"}}
