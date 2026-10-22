"""Node: sql_optimization — make validated SQL readable and fast, and estimate its cost.

Generated SQL (deterministic, no LLM):
  * pretty-format it (re-checked with SQLite so formatting can never break it);
  * estimate cost from EXPLAIN QUERY PLAN and recommend indexes for full scans.

User-supplied SQL ("optimize this", requirement 3.4 — one main-model call):
  * the model proposes a rewrite (readability, removed joins, cheaper predicates)
    and index recommendations, seeing SQLite's actual plan and the existing indexes;
  * the rewrite must pass the validator AND return exactly the same rows as the
    original when both are executed — otherwise it is rejected and the original kept;
  * cost is estimated before and after.
"""

from __future__ import annotations

from langchain_core.runnables import RunnableConfig

from agent.exec.cost_estimator import CostEstimate
from agent.exec.sqlite_runner import ReadOnlyDatabase
from agent.guardrails.sql_validator import format_sql, strip_sql
from agent.llm_schemas import OptimizationResult
from agent.supervisor.dependencies import AgentDeps
from agent.supervisor.state import AgentState
from prompt_library import get_prompt

COMPARE_ROWS = 5000


def sql_optimization(state: AgentState, deps: AgentDeps, config: RunnableConfig) -> dict:
    sql = state["sql"]
    before = _estimate(deps, sql)
    if state["intent"]["intent"] == "optimize_sql":
        return _optimize_user_sql(state, deps, config, sql, before)

    formatted = format_sql(sql)
    if formatted != sql and not _compiles(deps.db, formatted):
        formatted = sql
    recommendations = [r.__dict__ for r in before.recommendations] if before else []
    return {
        "sql": formatted,
        "optimized": True,
        "cost": before.as_dict() if before else None,
        "optimization": {"mode": "generated", "index_recommendations": recommendations},
        "_trace": {"mode": "format+cost", "cost": before.level if before else None,
                   "index_recommendations": len(recommendations)},
    }


def _optimize_user_sql(state, deps: AgentDeps, config, sql: str, before: CostEstimate | None) -> dict:
    messages = get_prompt(
        "sql_optimization",
        question=state["standalone_question"],
        schema_context=deps.kb.schema_context(state["retrieval"]["tables"], include_indexes=True),
        sql=sql,
        plan_steps=before.plan if before else [],
        cost_level=before.level if before else "unknown",
        index_candidates=[f"{r.ddl} — {r.reason}" for r in (before.recommendations if before else [])],
    )
    result, call = deps.llm.structured("sql_optimization", messages, OptimizationResult, config=config)
    candidate = strip_sql(result.optimized_sql)

    accepted, rejected_reason = True, None
    report = deps.validator.validate(candidate)
    if not report.ok:
        accepted, rejected_reason = False, "the rewrite did not pass validation: " + "; ".join(
            f.message for f in report.errors)
    else:
        same, note = results_match(deps.db, sql, candidate)
        if not same:
            accepted, rejected_reason = False, f"the rewrite returned different results ({note})"
    final = format_sql(candidate) if accepted else format_sql(sql)
    after = _estimate(deps, final) if accepted else before

    index_recs = {r.ddl: {"ddl": r.ddl, "reason": r.reason} for r in (before.recommendations if before else [])}
    for advice in result.index_recommendations:
        index_recs.setdefault(advice.ddl.strip().rstrip(";") + ";", {"ddl": advice.ddl, "reason": advice.reason})
    return {
        "sql": final,
        "sql_origin": "optimized" if accepted else state.get("sql_origin"),
        "optimized": True,
        "cost": after.as_dict() if after else None,
        "optimization": {
            "mode": "user",
            "original_sql": sql,
            "optimized_sql": final,
            "accepted": accepted,
            "rejected_reason": rejected_reason,
            "already_optimal": result.already_optimal,
            "summary": result.summary,
            "changes": [c.model_dump() for c in result.changes],
            "removed_joins": result.removed_joins,
            "index_recommendations": list(index_recs.values()),
            "cost_before": before.as_dict() if before else None,
            "cost_after": after.as_dict() if after else None,
        },
        "llm_calls": [call.as_dict()],
        "_trace": {"mode": "rewrite", "accepted": accepted, "rejected_reason": rejected_reason,
                   "cost_before": before.level if before else None, "cost_after": after.level if after else None},
    }


def results_match(db: ReadOnlyDatabase, original: str, rewrite: str) -> tuple[bool, str]:
    """Run both queries and compare their results (ordered if the original sorts, as a multiset otherwise)."""
    try:
        a = db.execute(original, max_rows=COMPARE_ROWS)
        b = db.execute(rewrite, max_rows=COMPARE_ROWS)
    except Exception as exc:
        return False, f"could not execute: {exc}"
    if len(a.columns) != len(b.columns):
        return False, f"{len(a.columns)} vs {len(b.columns)} columns"
    if a.row_count != b.row_count:
        return False, f"{a.row_count} vs {b.row_count} rows"
    norm = [_normalize_row(r) for r in a.rows], [_normalize_row(r) for r in b.rows]
    ordered = "order by" in original.lower()
    same = norm[0] == norm[1] if ordered else sorted(norm[0], key=repr) == sorted(norm[1], key=repr)
    return same, "identical" if same else "row values differ"


def _normalize_row(row: list) -> tuple:
    return tuple(round(v, 6) if isinstance(v, float) else v for v in row)


def _estimate(deps: AgentDeps, sql: str) -> CostEstimate | None:
    try:
        return deps.cost.estimate(sql)
    except Exception:
        return None


def _compiles(db: ReadOnlyDatabase, sql: str) -> bool:
    try:
        db.explain(sql)
        return True
    except Exception:
        return False
