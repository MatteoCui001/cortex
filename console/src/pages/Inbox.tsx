import { useEffect, useState, useCallback } from "react";
import { api, type Notification } from "../api";
import DetailDrawer, { type DrawerTarget } from "../DetailDrawer";

const STATUS_FILTERS = ["all", "pending", "delivered", "read", "acked", "dismissed"] as const;
const PRIORITY_FILTERS = ["all", "high", "medium", "low"] as const;

function PriorityDot({ priority }: { priority: string }) {
  const color = priority === "high" ? "var(--status-high)" : priority === "medium" ? "var(--status-medium)" : "var(--text-quaternary)";
  return <span className="inline-block w-2 h-2 rounded-full shrink-0" style={{ background: color }} />;
}

function StatusLabel({ status }: { status: string }) {
  const colorMap: Record<string, string> = {
    pending: "var(--status-medium)",
    delivered: "var(--type-article)",
    read: "var(--status-success)",
    acked: "var(--text-tertiary)",
    dismissed: "var(--text-quaternary)",
  };
  return <span className="text-[10px] font-medium" style={{ color: colorMap[status] ?? "var(--text-tertiary)" }}>{status}</span>;
}

function FilterBar({ options, value, onChange }: { options: readonly string[]; value: string; onChange: (v: string) => void }) {
  return (
    <div className="flex gap-0.5 p-0.5 rounded-lg" style={{ background: "var(--bg-surface)" }}>
      {options.map((s) => (
        <button
          key={s}
          onClick={() => onChange(s)}
          className="text-[11px] px-2.5 py-1 rounded-md transition-all duration-150"
          style={{
            background: value === s ? "var(--bg-elevated)" : "transparent",
            color: value === s ? "var(--text-primary)" : "var(--text-tertiary)",
            fontWeight: value === s ? 500 : 400,
          }}
        >
          {s}
        </button>
      ))}
    </div>
  );
}

export default function Inbox() {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [priorityFilter, setPriorityFilter] = useState<string>("all");
  const [loading, setLoading] = useState(true);
  const [acting, setActing] = useState<string | null>(null);
  const [drawer, setDrawer] = useState<DrawerTarget | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const status = statusFilter === "all" ? undefined : statusFilter;
      const data = await api.notifications(status, 100);
      setNotifications(data);
    } catch { /* ignore */ }
    setLoading(false);
  }, [statusFilter]);

  useEffect(() => { load(); }, [load]);

  async function handleAction(id: string, action: "read" | "ack" | "dismiss") {
    setActing(id);
    try {
      const updated = await api.notificationAction(id, action);
      setNotifications((prev) => prev.map((n) => (n.id === id ? updated : n)));
    } catch { /* ignore */ }
    setActing(null);
  }

  // Apply priority filter on top of status filter
  const filtered = priorityFilter === "all"
    ? notifications
    : notifications.filter((n) => n.priority === priorityFilter);

  // Split into needs-attention vs rest
  const needsAttention = filtered.filter((n) => n.status === "pending" || n.status === "delivered");
  const rest = filtered.filter((n) => n.status !== "pending" && n.status !== "delivered");

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-heading">Inbox</h1>
          <p className="text-caption mt-1">Triage notifications from your knowledge system</p>
        </div>
        <button
          onClick={load}
          className="text-[11px] font-medium px-3 py-1.5 rounded-lg transition-colors"
          style={{
            color: "var(--text-secondary)",
            background: "var(--bg-surface)",
            border: "1px solid var(--border-default)",
          }}
        >
          Refresh
        </button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3 mb-6">
        <FilterBar options={STATUS_FILTERS} value={statusFilter} onChange={setStatusFilter} />
        <FilterBar options={PRIORITY_FILTERS} value={priorityFilter} onChange={setPriorityFilter} />
        <span className="text-meta ml-auto">{filtered.length} notifications</span>
      </div>

      {loading ? (
        <div className="py-16 text-center text-body">Loading...</div>
      ) : filtered.length === 0 ? (
        <div
          className="rounded-xl p-12 text-center"
          style={{ background: "var(--bg-surface)", border: "1px solid var(--border-subtle)" }}
        >
          <div className="text-body">No notifications</div>
          <div className="text-meta mt-1">
            {statusFilter === "all" && priorityFilter === "all"
              ? "Your inbox is empty. Notifications appear when signals are detected."
              : "No matching notifications."}
          </div>
        </div>
      ) : (
        <>
          {/* Needs attention section */}
          {needsAttention.length > 0 && statusFilter === "all" && (
            <div className="mb-6">
              <div className="text-subheading mb-3">Needs Attention ({needsAttention.length})</div>
              <div className="space-y-2">
                {needsAttention.map((n) => (
                  <NotifCard
                    key={n.id}
                    n={n}
                    acting={acting}
                    onAction={handleAction}
                    onContext={() => setDrawer({ kind: "notification", id: n.id, related_event_ids: n.related_event_ids, signal_id: n.signal_id })}
                    highlight
                  />
                ))}
              </div>
            </div>
          )}

          {/* Other / all */}
          {(statusFilter !== "all" ? filtered : rest).length > 0 && (
            <div>
              {statusFilter === "all" && rest.length > 0 && (
                <div className="text-subheading mb-3">Earlier</div>
              )}
              <div className="space-y-2">
                {(statusFilter !== "all" ? filtered : rest).map((n) => (
                  <NotifCard
                    key={n.id}
                    n={n}
                    acting={acting}
                    onAction={handleAction}
                    onContext={() => setDrawer({ kind: "notification", id: n.id, related_event_ids: n.related_event_ids, signal_id: n.signal_id })}
                  />
                ))}
              </div>
            </div>
          )}
        </>
      )}

      <DetailDrawer target={drawer} onClose={() => setDrawer(null)} />
    </div>
  );
}

/* ── Notification card component ── */

function NotifCard({
  n,
  acting,
  onAction,
  onContext,
  highlight,
}: {
  n: Notification;
  acting: string | null;
  onAction: (id: string, action: "read" | "ack" | "dismiss") => void;
  onContext: () => void;
  highlight?: boolean;
}) {
  return (
    <div
      className="rounded-xl px-5 py-4 transition-all duration-150"
      style={{
        background: "var(--bg-surface)",
        border: highlight
          ? "1px solid var(--border-accent)"
          : "1px solid var(--border-subtle)",
      }}
      onMouseEnter={(e) => (e.currentTarget.style.borderColor = "var(--border-default)")}
      onMouseLeave={(e) => (e.currentTarget.style.borderColor = highlight ? "rgba(129,140,248,0.2)" : "var(--border-subtle)")}
    >
      <div className="flex items-start gap-3">
        <PriorityDot priority={n.priority} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <StatusLabel status={n.status} />
            <span className="text-meta font-mono">{n.id.slice(0, 7)}</span>
            {n.related_event_ids.length > 0 && (
              <span className="text-meta">{n.related_event_ids.length} event{n.related_event_ids.length > 1 ? "s" : ""}</span>
            )}
          </div>
          <div className="text-[13px] font-medium mb-1" style={{ color: "var(--text-primary)" }}>
            {n.title}
          </div>
          {n.body && (
            <div className="text-[12px] line-clamp-2" style={{ color: "var(--text-tertiary)" }}>
              {n.body}
            </div>
          )}
          <div className="text-meta mt-2">
            {new Date(n.created_at).toLocaleString()}
            {n.source_kind && <span className="ml-2">{n.source_kind}</span>}
          </div>
        </div>

        {/* Actions */}
        <div className="flex flex-col gap-1.5 shrink-0">
          <button
            onClick={onContext}
            className="text-[11px] font-medium px-2.5 py-1 rounded-md transition-colors"
            style={{
              color: "var(--text-accent-dim)",
              border: "1px solid var(--border-accent)",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = "rgba(129,140,248,0.08)";
              e.currentTarget.style.color = "var(--text-accent)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "transparent";
              e.currentTarget.style.color = "var(--text-accent-dim)";
            }}
          >
            Context
          </button>
          {(n.status === "pending" || n.status === "delivered") && (
            <>
              {(["Read", "Ack", "Dismiss"] as const).map((label) => {
                const action = label.toLowerCase() as "read" | "ack" | "dismiss";
                return (
                  <button
                    key={label}
                    onClick={() => onAction(n.id, action)}
                    disabled={acting === n.id}
                    className="text-[11px] font-medium px-2.5 py-1 rounded-md transition-colors disabled:opacity-30"
                    style={{
                      color: "var(--text-secondary)",
                      border: "1px solid var(--border-default)",
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.background = "var(--bg-elevated)";
                      e.currentTarget.style.color = "var(--text-primary)";
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background = "transparent";
                      e.currentTarget.style.color = "var(--text-secondary)";
                    }}
                  >
                    {label}
                  </button>
                );
              })}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
