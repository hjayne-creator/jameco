import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, RunSummary } from "../api/client";
import { StatusPill } from "../components/StatusPill";

export function RunHistory() {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.listRuns().then((r) => {
      setRuns(r);
      setLoading(false);
    });
  }, []);

  return (
    <>
      <h1>Run history</h1>
      {loading && <p className="muted">Loading...</p>}
      {!loading && runs.length === 0 && (
        <p className="muted">No runs yet. Start one from the New Run page.</p>
      )}
      <div className="card" style={{ padding: 0 }}>
        {runs.map((r) => (
          <Link
            to={`/runs/${r.id}`}
            key={r.id}
            style={{
              display: "grid",
              gridTemplateColumns: "60px 1fr 130px 90px 110px 160px",
              gap: 12,
              padding: "12px 16px",
              borderBottom: "1px solid var(--border)",
              color: "var(--text)",
              alignItems: "center",
            }}
          >
            <span className="mono">#{r.id}</span>
            <span className="mono small">{r.subject_url}</span>
            <StatusPill status={r.status} />
            <span className="small muted">step {r.current_step}/10</span>
            <span className="small muted">
              ${(r.llm_total_cost_usd ?? 0).toFixed(4)}
            </span>
            <span className="small muted">{new Date(r.updated_at).toLocaleString()}</span>
          </Link>
        ))}
      </div>
    </>
  );
}
