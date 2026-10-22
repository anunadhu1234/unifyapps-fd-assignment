"""GET /api/schema (summary, signed-in) and GET /api/schema/graph (interactive knowledge-graph page, public)."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from controllers import schema
from controllers.context import AppServices, services
from middleware.auth import current_user
from utils.config import get_settings

router = APIRouter(prefix="/api/schema", tags=["schema"])


@router.get("", dependencies=[Depends(current_user)])
def schema_summary(svc: AppServices = Depends(services)):
    return schema.schema_summary(svc)


@router.get("/graph")
def schema_graph():
    page = get_settings().knowledge_dir / "relations_graph.html"
    if not page.exists():
        raise HTTPException(status_code=404, detail="Knowledge graph page not built.")
    return FileResponse(page, media_type="text/html")
