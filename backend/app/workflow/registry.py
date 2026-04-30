"""Step + checkpoint registry. Single source of truth for ordering + names."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional


CHECKPOINT_AFTER_STEP: dict[int, str] = {
    2: "identity",       # After Identity Lock
    4: "competitors",    # After Competitor List
    6: "gaps",           # After Gap Validation Table
    7: "final_copy",     # After Final WYSIWYG Copy
}


@dataclass
class StepDefinition:
    step_no: int
    name: str
    label: str
    checkpoint: Optional[str] = None


STEPS: list[StepDefinition] = [
    StepDefinition(1, "subject_extract", "Subject Page Extraction"),
    StepDefinition(2, "identity_lock", "Product Identity Lock", checkpoint="identity"),
    StepDefinition(3, "manufacturer_verification", "Manufacturer Verification"),
    StepDefinition(4, "competitor_discovery", "Competitor Discovery", checkpoint="competitors"),
    StepDefinition(5, "competitor_extraction", "Competitor Extraction"),
    StepDefinition(6, "gap_validation", "Gap Validation", checkpoint="gaps"),
    StepDefinition(7, "final_copy", "Final PDP Copy", checkpoint="final_copy"),
    StepDefinition(8, "html_copy", "HTML PDP Copy"),
    StepDefinition(9, "json_ld", "JSON-LD Schema"),
    StepDefinition(10, "final_output", "Final Output Assembly"),
]


def step_by_no(step_no: int) -> StepDefinition:
    for s in STEPS:
        if s.step_no == step_no:
            return s
    raise KeyError(f"Unknown step {step_no}")


def step_by_checkpoint(name: str) -> StepDefinition:
    for s in STEPS:
        if s.checkpoint == name:
            return s
    raise KeyError(f"Unknown checkpoint {name}")
