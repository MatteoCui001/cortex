import { useEffect, useState } from "react";
import { api, type Stats, type Notification, type Signal, type Event } from "../api";
import { useNavigate } from "react-router-dom";

/* ── Shared small components ── */

function Metric({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div>
      <div className="text-subheading mb-1">{label}</div>
      <div className="text-2xl font-semibold" style={{ color: "var(--text-primary)", letterSpacing: "-0.02em" }}>
        {value}
      </div>
      {sub && <div className="text-meta mt-0.5">{sub}</div>}
    </div>
  );
}

function SectionHeader({ title, action, onAction }: { title: string; action?: string; onAction?: () => void }) {
  return (
    <div className="flex items-baseline justify-between mb-4">
      <h2 className="text-subheading">{title}</h2>
      {action && (
        <button
          onClick={onAction}
          className="text-[11px] font-medium transition-colors"
          style={{ color: "var(--text-accent-dim)" }}
          onMouseEnter={(e) => (e.currentTarget.style.color = "var(--text-accent)")}
          onMouseLeave={(e) => (e.currentTarget.style.color = "var(--text-accent-dim)")}
        >
          {action}
        </button>
      )}
    </div>
  );
}

function PriorityDot({ priority }: { priority: string }) {
  const color = priority === "high" ? "var(--status-high)" : priority === "medium" ? "var(--status-medium)" : "var(--text-quaternary)";
  return <span className="inline-block w-1.5 h-1.5 rounded-full shrink-0 mt-[5px]" style={{ background: color }} />;
}

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
    <span
      className="text-[10px] font-medium px-1.5 py-0.5 rounded"
      style={{ color: s.color, background: s.bg }}
    >
      {type}
    </span>
  );
}

function TypeBar({ distribution }: { distribution: Record<string, number> }) {
  const entries = Object.entries(distribution).sort((a, b) => b[1] - a[1]);
  const total = entries.reduce((s, [, c]) => s + c, 0);
  if (total === 0) return null;

  const colorMap: Record<string, string> = {
    article: "var(--type-article)", note: "var(--type-note)", chat: "var(--type-chat)",
    meeting: "var(--type-meeting)", thesis: "var(--type-thesis)", voice_memo: "var(--type-voice)",
    document: "var(--type-document)",
  };

  return (
    <div>
      <div className="flex rounded-full overflow-hidden h-1 mb-3" style={{ background: "var(--bg-active)" }}>
        {entries.map(([type, count]) => (
          <div
            key={type}
            className="opacity-80"
            style={{ width: `${(count / total) * 100}%`, background: colorMap[type] ?? "var(--text-quaternary)" }}
          />
        ))}
      </div>
      <div className="flex flex-wrap gap-x-4 gap-y-1">
        {entries.map(([type, count]) => (
          <div key={type} className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full opacity-80" style={{ background: colorMap[type] ?? "var(--text-quaternary)" }} />
            <span className="text-meta">{type}</span>
            <span className="text-[11px] font-medium" style={{ color: "var(--text-secondary)" }}>{count}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ── Main page ── */

export default function Overview() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [signals, setSignals] = useState<Signal[]>([]);
  const [recentEvents, setRecentEvents] = useState<Event[]>([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    setLoading(true);
    Promise.all([
      api.stats().catch(() => null),
      api.notifications(undefined, 20).catch(() => []),
      api.signals(10).catch(() => []),
      api.events(10, 7).catch(() => []),
    ]).then(([s, n, sig, ev]) => {
      if (s) setStats(s);
      setNotifications(n as Notification[]);
      setSignals(sig as Signal[]);
      setRecentEvents(ev as Event[]);
      setLoading(false);
    });
  }, []);

  const activeNotifs = notifications.filter(n => n.status === "pending" || n.status === "delivered");
  const deliveredCount = notifications.filter(n => n.status === "delivered").length;

  if (loading) {
    return (
      <div className="py-16 text-center">
        <div className="text-body">Loading...</div>
      </div>
    );
  }

  return (
    <div>
      {/* Page header */}
      <div className="mb-8">
        <h1 className="text-heading">Overview</h1>
        <p className="text-caption mt-1">What your knowledge system has been doing</p>
      </div>

      {/* Metrics strip */}
      <div
        className="grid grid-cols-4 gap-8 p-5 rounded-xl mb-8"
        style={{ background: "var(--bg-surface)", border: "1px solid var(--border-subtle)" }}
      >
        <Metric label="Events" value={stats?.events ?? 0} />
        <Metric label="Entities" value={stats?.entities ?? 0} />
        <Metric
          label="Pending"
          value={activeNotifs.filter(n => n.status === "pending").length}
          sub={deliveredCount > 0 ? `${deliveredCount} delivered` : undefined}
        />
        <Metric label="Signals" value={signals.length} />
      </div>

      {/* Type distribution */}
      {stats?.type_distribution && Object.keys(stats.type_distribution).length > 0 && (
        <div
          className="p-5 rounded-xl mb-8"
          style={{ background: "var(--bg-surface)", border: "1px solid var(--border-subtle)" }}
        >
          <SectionHeader title="Knowledge Distribution" />
          <TypeBar distribution={stats.type_distribution} />
        </div>
      )}

      {/* Two-column: Notifications + Recent Ingests */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        {/* Active notifications */}
        <div
          className="p-5 rounded-xl"
          style={{ background: "var(--bg-surface)", border: "1px solid var(--border-subtle)" }}
        >
          <SectionHeader title="Active Notifications" action="View all" onAction={() => navigate("/inbox")} />
          {activeNotifs.length === 0 ? (
            <div className="py-6 text-center">
              <div className="text-caption">All clear</div>
              <div className="text-meta mt-1">No pending notifications</div>
            </div>
          ) : (
            <div className="space-y-1">
              {activeNotifs.slice(0, 6).map((n) => (
                <div key={n.id} className="flex items-start gap-2.5 py-2 px-1 rounded-lg" style={{ transition: "background 120ms" }}>
                  <PriorityDot priority={n.priority} />
                  <div className="flex-1 min-w-0">
                    <div className="text-[13px] font-medium truncate" style={{ color: "var(--text-primary)" }}>{n.title}</div>
                    <div className="text-meta">{n.status}</div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Recent events */}
        <div
          className="p-5 rounded-xl"
          style={{ background: "var(--bg-surface)", border: "1px solid var(--border-subtle)" }}
        >
          <SectionHeader title="Recent Ingests (7d)" action="View all" onAction={() => navigate("/events")} />
          {recentEvents.length === 0 ? (
            <div className="py-6 text-center">
              <div className="text-caption">No recent ingests</div>
              <div className="text-meta mt-1">Send content via WeChat to get started</div>
            </div>
          ) : (
            <div className="space-y-1">
              {recentEvents.slice(0, 8).map((e) => (
                <div key={e.id} className="flex items-start gap-2.5 py-2 px-1">
                  <TypeLabel type={e.type} />
                  <div className="flex-1 min-w-0">
                    <div className="text-[13px] truncate" style={{ color: "var(--text-primary)" }}>{e.title || "—"}</div>
                  </div>
                  <span className="text-meta shrink-0">{new Date(e.created_at).toLocaleDateString()}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Signals preview */}
      {signals.length > 0 && (
        <div
          className="p-5 rounded-xl"
          style={{ background: "var(--bg-surface)", border: "1px solid var(--border-subtle)" }}
        >
          <SectionHeader title="Recent Signals" action="View all" onAction={() => navigate("/signals")} />
          <div className="space-y-2">
            {signals.slice(0, 5).map((s) => (
              <div key={s.id} className="flex items-start gap-3 py-2 px-1">
                <span
                  className="text-[10px] font-medium px-1.5 py-0.5 rounded shrink-0 mt-px"
                  style={{ color: "var(--type-thesis)", background: "var(--type-thesis-bg)" }}
                >
                  {s.signal_type}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="text-[13px]" style={{ color: "var(--text-primary)" }}>{s.topic || s.summary || "—"}</div>
                  {s.rationale && <div className="text-meta mt-0.5 line-clamp-1">{s.rationale}</div>}
                </div>
                <span className="text-meta shrink-0">{s.priority_score.toFixed(2)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
