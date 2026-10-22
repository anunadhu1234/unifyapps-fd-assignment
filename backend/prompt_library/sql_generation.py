"""Prompt for the `sql_generation` node (fast or main model by plan complexity; structured output: SQLDraft)."""

from langchain_core.messages import HumanMessage, SystemMessage

from prompt_library._shared import SECURITY_RULES, SQLITE_RULES, as_json, user_block

NAME = "sql_generation"
VERSION = "1.0"

SYSTEM = """\
You are an expert SQLite developer. Write ONE read-only SQLite query that implements the GROUNDED PLAN exactly.

RULES
1. One statement only: SELECT, optionally with WITH. No comments, no trailing explanation.
2. Use only the tables and columns in SCHEMA. Join only with the JOINS listed in the plan (they are the real \
foreign keys). Give each table a short alias and qualify every column with it.
3. Filters: use plan.filters[].stored_values exactly — they are already mapped to the values stored in the database \
(e.g. 'CA', 'Cancelled'). Use the operator given (IN for lists).
4. Metrics: implement plan metrics with the provided expression and default filters, verbatim.
5. Output columns: readable aliases in snake_case (total_revenue, order_count). Round money to 2 decimals with \
ROUND(x, 2) and percentages to 1 decimal.
6. Rankings and "top N": ORDER BY the measure DESC, then LIMIT. Listings: a sensible ORDER BY (date or name). \
Do not add a LIMIT the plan does not ask for (results are capped separately).
7. Use LEFT JOIN when the plan includes rows without matches (e.g. customers with no orders); count them with \
COUNT(child.id), not COUNT(*).
8. When PREVIOUS SQL is given for a follow-up, start from it and change only what the plan changed.
9. Use the snapshot date '{as_of}' instead of date('now') for relative dates.

{sqlite_rules}

{security}
"""

USER = """\
SCHEMA:
{schema_context}

GROUNDED PLAN:
{plan}
{previous}{examples}
REQUEST:
{question}
"""


def build(*, question: str, schema_context: str, plan: dict, as_of: str, previous_sql: str | None = None,
          examples: list[dict] | None = None, **_):
    previous = f"\nPREVIOUS SQL (follow-up — modify this):\n{previous_sql}\n" if previous_sql else ""
    examples_text = ""
    if examples:
        examples_text = "\nSIMILAR SOLVED REQUESTS:\n" + "\n".join(
            f"- {e['question']}\n  {' '.join(e['sql'].split())}" for e in examples) + "\n"
    return [
        SystemMessage(SYSTEM.format(as_of=as_of, sqlite_rules=SQLITE_RULES, security=SECURITY_RULES)),
        HumanMessage(USER.format(schema_context=schema_context, plan=as_json(plan), previous=previous,
                                 examples=examples_text, question=user_block(question))),
    ]
