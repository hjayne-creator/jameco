"""SSE event stream for live workflow progress."""
from __future__ import annotations

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from app.events import bus

router = APIRouter()


@router.get("/{run_id}/events")
async def stream(run_id: int) -> EventSourceResponse:
    async def event_generator():
        async for message in bus.subscribe(run_id):
            yield {"data": message}

    return EventSourceResponse(event_generator())
