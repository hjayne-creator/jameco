const API_BASE = import.meta.env.VITE_API_BASE ?? "/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: init?.body && !(init.body instanceof FormData)
      ? { "Content-Type": "application/json" }
      : undefined,
    ...init,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export interface RunSummary {
  id: number;
  subject_url: string;
  n_competitors: number;
  status: string;
  current_step: number;
  created_at: string;
  updated_at: string;
  error: string | null;
  llm_total_tokens?: number;
  llm_total_cost_usd?: number;
}

export interface BulkOptionsPayload {
  n_competitors: number;
  style_guide_id?: number | null;
  min_competitor_confidence: number;
  domain_blocklist: string[];
  min_distinct_competitor_domains: number;
}

export interface BatchSummary {
  id: number;
  name?: string | null;
  status: string;
  total_urls: number;
  finished_urls: number;
  /** Batch-level summary when status is `failed` (or stuck runs). */
  error?: string | null;
  created_at: string;
  updated_at: string;
  llm_total_tokens?: number;
  llm_total_cost_usd?: number;
}

export interface BatchRunRow {
  id: number;
  subject_url: string;
  status: string;
  current_step: number;
  terminal_reason: string | null;
  error: string | null;
  updated_at: string;
  llm_total_tokens?: number;
  llm_total_cost_usd?: number;
}

export interface BatchDetail extends BatchSummary {
  options_snapshot: BulkOptionsPayload;
  progress_percent: number;
  runs: BatchRunRow[];
}

export interface StepRecord {
  id: number;
  step_no: number;
  step_name: string;
  status: string;
  output: any;
  duration_ms: number | null;
  model_used: string | null;
  error: string | null;
  updated_at: string;
}

export interface SourceRecord {
  id: number;
  url: string;
  kind: string;
  title: string | null;
  classification: string | null;
  notes: string | null;
  fetched_at: string;
}

/** Per-run rows from GET /batches/:id/report (steps 7–10 when present). */
export interface BatchReportRun {
  id: number;
  subject_url: string;
  status: string;
  current_step: number;
  terminal_reason: string | null;
  error: string | null;
  steps?: StepRecord[];
  sources?: SourceRecord[];
}

export interface BatchReport {
  batch_id: number;
  runs: BatchReportRun[];
}

export interface RunDetail extends RunSummary {
  steps: StepRecord[];
  sources: SourceRecord[];
  style_guide_id: number | null;
  /** Present when this run was created as part of a bulk batch. */
  batch_id?: number | null;
  terminal_reason?: string | null;
  llm_usage?: {
    events: number;
    total_tokens: number;
    total_cost_usd: number;
    by_step: Array<{
      step_no: number | null;
      step_name: string | null;
      provider: string;
      model: string;
      events: number;
      input_tokens: number;
      output_tokens: number;
      total_tokens: number;
      total_cost_usd: number;
    }>;
  };
}

export interface StyleGuideSummary {
  id: number;
  name: string;
  length: number;
  created_at: string;
}

export interface PriceCard {
  id: number;
  provider: string;
  model: string;
  input_per_million_usd: number;
  output_per_million_usd: number;
  cached_input_per_million_usd: number;
  reasoning_per_million_usd: number;
  effective_from: string | null;
  effective_to: string | null;
  active: boolean;
  notes: string | null;
}

export interface DailyUsageSummary {
  day: string;
  provider: string;
  model: string;
  events: number;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  total_cost_usd: number;
}

export interface RunUsageSummary {
  run_id: number | null;
  subject_url: string | null;
  events: number;
  total_tokens: number;
  total_cost_usd: number;
  last_event_at: string | null;
}

export const api = {
  listRuns: () => request<RunSummary[]>("/runs"),
  getRun: (id: number) => request<RunDetail>(`/runs/${id}`),
  createRun: (payload: { subject_url: string; n_competitors: number; style_guide_id?: number | null }) =>
    request<{ id: number; status: string }>("/runs", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  restartRun: (id: number) =>
    request<{ id: number; status: string }>(`/runs/${id}/restart`, { method: "POST" }),
  approveCheckpoint: (runId: number, name: string, edited_payload: any) =>
    request<{ ok: boolean }>(`/runs/${runId}/checkpoints/${name}/approve`, {
      method: "POST",
      body: JSON.stringify({ edited_payload }),
    }),
  listGuides: () => request<StyleGuideSummary[]>("/style-guides"),
  getGuide: (id: number) =>
    request<{ id: number; name: string; text: string }>(`/style-guides/${id}`),
  uploadGuide: (formData: FormData) =>
    request<{ id: number; name: string; length: number }>("/style-guides", {
      method: "POST",
      body: formData,
    }),
  deleteGuide: (id: number) =>
    request<{ ok: boolean }>(`/style-guides/${id}`, { method: "DELETE" }),

  listBatches: () => request<BatchSummary[]>("/batches"),
  getBatch: (id: number) => request<BatchDetail>(`/batches/${id}`),
  getBatchReport: (id: number) => request<BatchReport>(`/batches/${id}/report`),
  reconcileBatch: (id: number) =>
    request<{ id: number; status: string; error: string | null }>(`/batches/${id}/reconcile`, { method: "POST" }),
  createBatch: (payload: { name?: string; urls: string[]; options: Partial<BulkOptionsPayload> }) =>
    request<{ id: number; status: string; name?: string | null; url_count: number; deduped_from: number }>("/batches", {
      method: "POST",
      body: JSON.stringify({
        name: payload.name,
        urls: payload.urls,
        options: {
          n_competitors: 5,
          min_competitor_confidence: 0.35,
          domain_blocklist: [],
          min_distinct_competitor_domains: 2,
          ...payload.options,
        },
      }),
    }),

  /** Opens CSV download in a new tab (same-origin cookie-free GET). */
  batchCsvDownloadUrl: (id: number) => `${API_BASE}/batches/${id}/export.csv`,

  listPriceCards: () => request<PriceCard[]>("/admin/pricing"),
  upsertPriceCard: (payload: {
    id?: number;
    provider: string;
    model: string;
    input_per_million_usd: number;
    output_per_million_usd: number;
    cached_input_per_million_usd?: number;
    reasoning_per_million_usd?: number;
    active?: boolean;
    notes?: string | null;
    effective_from?: string;
    effective_to?: string | null;
  }) =>
    request<{
      id: number;
      provider: string;
      model: string;
      active: boolean;
      effective_from: string | null;
      effective_to: string | null;
    }>("/admin/pricing", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getDailyUsageSummary: (days: number) =>
    request<DailyUsageSummary[]>(`/admin/usage/summary/daily?days=${encodeURIComponent(days)}`),
  getRunUsageSummary: (limit = 100) =>
    request<RunUsageSummary[]>(`/admin/usage/summary/runs?limit=${encodeURIComponent(limit)}`),
};
