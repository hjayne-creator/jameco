import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, BatchSummary } from "../api/client";
import { StatusPill } from "../components/StatusPill";

const POLL_MS = 2500;

export function BulkJobs() {
  const [batches, setBatches] = useState<BatchSummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = () =>
      api.listBatches().then((b) => {
        setBatches(b);
        setLoading(false);
      });
    load();
    const t = setInterval(load, POLL_MS);
    return () => clearInterval(t);
  }, []);

  return (
    <>
      <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
        <h1 style={{ margin: 0 }}>Bulk jobs</h1>
        <Link to="/bulk/new">
          <button type="button">New batch</button>
        </Link>
      </div>
      <p className="muted">Server-queued PDP batches (separate from single-URL run history).</p>
      {loading && <p className="muted">Loading…</p>}
      {!loading && batches.length === 0 && (
        <p className="muted">No batches yet. Create one to process many URLs without checkpoints.</p>
      )}
      <div className="card" style={{ padding: 0 }}>
        {batches.map((b) => (
          <div key={b.id} style={{ borderBottom: "1px solid var(--border)" }}>
            <Link
              to={`/bulk/${b.id}`}
              style={{
                display: "grid",
                gridTemplateColumns: "70px minmax(220px,1.4fr) 1fr 120px 140px 160px",
                gap: 12,
                padding: "12px 16px",
                color: "var(--text)",
                alignItems: "center",
              }}
            >
              <span className="mono">#{b.id}</span>
              <span className="small" style={{ fontWeight: 600 }}>{b.name?.trim() || `Batch ${b.id}`}</span>
              <span className="small">
                {b.finished_urls} / {b.total_urls} URLs
              </span>
              <StatusPill status={b.status} />
              <span className="small muted">
                {b.total_urls ? `${Math.round((100 * b.finished_urls) / b.total_urls)}%` : "—"}
              </span>
              <span className="small muted">{new Date(b.updated_at).toLocaleString()}</span>
            </Link>
            {b.error && (
              <div className="small" style={{ padding: "0 16px 12px", color: "var(--bad)", lineHeight: 1.4 }}>
                {b.error.length > 180 ? `${b.error.slice(0, 180)}…` : b.error}
              </div>
            )}
          </div>
        ))}
      </div>
    </>
  );
}
