"""GET /api/export/{request_id}.csv — full query results as CSV. Requires sign-in."""

from fastapi import APIRouter, Depends, Path
from fastapi.responses import StreamingResponse

from controllers import export
from controllers.context import ID_PATTERN, AppServices, owner, services

router = APIRouter(prefix="/api/export", tags=["export"])


@router.get("/{request_id}.csv")
def export_csv(request_id: str = Path(..., pattern=ID_PATTERN), svc: AppServices = Depends(services),
               who: str = Depends(owner)):
    rows, filename = export.export_csv(svc, request_id, who)
    return StreamingResponse(rows, media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="{filename}"'})
