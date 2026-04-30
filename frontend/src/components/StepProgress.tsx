import { StepRecord } from "../api/client";

const STEP_LABELS: Record<number, string> = {
  1: "Subject Extraction",
  2: "Identity Lock",
  3: "Manufacturer Verification",
  4: "Competitor Discovery",
  5: "Competitor Extraction",
  6: "Gap Validation",
  7: "Final PDP Copy",
  8: "HTML PDP Copy",
  9: "JSON-LD Schema",
  10: "Final Assembly",
};

interface Props {
  steps: StepRecord[];
  currentStep: number;
}

export function StepProgress({ steps, currentStep }: Props) {
  const byNo = new Map(steps.map((s) => [s.step_no, s]));
  return (
    <div className="step-rail">
      {Array.from({ length: 10 }, (_, i) => i + 1).map((no) => {
        const s = byNo.get(no);
        let cls = "step-row";
        if (s?.status === "completed") cls += " completed";
        else if (s?.status === "running" || (no === currentStep && !s)) cls += " running";
        else if (s?.status === "error") cls += " error";
        return (
          <div key={no} className={cls}>
            <div className="dot" />
            <div>
              <div style={{ fontWeight: 500 }}>{no}. {STEP_LABELS[no]}</div>
              {s?.duration_ms != null && (
                <div className="small muted">{(s.duration_ms / 1000).toFixed(1)}s</div>
              )}
              {s?.error && <div className="small" style={{ color: "var(--bad)" }}>{s.error}</div>}
            </div>
            <div className="small muted">{s?.status ?? "—"}</div>
          </div>
        );
      })}
    </div>
  );
}
