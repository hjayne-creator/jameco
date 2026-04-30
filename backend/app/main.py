from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import checkpoints, events, runs, style_guide
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
def _startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict:
    return {"ok": True}


app.include_router(runs.router, prefix="/runs", tags=["runs"])
app.include_router(checkpoints.router, prefix="/runs", tags=["checkpoints"])
app.include_router(events.router, prefix="/runs", tags=["events"])
app.include_router(style_guide.router, prefix="/style-guides", tags=["style-guides"])
