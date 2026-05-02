import { FormEvent, Fragment, useEffect, useState } from "react";
import { api, DailyUsageSummary, PriceCard, RunUsageSummary } from "../api/client";

type PriceCardForm = {
  id?: number;
  provider: string;
  model: string;
  input_per_million_usd: string;
  output_per_million_usd: string;
  cached_input_per_million_usd: string;
  reasoning_per_million_usd: string;
  active: boolean;
  notes: string;
};

const DEFAULT_FORM: PriceCardForm = {
  id: undefined,
  provider: "openai",
  model: "",
  input_per_million_usd: "0",
  output_per_million_usd: "0",
  cached_input_per_million_usd: "0",
  reasoning_per_million_usd: "0",
  active: true,
  notes: "",
};

export function AdminCosts() {
  const [cards, setCards] = useState<PriceCard[]>([]);
  const [daily, setDaily] = useState<DailyUsageSummary[]>([]);
  const [runs, setRuns] = useState<RunUsageSummary[]>([]);
  const [days, setDays] = useState("14");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState<PriceCardForm>(DEFAULT_FORM);
  const editing = form.id != null;

  const refresh = async (daysValue: number) => {
    setLoading(true);
    setError(null);
    try {
      const [priceCards, dailyRows, runRows] = await Promise.all([
        api.listPriceCards(),
        api.getDailyUsageSummary(daysValue),
        api.getRunUsageSummary(),
      ]);
      setCards(priceCards);
      setDaily(dailyRows);
      setRuns(runRows);
    } catch (err: any) {
      setError(err?.message ?? "Failed to load admin cost data");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refresh(14);
  }, []);

  const savePriceCard = async (event: FormEvent) => {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await api.upsertPriceCard({
        id: form.id,
        provider: form.provider.trim().toLowerCase(),
        model: form.model.trim(),
        input_per_million_usd: Number(form.input_per_million_usd),
        output_per_million_usd: Number(form.output_per_million_usd),
        cached_input_per_million_usd: Number(form.cached_input_per_million_usd),
        reasoning_per_million_usd: Number(form.reasoning_per_million_usd),
        active: form.active,
        notes: form.notes.trim() || null,
      });
      setForm(DEFAULT_FORM);
      const parsedDays = Math.max(1, parseInt(days, 10) || 14);
      await refresh(parsedDays);
    } catch (err: any) {
      setError(err?.message ?? "Failed to save price card");
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div>
          <h1 style={{ marginBottom: 4 }}>Cost Admin</h1>
          <p className="muted" style={{ marginTop: 0 }}>
            Manage model price cards and monitor daily/run-level LLM spend.
          </p>
        </div>
        <div className="row">
          <label htmlFor="days" style={{ margin: 0 }}>
            Days
          </label>
          <input
            id="days"
            style={{ width: 80 }}
            type="number"
            min={1}
            max={365}
            value={days}
            onChange={(e) => setDays(e.target.value)}
          />
          <button
            className="secondary"
            onClick={() => {
              const parsed = Math.max(1, Math.min(365, parseInt(days, 10) || 14));
              void refresh(parsed);
            }}
          >
            Refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="card" style={{ borderColor: "var(--bad)" }}>
          <span style={{ color: "var(--bad)" }}>{error}</span>
        </div>
      )}

      <div className="card">
        <h3 style={{ marginTop: 0 }}>{editing ? `Edit Price Card #${form.id}` : "Add Price Card"}</h3>
        <form onSubmit={savePriceCard} className="admin-grid">
          <div>
            <label htmlFor="provider">Provider</label>
            <select
              id="provider"
              value={form.provider}
              onChange={(e) => setForm((prev) => ({ ...prev, provider: e.target.value }))}
            >
              <option value="openai">openai</option>
              <option value="anthropic">anthropic</option>
              <option value="serpapi">serpapi</option>
              <option value="firecrawl">firecrawl</option>
            </select>
          </div>
          <div>
            <label htmlFor="model">Model</label>
            <input
              id="model"
              required
              value={form.model}
              onChange={(e) => setForm((prev) => ({ ...prev, model: e.target.value }))}
              placeholder="gpt-5"
            />
          </div>
          <div>
            <label htmlFor="input-rate">Input $/1M</label>
            <input
              id="input-rate"
              type="number"
              min={0}
              step="0.000001"
              value={form.input_per_million_usd}
              onChange={(e) =>
                setForm((prev) => ({ ...prev, input_per_million_usd: e.target.value }))
              }
            />
          </div>
          <div>
            <label htmlFor="output-rate">Output $/1M</label>
            <input
              id="output-rate"
              type="number"
              min={0}
              step="0.000001"
              value={form.output_per_million_usd}
              onChange={(e) =>
                setForm((prev) => ({ ...prev, output_per_million_usd: e.target.value }))
              }
            />
          </div>
          <div>
            <label htmlFor="cached-rate">Cached Input $/1M</label>
            <input
              id="cached-rate"
              type="number"
              min={0}
              step="0.000001"
              value={form.cached_input_per_million_usd}
              onChange={(e) =>
                setForm((prev) => ({ ...prev, cached_input_per_million_usd: e.target.value }))
              }
            />
          </div>
          <div>
            <label htmlFor="reasoning-rate">Reasoning $/1M</label>
            <input
              id="reasoning-rate"
              type="number"
              min={0}
              step="0.000001"
              value={form.reasoning_per_million_usd}
              onChange={(e) =>
                setForm((prev) => ({ ...prev, reasoning_per_million_usd: e.target.value }))
              }
            />
          </div>
          <div>
            <label htmlFor="notes">Notes</label>
            <input
              id="notes"
              value={form.notes}
              onChange={(e) => setForm((prev) => ({ ...prev, notes: e.target.value }))}
              placeholder="optional"
            />
          </div>
          <div style={{ alignSelf: "end" }}>
            <label className="row" style={{ marginBottom: 8 }}>
              <input
                type="checkbox"
                checked={form.active}
                onChange={(e) => setForm((prev) => ({ ...prev, active: e.target.checked }))}
                style={{ width: 16 }}
              />
              Active
            </label>
            <button type="submit" disabled={saving}>
              {saving ? "Saving..." : editing ? "Update" : "Save"}
            </button>
            {editing && (
              <button
                type="button"
                className="secondary"
                style={{ marginLeft: 8 }}
                onClick={() => setForm(DEFAULT_FORM)}
              >
                Cancel
              </button>
            )}
          </div>
        </form>
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Price Cards</h3>
        {loading && <p className="muted">Loading...</p>}
        {!loading && cards.length === 0 && <p className="muted">No price cards configured yet.</p>}
        {!loading && cards.length > 0 && (
          <div className="admin-table" style={{ gridTemplateColumns: "100px 1fr 100px 100px 100px 100px 80px 150px" }}>
            <div className="admin-head">Provider</div>
            <div className="admin-head">Model</div>
            <div className="admin-head">Input</div>
            <div className="admin-head">Output</div>
            <div className="admin-head">Cached</div>
            <div className="admin-head">Reasoning</div>
            <div className="admin-head">Active</div>
            <div className="admin-head">Actions</div>
            {cards.map((c) => (
              <Fragment key={c.id}>
                <div>{c.provider}</div>
                <div className="mono">{c.model}</div>
                <div>{c.input_per_million_usd}</div>
                <div>{c.output_per_million_usd}</div>
                <div>{c.cached_input_per_million_usd}</div>
                <div>{c.reasoning_per_million_usd}</div>
                <div>{c.active ? "yes" : "no"}</div>
                <div className="row">
                  <button
                    className="secondary"
                    type="button"
                    onClick={() =>
                      setForm({
                        id: c.id,
                        provider: c.provider,
                        model: c.model,
                        input_per_million_usd: String(c.input_per_million_usd),
                        output_per_million_usd: String(c.output_per_million_usd),
                        cached_input_per_million_usd: String(c.cached_input_per_million_usd),
                        reasoning_per_million_usd: String(c.reasoning_per_million_usd),
                        active: c.active,
                        notes: c.notes ?? "",
                      })
                    }
                  >
                    Edit
                  </button>
                  {c.active && (
                    <button
                      className="secondary"
                      type="button"
                      onClick={async () => {
                        await api.upsertPriceCard({
                          id: c.id,
                          provider: c.provider,
                          model: c.model,
                          input_per_million_usd: c.input_per_million_usd,
                          output_per_million_usd: c.output_per_million_usd,
                          cached_input_per_million_usd: c.cached_input_per_million_usd,
                          reasoning_per_million_usd: c.reasoning_per_million_usd,
                          active: false,
                          notes: c.notes,
                        });
                        const parsed = Math.max(1, Math.min(365, parseInt(days, 10) || 14));
                        await refresh(parsed);
                      }}
                    >
                      Deactivate
                    </button>
                  )}
                </div>
              </Fragment>
            ))}
          </div>
        )}
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Daily Usage Summary</h3>
        {!loading && daily.length === 0 && <p className="muted">No usage data yet.</p>}
        {daily.length > 0 && (
          <div className="admin-table" style={{ gridTemplateColumns: "140px 90px 1fr 80px 110px 110px 110px 120px" }}>
            <div className="admin-head">Day</div>
            <div className="admin-head">Provider</div>
            <div className="admin-head">Model</div>
            <div className="admin-head">Events</div>
            <div className="admin-head">Input</div>
            <div className="admin-head">Output</div>
            <div className="admin-head">Total</div>
            <div className="admin-head">Cost (USD)</div>
            {daily.map((d, idx) => (
              <Fragment key={`${d.day}-${d.provider}-${d.model}-${idx}`}>
                <div>{d.day}</div>
                <div>{d.provider}</div>
                <div className="mono">{d.model}</div>
                <div>{d.events}</div>
                <div>{d.input_tokens}</div>
                <div>{d.output_tokens}</div>
                <div>{d.total_tokens}</div>
                <div>${d.total_cost_usd.toFixed(4)}</div>
              </Fragment>
            ))}
          </div>
        )}
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Top Runs by Cost</h3>
        {!loading && runs.length === 0 && <p className="muted">No run-level usage data yet.</p>}
        {runs.length > 0 && (
          <div className="admin-table" style={{ gridTemplateColumns: "80px 1fr 80px 120px 120px 180px" }}>
            <div className="admin-head">Run</div>
            <div className="admin-head">URL</div>
            <div className="admin-head">Events</div>
            <div className="admin-head">Tokens</div>
            <div className="admin-head">Cost (USD)</div>
            <div className="admin-head">Last Event</div>
            {runs.map((r, idx) => (
              <Fragment key={`${r.run_id ?? "none"}-${idx}`}>
                <div>{r.run_id ?? "-"}</div>
                <div className="mono small">{r.subject_url ?? "-"}</div>
                <div>{r.events}</div>
                <div>{r.total_tokens}</div>
                <div>${r.total_cost_usd.toFixed(4)}</div>
                <div className="small muted">
                  {r.last_event_at ? new Date(r.last_event_at).toLocaleString() : "-"}
                </div>
              </Fragment>
            ))}
          </div>
        )}
      </div>
    </>
  );
}
