"""GET /api/health — liveness plus what is configured (no secrets)."""

from fastapi import APIRouter, Depends

from controllers.context import AppServices, services

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def health(svc: AppServices = Depends(services)):
    deps = svc.agent.deps
    s = deps.settings
    return {
        "status": "ok",
        "llm_provider": "aws-bedrock",
        "llm_configured": s.aws_bearer_token_bedrock is not None,
        "models": {"fast": s.llm_model_fast, "main": s.llm_model_main},
        "database": {"dialect": deps.kb.meta["dialect"], "tables": deps.kb.meta["row_counts"],
                     "as_of_date": deps.kb.meta["as_of_date"]},
        "auth_configured": bool(s.auth_normal_password or s.auth_dev_password),
    }
