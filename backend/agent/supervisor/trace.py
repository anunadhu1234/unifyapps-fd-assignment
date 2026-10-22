"""Node wrapper: timing, error capture and one trace event per node run.

Every node is a plain function `(state, deps, config) -> dict`. `traced` turns it
into a LangGraph node that

  * measures how long it ran,
  * appends {"node", "ms", "ok", ...summary} to state.trace — the node can add its
    own summary fields by returning them under the "_trace" key,
  * converts an exception into state.failure (the router then sends the turn to
    return_response with a friendly error) instead of crashing the graph,
  * keeps the LLMCall record of a failed model call so it still counts in cost.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

from langchain_core.runnables import RunnableConfig

from agent.llm_client import LLMCallFailed, LLMNotConfiguredError
from agent.supervisor.dependencies import AgentDeps
from agent.supervisor.state import RESET, AgentState

log = logging.getLogger("sql_agent")

NodeFn = Callable[[AgentState, AgentDeps, RunnableConfig], dict]


def traced(name: str, fn: NodeFn, deps: AgentDeps) -> Callable[[AgentState, RunnableConfig], dict]:
    def run(state: AgentState, config: RunnableConfig) -> dict:
        node_log = logging.getLogger(f"sql_agent.{name}")
        node_log.debug("▶ start")
        started = time.perf_counter()
        try:
            update = dict(fn(state, deps, config) or {})
            summary = update.pop("_trace", {})
            ok = True
        except LLMNotConfiguredError as exc:
            update = {"failure": {"node": name, "kind": "llm_not_configured", "message": str(exc)}}
            summary, ok = {}, False
        except LLMCallFailed as exc:
            log.warning("node %s: LLM call failed: %s", name, exc)
            update = {"failure": {"node": name, "kind": _llm_failure_kind(str(exc)), "message": str(exc)},
                      "llm_calls": [exc.call.as_dict()]}
            summary, ok = {}, False
        except Exception as exc:  # never let one node crash the whole turn
            log.exception("node %s failed", name)
            update = {"failure": {"node": name, "kind": "internal_error", "message": f"{type(exc).__name__}: {exc}"}}
            summary, ok = {}, False
        event = {"node": name, "ms": int((time.perf_counter() - started) * 1000), "ok": ok, **summary}
        if not ok:
            event["error"] = update["failure"]["message"][:300]
            node_log.error(f"✗ failed after {event['ms']} ms: {event['error']}")
        else:
            node_log.debug(f"✓ done in {event['ms']} ms")
        # A node that resets the trace (receive_request) still records its own event.
        update["trace"] = [RESET, event] if update.get("trace") is RESET else [event]
        return update

    run.__name__ = name
    return run


def _llm_failure_kind(message: str) -> str:
    """A provider quota / throttling gets its own message; anything else is a generic model error."""
    text = message.lower()
    if "servicequotaexceeded" in text or "quota" in text:
        return "llm_quota"
    if "throttl" in text or "too many requests" in text or "rate limit" in text or "429" in text:
        return "llm_rate_limited"
    return "llm_error"
