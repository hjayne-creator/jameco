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

export interface RunDetail extends RunSummary {
  steps: StepRecord[];
  sources: SourceRecord[];
  style_guide_id: number | null;
}

export interface StyleGuideSummary {
  id: number;
  name: string;
  length: number;
  created_at: string;
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
};
