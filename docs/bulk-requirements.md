# Bulk PDP workflow — requirements

This document captures approved product and behavior requirements for **bulk** processing of PDP URLs. It does **not** change the existing **single-URL** flow (checkpoints, UX, and orchestration remain as today).

## Goals

- Process **many URLs in one batch**, **one URL at a time** (serial, sequential within that batch).
- Use the **same analysis pipeline** as single-URL runs (shared core steps and schemas), with **no interactive checkpoints** during execution.
- Before a batch starts, the user configures an **Options** section that supplies everything the four checkpoints would have provided or constrained, so the run can **auto-approve** through the equivalent of each checkpoint.
- Persist results for **DB storage** and **CSV export**.
- Jobs run **entirely on the server**: progress is observable via **polling** (not tied to a browser tab or WebSocket session). Closing the browser does not stop work.
- **Throughput cap:** maximum URLs per batch is **config-driven** (default **100** in v1).

## Non-goals (v1)

- Replacing or removing the single-URL checkpointed experience.
- Parallel execution of URLs within a batch.
- **Per-item retry** after system failure (user may re-submit a new batch or URL manually).

## Architecture stance

- **One application**, **two orchestration paths**: single run (session + checkpoints) vs. batch job (queue + serial runner + auto-approval). Shared domain logic analyzes one PDP; batch mode wraps it with batch-specific persistence and policies.
- **Data model (approved):** each bulk URL is a **`Run` row linked to a parent batch** (`batch_id` on `Run`, nullable for single-URL runs). Reuses `StepResult` and existing step schemas. The **batch** entity holds queue metadata, options snapshot, and aggregate status.
- **Multiple batches:** users may submit **more than one** bulk job; new work is **enqueued**. A server-side worker processes the queue so **only one PDP pipeline executes at a time** globally in v1 (simple serialization). Ordering: **FIFO** unless a later requirement adds priority.

## Options (batch configuration)

Options mirror **run-start settings** plus **policy** for each former checkpoint. One Options object applies to **every URL** in the batch (v1).

### Already aligned with single-run start

| Option | Description |
|--------|-------------|
| `n_competitors` | Same semantics as today (e.g. 1–20): target competitor PDP count for discovery / extraction. |
| `style_guide_id` | Optional; same as single run when a style guide is selected. |

### Identity Lock (checkpoint `identity`)

- **Default:** Auto-continue using model-produced `IdentityLock` from step 2 when allowed by policy below.
- **Skip if** `ambiguous === true`. Do not continue the pipeline for that URL. **Terminal reason:** `skipped_ambiguous_identity`.
- **Skip if** `ambiguous === false` but identity is **effectively empty** (no usable primary identifiers for downstream search — implement with an explicit predicate, e.g. all of brand, manufacturer, MPN, SKU, GTIN/UPC/EAN, model_number absent or blank). **Terminal reason:** `skipped_empty_identity`.

### Competitor List (checkpoint `competitors`)

- **Auto-selection policy:** user-configurable in Options (thresholds, blocklist, top-K, etc.). **Default policy (v1 recommendation):** sort candidates by `confidence` descending; accept the **top `n_competitors`** candidates whose `confidence >= 0.35` (default floor, configurable in Options); then apply **domain blocklist** (user-supplied list drops candidates before counting toward K). If fewer than K pass the floor, accept all that pass the floor (may be zero). Document default floor and K in the options snapshot.
- **Skip if**, after applying the policy, **zero** competitors are accepted. **Terminal reason:** `skipped_no_competitors`.

### Gap Validation (checkpoint `gaps`)

- **Eligibility rule:** defaults match today’s `step6_gap_validation` enforcement: a row may be included if **`manufacturer_verified`** **or** the row has evidence from at least **`min_distinct_competitor_domains`** distinct competitor domains (default **2**, same as current `>= 2` behavior). Options may lower this (e.g. **1**) for bulk only; values below 1 are invalid.
- **After** eligibility is evaluated in code, set **`included: true` for every row that is eligible** and **`included: false` for ineligible rows** (do not leave eligible rows false because the model was conservative). Do **not** force ineligible rows to be included.

### Final Copy (checkpoint `final_copy`)

- **Default:** Auto-approve **unmodified** step-7 model output (`FinalCopy`) unless future options say otherwise.

## Policy skips vs system failures

| Outcome | Meaning | Batch behavior |
|--------|---------|----------------|
| **Skipped** | Policy decision (ambiguous identity, empty identity, zero competitors after policy, etc.). | Item terminal **skipped** + reason; **batch continues** to next URL. |
| **Failed** | System failure: LLM error, fetch failure, timeout, unhandled exception, etc. | Item terminal **failed** + error detail safe for logs/support; **batch continues**; **no automatic retry** in v1. |

Skipped and failed items **both** persist a **Run** (or batch-item) **row** with terminal status and reason so the DB and CSV stay complete.

## Skip / fail behavior (per URL)

- Terminal **skipped** or **failed** URL: remaining pipeline steps for **that URL** do not run.
- The **batch continues** with the next URL (no “abort entire batch on first failure” in v1).

## Snapshots

- When a batch is created, persist a **snapshot** of the full **Options** payload (and any resolved defaults) on the batch record.
- Snapshots are **immutable** for that batch id so exports, audits, and support can see exactly what ran.

## Run history / navigation

- **Separate list** (and API surface) for bulk batches vs. existing single-PDP **Run** history (`batch_id` IS NULL), so checkpointed runs are not mixed with auto batch jobs in the primary run history UI.
- Bulk UI shows aggregate progress via **polling** (e.g. “Processing 3 of 10 (30%)” from batch counts), independent of browser session.

## Export

- **CSV:** generated **on demand** when the user chooses **Download CSV**; **one row per URL** (including skipped and failed rows with status and terminal reason).
- **DB:** same per-URL facts as today’s run storage, plus **batch id** and access to **snapshotted options** on the batch for audit (exact column set for CSV defined at implementation time).

## Edge cases

- **Duplicate URLs** in the submitted list: **dedupe** (normalize URL, keep first occurrence order) before creating runs.
- **Max URLs per batch:** enforced from **config** (default 100).
- **Concurrent bulk jobs:** allowed; execution **queued** server-side (see Architecture stance).

## References in codebase

- Step and checkpoint catalog: `backend/app/workflow/registry.py` (`CHECKPOINT_AFTER_STEP`, `STEPS`).
- Gap inclusion enforcement: `backend/app/workflow/steps/step6_gap_validation.py` (`_enforce_inclusion_rules` — bulk mode extends with configurable minimum domains and post-enforcement `included` assignment).
- Checkpoint approval API: `backend/app/api/checkpoints.py`; payload schemas in `backend/app/models/schemas.py` (`IdentityLock`, `CompetitorList`, `GapValidation`, `FinalCopy`, `CreateRunRequest`).
