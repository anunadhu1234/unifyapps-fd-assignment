"""Uniform JSON errors: {"error": {"status", "message"}} for every failure."""

from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

log = logging.getLogger("api")


def _error(status: int, message: str, headers: dict | None = None) -> JSONResponse:
    return JSONResponse({"error": {"status": status, "message": message}}, status_code=status, headers=headers)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def http_error(_: Request, exc: HTTPException):
        return _error(exc.status_code, str(exc.detail), getattr(exc, "headers", None))

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError):
        first = exc.errors()[0] if exc.errors() else {}
        field = ".".join(str(p) for p in first.get("loc", [])[1:])
        return _error(422, f"Invalid request: {field} {first.get('msg', '')}".strip())

    @app.exception_handler(Exception)
    async def unexpected(_: Request, exc: Exception):
        log.exception("unhandled error")
        return _error(500, "Something went wrong on the server. Please try again.")
