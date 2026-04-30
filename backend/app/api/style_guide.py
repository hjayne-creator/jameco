"""Style guide upload + listing endpoints."""
from __future__ import annotations

import io
import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlmodel import Session, select

from app.models.db import StyleGuide, get_engine

logger = logging.getLogger(__name__)
router = APIRouter()


def get_session():
    with Session(get_engine()) as session:
        yield session


def _extract_text(filename: str, data: bytes) -> str:
    name_lower = filename.lower()
    if name_lower.endswith(".pdf"):
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise HTTPException(500, "pypdf not installed") from exc
        reader = PdfReader(io.BytesIO(data))
        pages = []
        for page in reader.pages:
            try:
                pages.append(page.extract_text() or "")
            except Exception:
                continue
        return "\n".join(pages)
    return data.decode("utf-8", errors="replace")


@router.post("")
async def upload(
    name: str = Form(...),
    file: Optional[UploadFile] = File(None),
    text: Optional[str] = Form(None),
    session: Session = Depends(get_session),
) -> dict:
    if not file and not text:
        raise HTTPException(400, "Provide either a file upload or raw text")
    if file is not None:
        data = await file.read()
        body = _extract_text(file.filename or "guide.txt", data)
    else:
        body = text or ""
    sg = StyleGuide(name=name, text=body)
    session.add(sg)
    session.commit()
    session.refresh(sg)
    return {"id": sg.id, "name": sg.name, "length": len(sg.text)}


@router.get("")
def list_guides(session: Session = Depends(get_session)) -> list[dict]:
    rows = session.exec(select(StyleGuide).order_by(StyleGuide.id.desc())).all()
    return [
        {
            "id": s.id,
            "name": s.name,
            "length": len(s.text),
            "created_at": s.created_at.isoformat(),
        }
        for s in rows
    ]


@router.get("/{guide_id}")
def get_guide(guide_id: int, session: Session = Depends(get_session)) -> dict:
    sg = session.get(StyleGuide, guide_id)
    if sg is None:
        raise HTTPException(404, "Style guide not found")
    return {
        "id": sg.id,
        "name": sg.name,
        "text": sg.text,
        "created_at": sg.created_at.isoformat(),
    }


@router.delete("/{guide_id}")
def delete_guide(guide_id: int, session: Session = Depends(get_session)) -> dict:
    sg = session.get(StyleGuide, guide_id)
    if sg is None:
        raise HTTPException(404, "Style guide not found")
    session.delete(sg)
    session.commit()
    return {"ok": True}
