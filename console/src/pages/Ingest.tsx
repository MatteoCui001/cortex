import { useState } from "react";
import { api } from "../api";

type Mode = "note" | "link";

export default function Ingest() {
  const [mode, setMode] = useState<Mode>("note");
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [url, setUrl] = useState("");
  const [annotation, setAnnotation] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<{ id: string; title: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    setResult(null);
    try {
      const event = await api.ingest(
        mode === "link"
          ? { url, user_annotation: annotation || undefined, source: "console" }
          : {
              title,
              content,
              source: "console",
              raw_input_type: "text",
              user_annotation: annotation || undefined,
            }
      );
      setResult({ id: event.id, title: event.title });
      // Reset form
      setTitle("");
      setContent("");
      setUrl("");
      setAnnotation("");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Ingest failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-heading" style={{ color: "var(--text-primary)" }}>Quick Ingest</h1>
        <p className="text-meta mt-1">Capture notes or links directly into your knowledge system</p>
      </div>

      {/* Mode toggle */}
      <div className="flex gap-0.5 p-0.5 rounded-lg mb-6 w-fit" style={{ background: "var(--bg-surface)" }}>
        {(["note", "link"] as const).map((m) => (
          <button
            key={m}
            onClick={() => setMode(m)}
            className="text-[12px] font-medium px-4 py-1.5 rounded-md transition-all duration-150"
            style={{
              background: mode === m ? "var(--bg-elevated)" : "transparent",
              color: mode === m ? "var(--text-primary)" : "var(--text-tertiary)",
            }}
          >
            {m === "note" ? "Note" : "Link"}
          </button>
        ))}
      </div>

      <form onSubmit={handleSubmit} className="max-w-2xl space-y-4">
        {mode === "note" ? (
          <>
            <div>
              <label className="text-[11px] font-medium block mb-1.5" style={{ color: "var(--text-secondary)" }}>
                Title
              </label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Brief title for this note"
                className="w-full text-[13px] px-4 py-2.5 rounded-lg outline-none transition-colors"
                style={{
                  background: "var(--bg-surface)",
                  border: "1px solid var(--border-default)",
                  color: "var(--text-primary)",
                }}
                onFocus={(e) => (e.currentTarget.style.borderColor = "var(--text-accent)")}
                onBlur={(e) => (e.currentTarget.style.borderColor = "var(--border-default)")}
              />
            </div>
            <div>
              <label className="text-[11px] font-medium block mb-1.5" style={{ color: "var(--text-secondary)" }}>
                Content
              </label>
              <textarea
                value={content}
                onChange={(e) => setContent(e.target.value)}
                placeholder="Your note, meeting takeaway, research insight..."
                rows={6}
                className="w-full text-[13px] px-4 py-3 rounded-lg outline-none transition-colors resize-y"
                style={{
                  background: "var(--bg-surface)",
                  border: "1px solid var(--border-default)",
                  color: "var(--text-primary)",
                }}
                onFocus={(e) => (e.currentTarget.style.borderColor = "var(--text-accent)")}
                onBlur={(e) => (e.currentTarget.style.borderColor = "var(--border-default)")}
              />
            </div>
          </>
        ) : (
          <div>
            <label className="text-[11px] font-medium block mb-1.5" style={{ color: "var(--text-secondary)" }}>
              URL
            </label>
            <input
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://example.com/article"
              className="w-full text-[13px] px-4 py-2.5 rounded-lg outline-none transition-colors"
              style={{
                background: "var(--bg-surface)",
                border: "1px solid var(--border-default)",
                color: "var(--text-primary)",
              }}
              onFocus={(e) => (e.currentTarget.style.borderColor = "var(--text-accent)")}
              onBlur={(e) => (e.currentTarget.style.borderColor = "var(--border-default)")}
            />
          </div>
        )}

        {/* Annotation (optional, both modes) */}
        <div>
          <label className="text-[11px] font-medium block mb-1.5" style={{ color: "var(--text-secondary)" }}>
            Your take <span style={{ color: "var(--text-quaternary)" }}>(optional)</span>
          </label>
          <input
            type="text"
            value={annotation}
            onChange={(e) => setAnnotation(e.target.value)}
            placeholder="Why this matters, your interpretation..."
            className="w-full text-[13px] px-4 py-2.5 rounded-lg outline-none transition-colors"
            style={{
              background: "var(--bg-surface)",
              border: "1px solid var(--border-default)",
              color: "var(--text-primary)",
            }}
            onFocus={(e) => (e.currentTarget.style.borderColor = "var(--text-accent)")}
            onBlur={(e) => (e.currentTarget.style.borderColor = "var(--border-default)")}
          />
        </div>

        <button
          type="submit"
          disabled={submitting || (mode === "note" ? !content.trim() : !url.trim())}
          className="text-[13px] font-medium px-6 py-2.5 rounded-lg transition-colors disabled:opacity-40"
          style={{
            background: "var(--text-accent)",
            color: "var(--bg-base)",
          }}
        >
          {submitting ? "Processing..." : mode === "note" ? "Save Note" : "Import Link"}
        </button>
      </form>

      {/* Result feedback */}
      {result && (
        <div
          className="mt-6 rounded-lg px-4 py-3 max-w-2xl"
          style={{
            background: "rgba(74,222,128,0.06)",
            border: "1px solid rgba(74,222,128,0.2)",
          }}
        >
          <div className="text-[13px] font-medium" style={{ color: "var(--status-up, #4ade80)" }}>
            Ingested successfully
          </div>
          <div className="text-[12px] mt-1" style={{ color: "var(--text-secondary)" }}>
            {result.title}
            <span className="text-meta ml-2 font-mono">{result.id.slice(0, 8)}</span>
          </div>
        </div>
      )}

      {error && (
        <div
          className="mt-6 text-[12px] py-3 px-4 rounded-lg max-w-2xl"
          style={{ background: "var(--bg-elevated)", color: "var(--status-high, #f87171)" }}
        >
          {error}
        </div>
      )}
    </div>
  );
}
