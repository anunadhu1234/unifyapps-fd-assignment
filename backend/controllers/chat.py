"""Chat controller — ask a question (JSON or streamed) and record the turn."""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import Iterator

from pydantic import BaseModel, Field

from controllers.context import ID_PATTERN, AppServices, ensure_owner
from middleware.auth import for_audience

log = logging.getLogger("api.chat")


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    thread_id: str | None = Field(None, pattern=ID_PATTERN, description="Omit to start a new chat.")
    execute: bool = Field(True, description="Run the validated SQL against the sample database.")


def ask(svc: AppServices, body: ChatRequest, client: str, dev: bool) -> dict:
    thread_id = body.thread_id or uuid.uuid4().hex
    ensure_owner(svc, thread_id, client, must_exist=False)
    log.info(f"question: {body.question[:200]}")
    response = svc.agent.run(body.question, thread_id=thread_id, options={"execute": body.execute})
    svc.threads.add_turn(thread_id, client, body.question, response)
    return {"thread_id": thread_id, "response": for_audience(response, dev)}


def ask_stream(svc: AppServices, body: ChatRequest, client: str, dev: bool) -> Iterator[str]:
    """Server-Sent Events: start → node (one per pipeline step) / token (explanation text) → response."""
    thread_id = body.thread_id or uuid.uuid4().hex
    ensure_owner(svc, thread_id, client, must_exist=False)

    def events() -> Iterator[str]:
        log.info(f"question: {body.question[:200]}")
        yield _sse("start", {"thread_id": thread_id})
        try:
            for event in svc.agent.stream(body.question, thread_id=thread_id, options={"execute": body.execute}):
                if event["event"] == "response":
                    response = event["data"]
                    svc.threads.add_turn(thread_id, client, body.question, response)
                    yield _sse("response", {"thread_id": thread_id, "response": for_audience(response, dev)})
                else:
                    yield _sse(event["event"], event)
        except Exception:
            log.exception("stream failed")
            yield _sse("error", {"message": "Something went wrong while answering. Please try again."})

    return events()


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"
