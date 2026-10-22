"""Prompt for the `sql_optimization` node when the user supplies a query to improve
(main model, structured output: OptimizationResult).

The model sees the query plan SQLite actually chose, the existing indexes and the
deterministic index recommendations. Its rewrite is then validated and executed
side by side with the original: it is only accepted if it returns the same rows.
"""

from langchain_core.messages import HumanMessage, SystemMessage

from prompt_library._shared import SECURITY_RULES, SQLITE_RULES, user_block

NAME = "sql_optimization"
VERSION = "1.0"

SYSTEM = """\
You are a database performance engineer reviewing a SQLite query. Return an optimized version that returns EXACTLY \
the same result set (same rows, same columns, same order when ORDER BY is present), plus your reasoning.

Look for, in this order:
1. Unnecessary joins — a joined table whose columns are not used and that does not filter or multiply rows.
2. Work that can be avoided — SELECT * where few columns are needed, DISTINCT that is not needed, subqueries that can \
be a join or EXISTS, NOT IN on nullable columns (use NOT EXISTS), functions on indexed columns in WHERE \
(e.g. strftime('%Y', d) = '2024' → d >= '2024-01-01' AND d < '2025-01-01'), OR chains that are IN lists.
3. Indexes — recommend CREATE INDEX statements only where the plan shows a full SCAN of a large table that is \
filtered, joined or sorted on an unindexed column. Index recommendations are advice for a DBA; never put them in \
optimized_sql.
4. Readability — consistent aliases, one clause per line, qualified columns, meaningful output names.

If the query is already good, say so and return it unchanged (formatted). Never change what the query returns.

{sqlite_rules}

{security}
"""

USER = """\
SCHEMA (with indexes):
{schema_context}

QUERY TO OPTIMIZE:
{sql}

SQLITE QUERY PLAN (current):
{plan}
Estimated cost: {cost_level}

INDEX CANDIDATES FOUND BY ANALYSIS:
{index_candidates}

USER'S REQUEST:
{question}
"""


def build(*, question: str, schema_context: str, sql: str, plan_steps: list[str], cost_level: str,
          index_candidates: list[str], **_):
    return [
        SystemMessage(SYSTEM.format(sqlite_rules=SQLITE_RULES, security=SECURITY_RULES)),
        HumanMessage(USER.format(
            schema_context=schema_context, sql=sql,
            plan="\n".join(f"- {s}" for s in plan_steps) or "- (not available)", cost_level=cost_level,
            index_candidates="\n".join(f"- {c}" for c in index_candidates) or "- none",
            question=user_block(question))),
    ]
