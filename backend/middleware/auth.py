"""Authentication: two test accounts (normal and dev), signed bearer tokens, role-based output.

The accounts come from backend/.env (AUTH_NORMAL_* and AUTH_DEV_*). Logging in
returns a short-lived HS256 JWT that carries the username and role; every API
request sends it as `Authorization: Bearer <token>`.

Role decides what the API returns — on the server, not just in the UI:
    normal → chat, SQL, explanation, results, cost, validation checks
    dev    → all of the above + the "dev" section (intent, retrieval, plan, validation
             attempts, node trace, every LLM call with model / tokens / cost) + /api/dev/*
"""

from __future__ import annotations

import hmac
import logging
import secrets
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Literal

import jwt
from fastapi import Depends, Header, HTTPException, Request

from utils.config import Settings, get_settings

log = logging.getLogger("auth")
Role = Literal["normal", "dev"]
ALGORITHM = "HS256"


@dataclass(frozen=True)
class User:
    username: str
    role: Role
    display_name: str

    @property
    def is_dev(self) -> bool:
        return self.role == "dev"

    def as_dict(self) -> dict:
        return asdict(self)


def _accounts(s: Settings) -> list[tuple[User, str]]:
    accounts = []
    if s.auth_normal_password:
        accounts.append((User(s.auth_normal_username, "normal", s.auth_normal_display_name),
                         s.auth_normal_password.get_secret_value()))
    if s.auth_dev_password:
        accounts.append((User(s.auth_dev_username, "dev", s.auth_dev_display_name),
                         s.auth_dev_password.get_secret_value()))
    return accounts


@lru_cache
def _secret() -> str:
    configured = get_settings().auth_secret
    if configured:
        return configured.get_secret_value()
    log.warning("AUTH_SECRET is not set — using a random secret; sessions end when the server restarts.")
    return secrets.token_urlsafe(48)


def authenticate(username: str, password: str) -> User | None:
    """Constant-time check against both accounts (every account is compared, match or not)."""
    found = None
    for user, expected in _accounts(get_settings()):
        same_name = hmac.compare_digest(username.strip().lower().encode(), user.username.lower().encode())
        same_password = hmac.compare_digest(password.encode(), expected.encode())
        if same_name and same_password:
            found = user
    return found


def issue_token(user: User) -> tuple[str, datetime]:
    expires = datetime.now(UTC) + timedelta(hours=get_settings().auth_token_ttl_hours)
    token = jwt.encode({"sub": user.username, "role": user.role, "name": user.display_name, "exp": expires},
                       _secret(), algorithm=ALGORITHM)
    return token, expires


def current_user(authorization: str | None = Header(None)) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Please sign in.")
    try:
        claims = jwt.decode(authorization[7:].strip(), _secret(), algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Your session has expired — please sign in again.") from None
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Please sign in.") from None
    if claims.get("role") not in ("normal", "dev"):
        raise HTTPException(status_code=401, detail="Please sign in.")
    return User(claims["sub"], claims["role"], claims.get("name") or claims["sub"])


def is_dev(user: User = Depends(current_user)) -> bool:
    return user.is_dev


def require_dev(user: User = Depends(current_user)) -> User:
    if not user.is_dev:
        raise HTTPException(status_code=403, detail="Developer access only.")
    return user


def for_audience(response: dict, dev: bool) -> dict:
    """Remove dev-only fields for normal users."""
    if dev:
        return response
    return {k: v for k, v in response.items() if k != "dev"}


def login_rate_limit(request: Request) -> None:
    from middleware.rate_limit import client_ip, limiter

    allowed, retry_after = limiter.check(f"login:{client_ip(request)}",
                                         get_settings().login_attempts_per_minute, 10_000)
    if not allowed:
        raise HTTPException(status_code=429, detail=f"Too many sign-in attempts — wait {retry_after} seconds.",
                            headers={"Retry-After": str(retry_after)})
