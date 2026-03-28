import { useEffect, useState } from "react";
import { api, type Event } from "../api";
import DetailDrawer, { type DrawerTarget } from "../DetailDrawer";

const DAY_FILTERS = [
  { label: "7d", days: 7 },
  { label: "30d", days: 30 },
  { label: "All", days: undefined },
] as const;

function TypeLabel({ type }: { type: string }) {
  const map: Record<string, { color: string; bg: string }> = {
    article: { color: "var(--type-article)", bg: "var(--type-article-bg)" },
    note: { color: "var(--type-note)", bg: "var(--type-note-bg)" },
    chat: { color: "var(--type-chat)", bg: "var(--type-chat-bg)" },
    meeting: { color: "var(--type-meeting)", bg: "var(--type-meeting-bg)" },
    thesis: { color: "var(--type-thesis)", bg: "var(--type-thesis-bg)" },
    voice_memo: { color: "var(--type-voice)", bg: "var(--type-voice-bg)" },
    document: { color: "var(--type-document)", bg: "var(--type-document-bg)" },
  };
  const s = map[type] ?? { color: "var(--text-tertiary)", bg: "var(--bg-elevated)" };
  return (
    <span className="text-[10px] font-medium px-1.5 py-0.5 rounded" style={{ color: s.color, background: s.bg }}>
      {type}
    </span>
  );
}

function MetaBadge({ children }: { children: string }) {
  return (
    <span className="text-[10px] px-1.5 py-0.5 rounded" style={{ color: "var(--text-tertiary)", background: "var(--bg-elevated)" }}>
      {children}
    </span>
  );
}

function TemporalityBadge({ value }: { value: string }) {
  const isWarm = value === "time_sensitive" || value === "prediction" || value === "trend";
  return (
    <span
      className="text-[10px] px-1.5 py-0.5 rounded"
      style={{
        color: isWarm ? "var(--status-medium)" : "var(--text-tertiary)",
        background: isWarm ? "var(--status-medium-bg)" : "var(--bg-elevated)",
      }}
    >
      {value}
    </span>
  );
}

function SourceLink({ path }: { path: string | null }) {
  if (!path) return null;
  const isUrl = path.startsWith("http") || path.startsWith("link:");
  const url = path.startsWith("link:") ? path.slice(5) : path;
  if (!isUrl) return <span className="text-meta font-mono truncate max-w-[280px] inline-block align-bottom">{path}</span>;
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="text-[11px] truncate max-w-[280px] inline-block align-bottom transition-colors"
      style={{ color: "var(--text-accent-dim)", textDecoration: "underline", textDecorationColor: "rgba(165,180,252,0.2)" }}
      onMouseEnter={(e) => (e.currentTarget.style.color = "var(--text-accent)")}
      onMouseLeave={(e) => (e.currentTarget.style.color = "var(--text-accent-dim)")}
    >
      {url.replace(/^https?:\/\//, "").slice(0, 55)}
    </a>
  );
}

export default function Events() {
  const [events, setEvents] = useState<Event[]>([]);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState<number | undefined>(30);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [drawer, setDrawer] = useState<DrawerTarget | null>(null);

  useEffect(() => {
    setLoading(true);
    api.events(100, days).then(setEvents).finally(() => setLoading(false));
  }, [days]);

  return (
    <div>
      {/* Header */}
      <div className="flex items-baseline justify-between mb-6">
        <div>
          <h1 className="text-heading">Events</h1>
          <p className="text-caption mt-1">Everything your system has ingested</p>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-meta">{events.length} events</span>
          <div className="flex gap-0.5 p-0.5 rounded-lg" style={{ background: "var(--bg-surface)" }}>
            {DAY_FILTERS.map((f) => (
              <button
                key={f.label}
                onClick={() => setDays(f.days)}
                className="text-[11px] px-2.5 py-1 rounded-md transition-all duration-150"
                style={{
                  background: days === f.days ? "var(--bg-elevated)" : "transparent",
                  color: days === f.days ? "var(--text-primary)" : "var(--text-tertiary)",
                  fontWeight: days === f.days ? 500 : 400,
                }}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {loading ? (
        <div className="py-16 text-center text-body">Loading...</div>
      ) : events.length === 0 ? (
        <div
          className="rounded-xl p-16 text-center"
          style={{ background: "var(--bg-surface)", border: "1px solid var(--border-subtle)" }}
        >
          <div className="text-2xl mb-3" style={{ color: "var(--text-quaternary)" }}>&mdash;</div>
          <div className="text-body">No events in this period</div>
          <div className="text-meta mt-2">Send content via WeChat or use the API to ingest knowledge</div>
        </div>
      ) : (
        <div className="space-y-px">
          {events.map((e) => (
            <div
              key={e.id}
              className="rounded-xl transition-all duration-150"
              style={{
                background: expanded === e.id ? "var(--bg-surface)" : "transparent",
                border: expanded === e.id ? "1px solid var(--border-default)" : "1px solid transparent",
              }}
            >
              <button
                onClick={() => setExpanded(expanded === e.id ? null : e.id)}
                className="w-full text-left px-4 py-3 rounded-xl transition-colors"
                onMouseEnter={(ev) => { if (expanded !== e.id) ev.currentTarget.style.background = "var(--bg-surface)"; }}
                onMouseLeave={(ev) => { if (expanded !== e.id) ev.currentTarget.style.background = ""; }}
              >
                <div className="flex items-start gap-3">
                  <TypeLabel type={e.type} />
                  <div className="flex-1 min-w-0">
                    <div className="text-[13px] font-medium" style={{ color: e.title ? "var(--text-primary)" : "var(--text-tertiary)" }}>
                      {e.title || "\u2014"}
                    </div>
                    <div className="flex items-center gap-2 mt-1 flex-wrap">
                      <span className="text-meta">{new Date(e.created_at).toLocaleString()}</span>
                      {e.source && <span className="text-meta">{e.source}</span>}
                      {e.raw_input_type && e.raw_input_type !== "text" && <MetaBadge>{e.raw_input_type}</MetaBadge>}
                      {e.source_type && <MetaBadge>{e.source_type}</MetaBadge>}
                      {e.temporality && e.temporality !== "permanent" && <TemporalityBadge value={e.temporality} />}
                    </div>
                    {e.user_annotation && (
                      <div className="mt-1.5 text-[12px] italic" style={{ color: "var(--text-accent-dim)" }}>
                        &ldquo;{e.user_annotation}&rdquo;
                      </div>
                    )}
                  </div>
                  <span className="text-meta shrink-0 mt-0.5">{expanded === e.id ? "\u25BC" : "\u25B6"}</span>
                </div>
              </button>

              {/* Expanded detail */}
              {expanded === e.id && (
                <div className="px-4 pb-4 pt-2 ml-12 space-y-3 border-t" style={{ borderColor: "var(--border-subtle)" }}>
                  {e.summary && <p className="text-body leading-relaxed">{e.summary}</p>}

                  {e.user_annotation && (
                    <div className="px-3 py-2 rounded-lg" style={{ background: "rgba(165,180,252,0.04)", borderLeft: "2px solid var(--text-accent-dim)" }}>
                      <div className="text-meta mb-0.5">Your annotation</div>
                      <div className="text-[13px]" style={{ color: "var(--text-accent)" }}>{e.user_annotation}</div>
                    </div>
                  )}

                  {e.tags.length > 0 && (
                    <div className="flex flex-wrap gap-1.5">
                      {e.tags.map((t) => (
                        <span key={t} className="text-[11px] px-2 py-0.5 rounded-full" style={{ color: "var(--text-tertiary)", background: "var(--bg-elevated)", border: "1px solid var(--border-subtle)" }}>{t}</span>
                      ))}
                    </div>
                  )}

                  {e.thesis_links.length > 0 && (
                    <div className="flex flex-wrap gap-1.5">
                      {e.thesis_links.map((t) => (
                        <span key={t} className="text-[11px] px-2 py-0.5 rounded" style={{ color: "var(--text-accent)", background: "rgba(165,180,252,0.08)" }}>{t}</span>
                      ))}
                    </div>
                  )}

                  <div className="flex items-center gap-4 pt-2 border-t" style={{ borderColor: "var(--border-subtle)" }}>
                    <span className="text-meta font-mono">{e.id.slice(0, 8)}</span>
                    {e.confidence > 0 && <span className="text-meta">conf {e.confidence.toFixed(2)}</span>}
                    <SourceLink path={e.source_path} />
                    <button
                      onClick={(ev) => { ev.stopPropagation(); setDrawer({ kind: "event", id: e.id }); }}
                      className="ml-auto text-[11px] font-medium px-2.5 py-1 rounded-md transition-colors"
                      style={{ color: "var(--text-accent-dim)", border: "1px solid var(--border-accent)" }}
                      onMouseEnter={(ev) => { ev.currentTarget.style.background = "rgba(129,140,248,0.08)"; ev.currentTarget.style.color = "var(--text-accent)"; }}
                      onMouseLeave={(ev) => { ev.currentTarget.style.background = "transparent"; ev.currentTarget.style.color = "var(--text-accent-dim)"; }}
                    >
                      Context
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      <DetailDrawer target={drawer} onClose={() => setDrawer(null)} />
    </div>
  );
}
