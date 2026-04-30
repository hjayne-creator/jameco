import { useState } from "react";

export interface FeatureBullet {
  feature: string;
  benefit?: string | null;
  sources?: any[];
}

export interface SpecificationRow {
  name: string;
  value: string;
  unit?: string | null;
  sources?: any[];
}

export interface FaqRow {
  question: string;
  answer: string;
  sources?: any[];
}

export interface ConcernRow {
  concern: string;
  response: string;
  sources?: any[];
}

export interface FinalCopyShape {
  h1: string;
  identity_block: string[];
  h2: string;
  overview: string;
  features: FeatureBullet[];
  applications: string[];
  specifications: SpecificationRow[];
  faqs: FaqRow[];
  customer_concerns: ConcernRow[];
}

interface Props {
  initial: FinalCopyShape;
  onApprove: (edited: FinalCopyShape) => Promise<void>;
}

function StringList({
  values,
  onChange,
  label,
  placeholder,
}: {
  values: string[];
  onChange: (next: string[]) => void;
  label: string;
  placeholder?: string;
}) {
  return (
    <>
      <label>{label}</label>
      {values.map((v, idx) => (
        <div key={idx} className="row" style={{ marginBottom: 6 }}>
          <input
            value={v}
            placeholder={placeholder}
            onChange={(e) => {
              const next = [...values];
              next[idx] = e.target.value;
              onChange(next);
            }}
          />
          <button
            className="secondary"
            type="button"
            onClick={() => onChange(values.filter((_, i) => i !== idx))}
          >
            Remove
          </button>
        </div>
      ))}
      <button className="secondary" type="button" onClick={() => onChange([...values, ""])}>
        Add
      </button>
    </>
  );
}

export function CopyEditor({ initial, onApprove }: Props) {
  const [copy, setCopy] = useState<FinalCopyShape>({ ...initial });
  const [busy, setBusy] = useState(false);

  const update = <K extends keyof FinalCopyShape>(key: K, value: FinalCopyShape[K]) => {
    setCopy((prev) => ({ ...prev, [key]: value }));
  };

  return (
    <div className="card">
      <h3>Checkpoint: Final PDP Copy</h3>
      <p className="muted small">
        Edit the copy before HTML and JSON-LD are rendered from it. Both are
        generated deterministically from this content, so what you approve here
        is what publishes.
      </p>

      <label>H1</label>
      <input value={copy.h1} onChange={(e) => update("h1", e.target.value)} />

      <label>H2</label>
      <input value={copy.h2} onChange={(e) => update("h2", e.target.value)} />

      <StringList
        label="Identity block bullets"
        values={copy.identity_block}
        onChange={(v) => update("identity_block", v)}
        placeholder="Brand: Acme"
      />

      <label>Overview</label>
      <textarea
        value={copy.overview}
        onChange={(e) => update("overview", e.target.value)}
      />

      <label>Features (feature — benefit)</label>
      {copy.features.map((f, idx) => (
        <div key={idx} className="row" style={{ marginBottom: 6 }}>
          <input
            value={f.feature}
            placeholder="Feature"
            onChange={(e) => {
              const next = [...copy.features];
              next[idx] = { ...next[idx], feature: e.target.value };
              update("features", next);
            }}
          />
          <input
            value={f.benefit ?? ""}
            placeholder="Benefit"
            onChange={(e) => {
              const next = [...copy.features];
              next[idx] = { ...next[idx], benefit: e.target.value || null };
              update("features", next);
            }}
          />
          <button
            type="button"
            className="secondary"
            onClick={() => update("features", copy.features.filter((_, i) => i !== idx))}
          >
            Remove
          </button>
        </div>
      ))}
      <button
        type="button"
        className="secondary"
        onClick={() => update("features", [...copy.features, { feature: "", benefit: "", sources: [] }])}
      >
        Add feature
      </button>

      <StringList
        label="Applications"
        values={copy.applications}
        onChange={(v) => update("applications", v)}
      />

      <label>Specifications</label>
      {copy.specifications.map((s, idx) => (
        <div key={idx} className="row" style={{ marginBottom: 6 }}>
          <input
            value={s.name}
            placeholder="Spec name"
            onChange={(e) => {
              const next = [...copy.specifications];
              next[idx] = { ...next[idx], name: e.target.value };
              update("specifications", next);
            }}
          />
          <input
            value={s.value}
            placeholder="Value"
            onChange={(e) => {
              const next = [...copy.specifications];
              next[idx] = { ...next[idx], value: e.target.value };
              update("specifications", next);
            }}
          />
          <input
            value={s.unit ?? ""}
            placeholder="Unit"
            onChange={(e) => {
              const next = [...copy.specifications];
              next[idx] = { ...next[idx], unit: e.target.value || null };
              update("specifications", next);
            }}
          />
          <button
            type="button"
            className="secondary"
            onClick={() => update("specifications", copy.specifications.filter((_, i) => i !== idx))}
          >
            Remove
          </button>
        </div>
      ))}
      <button
        type="button"
        className="secondary"
        onClick={() => update("specifications", [...copy.specifications, { name: "", value: "", unit: "", sources: [] }])}
      >
        Add spec
      </button>

      <label>FAQs</label>
      {copy.faqs.map((q, idx) => (
        <div key={idx} className="card" style={{ background: "var(--panel-2)" }}>
          <input
            value={q.question}
            placeholder="Question"
            onChange={(e) => {
              const next = [...copy.faqs];
              next[idx] = { ...next[idx], question: e.target.value };
              update("faqs", next);
            }}
          />
          <textarea
            value={q.answer}
            placeholder="Answer"
            onChange={(e) => {
              const next = [...copy.faqs];
              next[idx] = { ...next[idx], answer: e.target.value };
              update("faqs", next);
            }}
            style={{ marginTop: 8 }}
          />
          <button
            type="button"
            className="secondary"
            onClick={() => update("faqs", copy.faqs.filter((_, i) => i !== idx))}
            style={{ marginTop: 8 }}
          >
            Remove FAQ
          </button>
        </div>
      ))}
      <button
        type="button"
        className="secondary"
        onClick={() => update("faqs", [...copy.faqs, { question: "", answer: "", sources: [] }])}
      >
        Add FAQ
      </button>

      <label>Customer concerns</label>
      {copy.customer_concerns.map((c, idx) => (
        <div key={idx} className="card" style={{ background: "var(--panel-2)" }}>
          <input
            value={c.concern}
            placeholder="Concern"
            onChange={(e) => {
              const next = [...copy.customer_concerns];
              next[idx] = { ...next[idx], concern: e.target.value };
              update("customer_concerns", next);
            }}
          />
          <textarea
            value={c.response}
            placeholder="Response"
            onChange={(e) => {
              const next = [...copy.customer_concerns];
              next[idx] = { ...next[idx], response: e.target.value };
              update("customer_concerns", next);
            }}
            style={{ marginTop: 8 }}
          />
          <button
            type="button"
            className="secondary"
            onClick={() => update("customer_concerns", copy.customer_concerns.filter((_, i) => i !== idx))}
            style={{ marginTop: 8 }}
          >
            Remove concern
          </button>
        </div>
      ))}
      <button
        type="button"
        className="secondary"
        onClick={() => update("customer_concerns", [...copy.customer_concerns, { concern: "", response: "", sources: [] }])}
      >
        Add concern
      </button>

      <div className="row right" style={{ marginTop: 16 }}>
        <button
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            try {
              await onApprove(copy);
            } finally {
              setBusy(false);
            }
          }}
        >
          {busy ? "Approving..." : "Approve copy & render HTML/JSON-LD"}
        </button>
      </div>
    </div>
  );
}
