"""Node: return_response — assemble the reply and update conversation memory.

Every path through the graph ends here. The reply has one `type`:

    sql            validated SQL (+ explanation, results, cost, dialect versions)
    answer         an answer about the schema / SQL concepts
    clarification  one question with suggested options
    refusal        out of scope, destructive, or prompt injection
    error          the model was unavailable, or no valid SQL after the repair budget

User-facing fields are at the top level. Everything under "dev" (intent, plan,
grounding, retrieval, validation history, node trace, every LLM call with
model / tokens / cost) is for dev mode only — the API strips it for normal users.

Memory: the turn is appended to the history; a successful query becomes
last_sql / last_plan (what follow-ups modify); a clarification is remembered so
the next message is read as its answer.
"""

from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig

from agent.guardrails.sql_validator import transpile
from agent.supervisor.dependencies import AgentDeps
from agent.supervisor.state import AgentState

HISTORY_LIMIT = 20
DIALECTS = {"postgres": "postgres", "mysql": "mysql"}

FAILURE_MESSAGES = {
    "llm_not_configured": "The language model is not configured on this server (AWS_BEARER_TOKEN_BEDROCK is missing).",
    "llm_error": "The language model did not respond properly. Please try again in a moment.",
    "llm_quota": "The language model's usage quota has been reached. Please try again later.",
    "llm_rate_limited": "The language model is busy right now (rate limited). Please try again in a minute.",
    "internal_error": "Something went wrong while processing your request. Please try again.",
}


def return_response(state: AgentState, deps: AgentDeps, config: RunnableConfig) -> dict:
    rtype, message = _type_and_message(state, deps)
    intent = (state.get("intent") or {}).get("intent")
    sql = state.get("sql") if rtype in ("sql", "error") else None
    grounded = state.get("grounded_plan") or {}
    validation = state.get("validation") or {}

    response = {
        "request_id": state.get("request_id"),
        "type": rtype,
        "intent": intent,
        "message": message,
        "sql": sql,
        "dialects": _dialects(sql) if rtype == "sql" and sql else None,
        "explanation": _split_explanation(state.get("explanation")) if rtype == "sql" else None,
        "answer": state.get("explanation") if rtype == "answer" else None,
        "results": state.get("execution") if rtype == "sql" else None,
        "suggestions": (state.get("suggestions") or []) if rtype == "sql" else [],
        "cost": state.get("cost") if rtype == "sql" else None,
        "validation": {
            "ok": validation.get("ok"),
            "checks_passed": validation.get("checks_passed", []),
            "warnings": [f for f in validation.get("findings", []) if f["severity"] == "warning"],
            "errors": [f for f in validation.get("findings", []) if f["severity"] == "error"],
            "attempts": state.get("attempts") or 0,
        } if validation else None,
        "assumptions": grounded.get("assumptions", []),
        "mappings": grounded.get("mappings", []),
        "optimization": state.get("optimization") if intent == "optimize_sql" or rtype == "sql" else None,
        "debug": state.get("debug"),
        "clarification": state.get("clarification") if rtype == "clarification" else None,
        "refusal": state.get("refusal") if rtype == "refusal" else None,
        # Public step summary (names + timings only) — the detailed trace is dev-only.
        "pipeline": [{"node": e["node"], "ms": e.get("ms"), "ok": e.get("ok", True)} for e in state.get("trace") or []],
        "dev": _dev_section(state),
    }

    turn = {"question": state.get("question"), "standalone_question": state.get("standalone_question"),
            "intent": intent, "response_type": rtype, "sql": sql if rtype == "sql" else None,
            "message": message[:300]}
    update = {
        "response": response,
        "messages": [HumanMessage(state.get("question") or ""), AIMessage(message)],
        "history": ((state.get("history") or []) + [turn])[-HISTORY_LIMIT:],
        "pending_clarification": state.get("clarification") if rtype == "clarification" else None,
        "_trace": {"type": rtype},
    }
    if rtype == "sql":
        update["last_sql"] = sql
        update["last_plan"] = grounded if intent in ("generate_sql", "modify_previous") else None
    return update


def _type_and_message(state: AgentState, deps: AgentDeps) -> tuple[str, str]:
    if state.get("refusal"):
        return "refusal", state["refusal"]["message"]
    failure = state.get("failure")
    if failure:
        return "error", FAILURE_MESSAGES.get(failure.get("kind"), FAILURE_MESSAGES["internal_error"])
    if state.get("clarification"):
        return "clarification", state["clarification"]["question"]
    if (state.get("intent") or {}).get("intent") == "schema_question":
        return "answer", state.get("explanation") or ""
    validation = state.get("validation") or {}
    if validation and not validation.get("ok"):
        errors = [f["message"] for f in validation.get("findings", []) if f["severity"] == "error"]
        return "error", (f"I couldn't produce a query that passes validation after {state.get('attempts') or 0} "
                         f"attempt(s). Remaining problems: " + " ".join(errors[:3]))
    explanation = _split_explanation(state.get("explanation"))
    message = (explanation or {}).get("summary") or (state.get("grounded_plan") or {}).get("restated_request") \
        or "Here is the SQL for your request."
    return "sql", message


def _split_explanation(text: str | None) -> dict | None:
    if not text:
        return None
    paragraphs = [p.strip() for p in text.strip().split("\n\n") if p.strip()]
    summary = paragraphs[0] if paragraphs and not paragraphs[0].startswith("- ") else ""
    steps = [line.strip()[2:].strip() for line in text.splitlines() if line.strip().startswith(("- ", "* "))]
    return {"summary": summary, "steps": steps, "text": text.strip()}


def _dialects(sql: str) -> dict:
    out = {"sqlite": sql}
    for name, target in DIALECTS.items():
        converted = transpile(sql, target)
        if converted:
            out[name] = converted
    return out


def _dev_section(state: AgentState) -> dict:
    calls = state.get("llm_calls") or []
    costs = [c["cost_usd"] for c in calls if c.get("cost_usd") is not None]
    return {
        "input_check": state.get("input_check"),
        "intent": state.get("intent"),
        "standalone_question": state.get("standalone_question"),
        "retrieval": state.get("retrieval"),
        "plan": state.get("plan"),
        "grounded_plan": state.get("grounded_plan"),
        "validation_history": state.get("validation_history"),
        "failure": state.get("failure"),
        "trace": state.get("trace") or [],
        "llm_calls": calls,
        "totals": {
            "llm_calls": len(calls),
            "input_tokens": sum(c.get("input_tokens") or 0 for c in calls),
            "output_tokens": sum(c.get("output_tokens") or 0 for c in calls),
            "cost_usd": round(sum(costs), 6) if costs else None,
            "llm_ms": sum(c.get("ms") or 0 for c in calls),
            "pipeline_ms": sum(e.get("ms") or 0 for e in state.get("trace") or []),
        },
    }
