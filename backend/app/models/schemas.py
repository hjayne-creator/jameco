"""Typed step IO contracts shared between the orchestrator, steps and API."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, HttpUrl


SourceKind = Literal["subject", "manufacturer", "competitor"]
ManufacturerClassification = Literal[
    "exact_current",
    "exact_older",
    "exact_regional",
    "product_family",
    "near_match",
    "not_applicable",
]


class Provenance(BaseModel):
    kind: SourceKind
    url: str
    note: Optional[str] = None


class Specification(BaseModel):
    name: str
    value: str
    unit: Optional[str] = None
    sources: list[Provenance] = Field(default_factory=list)


class FeatureBullet(BaseModel):
    feature: str
    benefit: Optional[str] = None
    sources: list[Provenance] = Field(default_factory=list)


class FAQ(BaseModel):
    question: str
    answer: str
    sources: list[Provenance] = Field(default_factory=list)


class CustomerConcern(BaseModel):
    concern: str
    response: str
    sources: list[Provenance] = Field(default_factory=list)


class DocumentLink(BaseModel):
    label: str
    url: str


class SubjectExtract(BaseModel):
    """Raw structured extraction from the subject PDP (Step 1)."""

    url: str
    h1: Optional[str] = None
    title: Optional[str] = None
    brand: Optional[str] = None
    manufacturer: Optional[str] = None
    mpn: Optional[str] = None
    sku: Optional[str] = None
    product_type: Optional[str] = None
    overview: Optional[str] = None
    descriptions: list[str] = Field(default_factory=list)
    feature_bullets: list[str] = Field(default_factory=list)
    benefits: list[str] = Field(default_factory=list)
    applications: list[str] = Field(default_factory=list)
    specifications: list[Specification] = Field(default_factory=list)
    dimensions: Optional[str] = None
    weight: Optional[str] = None
    materials: Optional[str] = None
    compatibility: list[str] = Field(default_factory=list)
    installation_notes: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    documents: list[DocumentLink] = Field(default_factory=list)
    warranty: Optional[str] = None
    faqs: list[FAQ] = Field(default_factory=list)
    reviews: list[str] = Field(default_factory=list)
    structured_data: dict = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class IdentityLock(BaseModel):
    """Step 2 output: locked product identity used for downstream search."""

    brand: Optional[str] = None
    manufacturer: Optional[str] = None
    mpn: Optional[str] = None
    series: Optional[str] = None
    product_type: Optional[str] = None
    output_or_capacity: Optional[str] = None
    sku: Optional[str] = None
    gtin: Optional[str] = None
    upc: Optional[str] = None
    ean: Optional[str] = None
    model_number: Optional[str] = None
    ambiguous: bool = False
    ambiguity_notes: list[str] = Field(default_factory=list)


class ManufacturerSource(BaseModel):
    url: str
    title: Optional[str] = None
    classification: ManufacturerClassification
    type: Literal[
        "product_page",
        "datasheet",
        "manual",
        "compliance",
        "certificate",
        "drawing",
        "catalog",
        "other",
    ] = "product_page"
    summary: Optional[str] = None


class ManufacturerVerification(BaseModel):
    """Step 3 output."""

    sources: list[ManufacturerSource] = Field(default_factory=list)
    verified_specs: list[Specification] = Field(default_factory=list)
    verified_features: list[FeatureBullet] = Field(default_factory=list)
    verified_certifications: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class CompetitorCandidate(BaseModel):
    url: str
    title: str
    domain: str
    snippet: Optional[str] = None
    matched_query: Optional[str] = None
    confidence: float = 0.0
    rejected_reason: Optional[str] = None
    accepted: bool = False


class CompetitorList(BaseModel):
    """Step 4 output (pre-extraction)."""

    queries_run: list[str] = Field(default_factory=list)
    candidates: list[CompetitorCandidate] = Field(default_factory=list)
    accepted_count: int = 0
    requested_count: int = 0


class CompetitorExtract(BaseModel):
    """Per-competitor extraction (used inside Step 5 list)."""

    url: str
    title: Optional[str] = None
    brand: Optional[str] = None
    mpn: Optional[str] = None
    sku: Optional[str] = None
    description: Optional[str] = None
    feature_bullets: list[str] = Field(default_factory=list)
    benefits: list[str] = Field(default_factory=list)
    applications: list[str] = Field(default_factory=list)
    specifications: list[Specification] = Field(default_factory=list)
    dimensions: Optional[str] = None
    weight: Optional[str] = None
    materials: Optional[str] = None
    compatibility: list[str] = Field(default_factory=list)
    included_components: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    warranty: Optional[str] = None
    faqs: list[FAQ] = Field(default_factory=list)
    customer_concerns: list[CustomerConcern] = Field(default_factory=list)
    documents: list[DocumentLink] = Field(default_factory=list)
    schema_values: dict = Field(default_factory=dict)


class CompetitorExtracts(BaseModel):
    """Step 5 output."""

    extracts: list[CompetitorExtract] = Field(default_factory=list)


GapCategory = Literal[
    "Product Identifier",
    "Technical Specification",
    "Feature",
    "Feature-Linked Benefit",
    "Application",
    "Compatibility / Selection Guidance",
    "Installation / Use Guidance",
    "Safety / Compliance Note",
    "Material / Construction Detail",
    "Dimension / Fit Detail",
    "FAQ",
    "Customer Concern / Objection",
    "Warranty / Support Detail",
    "Schema Attribute",
    "Excluded Claim",
]


class GapRow(BaseModel):
    content_element: str
    category: GapCategory
    missing_from_subject: bool
    manufacturer_verified: bool
    competitor_count: int
    competitor_sources: list[str] = Field(default_factory=list)
    included: bool
    reason: str
    proposed_value: Optional[str] = None


class ExcludedRow(BaseModel):
    excluded_element: str
    source_found: str
    reason_excluded: str


class GapValidation(BaseModel):
    """Step 6 output."""

    rows: list[GapRow] = Field(default_factory=list)
    excluded: list[ExcludedRow] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)


class FinalCopy(BaseModel):
    """Step 7 output: clean WYSIWYG-style structured copy."""

    h1: str
    identity_block: list[str] = Field(default_factory=list)
    h2: str
    overview: str
    features: list[FeatureBullet] = Field(default_factory=list)
    applications: list[str] = Field(default_factory=list)
    specifications: list[Specification] = Field(default_factory=list)
    faqs: list[FAQ] = Field(default_factory=list)
    customer_concerns: list[CustomerConcern] = Field(default_factory=list)


class HtmlCopy(BaseModel):
    """Step 8 output."""

    html: str


class JsonLdProduct(BaseModel):
    """Step 9 output. Stored as a free-form dict to allow nesting."""

    json_ld: dict


class FinalOutput(BaseModel):
    """Step 10 output."""

    research_summary: str
    identity_lock: IdentityLock
    source_quality_notes: str
    gap_validation: GapValidation
    excluded: list[ExcludedRow]
    final_copy: FinalCopy
    html_copy: HtmlCopy
    json_ld: dict
    sources: list[dict]


# API request/response models


class CreateRunRequest(BaseModel):
    subject_url: HttpUrl
    n_competitors: int = Field(5, ge=1, le=20)
    style_guide_id: Optional[int] = None


class CheckpointApproval(BaseModel):
    """Generic checkpoint payload. Body should match the checkpoint's schema."""

    edited_payload: dict


class BulkOptions(BaseModel):
    """Options for a bulk batch (mirrors run start + checkpoint policies)."""

    n_competitors: int = Field(5, ge=1, le=20)
    style_guide_id: Optional[int] = None
    min_competitor_confidence: float = Field(0.35, ge=0.0, le=1.0)
    domain_blocklist: list[str] = Field(default_factory=list)
    min_distinct_competitor_domains: int = Field(2, ge=1, le=20)


class CreateBatchRequest(BaseModel):
    name: Optional[str] = Field(default=None, max_length=120)
    urls: list[HttpUrl] = Field(..., min_length=1)
    options: BulkOptions = Field(default_factory=BulkOptions)
