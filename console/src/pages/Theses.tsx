import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type ThesisCoverage, type Event } from "../api";
import TypeLabel from "../components/TypeLabel";
import DetailDrawer, { type DrawerTarget } from "../DetailDrawer";

function TrendBadge({ direction, delta }: { direction: string; delta: number | null }) {
  if (direction === "up") {
    return (
      <span className="text-[11px] font-medium" style={{ color: "var(--status-up, #4ade80)" }}>
        {delta !== null ? `+${(delta * 100).toFixed(1)}%` : "up"}
      </span>
    );
  }
  if (direction === "down") {
    return (
      <span className="text-[11px] font-medium" style={{ color: "var(--status-high, #f87171)" }}>
        {delta !== null ? `${(delta * 100).toFixed(1)}%` : "down"}
      </span>
    );
  }
  return <span className="text-meta text-[11px]">flat</span>;
}

function ConfBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const color = pct >= 70 ? "var(--status-up, #4ade80)" : pct >= 40 ? "var(--text-accent)" : "var(--text-tertiary)";
  return (
    <div className="flex items-center gap-2">
      <div className="w-20 h-1.5 rounded-full overflow-hidden" style={{ background: "var(--bg-active)" }}>
        <div className="h-full rounded-full" style={{ width: `${pct}%`, background: color, opacity: 0.7 }} />
      </div>
      <span className="text-[11px] font-mono" style={{ color }}>{pct}%</span>
    </div>
  );
}

function TypeDistribution({ dist }: { dist: Record<string, number> }) {
  const total = Object.values(dist).reduce((a, b) => a + b, 0);
  if (total === 0) return null;
  return (
    <div className="flex gap-1 flex-wrap">
      {Object.entries(dist)
        .sort((a, b) => b[1] - a[1])
        .map(([type, count]) => (
          <span
            key={type}
            className="text-[10px] px-1.5 py-0.5 rounded"
            style={{ color: "var(--text-tertiary)", background: "var(--bg-elevated)" }}
          >
            {type} {count}
          </span>
        ))}
    </div>
  );
}

export default function Theses() {
  const navigate = useNavigate();
  const [theses, setTheses] = useState<ThesisCoverage[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [evidence, setEvidence] = useState<Event[]>([]);
  const [evidenceLoading, setEvidenceLoading] = useState(false);
  const [drawer, setDrawer] = useState<DrawerTarget | null>(null);

  useEffect(() => {
    api.thesisCoverage()
      .then(setTheses)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  async function toggleExpand(thesis: string) {
    if (expanded === thesis) {
      setExpanded(null);
      setEvidence([]);
      return;
    }
    setExpanded(thesis);
    setEvidenceLoading(true);
    try {
      const events = await api.thesisEvidence(thesis);
      setEvidence(events);
    } catch {
      setEvidence([]);
    } finally {
      setEvidenceLoading(false);
    }
  }

  return (
    <div>
      <div className="flex items-baseline justify-between mb-6">
        <div>
          <h1 className="text-heading" style={{ color: "var(--text-primary)" }}>Thesis Dashboard</h1>
          <p className="text-meta mt-1">Your intellectual portfolio</p>
        </div>
        <span className="text-meta">{theses.length} theses tracked</span>
      </div>

      {error && (
        <div
          className="text-[12px] py-3 px-4 rounded-lg mb-4"
          style={{ background: "var(--bg-elevated)", color: "var(--status-high, #f87171)" }}
        >
          {error}
        </div>
      )}

      {loading ? (
        <div className="py-16 text-center text-body">Loading theses...</div>
      ) : theses.length === 0 && !error ? (
        <div
          className="rounded-xl p-12 text-center"
          style={{ background: "var(--bg-surface)", border: "1px solid var(--border-subtle)" }}
        >
          <div className="text-2xl mb-3" style={{ color: "var(--text-quaternary)" }}>&mdash;</div>
          <div className="text-body">No theses tracked yet</div>
          <div className="text-meta mt-2">Ingest content tagged with thesis links to start tracking</div>
        </div>
      ) : (
        <div className="space-y-2">
          {theses
            .sort((a, b) => b.event_count - a.event_count)
            .map((t) => (
            <div
              key={t.thesis}
              className="rounded-xl transition-all duration-150"
              style={{
                background: expanded === t.thesis ? "var(--bg-surface)" : "transparent",
                border: expanded === t.thesis ? "1px solid var(--border-default)" : "1px solid transparent",
              }}
            >
              {/* Header row */}
              <button
                onClick={() => toggleExpand(t.thesis)}
                className="w-full text-left px-5 py-4 rounded-xl transition-colors"
                onMouseEnter={(e) => { if (expanded !== t.thesis) e.currentTarget.style.background = "var(--bg-surface)"; }}
                onMouseLeave={(e) => { if (expanded !== t.thesis) e.currentTarget.style.background = ""; }}
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 mb-1.5">
                      <span className="text-[14px] font-medium" style={{ color: "var(--text-primary)" }}>
                        {t.thesis}
                      </span>
                      <TrendBadge direction={t.trend_direction} delta={t.confidence_delta} />
                    </div>
                    <div className="flex items-center gap-4">
                      <ConfBar value={t.avg_confidence} />
                      <span className="text-meta text-[11px]">{t.event_count} events</span>
                      <span className="text-meta text-[11px]">{t.recent_event_count} recent</span>
                      {t.days_since_update > 0 && (
                        <span
                          className="text-[10px] px-1.5 py-0.5 rounded"
                          style={{
                            color: t.days_since_update > 30 ? "var(--status-high, #f87171)" : "var(--text-tertiary)",
                            background: "var(--bg-elevated)",
                          }}
                        >
                          {t.days_since_update}d ago
                        </span>
                      )}
                    </div>
                    {t.type_distribution && (
                      <div className="mt-2">
                        <TypeDistribution dist={t.type_distribution} />
                      </div>
                    )}
                  </div>
                  <span className="text-meta shrink-0 mt-1">{expanded === t.thesis ? "\u25BC" : "\u25B6"}</span>
                </div>
              </button>

              {/* Expanded: evidence events */}
              {expanded === t.thesis && (
                <div className="px-5 pb-4 pt-1 border-t" style={{ borderColor: "var(--border-subtle)" }}>
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-[12px] font-medium" style={{ color: "var(--text-secondary)" }}>
                      Evidence ({evidence.length})
                    </span>
                    <button
                      onClick={() => navigate(`/events?thesis=${encodeURIComponent(t.thesis)}`)}
                      className="text-[11px] font-medium px-2.5 py-1 rounded-md transition-colors"
                      style={{ color: "var(--text-accent-dim)", border: "1px solid var(--border-accent)" }}
                      onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(129,140,248,0.08)"; }}
                      onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
                    >
                      View all in Events
                    </button>
                  </div>

                  {evidenceLoading ? (
                    <div className="text-meta py-4 text-center">Loading evidence...</div>
                  ) : evidence.length === 0 ? (
                    <div className="text-meta py-4 text-center">No evidence events found</div>
                  ) : (
                    <div className="space-y-1">
                      {evidence.slice(0, 8).map((e) => (
                        <button
                          key={e.id}
                          onClick={() => setDrawer({ kind: "event", id: e.id })}
                          className="w-full text-left px-3 py-2 rounded-lg transition-colors flex items-start gap-2"
                          style={{ color: "var(--text-primary)" }}
                          onMouseEnter={(ev) => (ev.currentTarget.style.background = "var(--bg-elevated)")}
                          onMouseLeave={(ev) => (ev.currentTarget.style.background = "transparent")}
                        >
                          <TypeLabel type={e.type} />
                          <div className="flex-1 min-w-0">
                            <div className="text-[13px] truncate">{e.title || "\u2014"}</div>
                            <div className="flex items-center gap-2 mt-0.5">
                              <span className="text-meta text-[10px]">{new Date(e.created_at).toLocaleDateString()}</span>
                              {e.confidence > 0 && (
                                <span className="text-meta text-[10px]">conf {(e.confidence * 100).toFixed(0)}%</span>
                              )}
                            </div>
                          </div>
                        </button>
                      ))}
                      {evidence.length > 8 && (
                        <div className="text-meta text-[11px] text-center py-1">
                          +{evidence.length - 8} more
                        </div>
                      )}
                    </div>
                  )}
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
