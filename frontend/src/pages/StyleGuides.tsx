import { useEffect, useRef, useState } from "react";
import { api, StyleGuideSummary } from "../api/client";

export function StyleGuides() {
  const [guides, setGuides] = useState<StyleGuideSummary[]>([]);
  const [name, setName] = useState("");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const refresh = () => api.listGuides().then(setGuides);

  useEffect(() => {
    refresh();
  }, []);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const fd = new FormData();
      fd.append("name", name);
      const file = fileRef.current?.files?.[0];
      if (file) fd.append("file", file);
      else if (text) fd.append("text", text);
      else throw new Error("Provide a file or text");
      await api.uploadGuide(fd);
      setName("");
      setText("");
      if (fileRef.current) fileRef.current.value = "";
      await refresh();
    } catch (err: any) {
      setError(err?.message ?? "Upload failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <h1>Style Guides</h1>
      <p className="muted">
        Upload the JameCo PDP style guide. The active guide is selected when starting a run
        and is included as system context for the final-copy step.
      </p>

      <form className="card" onSubmit={submit}>
        <label>Name</label>
        <input value={name} onChange={(e) => setName(e.target.value)} required />

        <label>Upload file (.md, .txt, .pdf)</label>
        <input type="file" accept=".md,.txt,.pdf,text/markdown,text/plain,application/pdf" ref={fileRef} />

        <label>...or paste text</label>
        <textarea value={text} onChange={(e) => setText(e.target.value)} />

        {error && <p className="small" style={{ color: "var(--bad)" }}>{error}</p>}

        <div className="row right" style={{ marginTop: 12 }}>
          <button disabled={busy}>{busy ? "Uploading..." : "Upload"}</button>
        </div>
      </form>

      <h2>Existing guides</h2>
      <div className="card" style={{ padding: 0 }}>
        {guides.length === 0 && <p className="muted" style={{ padding: 16 }}>None yet.</p>}
        {guides.map((g) => (
          <div
            key={g.id}
            style={{
              display: "grid",
              gridTemplateColumns: "60px 1fr 90px 160px 100px",
              gap: 12,
              padding: "12px 16px",
              borderBottom: "1px solid var(--border)",
              alignItems: "center",
            }}
          >
            <span className="mono">#{g.id}</span>
            <span>{g.name}</span>
            <span className="small muted">{g.length} chars</span>
            <span className="small muted">{new Date(g.created_at).toLocaleString()}</span>
            <button
              className="secondary"
              onClick={async () => {
                if (!confirm(`Delete "${g.name}"?`)) return;
                await api.deleteGuide(g.id);
                refresh();
              }}
            >
              Delete
            </button>
          </div>
        ))}
      </div>
    </>
  );
}
