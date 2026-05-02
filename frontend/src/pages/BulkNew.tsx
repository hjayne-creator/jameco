import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, StyleGuideSummary } from "../api/client";

const MIN_COMPETITOR_CONFIDENCE_HELP =
  "Search results are scored 0–1 for how well they match your product (brand, MPN, title/snippet signals). " +
  "Only candidates at or above this threshold can be chosen as competitor PDPs (up to your discovery cap, after the domain blocklist). " +
  "Higher = stricter, fewer weak matches; lower = more permissive.";

function FieldHelpIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" width={12} height={12} fill="currentColor" aria-hidden>
      <path
        fillRule="evenodd"
        d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-3a1 1 0 00-.867.5 1 1 0 11-1.731-1A3 3 0 0113 8a3.001 3.001 0 01-2 2.83V11a1 1 0 11-2 0v-1a1 1 0 011-1 1 1 0 100-2zm0 8a1 1 0 100-2 1 1 0 000 2z"
        clipRule="evenodd"
      />
    </svg>
  );
}

export function BulkNew() {
  const navigate = useNavigate();
  const [batchName, setBatchName] = useState("");
  const [urlsText, setUrlsText] = useState("");
  const [nText, setNText] = useState("3");
  const [minConf, setMinConf] = useState(0.35);
  const [minDomainsText, setMinDomainsText] = useState("2");
  const [blockText, setBlockText] = useState("");
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
    const parsedN = parseInt(nText.trim(), 10);
    const n = Number.isFinite(parsedN) ? Math.min(20, Math.max(1, parsedN)) : 1;
    const parsedMinDomains = parseInt(minDomainsText.trim(), 10);
    const minDomains = Number.isFinite(parsedMinDomains) ? Math.min(20, Math.max(1, parsedMinDomains)) : 1;
    const urls = urlsText
      .split(/\r?\n/)
      .map((s) => s.trim())
      .filter(Boolean);
    const domain_blocklist = blockText
      .split(/\r?\n/)
      .map((s) => s.trim().toLowerCase())
      .filter(Boolean);
    try {
      const res = await api.createBatch({
        name: batchName.trim() || undefined,
        urls,
        options: {
          n_competitors: n,
          style_guide_id: guideId,
          min_competitor_confidence: minConf,
          min_distinct_competitor_domains: minDomains,
          domain_blocklist,
        },
      });
      navigate(`/bulk/${res.id}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to create batch");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      <h1>New bulk batch</h1>
      <p className="muted">
        One PDP URL per line. Jobs run on the server (you can close this page). Progress appears on the batch
        page. Duplicates are removed automatically.
      </p>
      <form className="card" onSubmit={submit}>
        <label htmlFor="batch-name">Batch name </label>
        <input
          id="batch-name"
          type="text"
          maxLength={120}
          placeholder="May 2026 power supply refresh"
          value={batchName}
          onChange={(e) => setBatchName(e.target.value)}
        />

        <label htmlFor="urls">Product URLs</label>
        <textarea
          id="urls"
          required
          rows={10}
          placeholder={"https://www.jameco.com/...\nhttps://www.jameco.com/..."}
          value={urlsText}
          onChange={(e) => setUrlsText(e.target.value)}
          style={{ fontFamily: "var(--mono, monospace)", fontSize: 13 }}
        />

        <label htmlFor="n">Target competitor PDPs (discovery cap)</label>
        <input
          id="n"
          type="number"
          min={1}
          max={20}
          value={nText}
          onChange={(e) => setNText(e.target.value)}
        />

        <label htmlFor="minc" style={{ display: "flex", alignItems: "center", gap: "0.35rem", flexWrap: "wrap" }}>
          <span>Minimum competitor confidence (0–1)</span>
          <button
            type="button"
            className="field-help"
            style={{ cursor: "help" }}
            title={MIN_COMPETITOR_CONFIDENCE_HELP}
            aria-label={MIN_COMPETITOR_CONFIDENCE_HELP}
          >
            <FieldHelpIcon />
          </button>
        </label>
        <input
          id="minc"
          type="number"
          min={0}
          max={1}
          step={0.05}
          value={minConf}
          onChange={(e) => setMinConf(parseFloat(e.target.value) || 0)}
          title={MIN_COMPETITOR_CONFIDENCE_HELP}
        />

        <label htmlFor="mind">Min distinct competitor domains for gap inclusion</label>
        <input
          id="mind"
          type="number"
          min={1}
          max={20}
          value={minDomainsText}
          onChange={(e) => setMinDomainsText(e.target.value)}
        />

        <label htmlFor="block">Domain blocklist (one domain per line, e.g. amazon.com)</label>
        <textarea
          id="block"
          rows={3}
          value={blockText}
          onChange={(e) => setBlockText(e.target.value)}
          placeholder="competitor.example.com"
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
            {submitting ? "Creating…" : "Create batch"}
          </button>
        </div>
      </form>
    </>
  );
}
