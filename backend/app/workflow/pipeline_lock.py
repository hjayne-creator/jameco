"""Serialize PDP pipeline step execution (single-URL and bulk share this lock)."""
from __future__ import annotations

import asyncio

_pipeline_lock = asyncio.Lock()


def get_pipeline_lock() -> asyncio.Lock:
    return _pipeline_lock
