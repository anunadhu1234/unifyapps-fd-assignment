"""Dev controller — internals for developers: run history, model routing, prompts, knowledge graph."""

from __future__ import annotations

from agent.llm_client import STEP_TIERS
from controllers.context import AppServices
from prompt_library import REGISTRY


def llm_config(svc: AppServices) -> dict:
    s = svc.agent.deps.settings
    return {
        "models": {"fast": s.llm_model_fast, "main": s.llm_model_main},
        "provider": "aws-bedrock",
        "region": s.aws_region,
        "pinned_routes": s.model_routes,
        "step_tiers": STEP_TIERS,
        "sql_fast_model_max_complexity": s.sql_fast_model_max_complexity,
        "max_sql_fix_attempts": s.max_sql_fix_attempts,
    }


def prompts() -> dict:
    return {"prompts": [
        {"name": name, "version": module.VERSION, "system": getattr(module, "SYSTEM", ""),
         "user": getattr(module, "USER", "")}
        for name, module in REGISTRY.items()
    ]}


def knowledge_graph(svc: AppServices) -> dict:
    graph = svc.agent.deps.kb.graph
    return {"meta": graph["meta"], "nodes": graph["nodes"], "edges": graph["edges"],
            "metrics": graph["metrics"], "glossary": graph["glossary"]}


def run_history(svc: AppServices, owner: str, limit: int = 100) -> dict:
    """One row per question this developer ran: outcome, LLM usage and timing (from the stored trace)."""
    runs = []
    for run in svc.threads.list_runs(owner, limit):
        r = run["response"]
        dev_info = r.get("dev") or {}
        totals = dev_info.get("totals") or {}
        calls = dev_info.get("llm_calls") or []
        runs.append({
            "request_id": run["request_id"],
            "thread_id": run["thread_id"],
            "thread_title": run["thread_title"],
            "question": run["question"],
            "created_at": run["created_at"],
            "type": r.get("type"),
            "intent": r.get("intent"),
            "rows": (r.get("results") or {}).get("total_rows") if r.get("results") else None,
            "attempts": (r.get("validation") or {}).get("attempts"),
            "llm_calls": totals.get("llm_calls", len(calls)),
            "input_tokens": totals.get("input_tokens", 0),
            "output_tokens": totals.get("output_tokens", 0),
            "cost_usd": totals.get("cost_usd"),
            "llm_ms": totals.get("llm_ms", 0),
            "pipeline_ms": totals.get("pipeline_ms", 0),
            "models": sorted({c.get("served_by") or c.get("model") for c in calls if c.get("model")}),
        })
    summary = {
        "runs": len(runs),
        "input_tokens": sum(x["input_tokens"] for x in runs),
        "output_tokens": sum(x["output_tokens"] for x in runs),
        "llm_calls": sum(x["llm_calls"] for x in runs),
        "avg_pipeline_ms": int(sum(x["pipeline_ms"] for x in runs) / len(runs)) if runs else 0,
    }
    return {"runs": runs, "summary": summary}
