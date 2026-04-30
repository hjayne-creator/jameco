import { useState } from "react";

export interface IdentityLockShape {
  brand?: string | null;
  manufacturer?: string | null;
  mpn?: string | null;
  series?: string | null;
  product_type?: string | null;
  output_or_capacity?: string | null;
  sku?: string | null;
  gtin?: string | null;
  upc?: string | null;
  ean?: string | null;
  model_number?: string | null;
  ambiguous?: boolean;
  ambiguity_notes?: string[];
}

interface Props {
  initial: IdentityLockShape;
  onApprove: (edited: IdentityLockShape) => Promise<void>;
}

const FIELDS: Array<[keyof IdentityLockShape, string]> = [
  ["brand", "Brand"],
  ["manufacturer", "Manufacturer"],
  ["mpn", "Manufacturer Part Number (MPN)"],
  ["series", "Series"],
  ["product_type", "Product Type"],
  ["output_or_capacity", "Output / Capacity / Rating"],
  ["sku", "SKU"],
  ["model_number", "Model Number"],
  ["gtin", "GTIN"],
  ["upc", "UPC"],
  ["ean", "EAN"],
];

export function IdentityEditor({ initial, onApprove }: Props) {
  const [state, setState] = useState<IdentityLockShape>({ ...initial });
  const [busy, setBusy] = useState(false);

  const update = (key: keyof IdentityLockShape, value: string) => {
    setState((prev) => ({ ...prev, [key]: value || null }));
  };

  return (
    <div className="card">
      <h3>Checkpoint: Product Identity Lock</h3>
      <p className="muted small">
        Confirm or correct the locked identity. This is what the workflow will use
        for manufacturer + competitor search.
      </p>
      {state.ambiguous && (
        <p className="small" style={{ color: "var(--warn)" }}>
          Identity flagged as ambiguous: {(state.ambiguity_notes ?? []).join("; ")}
        </p>
      )}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
        {FIELDS.map(([key, label]) => (
          <div key={key as string}>
            <label>{label}</label>
            <input
              value={(state[key] as string) ?? ""}
              onChange={(e) => update(key, e.target.value)}
            />
          </div>
        ))}
      </div>
      <div className="row right" style={{ marginTop: 16 }}>
        <button
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            try {
              await onApprove({ ...state, ambiguous: false });
            } finally {
              setBusy(false);
            }
          }}
        >
          {busy ? "Approving..." : "Approve identity & continue"}
        </button>
      </div>
    </div>
  );
}
