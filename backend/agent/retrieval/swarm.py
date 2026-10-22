"""Retrieval swarm — independent retrievers run in parallel, then merged.

Mirrors the intelligence-assistant "knowledge swarm": each retriever looks at the
request from one angle, and the merge step builds the single schema context the
planner and SQL writer see.

    schema retriever     tables / columns the request mentions (knowledge-graph phrase index)
    value retriever      stored values the request refers to ("California" → 'CA')
    knowledge retriever  business metrics and glossary terms with validated SQL
    example retriever    the most similar solved requests (few-shot examples)
    sql retriever        tables referenced by SQL the user pasted
    memory retriever     tables of the previous plan, for follow-ups

The merge keeps every table any retriever needed, then adds the bridge tables
the foreign-key graph requires to connect them.
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor

import sqlglot
from sqlglot import exp

from agent.knowledge.kb_resolver import KnowledgeBase, Retrieval

_STOP = {"the", "and", "for", "all", "with", "from", "that", "this", "show", "list", "give", "what", "which", "who",
         "how", "many", "much", "are", "was", "were", "have", "has", "per", "each", "into", "their", "they", "them",
         "our", "out", "get", "find", "me", "of", "in", "on", "by", "to", "a", "an", "is", "do", "did"}


def _tokens(text: str) -> set[str]:
    return {w.rstrip("s") for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 2 and w not in _STOP}


def schema_retriever(kb: KnowledgeBase, question: str) -> Retrieval:
    return kb.relevant_tables(question)


def example_retriever(examples: list[dict], question: str, k: int = 3) -> list[dict]:
    query = _tokens(question)
    if not query:
        return []
    scored = []
    for ex in examples:
        words = _tokens(ex["question"])
        overlap = len(query & words) / len(query | words) if words else 0.0
        if overlap > 0.12:
            scored.append((overlap, ex))
    scored.sort(key=lambda s: -s[0])
    return [{"question": e["question"], "sql": e["sql"]} for _, e in scored[:k]]


def sql_retriever(kb: KnowledgeBase, sql: str | None) -> list[str]:
    if not sql:
        return []
    try:
        names = {t.name.lower() for t in sqlglot.parse_one(sql, read="sqlite").find_all(exp.Table)}
    except Exception:
        names = {w.lower() for w in re.findall(r"(?i)\b(?:from|join)\s+([A-Za-z_]\w*)", sql)}
    return [t for t in kb.tables if t.lower() in names]


def schema_context_for(kb: KnowledgeBase, retrieval: dict, grounded: dict | None) -> str:
    """Schema text for SQL writing: every table the grounded plan uses (planning may add tables
    retrieval did not detail — e.g. OrderItems for "never ordered") plus what retrieval found."""
    tables = list(dict.fromkeys([*(grounded or {}).get("tables", []), *retrieval.get("tables", [])]))
    metric_names = set(retrieval.get("metrics", [])) | {m["name"] for m in (grounded or {}).get("metrics", [])}
    metrics = [m for m in kb.metrics.values() if m["name"] in metric_names]
    glossary = [g for g in kb.glossary.values() if g["term"] in set(retrieval.get("glossary", []))]
    return kb.schema_context(tables, metrics=metrics, glossary=glossary)


def run_swarm(kb: KnowledgeBase, examples: list[dict], question: str, *, user_sql: str | None = None,
              previous_tables: list[str] | None = None, include_indexes: bool = False) -> dict:
    with ThreadPoolExecutor(max_workers=3, thread_name_prefix="swarm") as pool:
        f_schema = pool.submit(schema_retriever, kb, question)
        f_examples = pool.submit(example_retriever, examples, question)
        f_sql = pool.submit(sql_retriever, kb, user_sql)
        found, similar, sql_tables = f_schema.result(), f_examples.result(), f_sql.result()

    sources = {
        "schema": found.tables,
        "sql": sql_tables,
        "memory": list(previous_tables or []),
    }
    # Pasted SQL defines the scope exactly; otherwise take what the question and memory point to.
    wanted = sql_tables or list(dict.fromkeys(found.tables + list(previous_tables or [])))
    mentioned = {f"{e['table']}.{e['column']}" for m in found.term_matches for e in m.entries if e["kind"] == "column"}
    tables, joins = kb.connect(wanted, mentioned)

    context = kb.schema_context(tables, metrics=found.metrics, glossary=found.glossary,
                                include_indexes=include_indexes)
    return {
        "tables": tables,
        "joins": joins,
        "ambiguous_links": kb.ambiguous_links(tables),
        "sources": sources,
        "table_scores": {t: s for t, s in found.scores.items() if s},
        "terms": [{"text": m.text, "refers_to": list(m.entries)} for m in found.term_matches],
        "values": [{"text": m.text, "refers_to": list(m.entries)} for m in found.value_matches],
        "metrics": [m["name"] for m in found.metrics],
        "glossary": [g["term"] for g in found.glossary],
        "examples": similar,
        "schema_context": context,
    }
