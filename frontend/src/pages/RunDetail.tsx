import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { api, RunDetail as RunDetailType } from "../api/client";
import { useRunStream } from "../hooks/useRunStream";
import { StatusPill } from "../components/StatusPill";
import { StepProgress } from "../components/StepProgress";
import { CompetitorPicker } from "../components/CompetitorPicker";
import { GapTableEditor } from "../components/GapTableEditor";
import { IdentityEditor } from "../components/IdentityEditor";
import { CopyEditor } from "../components/CopyEditor";
import { FinalOutputTabs } from "../components/FinalOutputTabs";

const POLL_MS = 1500;

export function RunDetail() {
  const { id } = useParams<{ id: string }>();
  const runId = id ? parseInt(id, 10) : null;
  const [data, setData] = useState<RunDetailType | null>(null);
  const events = useRunStream(runId);

  const refresh = useCallback(async () => {
    if (runId == null) return;
    try {
      const d = await api.getRun(runId);
      setData(d);
    } catch (err) {
      console.error(err);
    }
  }, [runId]);

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, POLL_MS);
    return () => clearInterval(t);
  }, [refresh, events.length]);

  const checkpointName = useMemo(() => {
    if (!data?.status?.startsWith("awaiting_checkpoint:")) return null;
    return data.status.split(":")[1];
  }, [data?.status]);

  const stepByNo = useMemo(() => {
    const map = new Map<number, any>();
    data?.steps.forEach((s) => map.set(s.step_no, s));
    return map;
  }, [data]);

  if (runId == null) return <p>Bad run id</p>;
  if (!data) return <p className="muted">Loading run #{runId}...</p>;

  const onApprove = async (name: string, payload: any) => {
    await api.approveCheckpoint(runId, name, payload);
    await refresh();
  };

  return (
    <>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div>
          <h1 style={{ margin: 0 }}>Run #{data.id}</h1>
          <div className="mono small muted">{data.subject_url}</div>
        </div>
        <div className="row">
          <StatusPill status={data.status} />
          <button className="secondary" onClick={refresh}>Refresh</button>
          <button
            className="secondary"
            onClick={async () => {
              await api.restartRun(runId);
              refresh();
            }}
          >
            Restart
          </button>
        </div>
      </div>

      {data.error && (
        <div className="card" style={{ borderColor: "var(--bad)" }}>
          <strong style={{ color: "var(--bad)" }}>Error:</strong>
          <pre className="code-block">{data.error}</pre>
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "320px 1fr", gap: 18 }}>
        <div className="card" style={{ position: "sticky", top: 0 }}>
          <h3 style={{ marginTop: 0 }}>Steps</h3>
          <StepProgress steps={data.steps} currentStep={data.current_step} />
          <h3 style={{ marginTop: 16 }}>Activity</h3>
          <div className="activity-log">
            {events.length === 0 && <div className="line">(waiting for events)</div>}
            {events.map((e, i) => (
              <div key={i} className={e.type === "step.error" || e.type === "run.error" ? "line error" : "line"}>
                {new Date(e.receivedAt).toLocaleTimeString()} {e.type}{" "}
                {e.payload?.message ? `— ${e.payload.message}` : ""}
              </div>
            ))}
          </div>
        </div>

        <div>
          {checkpointName === "identity" && stepByNo.get(2)?.output && (
            <IdentityEditor
              initial={stepByNo.get(2).output}
              onApprove={(p) => onApprove("identity", p)}
            />
          )}
          {checkpointName === "competitors" && stepByNo.get(4)?.output && (
            <CompetitorPicker
              initial={stepByNo.get(4).output}
              onApprove={(p) => onApprove("competitors", p)}
            />
          )}
          {checkpointName === "gaps" && stepByNo.get(6)?.output && (
            <GapTableEditor
              initial={stepByNo.get(6).output}
              onApprove={(p) => onApprove("gaps", p)}
            />
          )}
          {checkpointName === "final_copy" && stepByNo.get(7)?.output && (
            <CopyEditor
              initial={stepByNo.get(7).output}
              onApprove={(p) => onApprove("final_copy", p)}
            />
          )}

          {(data.status === "done" || stepByNo.get(7)?.output) && (
            <FinalOutputTabs steps={data.steps} sources={data.sources} />
          )}

          {data.status === "running" && !checkpointName && (
            <div className="card">
              <p className="muted">
                Workflow is running. The next checkpoint editor will appear here when ready.
              </p>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
