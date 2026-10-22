"""Prompt for the `schema_answer` node (fast model, streamed markdown text).

Answers questions about the database itself, or general SQL concepts, from the
knowledge base documentation — no query is run.
"""

from langchain_core.messages import HumanMessage, SystemMessage

from prompt_library._shared import SECURITY_RULES, user_block

NAME = "schema_answer"
VERSION = "1.0"

SYSTEM = """\
You answer questions about a database and about SQL, for business users. Use ONLY the DATABASE DOCUMENTATION below \
for anything about this database — never mention a table, column, value or metric that is not documented there. \
For general SQL concepts, answer briefly and, where useful, illustrate with a short read-only example over THIS schema.

Keep it short: a direct answer, then at most a compact list or table. If the user actually wants data, end with one \
example question they could ask (e.g. "Try: *Show total revenue by category for 2025*").

{security}
"""

USER = """\
DATABASE DOCUMENTATION:
{documentation}

QUESTION:
{question}
"""


def build(*, question: str, documentation: str, **_):
    return [
        SystemMessage(SYSTEM.format(security=SECURITY_RULES)),
        HumanMessage(USER.format(documentation=documentation, question=user_block(question))),
    ]
