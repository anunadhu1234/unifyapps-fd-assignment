"""POST /api/auth/login, GET /api/auth/me, GET /api/auth/accounts (public: usernames + roles only)."""

from fastapi import APIRouter, Depends

from controllers import auth
from middleware.auth import User, current_user, login_rate_limit

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", dependencies=[Depends(login_rate_limit)])
def login(body: auth.LoginRequest):
    return auth.login(body)


@router.get("/me")
def me(user: User = Depends(current_user)):
    return auth.me(user)


@router.get("/accounts")
def accounts():
    return auth.accounts()
