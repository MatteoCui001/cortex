import { useState } from "react";
import { api, type SearchResult } from "../api";
import TypeLabel from "../components/TypeLabel";
import DetailDrawer, { type DrawerTarget } from "../DetailDrawer";

const MODES = [
  { value: "hybrid", label: "Hybrid" },
  { value: "semantic", label: "Semantic" },
  { value: "fulltext", label: "Fulltext" },
] as const;

const TYPES = ["", "article", "note", "chat", "meeting", "thesis", "voice_memo", "document"] as const;

function ScoreBadge({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const color = pct >= 80 ? "var(--status-up, #4ade80)" : pct >= 50 ? "var(--text-accent)" : "var(--text-tertiary)";
  return (
    <span
      className="text-[10px] font-mono px-1.5 py-0.5 rounded"
      style={{ color, background: "var(--bg-elevated)" }}
    >
      {pct}%
    </span>
  );
}

export default function Search() {
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState("hybrid");
  const [typeFilter, setTypeFilter] = useState("");
  const [results, setResults] = useState<SearchResult[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [drawer, setDrawer] = useState<DrawerTarget | null>(null);

  async function doSearch(e?: React.FormEvent) {
    e?.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const r = await api.search(query.trim(), mode, 20, typeFilter || undefined);
      setResults(r);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Search failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-heading" style={{ color: "var(--text-primary)" }}>Search</h1>
        <p className="text-meta mt-1">Semantic and full-text search across your knowledge</p>
      </div>

      {/* Search form */}
      <form onSubmit={doSearch} className="mb-6">
        <div className="flex gap-2">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search events, entities, topics..."
            className="flex-1 text-[13px] px-4 py-2.5 rounded-lg outline-none transition-colors"
            style={{
              background: "var(--bg-surface)",
              border: "1px solid var(--border-default)",
              color: "var(--text-primary)",
            }}
            onFocus={(e) => (e.currentTarget.style.borderColor = "var(--text-accent)")}
            onBlur={(e) => (e.currentTarget.style.borderColor = "var(--border-default)")}
          />
          <button
            type="submit"
            disabled={loading || !query.trim()}
            className="text-[13px] font-medium px-5 py-2.5 rounded-lg transition-colors disabled:opacity-40"
            style={{
              background: "var(--text-accent)",
              color: "var(--bg-base)",
            }}
          >
            {loading ? "..." : "Search"}
          </button>
        </div>

        <div className="flex items-center gap-4 mt-3">
          {/* Mode selector */}
          <div className="flex gap-0.5 p-0.5 rounded-lg" style={{ background: "var(--bg-surface)" }}>
            {MODES.map((m) => (
              <button
                key={m.value}
                type="button"
                onClick={() => setMode(m.value)}
                className="text-[11px] px-2.5 py-1 rounded-md transition-all duration-150"
                style={{
                  background: mode === m.value ? "var(--bg-elevated)" : "transparent",
                  color: mode === m.value ? "var(--text-primary)" : "var(--text-tertiary)",
                  fontWeight: mode === m.value ? 500 : 400,
                }}
              >
                {m.label}
              </button>
            ))}
          </div>

          {/* Type filter */}
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="text-[11px] px-2 py-1 rounded-md"
            style={{
              background: "var(--bg-surface)",
              border: "1px solid var(--border-subtle)",
              color: "var(--text-secondary)",
            }}
          >
            <option value="">All types</option>
            {TYPES.filter(Boolean).map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
        </div>
      </form>

      {error && (
        <div
          className="text-[12px] py-3 px-4 rounded-lg mb-4"
          style={{ background: "var(--bg-elevated)", color: "var(--status-high, #f87171)" }}
        >
          {error}
        </div>
      )}

      {/* Results */}
      {loading && (
        <div className="py-16 text-center text-body">Searching...</div>
      )}

      {results !== null && !loading && results.length === 0 && (
        <div
          className="rounded-xl p-12 text-center"
          style={{ background: "var(--bg-surface)", border: "1px solid var(--border-subtle)" }}
        >
          <div className="text-2xl mb-3" style={{ color: "var(--text-quaternary)" }}>&mdash;</div>
          <div className="text-body">No results for &ldquo;{query}&rdquo;</div>
          <div className="text-meta mt-2">Try different keywords or switch search mode</div>
        </div>
      )}

      {results !== null && !loading && results.length > 0 && (
        <div className="space-y-1">
          <div className="text-meta mb-3">{results.length} result{results.length > 1 ? "s" : ""}</div>
          {results.map((r) => (
            <button
              key={r.event.id}
              onClick={() => setDrawer({ kind: "event", id: r.event.id })}
              className="w-full text-left rounded-xl px-4 py-3 transition-all duration-150"
              style={{
                background: "transparent",
                border: "1px solid transparent",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = "var(--bg-surface)";
                e.currentTarget.style.borderColor = "var(--border-default)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = "transparent";
                e.currentTarget.style.borderColor = "transparent";
              }}
            >
              <div className="flex items-start gap-3">
                <TypeLabel type={r.event.type} />
                <div className="flex-1 min-w-0">
                  <div
                    className="text-[13px] font-medium truncate"
                    style={{ color: r.event.title ? "var(--text-primary)" : "var(--text-tertiary)" }}
                  >
                    {r.event.title || "\u2014"}
                  </div>
                  {r.event.summary && (
                    <div className="text-[12px] mt-1 line-clamp-2" style={{ color: "var(--text-tertiary)" }}>
                      {r.event.summary}
                    </div>
                  )}
                  <div className="flex items-center gap-2 mt-1.5">
                    <span className="text-meta">{new Date(r.event.created_at).toLocaleDateString()}</span>
                    <span className="text-meta font-mono">{r.match_type}</span>
                    {r.event.thesis_links.length > 0 && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded" style={{ color: "var(--text-accent)", background: "rgba(165,180,252,0.08)" }}>
                        {r.event.thesis_links[0]}{r.event.thesis_links.length > 1 ? ` +${r.event.thesis_links.length - 1}` : ""}
                      </span>
                    )}
                  </div>
                </div>
                <ScoreBadge score={r.score} />
              </div>
            </button>
          ))}
        </div>
      )}

      {results === null && !loading && (
        <div
          className="rounded-xl p-12 text-center"
          style={{ background: "var(--bg-surface)", border: "1px solid var(--border-subtle)" }}
        >
          <div className="text-2xl mb-3" style={{ color: "var(--text-quaternary)" }}>?</div>
          <div className="text-body">Type a query to search across all ingested knowledge</div>
          <div className="text-meta mt-2">Supports natural language, entity names, thesis topics</div>
        </div>
      )}

      <DetailDrawer target={drawer} onClose={() => setDrawer(null)} />
    </div>
  );
}
