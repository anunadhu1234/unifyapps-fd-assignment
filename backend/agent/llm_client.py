"""LLM client — AWS Bedrock (Converse API) via LangChain, with per-step model routing and call tracking.

Same Bedrock setup as the intelligence-assistant: the Converse API in the
configured region, authenticated with a Bedrock API key (the
`AWS_BEARER_TOKEN_BEDROCK` bearer token, read by botocore), and no sampling
parameters (current Claude models reject a non-default temperature).

Every LangGraph node asks for an LLM by *pipeline step* ("intent_detection",
"sql_generation", ...), never by model name. The ModelRouter decides which
model serves the step:

    1. MODEL_ROUTES override for the step (from .env)        → that exact model
    2. sql_generation: by the plan's complexity score         → fast (simple) / main (complex)
    3. repair attempts (attempt > 1)                          → always main (escalate)
    4. otherwise the step's default tier                      → fast / main

Structured outputs use Bedrock's native JSON-schema mode (fewest tokens); if a
reply cannot be parsed, the call is retried once with tool calling.

Each call returns its result together with an LLMCall record (step, model,
routing reason, latency, tokens, USD cost from the configured per-token rates).
Nodes put those records in the graph state, which is what the developer view shows.

`LLMGateway` is a protocol so tests can swap in a scripted fake: the graph
never imports the Bedrock client directly.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import asdict, dataclass
from typing import Any, Literal, Protocol, TypeVar

from botocore.config import Config
from langchain_aws import ChatBedrockConverse
from langchain_core.messages import BaseMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel

from utils.config import Settings, get_settings

Tier = Literal["fast", "main"]
T = TypeVar("T", bound=BaseModel)

# Default tier per pipeline step. "auto" = decided by plan complexity.
STEP_TIERS: dict[str, Tier | Literal["auto"]] = {
    "intent_detection": "fast",
    "schema_answer": "fast",
    "query_planner": "main",
    "sql_generation": "auto",
    "sql_repair": "main",
    "sql_optimization": "main",
    "sql_debugging": "main",
    "generate_explanation": "fast",
    "suggest_follow_ups": "fast",
}

# Structured-output strategies, tried in order: native JSON schema first, tool calling as the fallback.
STRUCTURED_METHODS = ("json_schema", "function_calling")


class LLMNotConfiguredError(RuntimeError):
    pass


class LLMOutputError(RuntimeError):
    """The model answered, but not in the structured shape that was asked for."""


@dataclass(frozen=True)
class RouteDecision:
    step: str
    model: str
    tier: str
    reason: str


@dataclass
class LLMCall:
    step: str
    model: str
    tier: str
    route_reason: str
    ms: int
    ok: bool
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None
    error: str | None = None
    served_by: str | None = None  # model ID Bedrock reports for the response
    retried: bool = False  # True when the structured-output fallback (tool calling) was needed

    def as_dict(self) -> dict:
        return asdict(self)


class ModelRouter:
    def __init__(self, settings: Settings):
        self.settings = settings

    def route(self, step: str, *, complexity: int | None = None, attempt: int = 1) -> RouteDecision:
        s = self.settings
        if step in s.model_routes:
            return RouteDecision(step, s.model_routes[step], "pinned", "pinned by MODEL_ROUTES")
        tier = STEP_TIERS.get(step, "main")
        if attempt > 1:
            return RouteDecision(step, s.llm_model_main, "main", f"attempt {attempt}: escalated to the main model")
        if tier == "auto":
            if complexity is not None and complexity <= s.sql_fast_model_max_complexity:
                return RouteDecision(step, s.llm_model_fast, "fast",
                                     f"simple plan (complexity {complexity}): fast model")
            return RouteDecision(step, s.llm_model_main, "main",
                                 f"complex plan (complexity {complexity}): main model")
        model = s.llm_model_fast if tier == "fast" else s.llm_model_main
        return RouteDecision(step, model, tier, f"default {tier} model for {step}")


class LLMGateway(Protocol):
    def structured(self, step: str, messages: list[BaseMessage], schema: type[T], *,
                   complexity: int | None = None, attempt: int = 1,
                   config: RunnableConfig | None = None) -> tuple[T, LLMCall]: ...

    def text(self, step: str, messages: list[BaseMessage], *, complexity: int | None = None,
             attempt: int = 1, config: RunnableConfig | None = None) -> tuple[str, LLMCall]: ...


def build_chat_model(model: str, settings: Settings | None = None, **overrides: Any) -> ChatBedrockConverse:
    settings = settings or get_settings()
    if settings.aws_bearer_token_bedrock is None:
        raise LLMNotConfiguredError("AWS_BEARER_TOKEN_BEDROCK is not set — add the Bedrock API key to backend/.env.")
    # botocore reads the Bedrock API key (bearer token) from this environment variable.
    os.environ["AWS_BEARER_TOKEN_BEDROCK"] = settings.aws_bearer_token_bedrock.get_secret_value()
    params: dict[str, Any] = {
        "model": model,
        "region_name": settings.aws_region,
        "max_tokens": settings.llm_max_tokens,
        "config": Config(
            connect_timeout=10,
            read_timeout=settings.llm_timeout_s,
            retries={"max_attempts": settings.llm_max_retries + 1, "mode": "standard"},
        ),
    }
    params.update(overrides)
    return ChatBedrockConverse(**params)


def get_chat_model(role: Tier = "main", **overrides: Any) -> ChatBedrockConverse:
    settings = get_settings()
    return build_chat_model(settings.llm_model_fast if role == "fast" else settings.llm_model_main,
                            settings, **overrides)


def _usage(message: Any, settings: Settings) -> tuple[int | None, int | None, float | None]:
    """Token counts from the response, and their USD cost at the configured per-million rates."""
    usage = getattr(message, "usage_metadata", None) or {}
    tokens_in, tokens_out = usage.get("input_tokens"), usage.get("output_tokens")
    if tokens_in is None and tokens_out is None:
        return None, None, None
    cost = ((tokens_in or 0) * settings.llm_input_cost_per_m + (tokens_out or 0) * settings.llm_output_cost_per_m) / 1e6
    return tokens_in, tokens_out, round(cost, 8)


def _served_model(message: Any) -> str | None:
    return (getattr(message, "response_metadata", {}) or {}).get("model_name")


class BedrockGateway:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.router = ModelRouter(self.settings)
        self._models: dict[str, ChatBedrockConverse] = {}

    def _model(self, name: str) -> ChatBedrockConverse:
        if name not in self._models:
            self._models[name] = build_chat_model(name, self.settings)
        return self._models[name]

    def structured(self, step, messages, schema, *, complexity=None, attempt=1, config=None):
        route = self.router.route(step, complexity=complexity, attempt=attempt)
        started = time.perf_counter()
        log = logging.getLogger(f"llm.{step}")
        failure = None
        for i, method in enumerate(STRUCTURED_METHODS):
            runnable = self._model(route.model).with_structured_output(schema, method=method, include_raw=True)
            try:
                out = runnable.invoke(messages, config=config)
            except Exception as exc:
                call = LLMCall(step, route.model, route.tier, route.reason, _ms(started), False,
                               error=str(exc)[:300], retried=i > 0)
                if i + 1 < len(STRUCTURED_METHODS) and not _is_throttle(exc):
                    log.warning(f"⚠ {method} structured output failed ({str(exc)[:160]}) — retrying with tool calling")
                    failure = call
                    continue
                raise LLMCallFailed(call) from exc
            tokens_in, tokens_out, cost = _usage(out.get("raw"), self.settings)
            call = LLMCall(step, route.model, route.tier, route.reason, _ms(started), out.get("parsed") is not None,
                           tokens_in, tokens_out, cost, served_by=_served_model(out.get("raw")), retried=i > 0)
            if out.get("parsed") is not None:
                return out["parsed"], call
            call.error = f"unparseable structured output ({method}): {out.get('parsing_error')}"[:300]
            more = i + 1 < len(STRUCTURED_METHODS)
            log.warning(f"⚠ {call.error}" + (" — retrying with tool calling" if more else ""))
            failure = call
        raise LLMCallFailed(failure, LLMOutputError(failure.error))

    def text(self, step, messages, *, complexity=None, attempt=1, config=None):
        route = self.router.route(step, complexity=complexity, attempt=attempt)
        started = time.perf_counter()
        try:
            reply = self._model(route.model).invoke(messages, config=config)
        except Exception as exc:
            call = LLMCall(step, route.model, route.tier, route.reason, _ms(started), False, error=str(exc)[:300])
            raise LLMCallFailed(call) from exc
        tokens_in, tokens_out, cost = _usage(reply, self.settings)
        call = LLMCall(step, route.model, route.tier, route.reason, _ms(started), True,
                       tokens_in, tokens_out, cost, served_by=_served_model(reply))
        # .text joins the text blocks only (models that think first also return reasoning blocks).
        return reply.text, call


class LLMCallFailed(RuntimeError):
    """Carries the LLMCall record so a failed call still shows up in the trace and cost totals."""

    def __init__(self, call: LLMCall, cause: Exception | None = None):
        super().__init__(call.error or "LLM call failed")
        self.call = call
        self.cause = cause


class LoggingGateway:
    """Wraps any gateway so every LLM stage is logged: the model it was routed to and why, then the
    outcome with tokens, cost and latency (prompt and response at DEBUG level)."""

    def __init__(self, inner: LLMGateway, router: ModelRouter):
        self.inner = inner
        self.router = router

    def structured(self, step, messages, schema, *, complexity=None, attempt=1, config=None):
        log = self._before(step, messages, complexity, attempt)
        try:
            parsed, call = self.inner.structured(step, messages, schema, complexity=complexity, attempt=attempt,
                                                 config=config)
        except LLMCallFailed as exc:
            log.error(f"✗ {exc.call.model} failed after {exc.call.ms} ms: {exc.call.error}")
            raise
        self._after(log, call, parsed.model_dump() if isinstance(parsed, BaseModel) else parsed)
        return parsed, call

    def text(self, step, messages, *, complexity=None, attempt=1, config=None):
        log = self._before(step, messages, complexity, attempt)
        try:
            text, call = self.inner.text(step, messages, complexity=complexity, attempt=attempt, config=config)
        except LLMCallFailed as exc:
            log.error(f"✗ {exc.call.model} failed after {exc.call.ms} ms: {exc.call.error}")
            raise
        self._after(log, call, text)
        return text, call

    def _before(self, step, messages, complexity, attempt) -> logging.Logger:
        route = self.router.route(step, complexity=complexity, attempt=attempt)
        log = logging.getLogger(f"llm.{step}")
        log.info(f"→ {route.model} · {route.reason}")
        log.debug("prompt: %s", [{"role": m.type, "content": m.content} for m in messages])
        return log

    @staticmethod
    def _after(log: logging.Logger, call: LLMCall, response: Any) -> None:
        tokens = f"{call.input_tokens or 0}→{call.output_tokens or 0} tok"
        cost = f"${call.cost_usd:.6f}" if call.cost_usd is not None else "cost n/a"
        log.info(f"← {call.served_by or call.model} · {call.ms} ms · {tokens} · {cost}")
        log.debug("response: %s", response)


def _is_throttle(exc: Exception) -> bool:
    text = f"{type(exc).__name__} {exc}".lower()
    return "throttl" in text or "too many requests" in text or "servicequota" in text


def _ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)
