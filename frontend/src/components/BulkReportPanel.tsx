import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, BatchReport, BatchReportRun, StepRecord } from "../api/client";
import { FinalOutputTabs } from "./FinalOutputTabs";
import { StatusPill } from "./StatusPill";

const POLL_MS = 3000;

function runTitle(run: BatchReportRun): string {
  const s7 = run.steps?.find((s) => s.step_no === 7);
  const h1 = s7?.output?.h1;
  if (typeof h1 === "string" && h1.trim()) return h1.trim();
  return run.subject_url;
}

export function BulkReportPanel({ batchId }: { batchId: number }) {
  const [report, setReport] = useState<BatchReport | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    const load = () =>
      api
        .getBatchReport(batchId)
        .then((r) => {
          setReport(r);
          setErr(null);
        })
        .catch((e) => setErr(e instanceof Error ? e.message : "Failed to load report"));
    load();
    const t = setInterval(load, POLL_MS);
    return () => clearInterval(t);
  }, [batchId]);

  if (err) {
    return (
      <p className="card" style={{ color: "var(--bad)" }}>
        {err}
      </p>
    );
  }
  if (!report) {
    return <p className="muted">Loading results…</p>;
  }

  const doneWithOutputs = report.runs.filter((r) => r.status === "done" && r.steps && r.steps.length > 0);
  const doneIncomplete = report.runs.filter((r) => r.status === "done" && (!r.steps || r.steps.length === 0));
  const otherRuns = report.runs.filter((r) => r.status !== "done" || !r.steps?.length);

  return (
    <div style={{ marginTop: 20 }}>
      <p className="muted" style={{ marginBottom: 16 }}>
        Completed runs include the same WYSIWYG, HTML, JSON-LD, sources, and audit bundle as a single-URL run.
        Expand a row to review or use the run link for the full step timeline.
      </p>

      {doneWithOutputs.length === 0 && report.runs.every((r) => r.status !== "done") && (
        <p className="card muted">No completed runs yet. Check back when the batch finishes processing.</p>
      )}

      {doneIncomplete.length > 0 && (
        <div className="card" style={{ borderColor: "var(--warn)", marginBottom: 16 }}>
          <strong>{doneIncomplete.length} run(s)</strong> are marked done but have no step 7–10 output in the database
          (unexpected). Open the run for details:{" "}
          {doneIncomplete.map((r) => (
            <Link key={r.id} to={`/runs/${r.id}`} style={{ marginRight: 8 }}>
              #{r.id}
            </Link>
          ))}
        </div>
      )}

      {doneWithOutputs.map((run) => {
        const tabsSources = (run.sources ?? []).map((s) => ({
          url: s.url,
          kind: s.kind,
          title: s.title,
        }));
        const steps = (run.steps ?? []) as StepRecord[];
        return (
          <details
            key={run.id}
            className="card bulk-report-run"
            style={{ marginBottom: 14, padding: "12px 14px" }}
          >
            <summary
              style={{
                cursor: "pointer",
                listStyle: "none",
              }}
            >
              <div
                style={{
                  display: "flex",
                  flexWrap: "wrap",
                  alignItems: "center",
                  gap: "8px 12px",
                }}
              >
                <span className="mono small">
                  <Link to={`/runs/${run.id}`} onClick={(e) => e.stopPropagation()}>
                    #{run.id}
                  </Link>
                </span>
                <StatusPill status={run.status} />
                <span style={{ fontWeight: 600 }}>{runTitle(run)}</span>
              </div>
              <div
                className="small mono muted"
                style={{
                  marginTop: 6,
                  wordBreak: "break-all",
                  lineHeight: 1.45,
                }}
              >
                {run.subject_url}
              </div>
            </summary>
            <div style={{ marginTop: 16 }}>
              <FinalOutputTabs steps={steps} sources={tabsSources} />
            </div>
          </details>
        );
      })}

      {otherRuns.length > 0 && (
        <>
          <h3 style={{ marginTop: 28 }}>Other outcomes</h3>
          <p className="small muted">Skipped, failed, or still processing (no full PDP bundle yet).</p>
          <div className="card" style={{ padding: 0 }}>
            {otherRuns.map((run) => (
              <div
                key={run.id}
                style={{
                  display: "grid",
                  gridTemplateColumns: "56px 1fr 100px minmax(140px, 1fr)",
                  gap: 10,
                  padding: "10px 14px",
                  borderBottom: "1px solid var(--border)",
                  alignItems: "center",
                }}
              >
                <span className="mono small">
                  <Link to={`/runs/${run.id}`}>#{run.id}</Link>
                </span>
                <span className="mono small" style={{ overflow: "hidden", textOverflow: "ellipsis" }}>
                  {run.subject_url}
                </span>
                <StatusPill status={run.status} />
                <span className="small muted">{run.terminal_reason || run.error || "—"}</span>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
