import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, StyleGuideSummary } from "../api/client";

export function NewRun() {
  const navigate = useNavigate();
  const [url, setUrl] = useState("");
  const [n, setN] = useState(5);
  const [guideId, setGuideId] = useState<number | null>(null);
  const [guides, setGuides] = useState<StyleGuideSummary[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.listGuides().then(setGuides).catch(() => setGuides([]));
  }, []);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const res = await api.createRun({
        subject_url: url,
        n_competitors: n,
        style_guide_id: guideId,
      });
      navigate(`/runs/${res.id}`);
    } catch (err: any) {
      setError(err?.message ?? "Failed to start run");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      <h1>Start a new PDP run</h1>
      <p className="muted">
        Paste a Jameco PDP URL. The workflow will pause for your review at four
        checkpoints: Identity Lock, Competitor List, Gap Validation, and Final Copy.
      </p>
      <form className="card" onSubmit={submit}>
        <label htmlFor="url">Subject product URL</label>
        <input
          id="url"
          type="url"
          required
          placeholder="https://www.jameco.com/..."
          value={url}
          onChange={(e) => setUrl(e.target.value)}
        />

        <label htmlFor="n">Target competitor PDPs to review</label>
        <input
          id="n"
          type="number"
          min={1}
          max={20}
          value={n}
          onChange={(e) => setN(parseInt(e.target.value, 10) || 1)}
        />

        <label htmlFor="guide">Style guide</label>
        <select
          id="guide"
          value={guideId ?? ""}
          onChange={(e) => setGuideId(e.target.value ? parseInt(e.target.value, 10) : null)}
        >
          <option value="">(none)</option>
          {guides.map((g) => (
            <option key={g.id} value={g.id}>
              {g.name}
            </option>
          ))}
        </select>

        {error && <p className="small" style={{ color: "var(--bad)" }}>{error}</p>}

        <div className="row right" style={{ marginTop: 16 }}>
          <button type="submit" disabled={submitting}>
            {submitting ? "Starting..." : "Start run"}
          </button>
        </div>
      </form>
    </>
  );
}
