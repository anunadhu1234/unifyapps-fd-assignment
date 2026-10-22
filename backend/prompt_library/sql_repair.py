"""Prompt for the `sql_repair` node (main model, structured output: SQLDraft).

Receives the validator's findings verbatim — each with a code, a precise message
and usually a fix hint — so the model repairs exactly what is wrong.
"""

from langchain_core.messages import HumanMessage, SystemMessage

from prompt_library._shared import SECURITY_RULES, SQLITE_RULES, as_json, user_block

NAME = "sql_repair"
VERSION = "1.0"

SYSTEM = """\
You repair SQLite queries that failed validation. Fix EVERY finding listed, keep everything else exactly as it was, \
and keep the query answering the same request. Follow each finding's "Fix:" hint — the hints come from the real \
schema and the values actually stored in the database.

Never "fix" a finding by inventing a table, column or value that is not in SCHEMA. If the request truly cannot be \
answered with this schema, return the closest valid query and explain the gap in notes.

{sqlite_rules}

{security}
"""

USER = """\
SCHEMA:
{schema_context}
{plan}
REQUEST:
{question}

FAILED SQL (attempt {attempt}):
{sql}

VALIDATION FINDINGS:
{findings}
"""


def build(*, question: str, schema_context: str, sql: str, findings: str, attempt: int,
          plan: dict | None = None, **_):
    plan_text = f"\nGROUNDED PLAN:\n{as_json(plan)}\n" if plan else ""
    return [
        SystemMessage(SYSTEM.format(sqlite_rules=SQLITE_RULES, security=SECURITY_RULES)),
        HumanMessage(USER.format(schema_context=schema_context, plan=plan_text, question=user_block(question),
                                 sql=sql, findings=findings, attempt=attempt)),
    ]
