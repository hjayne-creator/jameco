import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, BatchDetail } from "../api/client";
import { BulkReportPanel } from "../components/BulkReportPanel";
import { StatusPill } from "../components/StatusPill";

const POLL_MS = 2000;

type BatchTab = "progress" | "report";

export function BulkJobDetail() {
  const { id } = useParams<{ id: string }>();
  const batchId = id ? parseInt(id, 10) : null;
  const [data, setData] = useState<BatchDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<BatchTab>("progress");
  const [reconciling, setReconciling] = useState(false);

  useEffect(() => {
    if (batchId == null) return;
    const load = () =>
      api
        .getBatch(batchId)
        .then(setData)
        .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"));
    load();
    const t = setInterval(load, POLL_MS);
    return () => clearInterval(t);
  }, [batchId]);

  if (batchId == null) return <p>Invalid batch id</p>;
  if (error) return <p style={{ color: "var(--bad)" }}>{error}</p>;
  if (!data) return <p className="muted">Loading batch #{batchId}…</p>;

  const pct = data.progress_percent;

  return (
    <>
      <p className="small muted">
        <Link to="/bulk">← Bulk jobs</Link>
      </p>
      <div className="row" style={{ justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <h1 style={{ margin: 0 }}>{data.name?.trim() || `Batch ${data.id}`}</h1>
          <p className="small muted" style={{ marginTop: 6, marginBottom: 0 }}>
            Batch #{data.id}
          </p>
          <p className="muted" style={{ marginTop: 8 }}>
            Processing {data.finished_urls} of {data.total_urls} ({pct}%)
          </p>
          <p className="small muted" style={{ marginTop: 6, marginBottom: 0 }}>
            LLM cost: ${(data.llm_total_cost_usd ?? 0).toFixed(4)} ({data.llm_total_tokens ?? 0} tokens)
          </p>
        </div>
        <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
          <StatusPill status={data.status} />
          {data.status === "running" && (
            <button
              type="button"
              className="secondary"
              disabled={reconciling}
              title="If every URL already finished but the batch still says Running, refresh status from the database."
              onClick={async () => {
                setReconciling(true);
                try {
                  await api.reconcileBatch(batchId);
                  const full = await api.getBatch(batchId);
                  setData(full);
                } catch (e) {
                  setError(e instanceof Error ? e.message : "Reconcile failed");
                } finally {
                  setReconciling(false);
                }
              }}
            >
              {reconciling ? "Recalculating…" : "Recalculate status"}
            </button>
          )}
          <a className="btn secondary" href={api.batchCsvDownloadUrl(batchId)} download>
            Download CSV
          </a>
        </div>
      </div>

      {data.error && (
        <div
          className="card"
          style={{ marginTop: 14, borderColor: "var(--bad)", color: "var(--bad)" }}
        >
          <strong>Batch issue</strong>
          <p style={{ margin: "8px 0 0", whiteSpace: "pre-wrap", fontSize: 14 }}>{data.error}</p>
        </div>
      )}

      <div className="tabs" style={{ marginTop: 20 }}>
        <button type="button" className={tab === "progress" ? "active" : ""} onClick={() => setTab("progress")}>
          Progress
        </button>
        <button type="button" className={tab === "report" ? "active" : ""} onClick={() => setTab("report")}>
          Results report
        </button>
      </div>

      {tab === "progress" && (
        <>
          <div className="card" style={{ marginTop: 16 }}>
            <h3 style={{ marginTop: 0 }}>Options snapshot</h3>
            <pre className="code-block" style={{ fontSize: 12 }}>
              {JSON.stringify(data.options_snapshot, null, 2)}
            </pre>
          </div>

          <h2 style={{ marginTop: 24 }}>URLs</h2>
          <div className="card" style={{ padding: 0 }}>
            {data.runs.map((r) => (
              <div
                key={r.id}
                style={{
                  display: "grid",
                  gridTemplateColumns: "56px 1fr 100px 100px 110px 160px",
                  gap: 10,
                  padding: "10px 14px",
                  borderBottom: "1px solid var(--border)",
                  alignItems: "center",
                }}
              >
                <span className="mono small">
                  <Link to={`/runs/${r.id}`}>#{r.id}</Link>
                </span>
                <span className="mono small" style={{ overflow: "hidden", textOverflow: "ellipsis" }}>
                  {r.subject_url}
                </span>
                <StatusPill status={r.status} />
                <span className="small muted">{r.terminal_reason || "—"}</span>
                <span className="small muted">${(r.llm_total_cost_usd ?? 0).toFixed(4)}</span>
                <span className="small muted">{new Date(r.updated_at).toLocaleString()}</span>
              </div>
            ))}
          </div>
        </>
      )}

      {tab === "report" && batchId != null && <BulkReportPanel batchId={batchId} />}
    </>
  );
}
