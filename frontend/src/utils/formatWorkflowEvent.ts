import type { StreamEvent } from "../hooks/useRunStream";

/** Mirrors `backend/app/workflow/registry.py` STEP labels for display when payload omits `label`. */
const STEP_LABELS: Record<number, string> = {
  1: "Subject Page Extraction",
  2: "Product Identity Lock",
  3: "Manufacturer Verification",
  4: "Competitor Discovery",
  5: "Competitor Extraction",
  6: "Gap Validation",
  7: "Final PDP Copy",
  8: "HTML PDP Copy",
  9: "JSON-LD Schema",
  10: "Final Output Assembly",
};

const CHECKPOINT_TITLES: Record<string, string> = {
  identity: "Identity Lock",
  competitors: "Competitor List",
  gaps: "Gap Validation",
  final_copy: "Final Copy",
};

const BULK_SKIP_SUMMARY: Record<string, string> = {
  skipped_ambiguous_identity: "Batch policy: ambiguous product identity — run stopped for this URL",
  skipped_empty_identity: "Batch policy: missing product identifiers — run stopped for this URL",
  skipped_no_competitors: "Batch policy: no competitors passed auto-selection — run stopped for this URL",
};

function stepTitle(p: Record<string, unknown>): string {
  const n = p.step_no as number | undefined;
  const label = typeof p.label === "string" ? p.label : null;
  const name = typeof p.name === "string" ? p.name : null;
  if (label) return label;
  if (n != null && STEP_LABELS[n]) return STEP_LABELS[n];
  if (name) return name;
  return n != null ? `Step ${n}` : "Step";
}

/** One-line description for the run Activity log (not the raw SSE `type`). */
export function formatWorkflowEventDescription(e: StreamEvent): string {
  const p = (e.payload || {}) as Record<string, unknown>;

  switch (e.type) {
    case "run.started":
      return p.bulk ? "Pipeline started (bulk / auto checkpoints)" : "Pipeline started";

    case "run.completed":
      return p.bulk ? "Pipeline finished — all steps done (bulk)" : "Pipeline finished — all steps done";

    case "run.error": {
      const msg = typeof p.message === "string" ? p.message : String(p.message ?? "Unknown error");
      const first = msg.split("\n")[0].trim();
      return `Run failed — ${first || "Unknown error"}`;
    }

    case "run.bulk_failed": {
      const n = p.step_no as number | undefined;
      const st = n != null ? stepTitle(p) : "Pipeline";
      const msg = typeof p.message === "string" ? p.message : "";
      return `Bulk run failed during “${st}” — ${msg || "see logs"}`;
    }

    case "run.bulk_skipped": {
      const reason = typeof p.reason === "string" ? p.reason : "";
      const base = BULK_SKIP_SUMMARY[reason] || `Batch run stopped — ${reason || "policy"}`;
      const n = p.step_no as number | undefined;
      if (n != null && STEP_LABELS[n]) {
        return `${base} (after step ${n}: ${STEP_LABELS[n]})`;
      }
      return base;
    }

    case "step.started":
      return `${stepTitle(p)} — started (step ${p.step_no ?? "?"})`;

    case "step.completed": {
      const ms = p.duration_ms != null ? `${p.duration_ms} ms` : "done";
      return `${stepTitle(p)} — finished in ${ms}`;
    }

    case "step.skipped":
      return `${stepTitle(p)} — skipped (already saved from earlier run)`;

    case "step.progress": {
      const n = p.step_no as number | undefined;
      const base = n != null ? `${stepTitle(p)} (step ${n})` : stepTitle(p);
      const msg = typeof p.message === "string" ? p.message : "";
      return msg ? `${base}: ${msg}` : `${base}: working…`;
    }

    case "step.error": {
      const msg = typeof p.message === "string" ? p.message : "";
      return `${stepTitle(p)} — error: ${msg || "see step details"}`;
    }

    case "checkpoint.pause": {
      const ck = typeof p.name === "string" ? p.name : "";
      const title = CHECKPOINT_TITLES[ck] || ck || "checkpoint";
      const n = p.step_no as number | undefined;
      return `Paused for your review — ${title}${n != null ? ` (after step ${n})` : ""}`;
    }

    case "checkpoint.approved": {
      const ck = typeof p.name === "string" ? p.name : "";
      const title = (typeof p.label === "string" && p.label) || CHECKPOINT_TITLES[ck] || ck;
      return `Checkpoint approved — ${title}; resuming pipeline`;
    }

    default:
      return e.type;
  }
}
