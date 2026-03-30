import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import DetailDrawer, { type DrawerTarget } from "../DetailDrawer";

/* ── Types ── */

interface ThesisTrend {
  thesis: string;
  trend_direction: "up" | "down";
  confidence_delta: number | null;
  recent_avg_confidence: number | null;
  recent_event_count: number;
}

interface HighConfEvent {
  id: string;
  title: string;
  confidence: number;
  type: string;
  created_at: string;
}

interface StaleThesis {
  thesis: string;
  event_count: number;
  days_since_update: number;
}

interface EntityMomentum {
  name: string;
  mentions: number;
  type: string;
}

interface DigestData {
  narrative?: string;
  thesis_activity?: Record<string, Record<string, number>>;
  thesis_trends?: ThesisTrend[];
  high_confidence?: HighConfEvent[];
  stale_theses?: StaleThesis[];
  entity_momentum?: EntityMomentum[];
}

/* ── Small components ── */

function SectionCard({
  title,
  children,
  empty,
}: {
  title: string;
  children: React.ReactNode;
  empty?: string;
}) {
  return (
    <div className="card p-5">
      <h3 className="text-subheading mb-3">{title}</h3>
      {children}
      {empty && (
        <div className="text-meta text-[12px] py-2">{empty}</div>
      )}
    </div>
  );
}

function TrendArrow({ direction }: { direction: string }) {
  if (direction === "up")
    return (
      <span style={{ color: "var(--status-success)" }} className="font-semibold">
        ↑
      </span>
    );
  if (direction === "down")
    return (
      <span style={{ color: "var(--status-high)" }} className="font-semibold">
        ↓
      </span>
    );
  return <span style={{ color: "var(--text-quaternary)" }}>—</span>;
}

function ConfBadge({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const color =
    pct >= 90
      ? "var(--status-success)"
      : pct >= 80
        ? "var(--text-accent)"
        : "var(--text-tertiary)";
  return (
    <span
      className="text-[10px] font-medium font-data px-1.5 py-0.5 rounded"
      style={{ color, background: "var(--bg-elevated)" }}
    >
      {pct}%
    </span>
  );
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const hours = Math.floor(diff / 3600000);
  if (hours < 1) return "just now";
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

/* ── Main page ── */

export default function Digest() {
  const navigate = useNavigate();
  const [data, setData] = useState<DigestData | null>(null);
  const [days, setDays] = useState(7);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [drawer, setDrawer] = useState<DrawerTarget | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    api
      .digest(days)
      .then((d) => setData(d as DigestData))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [days]);

  return (
    <div>
      {/* Header */}
      <div className="flex items-baseline justify-between mb-6 animate-in">
        <div>
          <h1 className="text-heading">Research Digest</h1>
          <p className="text-caption mt-1">What deserves your attention</p>
        </div>
        <div className="segment-control">
          {[1, 7, 14, 30].map((d) => (
            <button
              key={d}
              onClick={() => setDays(d)}
              className="segment-btn"
              data-active={days === d ? "true" : undefined}
            >
              {d}d
            </button>
          ))}
        </div>
      </div>

      {loading && (
        <div className="text-body py-12 text-center" style={{ color: "var(--text-tertiary)" }}>Loading digest...</div>
      )}
      {error && (
        <div
          className="text-[12px] py-3 px-4 rounded-lg mb-4"
          style={{ background: "var(--status-high-bg)", color: "var(--status-high)" }}
        >
          Failed to load digest: {error}
        </div>
      )}

      {data && !loading && (
        <div className="flex flex-col gap-5 animate-in animate-in-delay-1">
          {/* 1. Narrative */}
          {data.narrative && (
            <div className="card-glow p-5">
              <div
                className="text-[13px] leading-relaxed whitespace-pre-line"
                style={{ color: "var(--text-primary)" }}
              >
                {data.narrative}
              </div>
            </div>
          )}

          {/* 2. Thesis Trends */}
          <SectionCard
            title="Thesis Trends"
            empty={
              !data.thesis_trends?.length
                ? "No significant trends detected"
                : undefined
            }
          >
            {data.thesis_trends && data.thesis_trends.length > 0 && (
              <div className="flex flex-col gap-2">
                {data.thesis_trends.map((t) => (
                  <div
                    key={t.thesis}
                    className="flex items-center justify-between py-1.5"
                  >
                    <div className="flex items-center gap-2">
                      <TrendArrow direction={t.trend_direction} />
                      <button
                        onClick={() => navigate(`/events?thesis=${encodeURIComponent(t.thesis)}`)}
                        className="thesis-chip"
                      >
                        {t.thesis}
                      </button>
                    </div>
                    <div className="flex items-center gap-3">
                      {t.confidence_delta !== null && (
                        <span
                          className="text-[11px] font-data"
                          style={{
                            color:
                              t.confidence_delta > 0
                                ? "var(--status-success)"
                                : "var(--status-high)",
                          }}
                        >
                          {t.confidence_delta > 0 ? "+" : ""}
                          {(t.confidence_delta * 100).toFixed(1)}%
                        </span>
                      )}
                      <span className="text-meta text-[10px]">
                        {t.recent_event_count} recent
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </SectionCard>

          {/* 3. High Confidence Insights */}
          <SectionCard
            title="High Confidence Insights"
            empty={
              !data.high_confidence?.length
                ? "No high-confidence events in this period"
                : undefined
            }
          >
            {data.high_confidence && data.high_confidence.length > 0 && (
              <div className="flex flex-col gap-2">
                {data.high_confidence.map((e) => (
                  <div
                    key={e.id}
                    className="flex items-start justify-between py-1.5"
                  >
                    <div className="flex-1 min-w-0">
                      <button
                        onClick={() => setDrawer({ kind: "event", id: e.id })}
                        className="btn-ghost text-[13px] truncate text-left block px-2 py-0.5 -mx-2"
                      >
                        {e.title}
                      </button>
                      <div className="flex items-center gap-2 mt-0.5">
                        <span
                          className="chip"
                        >
                          {e.type}
                        </span>
                        <span className="text-meta text-[10px]">
                          {timeAgo(e.created_at)}
                        </span>
                      </div>
                    </div>
                    <ConfBadge value={e.confidence} />
                  </div>
                ))}
              </div>
            )}
          </SectionCard>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            {/* 4. Entity Momentum */}
            <SectionCard
              title="Hot Entities"
              empty={
                !data.entity_momentum?.length
                  ? "No notable entity activity"
                  : undefined
              }
            >
              {data.entity_momentum && data.entity_momentum.length > 0 && (
                <div className="flex flex-col gap-1.5">
                  {data.entity_momentum.slice(0, 8).map((e, i) => (
                    <div
                      key={e.name}
                      className="flex items-center justify-between py-1"
                    >
                      <div className="flex items-center gap-2">
                        <span
                          className="text-[10px] font-data w-4 text-right"
                          style={{ color: "var(--text-quaternary)" }}
                        >
                          {i + 1}
                        </span>
                        <span
                          className="text-[12px]"
                          style={{ color: "var(--text-primary)" }}
                        >
                          {e.name}
                        </span>
                      </div>
                      <span className="text-meta text-[10px]">
                        {e.mentions} mentions
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </SectionCard>

            {/* 5. Stale Theses */}
            <SectionCard
              title="Stale Theses"
              empty={
                !data.stale_theses?.length
                  ? "All theses are actively tracked"
                  : undefined
              }
            >
              {data.stale_theses && data.stale_theses.length > 0 && (
                <div className="flex flex-col gap-1.5">
                  {data.stale_theses.map((t) => (
                    <div
                      key={t.thesis}
                      className="flex items-center justify-between py-1"
                    >
                      <span
                        className="text-[12px]"
                        style={{ color: "var(--text-primary)" }}
                      >
                        {t.thesis}
                      </span>
                      <span
                        className="text-[10px] font-medium px-1.5 py-0.5 rounded"
                        style={{
                          color: "var(--status-high)",
                          background: "var(--status-high-bg)",
                        }}
                      >
                        {t.days_since_update}d stale
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </SectionCard>
          </div>
        </div>
      )}

      <DetailDrawer target={drawer} onClose={() => setDrawer(null)} />
    </div>
  );
}