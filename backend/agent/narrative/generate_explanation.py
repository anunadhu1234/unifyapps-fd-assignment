"""Node: generate_explanation — explain the final SQL in plain English (requirement 3.3).

Fast model, plain-text output so the explanation can stream to the UI token by
token. Format: a one-sentence summary paragraph, then bullets walking through
the query. The model is given the value mappings, assumptions, optimization
changes or debug findings, and the row count — never invented numbers.

If the model call fails, a deterministic explanation built from the plan is used
instead: the user still gets their (already validated) SQL.
"""

from __future__ import annotations

from langchain_core.runnables import RunnableConfig

from agent.llm_client import LLMCallFailed, LLMNotConfiguredError
from agent.supervisor.dependencies import AgentDeps
from agent.supervisor.state import AgentState
from prompt_library import get_prompt

MODES = {"generate_sql": "generate", "modify_previous": "generate", "optimize_sql": "optimize",
         "debug_sql": "debug", "explain_sql": "explain"}


def generate_explanation(state: AgentState, deps: AgentDeps, config: RunnableConfig) -> dict:
    intent = state["intent"]["intent"]
    grounded = state.get("grounded_plan") or {}
    messages = get_prompt(
        "generate_explanation",
        question=state["standalone_question"],
        sql=state["sql"],
        mode=MODES.get(intent, "generate"),
        assumptions=grounded.get("assumptions"),
        mappings=grounded.get("mappings"),
        changes=_changes(state),
        result_note=_result_note(state.get("execution")),
    )
    try:
        text, call = deps.llm.text("generate_explanation", messages, config=config)
        return {"explanation": text.strip(), "llm_calls": [call.as_dict()], "_trace": {"chars": len(text)}}
    except (LLMCallFailed, LLMNotConfiguredError) as exc:
        calls = [exc.call.as_dict()] if isinstance(exc, LLMCallFailed) else []
        return {"explanation": _fallback(state), "llm_calls": calls, "_trace": {"fallback": True}}


def _changes(state: AgentState) -> list[str]:
    out = []
    opt = state.get("optimization") or {}
    if opt.get("mode") == "user":
        if opt.get("accepted"):
            out += [f"{c['change']} — {c['reason']}" for c in opt.get("changes", [])]
        else:
            out.append(f"The proposed rewrite was not used because {opt.get('rejected_reason')}; "
                       "the original query is kept.")
        out += [f"Recommended index: {r['ddl']}" for r in opt.get("index_recommendations", [])]
    debug = state.get("debug") or {}
    out += [f"Issue: {i['problem']} — {i['why_incorrect']}" for i in debug.get("issues", [])]
    return out


def _result_note(execution: dict | None) -> str | None:
    if not execution:
        return None
    if execution.get("error"):
        return f"the query could not be run: {execution['error']}"
    n = execution["row_count"]
    if n == 0:
        return "the query returned no rows"
    return f"{n} row{'s' if n != 1 else ''} returned" + (" (showing the first rows only)" if execution["truncated"]
                                                         else "")


def _fallback(state: AgentState) -> str:
    grounded = state.get("grounded_plan") or {}
    summary = grounded.get("restated_request") or f"This query answers: {state['standalone_question']}"
    bullets = [f"- {m}" for m in grounded.get("mappings", [])] + [f"- {a}" for a in grounded.get("assumptions", [])]
    return summary + ("\n\n" + "\n".join(bullets) if bullets else "")
