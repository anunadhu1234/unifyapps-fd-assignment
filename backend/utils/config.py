"""Application settings, read from environment variables / a .env file.

Every tunable lives here so nothing else reads os.environ directly.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── LLM: AWS Bedrock (Converse API), same setup as the intelligence-assistant ──
    # Bedrock API key — botocore reads it as the AWS_BEARER_TOKEN_BEDROCK bearer token.
    aws_bearer_token_bedrock: SecretStr | None = None
    aws_region: str = "us-west-2"
    # Fast model: intent, explanations, suggestions. Main model: planning, SQL, repair.
    # Both default to Claude Haiku 5.5 (US cross-region inference profile).
    llm_model_fast: str = "us.anthropic.claude-haiku-5-5"
    llm_model_main: str = "us.anthropic.claude-haiku-5-5"
    llm_max_tokens: int = 8192
    llm_timeout_s: float = 90.0
    llm_max_retries: int = 2
    # USD per million tokens, used for the per-call cost shown in the developer view
    # (Claude Haiku 5.5 list price; set your Bedrock rates if they differ).
    llm_input_cost_per_m: float = 0.10
    llm_output_cost_per_m: float = 0.50
    # Model routing: pin any pipeline step to a specific model, e.g.
    # MODEL_ROUTES='{"sql_generation": "openai/gpt-5", "generate_explanation": "anthropic/claude-haiku-5.5"}'
    model_routes: dict[str, str] = {}
    # SQL generation goes to the fast model when the plan's complexity score is at
    # or below this (single table, no aggregation), otherwise to the main model.
    sql_fast_model_max_complexity: int = 1

    # ── Data & knowledge ──
    database_path: Path = BACKEND_DIR / "data" / "company.db"
    knowledge_dir: Path = BACKEND_DIR / "knowledge_base"
    # Conversation memory (LangGraph checkpoints), one thread per chat.
    checkpoint_path: Path = BACKEND_DIR / "data" / "runtime" / "checkpoints.db"

    # ── Authentication: two test accounts ──
    # The "normal" account sees chat, SQL, explanation, results, cost and validation.
    # The "dev" account also gets the internals (intent, retrieval, plan, validation
    # attempts, node trace, every LLM call with model / tokens / cost, prompts).
    # The role is checked server-side: dev-only fields never reach a normal session.
    auth_normal_username: str = "demo"
    auth_normal_password: SecretStr | None = None
    auth_normal_display_name: str = "Demo User"
    auth_dev_username: str = "developer"
    auth_dev_password: SecretStr | None = None
    auth_dev_display_name: str = "Developer"
    # Signs login tokens. Set a long random value in production; if empty, a random
    # one is generated at startup (sessions then end when the server restarts).
    auth_secret: SecretStr | None = None
    auth_token_ttl_hours: int = 12
    login_attempts_per_minute: int = 10

    # ── Guardrails ──
    max_result_rows: int = 500
    query_timeout_s: float = 5.0
    max_sql_fix_attempts: int = 3
    max_question_chars: int = 2000
    history_turns: int = 6  # past turns shown to intent detection / planner
    # "Dive deeper" follow-up suggestions after each SQL answer (one extra fast-model call,
    # run in parallel with the explanation). Turn off to save calls on a free LLM tier.
    suggestions_enabled: bool = True
    export_max_rows: int = 50_000  # full-result CSV export cap

    # ── API ──
    # Questions per client IP, for every account. Protects the LLM quota on a public link.
    rate_limit_per_minute: int = 6
    rate_limit_per_day: int = 60
    # Browser origins allowed to call the API when the frontend is hosted separately (e.g. on Vercel).
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    # Optional regex for origins that change per deploy, e.g. Vercel preview URLs:
    # ^https://unifyapps-fd-assignment(-[a-z0-9-]+)?\.vercel\.app$
    cors_origin_regex: str | None = None
    app_db_path: Path = BACKEND_DIR / "data" / "runtime" / "app.db"  # chat list + turn history
    frontend_dist: Path = REPO_DIR / "frontend" / "dist"


@lru_cache
def get_settings() -> Settings:
    return Settings()
