import { useState } from "react";

export interface GapRow {
  content_element: string;
  category: string;
  missing_from_subject: boolean;
  manufacturer_verified: boolean;
  competitor_count: number;
  competitor_sources: string[];
  included: boolean;
  reason: string;
  proposed_value?: string | null;
}

export interface ExcludedRow {
  excluded_element: string;
  source_found: string;
  reason_excluded: string;
}

export interface GapValidationShape {
  rows: GapRow[];
  excluded: ExcludedRow[];
  conflicts: string[];
}

interface Props {
  initial: GapValidationShape;
  onApprove: (edited: GapValidationShape) => Promise<void>;
}

export function GapTableEditor({ initial, onApprove }: Props) {
  const [rows, setRows] = useState<GapRow[]>(initial.rows);
  const [busy, setBusy] = useState(false);

  const toggle = (idx: number) => {
    setRows((prev) => {
      const copy = [...prev];
      const r = { ...copy[idx] };
      const allowed = r.manufacturer_verified || r.competitor_count >= 2;
      if (!allowed && !r.included) return prev; // can't include
      r.included = !r.included;
      copy[idx] = r;
      return copy;
    });
  };

  const includedCount = rows.filter((r) => r.included).length;

  return (
    <div className="card">
      <h3>Checkpoint: Gap Validation</h3>
      <p className="muted small">
        Toggle each row to control what feeds the final copy. Rows that are
        neither manufacturer-verified nor backed by 2+ competitor domains cannot
        be included.
      </p>
      <p className="small">{includedCount} of {rows.length} rows included.</p>

      {initial.conflicts.length > 0 && (
        <div className="card" style={{ background: "var(--panel-2)", borderColor: "var(--warn)" }}>
          <div className="small" style={{ color: "var(--warn)", fontWeight: 600 }}>
            Conflicts flagged
          </div>
          <ul className="small">
            {initial.conflicts.map((c, i) => (
              <li key={i}>{c}</li>
            ))}
          </ul>
        </div>
      )}

      <div style={{ marginTop: 12 }}>
        <div className="gap-row" style={{ background: "var(--panel-2)", fontWeight: 600 }}>
          <span>Inc.</span>
          <span>Content element / reason</span>
          <span>MFR</span>
          <span>Competitors</span>
          <span>Category</span>
        </div>
        {rows.map((r, idx) => {
          const allowed = r.manufacturer_verified || r.competitor_count >= 2;
          return (
            <div className="gap-row" key={idx}>
              <input
                type="checkbox"
                disabled={!allowed}
                checked={r.included}
                onChange={() => toggle(idx)}
                title={allowed ? "" : "Not eligible: needs MFR verification or 2+ competitor domains"}
              />
              <div>
                <div style={{ fontWeight: 500 }}>{r.content_element}</div>
                <div className="small muted">{r.reason}</div>
                {r.proposed_value && (
                  <div className="small mono" style={{ marginTop: 2 }}>{r.proposed_value}</div>
                )}
              </div>
              <span className="small">{r.manufacturer_verified ? "yes" : "no"}</span>
              <span className="small">{r.competitor_count}</span>
              <span className="cat">{r.category}</span>
            </div>
          );
        })}
      </div>

      {initial.excluded.length > 0 && (
        <>
          <h4>Explicit exclusions</h4>
          <div className="card" style={{ background: "var(--panel-2)", padding: 8 }}>
            {initial.excluded.map((e, i) => (
              <div key={i} className="small" style={{ padding: "6px 0", borderBottom: "1px solid var(--border)" }}>
                <strong>{e.excluded_element}</strong> — <span className="muted">{e.reason_excluded}</span>
                <div className="mono small muted">{e.source_found}</div>
              </div>
            ))}
          </div>
        </>
      )}

      <div className="row right" style={{ marginTop: 16 }}>
        <button
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            try {
              await onApprove({ rows, excluded: initial.excluded, conflicts: initial.conflicts });
            } finally {
              setBusy(false);
            }
          }}
        >
          {busy ? "Approving..." : `Approve ${includedCount} rows & generate copy`}
        </button>
      </div>
    </div>
  );
}
