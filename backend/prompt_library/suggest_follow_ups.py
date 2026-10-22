"""Prompt for the `suggest_follow_ups` node (fast model, structured output: FollowUpSuggestions).

Produces exactly three "Dive deeper" questions grounded in what the answer
actually used — tables, filters, grouping, metrics and the result columns — so
every suggestion is answerable from this schema. Two are phrased as follow-ups
that modify the current query (exercising conversation context); one opens a
related question.
"""

from langchain_core.messages import HumanMessage, SystemMessage

from prompt_library._shared import SECURITY_RULES, as_json, user_block

NAME = "suggest_follow_ups"
VERSION = "1.0"

SYSTEM = """\
You suggest follow-up questions for a business user who just got an answer from a SQL assistant.

Return EXACTLY 3 suggestions, each a different kind:
1. drill_down — break the SAME result down by another dimension that exists in SCHEMA and is not already used \
(e.g. by customer segment, product category, state, channel, department, month or year). Phrase it as a follow-up \
to the current query: "Break this down by customer segment".
2. refine — narrow or shift the SAME query: an extra filter on a real column/value, or a different time period \
("Only for 2025", "Just the corporate customers", "Compare with the previous year"). Phrase it as a follow-up.
3. related — a new, complete question about a closely related measure or entity in SCHEMA (a business metric from \
BUSINESS METRICS, or a table joined to what the user asked about). Phrase it as a standalone question.

RULES
- Every suggestion must be answerable with the tables, columns, values and metrics listed — never invent a column, \
value or metric. Use the business wording a user would use (not column names in CamelCase).
- Keep the user's subject: if they asked about revenue, stay with revenue for drill_down and refine.
- Do not repeat the user's question or anything already asked in this conversation.
- Each suggestion is at most 12 words.

{security}
"""

USER = """\
SCHEMA:
{schema_context}

WHAT THE ANSWER USED:
{plan}

RESULT: {result}

ALREADY ASKED IN THIS CONVERSATION:
{asked}

THE USER'S QUESTION:
{question}
"""


def build(*, question: str, schema_context: str, plan: dict, result: str, asked: list[str], **_):
    return [
        SystemMessage(SYSTEM.format(security=SECURITY_RULES)),
        HumanMessage(USER.format(schema_context=schema_context, plan=as_json(plan), result=result,
                                 asked="\n".join(f"- {q}" for q in asked) or "(nothing else)",
                                 question=user_block(question))),
    ]
