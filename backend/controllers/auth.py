"""Auth controller — sign in with one of the two test accounts."""

from __future__ import annotations

import logging

from fastapi import HTTPException
from pydantic import BaseModel, Field

from middleware.auth import User, authenticate, issue_token
from utils.config import get_settings

log = logging.getLogger("auth")


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=200)


def login(body: LoginRequest) -> dict:
    if not (get_settings().auth_normal_password or get_settings().auth_dev_password):
        raise HTTPException(status_code=503, detail="Sign-in is not configured on this server.")
    user = authenticate(body.username, body.password)
    if user is None:
        log.warning(f"sign-in failed for '{body.username[:40]}'")
        raise HTTPException(status_code=401, detail="Incorrect username or password.")
    log.info(f"signed in: {user.username} ({user.role})")
    token, expires = issue_token(user)
    return {"token": token, "expires_at": expires.isoformat(), "user": user.as_dict()}


def me(user: User) -> dict:
    return {"user": user.as_dict()}


def accounts() -> dict:
    """Which test accounts exist (usernames and roles only — never passwords), for the sign-in page."""
    s = get_settings()
    out = []
    if s.auth_normal_password:
        out.append({"username": s.auth_normal_username, "role": "normal", "display_name": s.auth_normal_display_name})
    if s.auth_dev_password:
        out.append({"username": s.auth_dev_username, "role": "dev", "display_name": s.auth_dev_display_name})
    return {"accounts": out}
