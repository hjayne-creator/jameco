"""Helpers for recording Source rows associated with a run."""
from __future__ import annotations

from typing import Optional

from sqlmodel import Session

from app.models.db import Source, get_engine


def record_source(
    *,
    run_id: int,
    url: str,
    kind: str,
    title: Optional[str] = None,
    classification: Optional[str] = None,
    raw_md: Optional[str] = None,
    notes: Optional[str] = None,
) -> None:
    with Session(get_engine()) as session:
        session.add(
            Source(
                run_id=run_id,
                url=url,
                kind=kind,
                title=title,
                classification=classification,
                raw_md=raw_md,
                notes=notes,
            )
        )
        session.commit()
