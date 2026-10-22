"""Conversation history: GET/PATCH/DELETE /api/threads[/{thread_id}]. Requires sign-in."""

from fastapi import APIRouter, Depends, Path

from controllers import threads
from controllers.context import ID_PATTERN, AppServices, owner, services
from middleware.auth import is_dev

router = APIRouter(prefix="/api/threads", tags=["threads"])
ThreadId = Path(..., pattern=ID_PATTERN)


@router.get("")
def list_threads(svc: AppServices = Depends(services), who: str = Depends(owner)):
    return threads.list_threads(svc, who)


@router.get("/{thread_id}")
def get_thread(thread_id: str = ThreadId, svc: AppServices = Depends(services), who: str = Depends(owner),
               dev: bool = Depends(is_dev)):
    return threads.get_thread(svc, thread_id, who, dev)


@router.patch("/{thread_id}")
def rename_thread(body: threads.RenameRequest, thread_id: str = ThreadId, svc: AppServices = Depends(services),
                  who: str = Depends(owner)):
    return threads.rename_thread(svc, thread_id, body, who)


@router.delete("/{thread_id}")
def delete_thread(thread_id: str = ThreadId, svc: AppServices = Depends(services), who: str = Depends(owner)):
    return threads.delete_thread(svc, thread_id, who)
