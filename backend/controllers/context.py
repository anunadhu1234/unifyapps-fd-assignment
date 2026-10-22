"""Shared request context: the agent and stores (created once at startup), and who owns a chat."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, Request

from agent.supervisor.supervisor import SQLAgent
from middleware.auth import User, current_user
from utils.thread_store import ThreadStore

ID_PATTERN = r"^[A-Za-z0-9_-]{8,64}$"


@dataclass
class AppServices:
    agent: SQLAgent
    threads: ThreadStore


def services(request: Request) -> AppServices:
    return request.app.state.services


def client_id(x_client_id: str = Header(..., alias="X-Client-Id", pattern=ID_PATTERN)) -> str:
    """Per-browser id (generated and kept in localStorage by the frontend)."""
    return x_client_id


def owner(user: User = Depends(current_user), client: str = Depends(client_id)) -> str:
    """Chats belong to an account AND a browser: reviewers sharing a test login don't see each other's chats."""
    return f"{user.username}:{client}"


def ensure_owner(svc: AppServices, thread_id: str, client: str, *, must_exist: bool) -> None:
    owner = svc.threads.owner(thread_id)
    if owner is None and must_exist:
        raise HTTPException(status_code=404, detail="Chat not found.")
    if owner is not None and owner != client:
        raise HTTPException(status_code=404, detail="Chat not found.")
