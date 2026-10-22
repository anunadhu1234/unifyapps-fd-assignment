"""Prompt library — the single registry of every LLM prompt the agent uses.

Each prompt lives in its own module named after the LangGraph node that uses it
and exports NAME, VERSION and build(**vars) -> list[BaseMessage]. Callers do:

    from prompt_library import get_prompt
    messages = get_prompt("sql_generation", question=..., schema_context=..., plan=..., as_of=...)

The library owns only prompt TEXT: model choice, calling, parsing and retries
belong to the nodes and the LLM gateway.
"""

from __future__ import annotations

from langchain_core.messages import BaseMessage

from prompt_library import (
    generate_explanation,
    intent_detection,
    query_planner,
    schema_answer,
    sql_debugging,
    sql_generation,
    sql_optimization,
    sql_repair,
    suggest_follow_ups,
)

REGISTRY = {m.NAME: m for m in (
    intent_detection, query_planner, sql_generation, sql_repair,
    sql_optimization, sql_debugging, generate_explanation, suggest_follow_ups, schema_answer,
)}


def get_prompt(name: str, **variables) -> list[BaseMessage]:
    if name not in REGISTRY:
        raise KeyError(f"unknown prompt {name!r}; known prompts: {', '.join(REGISTRY)}")
    return REGISTRY[name].build(**variables)


def prompt_version(name: str) -> str:
    return REGISTRY[name].VERSION


def list_prompts() -> list[str]:
    return list(REGISTRY)
