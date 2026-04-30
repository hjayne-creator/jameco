"""In-memory representation of a run, hydrated from / persisted to the DB."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from app.models.schemas import (
    CompetitorExtracts,
    CompetitorList,
    FinalCopy,
    GapValidation,
    HtmlCopy,
    IdentityLock,
    ManufacturerVerification,
    SubjectExtract,
)


@dataclass
class RunState:
    run_id: int
    subject_url: str
    n_competitors: int
    style_guide_text: str = ""

    # Step outputs (populated as we go)
    subject_extract: Optional[SubjectExtract] = None
    identity_lock: Optional[IdentityLock] = None
    manufacturer: Optional[ManufacturerVerification] = None
    competitor_list: Optional[CompetitorList] = None
    competitor_extracts: Optional[CompetitorExtracts] = None
    gap_validation: Optional[GapValidation] = None
    final_copy: Optional[FinalCopy] = None
    html_copy: Optional[HtmlCopy] = None
    json_ld: Optional[dict] = None

    # Bookkeeping
    sources_used: list[dict[str, Any]] = field(default_factory=list)
    audit_notes: list[str] = field(default_factory=list)
