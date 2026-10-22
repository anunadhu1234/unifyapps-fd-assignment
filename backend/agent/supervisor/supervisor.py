"""Supervisor — builds the LangGraph workflow and is the single entry point for every request.

    receive_request ─► intent_detection ─► scope_validation ─┬─► return_response   (refusal)
                                                              ├─► ask_clarification (needs the SQL pasted)
                                                              ├─► schema_answer     (questions about the schema)
                                                              └─► schema_retrieval
    schema_retrieval ─┬─► query_planner ─► plan_grounding ─┬─► ask_clarification
                      │                                    └─► sql_generation ─► sql_validation
                      └─► sql_validation (user-supplied SQL: optimize / debug / explain)

    sql_validation ─┬─ valid ───► [sql_debugging once, for debug requests] ─► sql_optimization
                    │                                                        ─► execute_query
                    │                                                        ─► generate_explanation ┐ parallel
                    │                                                        ─► suggest_follow_ups   ┘ fan-out
                    ├─ invalid, user SQL ─► sql_debugging ─► sql_validation
                    ├─ invalid, attempts left ─► sql_repair ─► sql_validation      (self-correction loop)
                    └─ invalid, budget spent ─► return_response (error with findings)

    every terminal node ─► return_response ─► END

Conversation memory is LangGraph checkpointing: one thread per chat, so
follow-ups see the previous plan and SQL.
"""

from __future__ import annotations

import sqlite3
import uuid
from collections.abc import Iterator
from pathlib import Path

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from agent.exec.execute_query import execute_query
from agent.exec.sql_debugging import sql_debugging
from agent.exec.sql_generation import sql_generation
from agent.exec.sql_optimization import sql_optimization
from agent.exec.sql_repair import sql_repair
from agent.guardrails.sql_validation import sql_validation
from agent.intent.intent_detection import intent_detection
from agent.intent.receive_request import receive_request
from agent.intent.scope_validation import scope_validation
from agent.narrative.ask_clarification import ask_clarification
from agent.narrative.generate_explanation import generate_explanation
from agent.narrative.return_response import return_response
from agent.narrative.schema_answer import schema_answer
from agent.narrative.suggest_follow_ups import suggest_follow_ups
from agent.planner.plan_grounding import plan_grounding
from agent.planner.query_planner import query_planner
from agent.retrieval.schema_retrieval import schema_retrieval
from agent.supervisor import routing
from agent.supervisor.dependencies import AgentDeps, build_deps
from agent.supervisor.state import AgentState
from agent.supervisor.trace import traced

NODES = {
    "receive_request": receive_request,
    "intent_detection": intent_detection,
    "scope_validation": scope_validation,
    "schema_retrieval": schema_retrieval,
    "query_planner": query_planner,
    "plan_grounding": plan_grounding,
    "sql_generation": sql_generation,
    "sql_validation": sql_validation,
    "sql_repair": sql_repair,
    "sql_debugging": sql_debugging,
    "sql_optimization": sql_optimization,
    "execute_query": execute_query,
    "generate_explanation": generate_explanation,
    "suggest_follow_ups": suggest_follow_ups,
    "ask_clarification": ask_clarification,
    "schema_answer": schema_answer,
    "return_response": return_response,
}

# Nodes whose text output is streamed token by token to the UI.
STREAMED_NODES = {"generate_explanation", "schema_answer"}


def build_graph(deps: AgentDeps, checkpointer: BaseCheckpointSaver | None = None):
    g = StateGraph(AgentState)
    for name, fn in NODES.items():
        g.add_node(name, traced(name, fn, deps))

    R = routing.RESPOND
    g.add_edge(START, "receive_request")
    g.add_conditional_edges("receive_request", routing.after_receive_request, ["intent_detection", R])
    g.add_conditional_edges("intent_detection", routing.after_intent_detection, ["scope_validation", R])
    g.add_conditional_edges("scope_validation", routing.after_scope_validation,
                            ["ask_clarification", "schema_answer", "schema_retrieval", R])
    g.add_conditional_edges("schema_retrieval", routing.after_schema_retrieval, ["query_planner", "sql_validation", R])
    g.add_conditional_edges("query_planner", routing.after_query_planner, ["plan_grounding", R])
    g.add_conditional_edges("plan_grounding", routing.after_plan_grounding, ["ask_clarification", "sql_generation", R])
    g.add_conditional_edges("sql_generation", routing.after_sql_generation, ["sql_validation", R])
    g.add_conditional_edges(
        "sql_validation", routing.make_after_sql_validation(deps.settings.max_sql_fix_attempts),
        ["sql_debugging", "sql_optimization", "execute_query", "sql_repair", R])
    g.add_conditional_edges("sql_repair", routing.after_sql_repair, ["sql_validation", R])
    g.add_conditional_edges("sql_debugging", routing.after_sql_debugging, ["sql_validation", R])
    g.add_conditional_edges("sql_optimization", routing.after_sql_optimization, ["execute_query", R])
    g.add_conditional_edges("execute_query", routing.after_execute_query,
                            ["generate_explanation", "suggest_follow_ups", R])
    for name in ("generate_explanation", "suggest_follow_ups", "ask_clarification", "schema_answer"):
        g.add_edge(name, R)
    g.add_edge(R, END)
    return g.compile(checkpointer=checkpointer or InMemorySaver())


def sqlite_checkpointer(path: Path) -> BaseCheckpointSaver:
    from langgraph.checkpoint.sqlite import SqliteSaver

    path.parent.mkdir(parents=True, exist_ok=True)
    return SqliteSaver(sqlite3.connect(path, check_same_thread=False))


class SQLAgent:
    """The facade the API uses: run a turn, stream a turn, read a thread's history."""

    def __init__(self, deps: AgentDeps | None = None, checkpointer: BaseCheckpointSaver | None = None):
        self.deps = deps or build_deps()
        self.graph = build_graph(self.deps, checkpointer)

    @staticmethod
    def _input(question: str, options: dict | None, request_id: str | None) -> dict:
        return {"question": question, "options": options or {}, "request_id": request_id or uuid.uuid4().hex}

    @staticmethod
    def _config(thread_id: str) -> dict:
        return {"configurable": {"thread_id": thread_id}, "recursion_limit": 40}

    def run(self, question: str, *, thread_id: str, options: dict | None = None,
            request_id: str | None = None) -> dict:
        final = self.graph.invoke(self._input(question, options, request_id), self._config(thread_id))
        return final["response"]

    def stream(self, question: str, *, thread_id: str, options: dict | None = None,
               request_id: str | None = None) -> Iterator[dict]:
        """Yield UI events: one per finished node, explanation tokens as they arrive, then the response."""
        response = None
        for mode, chunk in self.graph.stream(self._input(question, options, request_id),
                                             self._config(thread_id),
                                             stream_mode=["updates", "messages"]):
            if mode == "messages":
                message, meta = chunk
                text = getattr(message, "text", None)
                if meta.get("langgraph_node") in STREAMED_NODES and isinstance(text, str) and text:
                    yield {"event": "token", "node": meta["langgraph_node"], "text": text}
                continue
            for node, update in chunk.items():
                if not isinstance(update, dict):
                    continue
                event = next((e for e in update.get("trace") or [] if isinstance(e, dict) and e.get("node")), None)
                yield {"event": "node", "node": node, "ok": (event or {}).get("ok", True),
                       "ms": (event or {}).get("ms"), "detail": _public_detail(node, event)}
                if node == "return_response":
                    response = update.get("response")
        if response is not None:
            yield {"event": "response", "data": response}

    def history(self, thread_id: str) -> list[dict]:
        snapshot = self.graph.get_state(self._config(thread_id))
        return (snapshot.values or {}).get("history", []) if snapshot else []


_PUBLIC_DETAIL = {
    "intent_detection": ("intent",),
    "schema_retrieval": ("tables",),
    "plan_grounding": ("mappings",),
    "sql_validation": ("ok", "errors", "attempt"),
    "sql_repair": ("attempt",),
    "sql_optimization": ("cost",),
    "execute_query": ("rows", "skipped"),
}


def _public_detail(node: str, event: dict | None) -> dict:
    """The few trace fields shown in the normal-mode progress indicator."""
    if not event:
        return {}
    return {k: event[k] for k in _PUBLIC_DETAIL.get(node, ()) if k in event}
