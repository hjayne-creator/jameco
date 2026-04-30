"""In-process pub/sub used to stream workflow progress to SSE consumers."""
from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from dataclasses import dataclass, field
from typing import AsyncIterator, Dict


@dataclass
class _RunChannel:
    subscribers: list[asyncio.Queue[str]] = field(default_factory=list)
    last_events: list[str] = field(default_factory=list)


class EventBus:
    """Per-run event channels.

    Late-joining subscribers receive any events buffered so far, then live
    events. Buffer is small and intended for short-lived runs only.
    """

    def __init__(self) -> None:
        self._channels: Dict[int, _RunChannel] = defaultdict(_RunChannel)
        self._lock = asyncio.Lock()
        self._buffer_limit = 200

    async def publish(self, run_id: int, event_type: str, payload: dict | None = None) -> None:
        message = json.dumps({"type": event_type, "payload": payload or {}})
        async with self._lock:
            channel = self._channels[run_id]
            channel.last_events.append(message)
            if len(channel.last_events) > self._buffer_limit:
                channel.last_events = channel.last_events[-self._buffer_limit :]
            for queue in list(channel.subscribers):
                queue.put_nowait(message)

    async def subscribe(self, run_id: int) -> AsyncIterator[str]:
        queue: asyncio.Queue[str] = asyncio.Queue()
        async with self._lock:
            channel = self._channels[run_id]
            channel.subscribers.append(queue)
            backlog = list(channel.last_events)
        try:
            for message in backlog:
                yield message
            while True:
                message = await queue.get()
                yield message
        finally:
            async with self._lock:
                channel = self._channels.get(run_id)
                if channel and queue in channel.subscribers:
                    channel.subscribers.remove(queue)


bus = EventBus()
