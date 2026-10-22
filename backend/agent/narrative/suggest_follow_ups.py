"""Node: suggest_follow_ups — three grounded "Dive deeper" questions after an answer.

Runs in parallel with generate_explanation (LangGraph fan-out after execute_query),
so it adds no waiting time. One fast-model call proposes a drill-down, a refinement
and a related question from what the answer actually used (tables, filters,
grouping, metrics, result columns). Then, deterministically:

  * a suggestion must refer to something in the knowledge graph (a table, column,
    metric, business term or stored value) — otherwise it is dropped;
  * duplicates of each other or of anything already asked are dropped;
  * gaps are filled with rule-based suggestions built from the plan.

Fails soft like the intelligence-assistant suggester: a model or parsing failure
never affects the answer — the rule-based suggestions are used instead.
"""

from __future__ import annotations

import re

from langchain_core.runnables import RunnableConfig

from agent.knowledge.kb_resolver import KnowledgeBase
from agent.llm_client import LLMCallFailed
from agent.llm_schemas import FollowUpSuggestions
from agent.retrieval.swarm import schema_context_for
from agent.supervisor.dependencies import AgentDeps
from agent.supervisor.state import AgentState
from prompt_library import get_prompt

MAX_SUGGESTIONS = 3

# Dimensions worth drilling into, in order of usefulness: (table, column, how users say it).
DIMENSIONS = [
    ("Customers", "Segment", "customer segment"),
    ("Products", "Category", "product category"),
    ("Orders", "Channel", "sales channel"),
    ("Customers", "State", "customer state"),
    ("Employees", "Department", "department"),
    ("Customers", "LoyaltyTier", "loyalty tier"),
    ("Orders", "Status", "order status"),
]


def suggest_follow_ups(state: AgentState, deps: AgentDeps, config: RunnableConfig) -> dict:
    if not deps.settings.suggestions_enabled:
        return {"suggestions": [], "_trace": {"skipped": "disabled"}}

    grounded = state.get("grounded_plan") or {}
    asked = [t.get("question") or "" for t in state.get("history") or []] + [state.get("question") or ""]
    fallback = rule_based(grounded, deps.kb)

    proposed, calls, source = [], [], "rules"
    try:
        messages = get_prompt(
            "suggest_follow_ups",
            question=state["standalone_question"],
            schema_context=schema_context_for(deps.kb, state.get("retrieval") or {}, grounded),
            plan=_plan_summary(grounded),
            result=_result_summary(state.get("execution")),
            asked=asked,
        )
        result, call = deps.llm.structured("suggest_follow_ups", messages, FollowUpSuggestions, config=config)
        proposed, calls, source = [s.model_dump() for s in result.suggestions], [call.as_dict()], "llm"
    except LLMCallFailed as exc:
        calls = [exc.call.as_dict()]
    except Exception:  # suggestions are optional: never let them break an answer
        pass

    grounded_ones = [s for s in proposed if refers_to_schema(s["question"], deps.kb)]
    chosen = dedupe(grounded_ones + fallback, asked)[:MAX_SUGGESTIONS]
    return {
        "suggestions": chosen,
        "llm_calls": calls,
        "_trace": {"source": source, "proposed": len(proposed), "kept": len(grounded_ones),
                   "returned": len(chosen)},
    }


def refers_to_schema(question: str, kb: KnowledgeBase) -> bool:
    return bool(kb.match_terms(question) or kb.match_values(question))


def dedupe(suggestions: list[dict], asked: list[str]) -> list[dict]:
    seen = {_key(q) for q in asked}
    out = []
    for s in suggestions:
        key = _key(s["question"])
        if key and key not in seen:
            seen.add(key)
            out.append({"kind": s["kind"], "question": s["question"].strip()})
    return out


def _key(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", (text or "").lower()).strip()


def rule_based(grounded: dict, kb: KnowledgeBase) -> list[dict]:
    """Deterministic suggestions from the plan: one drill-down, one refinement, one related question."""
    tables = set(grounded.get("tables") or [])
    used = {g.split(".")[-1] for g in grounded.get("group_by") or []}
    used |= {f["column"] for f in grounded.get("filters") or []}
    out: list[dict] = []

    reachable = tables | ({"Customers", "Products"} if tables & {"Orders", "OrderItems"} else set())
    for table, column, phrase in DIMENSIONS:
        if table in reachable and column not in used:
            out.append({"kind": "drill_down", "question": f"Break this down by {phrase}"})
            break

    years = {v[:4] for f in grounded.get("filters") or [] for v in f.get("stored_values") or []
             if re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(v))}
    has_dates = any(kb.column(t, c)["role"] == "date" for t in tables for c in kb.tables[t]["columns"])
    if years:
        out.append({"kind": "refine", "question": f"Compare with {int(min(years)) - 1}"})
    elif has_dates:
        out.append({"kind": "refine", "question": "Only for 2025"})
    elif "Customers" in reachable and "Segment" not in used:
        out.append({"kind": "refine", "question": "Only the corporate customers"})

    metric_names = {m["name"] for m in grounded.get("metrics") or []}
    if "Net Revenue" in metric_names:
        related = "What is the average order value by month in 2025?"
    elif tables & {"Orders", "OrderItems"}:
        related = "What was the net revenue by month in 2025?"
    elif "Employees" in tables:
        related = "What is the average salary by department?"
    elif "Customers" in tables:
        related = "How many customers are in each segment?"
    else:
        related = "Which products are low on stock?"
    out.append({"kind": "related", "question": related})
    return out


def _plan_summary(grounded: dict) -> dict:
    return {
        "restated_request": grounded.get("restated_request"),
        "tables": grounded.get("tables"),
        "filters": [f"{f['table']}.{f['column']} {f['operator']} {f.get('stored_values')}"
                    for f in grounded.get("filters") or []],
        "group_by": grounded.get("group_by"),
        "metrics": [m["name"] for m in grounded.get("metrics") or []],
    }


def _result_summary(execution: dict | None) -> str:
    if not execution:
        return "not executed"
    if execution.get("error"):
        return "the query failed to run"
    return f"{execution.get('total_rows') or execution['row_count']} rows with columns {execution['columns']}"
