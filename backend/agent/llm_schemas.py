"""Structured-output contracts — the shape every LLM call must return.

Nodes never parse free text from a model (except the two streamed prose nodes,
explanation and schema answer): each call is bound to one of these Pydantic
models through function calling, so a malformed answer fails loudly.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Intent = Literal["generate_sql", "modify_previous", "optimize_sql", "debug_sql", "explain_sql",
                 "schema_question", "destructive", "out_of_scope"]


class IntentResult(BaseModel):
    intent: Intent
    standalone_question: str = Field(description="The request rewritten as one complete, self-contained question.")
    user_sql: str | None = Field(None, description="SQL contained in the message, copied exactly; null if none.")
    reason: str = Field(description="One short sentence explaining the classification.")


# ── query plan ───────────────────────────────────────────────────────────────


class SelectItem(BaseModel):
    kind: Literal["column", "aggregate", "metric", "expression", "all_columns"]
    table: str | None = None
    column: str | None = None
    aggregate: Literal["COUNT", "COUNT_DISTINCT", "SUM", "AVG", "MIN", "MAX"] | None = None
    metric: str | None = Field(None, description="Exact business metric name, for kind = metric.")
    expression: str | None = Field(None, description="Plain-words description of a derived value, e.g. "
                                                     "'year of Orders.OrderDate'.")
    alias: str | None = None


class PlanFilter(BaseModel):
    table: str
    column: str
    operator: Literal["=", "!=", ">", ">=", "<", "<=", "IN", "NOT IN", "LIKE", "NOT LIKE", "BETWEEN",
                      "IS NULL", "IS NOT NULL"]
    values: list[str] = Field(default_factory=list, description="Values as the user said them; numbers and ISO "
                                                                "dates as strings.")


class PlanOrder(BaseModel):
    expression: str = Field(description="Output alias or Table.Column to sort by.")
    direction: Literal["ASC", "DESC"] = "ASC"


class QueryPlan(BaseModel):
    restated_request: str = Field(description="What the query will return, in one plain sentence.")
    tables: list[str]
    select: list[SelectItem]
    filters: list[PlanFilter] = Field(default_factory=list)
    group_by: list[str] = Field(default_factory=list, description="Table.Column or derived expressions.")
    having: list[str] = Field(default_factory=list, description="Conditions on aggregates, in words.")
    order_by: list[PlanOrder] = Field(default_factory=list)
    limit: int | None = None
    distinct: bool = False
    include_unmatched: bool = Field(False, description="True when rows without matches must be kept "
                                                       "(LEFT JOIN), e.g. customers with no orders.")
    relationship_notes: list[str] = Field(default_factory=list, description="Which link was chosen when two "
                                                                            "tables connect in more than one way.")
    assumptions: list[str] = Field(default_factory=list)
    needs_clarification: bool = False
    clarification_question: str | None = None
    clarification_options: list[str] = Field(default_factory=list)


# ── SQL producing steps ──────────────────────────────────────────────────────


class SQLDraft(BaseModel):
    sql: str = Field(description="One read-only SQLite SELECT statement.")
    notes: str | None = Field(None, description="Anything the reader should know about the query.")


class OptimizationChange(BaseModel):
    change: str
    reason: str


class IndexAdvice(BaseModel):
    ddl: str = Field(description="CREATE INDEX statement (advice only, never executed).")
    reason: str


class OptimizationResult(BaseModel):
    optimized_sql: str
    changes: list[OptimizationChange] = Field(default_factory=list)
    index_recommendations: list[IndexAdvice] = Field(default_factory=list)
    removed_joins: list[str] = Field(default_factory=list)
    already_optimal: bool = False
    summary: str


class FollowUp(BaseModel):
    kind: Literal["drill_down", "refine", "related"]
    question: str = Field(description="At most 12 words, in business language.")


class FollowUpSuggestions(BaseModel):
    suggestions: list[FollowUp] = Field(description="Exactly 3, one of each kind.")


class DebugIssue(BaseModel):
    problem: str
    why_incorrect: str


class DebugResult(BaseModel):
    issues: list[DebugIssue] = Field(default_factory=list)
    corrected_sql: str
    summary: str
