"""Prompt for the `generate_explanation` node (fast model, streamed markdown text).

Output format is fixed so the response can be split into the explanation panel:
the first paragraph is a one-sentence summary; then "- " bullets walk through the query.
"""

from langchain_core.messages import HumanMessage, SystemMessage

from prompt_library._shared import SECURITY_RULES, user_block

NAME = "generate_explanation"
VERSION = "1.1"

SYSTEM = """\
You explain SQL queries to business users who do not know SQL.

Write in this exact format:
<one sentence saying what the query returns, in business terms — e.g. "This query retrieves all employees whose \
hire date is on or after January 1, 2024.">

- <one bullet per meaningful part: which data it reads, how tables are connected, each filter, grouping, \
calculation, sorting and limit — in plain words, mentioning the real column names in backticks>

Rules: no headings, no SQL code blocks, at most 6 bullets. Only describe what the query DOES — never list things \
it does not do ("no joins", "no grouping", "no limit"). Mention stored-value mappings the user would not \
expect (e.g. "California is stored as the code `CA`"). Do not state numbers from the results unless they are given \
below. {mode_rules}

{security}
"""

MODE_RULES = {
    "generate": "",
    "optimize": "This query is the OPTIMIZED version of the user's query: summarise what changed and why it is faster "
                "or clearer, in the bullets.",
    "debug": "This query is the CORRECTED version of the user's query: the bullets should explain what was wrong and "
             "what was fixed, then what the corrected query does.",
    "explain": "",
}

USER = """\
REQUEST:
{question}

SQL:
{sql}
{context}"""


def build(*, question: str, sql: str, mode: str = "generate", assumptions: list[str] | None = None,
          mappings: list[str] | None = None, changes: list[str] | None = None, result_note: str | None = None, **_):
    context = []
    if mappings:
        context.append("VALUE MAPPINGS APPLIED:\n" + "\n".join(f"- {m}" for m in mappings))
    if assumptions:
        context.append("ASSUMPTIONS MADE:\n" + "\n".join(f"- {a}" for a in assumptions))
    if changes:
        context.append("CHANGES / ISSUES:\n" + "\n".join(f"- {c}" for c in changes))
    if result_note:
        context.append(f"RESULT: {result_note}")
    return [
        SystemMessage(SYSTEM.format(mode_rules=MODE_RULES.get(mode, ""), security=SECURITY_RULES)),
        HumanMessage(USER.format(question=user_block(question), sql=sql,
                                 context=("\n" + "\n\n".join(context) + "\n") if context else "")),
    ]
