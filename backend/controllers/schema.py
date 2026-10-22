"""Schema controller — what the database contains, for the schema explorer and suggested questions."""

from __future__ import annotations

from controllers.context import AppServices

SUGGESTED_QUESTIONS = [
    "Show all employees hired after January 2024.",
    "What was the net revenue by product category in 2025?",
    "Who are our top 10 customers by revenue?",
    "Which products have never been ordered?",
    "Which sales reps booked the most revenue from corporate customers in 2025?",
    "What is the return rate by product category?",
]


def schema_summary(svc: AppServices) -> dict:
    kb = svc.agent.deps.kb
    tables = []
    for name, info in kb.tables.items():
        tables.append({
            "name": name,
            "description": info["description"],
            "row_count": info["row_count"],
            "columns": [{"name": c, "type": col["type"], "role": col["role"], "description": col["description"],
                         "references": col.get("references")} for c, col in info["columns"].items()],
        })
    return {
        "database": kb.meta["domain"],
        "dialect": kb.meta["dialect"],
        "as_of_date": kb.meta["as_of_date"],
        "tables": tables,
        "relationships": [{"join": r["join_condition"], "description": r["description"]} for r in kb.relationships],
        "metrics": [{"name": m["name"], "description": m["description"]} for m in kb.metrics.values()],
        "suggested_questions": SUGGESTED_QUESTIONS,
    }
