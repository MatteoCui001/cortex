import { useEffect, useState, useCallback } from "react";
import { api, type Notification } from "../api";

const STATUS_FILTERS = ["all", "pending", "delivered", "read", "acked", "dismissed"] as const;

function PriorityDot({ priority }: { priority: string }) {
  const color = priority === "high" ? "var(--status-high)" : priority === "medium" ? "var(--status-medium)" : "var(--text-quaternary)";
  return <span className="inline-block w-1.5 h-1.5 rounded-full shrink-0 mt-[5px]" style={{ background: color }} />;
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

export default function Inbox() {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [filter, setFilter] = useState<string>("all");
  const [loading, setLoading] = useState(true);
  const [acting, setActing] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const status = filter === "all" ? undefined : filter;
      const data = await api.notifications(status, 100);
      setNotifications(data);
    } catch { /* ignore */ }
    setLoading(false);
  }, [filter]);

  useEffect(() => { load(); }, [load]);

  async function handleAction(id: string, action: "read" | "ack" | "dismiss") {
    setActing(id);
    try {
      const updated = await api.notificationAction(id, action);
      setNotifications((prev) => prev.map((n) => (n.id === id ? updated : n)));
    } catch { /* ignore */ }
    setActing(null);
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-heading">Inbox</h1>
          <p className="text-caption mt-1">Notifications from your knowledge system</p>
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

      {/* Filter tabs */}
      <div
        className="flex gap-0.5 mb-6 p-0.5 rounded-lg w-fit"
        style={{ background: "var(--bg-surface)" }}
      >
        {STATUS_FILTERS.map((s) => (
          <button
            key={s}
            onClick={() => setFilter(s)}
            className="text-[11px] px-2.5 py-1 rounded-md transition-all duration-150"
            style={{
              background: filter === s ? "var(--bg-elevated)" : "transparent",
              color: filter === s ? "var(--text-primary)" : "var(--text-tertiary)",
              fontWeight: filter === s ? 500 : 400,
            }}
          >
            {s}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="py-16 text-center text-body">Loading...</div>
      ) : notifications.length === 0 ? (
        <div
          className="rounded-xl p-12 text-center"
          style={{ background: "var(--bg-surface)", border: "1px solid var(--border-subtle)" }}
        >
          <div className="text-body">No notifications</div>
          <div className="text-meta mt-1">
            {filter === "all"
              ? "Your inbox is empty. Notifications appear when signals are detected."
              : `No ${filter} notifications.`}
          </div>
        </div>
      ) : (
        <div className="space-y-2">
          {notifications.map((n) => (
            <div
              key={n.id}
              className="rounded-xl px-5 py-4 transition-all duration-150"
              style={{
                background: "var(--bg-surface)",
                border: "1px solid var(--border-subtle)",
              }}
              onMouseEnter={(e) => (e.currentTarget.style.borderColor = "var(--border-default)")}
              onMouseLeave={(e) => (e.currentTarget.style.borderColor = "var(--border-subtle)")}
            >
              <div className="flex items-start gap-3">
                <PriorityDot priority={n.priority} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <StatusLabel status={n.status} />
                    <span className="text-meta font-mono">{n.id.slice(0, 7)}</span>
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
                {(n.status === "pending" || n.status === "delivered") && (
                  <div className="flex gap-1.5 shrink-0">
                    {(["Read", "Ack", "Dismiss"] as const).map((label) => {
                      const action = label.toLowerCase() as "read" | "ack" | "dismiss";
                      return (
                        <button
                          key={label}
                          onClick={() => handleAction(n.id, action)}
                          disabled={acting === n.id}
                          className="text-[11px] font-medium px-2.5 py-1 rounded-md transition-colors disabled:opacity-30"
                          style={{
                            color: "var(--text-secondary)",
                            border: "1px solid var(--border-default)",
                            background: "transparent",
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
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
