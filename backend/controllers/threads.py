"""Threads controller — the conversation history panel (list, open, rename, delete chats)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from controllers.context import AppServices, ensure_owner
from middleware.auth import for_audience


class RenameRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)


def list_threads(svc: AppServices, client: str) -> dict:
    return {"threads": svc.threads.list_threads(client)}


def get_thread(svc: AppServices, thread_id: str, client: str, dev: bool) -> dict:
    ensure_owner(svc, thread_id, client, must_exist=True)
    turns = svc.threads.get_turns(thread_id)
    for turn in turns:
        turn["response"] = for_audience(turn["response"], dev)
    return {"thread_id": thread_id, "turns": turns}


def rename_thread(svc: AppServices, thread_id: str, body: RenameRequest, client: str) -> dict:
    ensure_owner(svc, thread_id, client, must_exist=True)
    svc.threads.rename(thread_id, body.title)
    return {"ok": True}


def delete_thread(svc: AppServices, thread_id: str, client: str) -> dict:
    ensure_owner(svc, thread_id, client, must_exist=True)
    svc.threads.delete(thread_id)
    return {"ok": True}
