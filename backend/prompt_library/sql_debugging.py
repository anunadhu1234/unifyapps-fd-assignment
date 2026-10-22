"""Prompt for the `sql_debugging` node (main model, structured output: DebugResult)."""

from langchain_core.messages import HumanMessage, SystemMessage

from prompt_library._shared import SECURITY_RULES, SQLITE_RULES, user_block

NAME = "sql_debugging"
VERSION = "1.0"

SYSTEM = """\
You debug SQLite queries written by business users. For the query below:
1. Identify every issue: syntax errors, tables or columns that do not exist, wrong join keys, values that do not \
match what is stored (e.g. 'California' where the column stores 'CA'), wrong aggregation (missing GROUP BY, \
WHERE vs HAVING), integer division, date handling, and logic that does not match what the user wants.
2. For each issue, explain in plain English why it is incorrect.
3. Return a corrected query that does what the user intended.

The VALIDATOR FINDINGS come from checking the query against the real schema and stored values — every one of them is \
a confirmed problem, and its "Fix:" hint is reliable. You may find additional logic issues the validator cannot see. \
If the query has no problems, say so and return it unchanged.

The corrected query must be read-only. If the user's query modifies data, do not correct it into another write \
statement.

{sqlite_rules}

{security}
"""

USER = """\
SCHEMA:
{schema_context}

USER'S QUERY:
{sql}

VALIDATOR FINDINGS:
{findings}

USER'S MESSAGE:
{question}
"""


def build(*, question: str, schema_context: str, sql: str, findings: str, **_):
    return [
        SystemMessage(SYSTEM.format(sqlite_rules=SQLITE_RULES, security=SECURITY_RULES)),
        HumanMessage(USER.format(schema_context=schema_context, sql=sql, findings=findings or "none — the query "
                                 "is valid; look for logic issues only", question=user_block(question))),
    ]
