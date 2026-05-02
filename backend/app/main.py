from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import admin_reporting, batches, checkpoints, events, runs, style_guide
from app.config import get_settings
from app.models.db import init_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

settings = get_settings()

app = FastAPI(title="JameCo PDP Workflow", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def _startup() -> None:
    init_db()
    from app.workflow.bulk_worker import repair_stuck_running_batches, start_bulk_worker

    repair_stuck_running_batches()
    await start_bulk_worker()


@app.get("/health")
def health() -> dict:
    return {"ok": True}


app.include_router(batches.router, prefix="/batches", tags=["batches"])
app.include_router(runs.router, prefix="/runs", tags=["runs"])
app.include_router(checkpoints.router, prefix="/runs", tags=["checkpoints"])
app.include_router(events.router, prefix="/runs", tags=["events"])
app.include_router(style_guide.router, prefix="/style-guides", tags=["style-guides"])
app.include_router(admin_reporting.router, prefix="/admin", tags=["admin"])
