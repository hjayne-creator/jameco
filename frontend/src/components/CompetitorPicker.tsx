import { useState } from "react";

export interface Candidate {
  url: string;
  title: string;
  domain: string;
  snippet?: string | null;
  matched_query?: string | null;
  confidence: number;
  rejected_reason?: string | null;
  accepted: boolean;
}

export interface CompetitorListShape {
  queries_run: string[];
  candidates: Candidate[];
  accepted_count: number;
  requested_count: number;
}

interface Props {
  initial: CompetitorListShape;
  onApprove: (edited: CompetitorListShape) => Promise<void>;
}

export function CompetitorPicker({ initial, onApprove }: Props) {
  const [candidates, setCandidates] = useState<Candidate[]>(initial.candidates);
  const [busy, setBusy] = useState(false);

  const toggle = (idx: number) => {
    setCandidates((prev) => {
      const copy = [...prev];
      const c = { ...copy[idx] };
      c.accepted = !c.accepted;
      if (c.accepted) c.rejected_reason = null;
      copy[idx] = c;
      return copy;
    });
  };

  const acceptedCount = candidates.filter((c) => c.accepted).length;

  return (
    <div className="card">
      <h3>Checkpoint: Competitor List</h3>
      <p className="muted small">
        Toggle which exact-match competitor PDPs the workflow should extract.
        Removing weak or wrong-product matches saves time and money.
      </p>
      <p className="small">
        {acceptedCount} accepted / {initial.requested_count} requested.
      </p>
      <div className="card" style={{ background: "var(--panel-2)" }}>
        <div className="small muted" style={{ marginBottom: 6 }}>
          Queries run
        </div>
        <div className="mono small">
          {initial.queries_run.map((q, i) => (
            <div key={i}>• {q}</div>
          ))}
        </div>
      </div>
      <div style={{ marginTop: 12 }}>
        {candidates.map((c, idx) => (
          <div key={c.url} className="candidate-row">
            <input type="checkbox" checked={c.accepted} onChange={() => toggle(idx)} />
            <div>
              <div style={{ fontWeight: 500 }}>{c.title || c.url}</div>
              <div className="url">{c.url}</div>
              {c.snippet && <div className="small muted">{c.snippet}</div>}
              {c.rejected_reason && (
                <div className="small" style={{ color: "var(--warn)" }}>
                  reason: {c.rejected_reason}
                </div>
              )}
            </div>
            <div className="small muted">{(c.confidence * 100).toFixed(0)}%</div>
            <div className="small mono">{c.domain}</div>
          </div>
        ))}
      </div>
      <div className="row right" style={{ marginTop: 16 }}>
        <button
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            try {
              await onApprove({
                ...initial,
                candidates,
                accepted_count: acceptedCount,
              });
            } finally {
              setBusy(false);
            }
          }}
        >
          {busy ? "Approving..." : `Approve ${acceptedCount} competitors & continue`}
        </button>
      </div>
    </div>
  );
}
