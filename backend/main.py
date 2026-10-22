"""FastAPI application — the API and (in production) the built frontend, from one process.

Run locally (from backend/):
    uvicorn main:app --reload --port 8000

Routes (all but login, health and the graph page require `Authorization: Bearer <token>`)
    POST   /api/auth/login              sign in with a test account → token + role
    GET    /api/auth/me                 the signed-in account
    POST   /api/chat                    ask (JSON)
    POST   /api/chat/stream             ask (Server-Sent Events: node progress, explanation tokens, response)
    GET    /api/threads                 chat list for this browser
    GET    /api/threads/{id}            one chat with every turn
    PATCH  /api/threads/{id}            rename          DELETE /api/threads/{id}   delete
    GET    /api/export/{request_id}.csv full results as CSV
    GET    /api/schema                  tables, columns, relationships, metrics, suggested questions
    GET    /api/schema/graph            interactive knowledge-graph page
    GET    /api/health                  status
    GET    /api/dev/*                   dev account only: run history, llm routing, prompts, knowledge graph
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from agent.supervisor.supervisor import SQLAgent, sqlite_checkpointer
from controllers.context import AppServices
from middleware.errors import install_error_handlers
from routes import auth_route, chat_route, dev_route, export_route, health_route, schema_route, threads_route
from utils.config import get_settings
from utils.thread_store import ThreadStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
api_log = logging.getLogger("api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    if getattr(app.state, "services", None) is None:  # tests may inject their own
        app.state.services = AppServices(
            agent=SQLAgent(checkpointer=sqlite_checkpointer(settings.checkpoint_path)),
            threads=ThreadStore(settings.app_db_path),
        )
    yield


def create_app(services: AppServices | None = None) -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="SQL Query Agent", version="1.0.0", lifespan=lifespan,
                  description="LangGraph agent that turns natural language into validated, read-only SQL.")
    app.state.services = services
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins,
                       allow_origin_regex=settings.cors_origin_regex, allow_methods=["*"],
                       allow_headers=["*"], expose_headers=["Content-Disposition", "Retry-After"])
    install_error_handlers(app)

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        """One log line per API call (static files are skipped)."""
        started = time.perf_counter()
        response = await call_next(request)
        path = request.url.path
        if path.startswith("/api/"):
            ms = int((time.perf_counter() - started) * 1000)
            level = logging.WARNING if response.status_code >= 400 else logging.INFO
            api_log.log(level, f"{request.method} {path} → {response.status_code} · {ms} ms")
        return response

    for module in (auth_route, chat_route, threads_route, export_route, schema_route, dev_route, health_route):
        app.include_router(module.router)
    _serve_frontend(app, settings.frontend_dist)
    return app


def _serve_frontend(app: FastAPI, dist) -> None:
    """Serve the built React app (single-page app: unknown paths fall back to index.html)."""
    if not (dist / "index.html").exists():
        return
    app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        candidate = dist / path
        if path and candidate.is_file() and dist in candidate.resolve().parents:
            return FileResponse(candidate)
        return FileResponse(dist / "index.html")


app = create_app()
