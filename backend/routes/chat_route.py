"""POST /api/chat (JSON) and POST /api/chat/stream (Server-Sent Events). Requires sign-in."""

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from controllers import chat
from controllers.context import AppServices, owner, services
from middleware.auth import is_dev
from middleware.rate_limit import rate_limit

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("", dependencies=[Depends(rate_limit)])
def ask(body: chat.ChatRequest, svc: AppServices = Depends(services), who: str = Depends(owner),
        dev: bool = Depends(is_dev)):
    return chat.ask(svc, body, who, dev)


@router.post("/stream", dependencies=[Depends(rate_limit)])
def ask_stream(body: chat.ChatRequest, svc: AppServices = Depends(services), who: str = Depends(owner),
               dev: bool = Depends(is_dev)):
    return StreamingResponse(chat.ask_stream(svc, body, who, dev), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
