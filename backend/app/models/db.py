"""SQLModel tables and the engine setup."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import JSON, text
from sqlalchemy.engine import Engine
from sqlmodel import Column, Field, SQLModel, create_engine

from app.config import get_settings


def _now() -> datetime:
    return datetime.now(timezone.utc)


class StyleGuide(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    text: str
    created_at: datetime = Field(default_factory=_now)


class Batch(SQLModel, table=True):
    """Bulk PDP job: many runs, one options snapshot, FIFO queue execution."""

    id: Optional[int] = Field(default=None, primary_key=True)
    name: Optional[str] = None
    status: str = "queued"  # queued | running | done | failed
    options_snapshot: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class Run(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    subject_url: str
    n_competitors: int = 5
    style_guide_id: Optional[int] = Field(default=None, foreign_key="styleguide.id")
    status: str = "pending"
    current_step: int = 0
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)
    batch_id: Optional[int] = Field(default=None, foreign_key="batch.id", index=True)
    batch_index: int = 0
    terminal_reason: Optional[str] = None


class StepResult(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="run.id", index=True)
    step_no: int
    step_name: str
    status: str = "pending"
    input_json: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    output_json: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    model_used: Optional[str] = None
    duration_ms: Optional[int] = None
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class Source(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="run.id", index=True)
    url: str
    kind: str
    classification: Optional[str] = None
    title: Optional[str] = None
    fetched_at: datetime = Field(default_factory=_now)
    raw_md: Optional[str] = None
    notes: Optional[str] = None


_engine = None


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
        _engine = create_engine(settings.database_url, echo=False, connect_args=connect_args)
    return _engine


def _migrate_sqlite_run_columns(engine: Engine) -> None:
    if engine.dialect.name != "sqlite":
        return
    with engine.begin() as conn:
        rows = conn.execute(text("PRAGMA table_info(run)")).fetchall()
        col_names = {r[1] for r in rows}
        if "batch_id" not in col_names:
            conn.execute(text("ALTER TABLE run ADD COLUMN batch_id INTEGER"))
        if "batch_index" not in col_names:
            conn.execute(text("ALTER TABLE run ADD COLUMN batch_index INTEGER DEFAULT 0"))
        if "terminal_reason" not in col_names:
            conn.execute(text("ALTER TABLE run ADD COLUMN terminal_reason VARCHAR"))


def _migrate_sqlite_batch_columns(engine: Engine) -> None:
    if engine.dialect.name != "sqlite":
        return
    with engine.begin() as conn:
        tables = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='batch'")
        ).fetchall()
        if not tables:
            return
        rows = conn.execute(text("PRAGMA table_info(batch)")).fetchall()
        col_names = {r[1] for r in rows}
        if "error" not in col_names:
            conn.execute(text("ALTER TABLE batch ADD COLUMN error VARCHAR"))
        if "name" not in col_names:
            conn.execute(text("ALTER TABLE batch ADD COLUMN name VARCHAR"))


def init_db() -> None:
    engine = get_engine()
    SQLModel.metadata.create_all(engine)
    _migrate_sqlite_run_columns(engine)
    _migrate_sqlite_batch_columns(engine)
