"""Developer endpoints — dev account only (run history, LLM routing, prompts, knowledge graph)."""

from fastapi import APIRouter, Depends, Query

from controllers import dev
from controllers.context import AppServices, owner, services
from middleware.auth import require_dev

router = APIRouter(prefix="/api/dev", tags=["dev"], dependencies=[Depends(require_dev)])


@router.get("/llm")
def llm_config(svc: AppServices = Depends(services)):
    return dev.llm_config(svc)


@router.get("/prompts")
def prompts():
    return dev.prompts()


@router.get("/knowledge-graph")
def knowledge_graph(svc: AppServices = Depends(services)):
    return dev.knowledge_graph(svc)


@router.get("/runs")
def run_history(limit: int = Query(100, ge=1, le=500), svc: AppServices = Depends(services),
                who: str = Depends(owner)):
    return dev.run_history(svc, who, limit)
