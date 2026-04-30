import { useMemo, useState } from "react";
import { StepRecord } from "../api/client";

interface Props {
  steps: StepRecord[];
  sources: Array<{ url: string; kind: string; title: string | null }>;
}

type TabId = "wysiwyg" | "html" | "jsonld" | "sources" | "audit";

function copyToClipboard(text: string) {
  navigator.clipboard.writeText(text).catch(() => {});
}

function downloadFile(filename: string, contents: string, mime: string) {
  const blob = new Blob([contents], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export function FinalOutputTabs({ steps, sources }: Props) {
  const [tab, setTab] = useState<TabId>("wysiwyg");

  const finalCopy = steps.find((s) => s.step_no === 7)?.output ?? null;
  const html = steps.find((s) => s.step_no === 8)?.output?.html ?? "";
  const jsonLd = steps.find((s) => s.step_no === 9)?.output ?? null;
  const finalAssembly = steps.find((s) => s.step_no === 10)?.output ?? null;

  const wysiwyg = useMemo(() => {
    if (!finalCopy) return "";
    const lines: string[] = [];
    lines.push(`# ${finalCopy.h1}`);
    if (finalCopy.identity_block?.length) {
      finalCopy.identity_block.forEach((b: string) => lines.push(`- ${b}`));
    }
    lines.push("");
    lines.push(`## ${finalCopy.h2}`);
    if (finalCopy.overview) lines.push("", finalCopy.overview);
    if (finalCopy.features?.length) {
      lines.push("", "## Key Features and Benefits");
      finalCopy.features.forEach((f: any) =>
        lines.push(`- ${f.feature}${f.benefit ? ` — ${f.benefit}` : ""}`),
      );
    }
    if (finalCopy.applications?.length) {
      lines.push("", "## Applications");
      finalCopy.applications.forEach((a: string) => lines.push(`- ${a}`));
    }
    if (finalCopy.specifications?.length) {
      lines.push("", "## Specifications", "", "| Specification | Value |", "| --- | --- |");
      finalCopy.specifications.forEach((s: any) => {
        const v = s.unit ? `${s.value} ${s.unit}` : s.value;
        lines.push(`| ${s.name} | ${v} |`);
      });
    }
    if (finalCopy.faqs?.length) {
      lines.push("", "## Customer Questions");
      finalCopy.faqs.forEach((q: any) => {
        lines.push("", `### ${q.question}`, "", q.answer);
      });
    }
    if (finalCopy.customer_concerns?.length) {
      lines.push("", "## Customer Concerns");
      finalCopy.customer_concerns.forEach((c: any) => {
        lines.push("", `### ${c.concern}`, "", c.response);
      });
    }
    return lines.join("\n");
  }, [finalCopy]);

  return (
    <div className="card">
      <div className="tabs">
        <button className={tab === "wysiwyg" ? "active" : ""} onClick={() => setTab("wysiwyg")}>
          WYSIWYG
        </button>
        <button className={tab === "html" ? "active" : ""} onClick={() => setTab("html")}>
          HTML
        </button>
        <button className={tab === "jsonld" ? "active" : ""} onClick={() => setTab("jsonld")}>
          JSON-LD
        </button>
        <button className={tab === "sources" ? "active" : ""} onClick={() => setTab("sources")}>
          Sources
        </button>
        <button className={tab === "audit" ? "active" : ""} onClick={() => setTab("audit")}>
          Audit
        </button>
      </div>

      {tab === "wysiwyg" && finalCopy && (
        <>
          <div className="row right" style={{ marginBottom: 8 }}>
            <button className="secondary" onClick={() => copyToClipboard(wysiwyg)}>Copy markdown</button>
            <button className="secondary" onClick={() => downloadFile("pdp.md", wysiwyg, "text/markdown")}>Download .md</button>
          </div>
          <div
            className="preview-html"
            dangerouslySetInnerHTML={{ __html: html || "<p>No HTML rendered yet.</p>" }}
          />
        </>
      )}

      {tab === "html" && (
        <>
          <div className="row right" style={{ marginBottom: 8 }}>
            <button className="secondary" onClick={() => copyToClipboard(html)}>Copy HTML</button>
            <button className="secondary" onClick={() => downloadFile("pdp.html", html, "text/html")}>Download .html</button>
          </div>
          <pre className="code-block">{html || "(not generated yet)"}</pre>
        </>
      )}

      {tab === "jsonld" && (
        <>
          <div className="row right" style={{ marginBottom: 8 }}>
            <button
              className="secondary"
              onClick={() => copyToClipboard(JSON.stringify(jsonLd, null, 2))}
            >
              Copy JSON
            </button>
            <button
              className="secondary"
              onClick={() => downloadFile("pdp.jsonld", JSON.stringify(jsonLd, null, 2), "application/ld+json")}
            >
              Download .jsonld
            </button>
          </div>
          <pre className="code-block">{JSON.stringify(jsonLd, null, 2) || "(not generated yet)"}</pre>
        </>
      )}

      {tab === "sources" && (
        <>
          {sources.length === 0 && <p className="muted">No sources captured yet.</p>}
          {sources.map((s, i) => (
            <div key={i} style={{ padding: "6px 0", borderBottom: "1px solid var(--border)" }}>
              <div className="small">
                <span className="status-pill" style={{ marginRight: 8 }}>{s.kind}</span>
                <a href={s.url} target="_blank" rel="noreferrer">{s.title || s.url}</a>
              </div>
              <div className="mono small muted">{s.url}</div>
            </div>
          ))}
        </>
      )}

      {tab === "audit" && (
        <pre className="code-block">{finalAssembly ? JSON.stringify(finalAssembly, null, 2) : "(not generated yet)"}</pre>
      )}
    </div>
  );
}
