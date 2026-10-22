"""A scripted stand-in for the Bedrock gateway.

Each pipeline step gets a queue of responses. A response is either the object to
return (a dict is turned into the requested Pydantic schema) or a function
`messages -> response`, which lets a test assert on the prompt a node built.
Routing decisions come from the real ModelRouter, so tests also cover routing.
"""

from __future__ import annotations

from langchain_core.messages import BaseMessage

from agent.llm_client import LLMCall, LLMCallFailed, ModelRouter
from utils.config import get_settings


def prompt_text(messages: list[BaseMessage]) -> str:
    return "\n".join(str(m.content) for m in messages)


class ScriptedLLM:
    def __init__(self, script: dict[str, list] | None = None):
        self.script = {k: list(v) for k, v in (script or {}).items()}
        self.calls: list[dict] = []
        self.router = ModelRouter(get_settings())

    def _next(self, step: str, messages):
        queue = self.script.get(step)
        if not queue:
            raise AssertionError(f"unexpected LLM call for step '{step}'")
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item(messages) if callable(item) else item

    def _record(self, step, complexity, attempt, messages) -> LLMCall:
        route = self.router.route(step, complexity=complexity, attempt=attempt)
        self.calls.append({"step": step, "model": route.model, "tier": route.tier, "reason": route.reason,
                           "prompt": prompt_text(messages)})
        return LLMCall(step, route.model, route.tier, route.reason, 3, True, 100, 20, 0.0001)

    def structured(self, step, messages, schema, *, complexity=None, attempt=1, config=None):
        call = self._record(step, complexity, attempt, messages)
        out = self._next(step, messages)
        return (schema(**out) if isinstance(out, dict) else out), call

    def text(self, step, messages, *, complexity=None, attempt=1, config=None):
        call = self._record(step, complexity, attempt, messages)
        return self._next(step, messages), call

    def steps(self) -> list[str]:
        return [c["step"] for c in self.calls]


def llm_failure(step: str) -> LLMCallFailed:
    return LLMCallFailed(LLMCall(step, "test/model", "main", "test", 5, False, error="upstream timeout"))
