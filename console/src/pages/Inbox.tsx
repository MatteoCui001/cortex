import { useEffect, useState, useCallback } from "react";
import { api, type Notification } from "../api";
import DetailDrawer, { type DrawerTarget } from "../DetailDrawer";
import { useToast } from "../Toast";

const STATUS_FILTERS = ["all", "pending", "delivered", "read", "acked", "dismissed"] as const;
const PRIORITY_FILTERS = ["all", "high", "medium", "low"] as const;

function PriorityDot({ priority }: { priority: string }) {
  const cls = priority === "high" ? "dot-high" : priority === "medium" ? "dot-medium" : "dot-low";
  return <span className={`dot ${cls}`} />;
}

function StatusLabel({ status }: { status: string }) {
  const colorMap: Record<string, string> = {
    pending: "var(--status-medium)",
    delivered: "var(--type-article)",
    read: "var(--status-success)",
    acked: "var(--text-tertiary)",
    dismissed: "var(--text-quaternary)",
  };
  return <span className="text-[10px] font-semibold font-data" style={{ color: colorMap[status] ?? "var(--text-tertiary)" }}>{status}</span>;
}

function FilterBar({ options, value, onChange }: { options: readonly string[]; value: string; onChange: (v: string) => void }) {
  return (
    <div className="segment-control">
      {options.map((s) => (
        <button
          key={s}
          onClick={() => onChange(s)}
          className="segment-btn"
          data-active={value === s ? "true" : undefined}
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
  const [error, setError] = useState<string | null>(null);
  const [acting, setActing] = useState<string | null>(null);
  const [drawer, setDrawer] = useState<DrawerTarget | null>(null);
  const { toast } = useToast();

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const status = statusFilter === "all" ? undefined : statusFilter;
      const data = await api.notifications(status, 100);
      setNotifications(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load notifications");
    }
    setLoading(false);
  }, [statusFilter]);

  useEffect(() => { load(); }, [load]);

  async function handleAction(id: string, action: "read" | "ack" | "dismiss") {
    setActing(id);
    try {
      const updated = await api.notificationAction(id, action);
      setNotifications((prev) => prev.map((n) => (n.id === id ? updated : n)));
    } catch (e: unknown) {
      toast(e instanceof Error ? e.message : "Action failed", "error");
    }
    setActing(null);
  }

  const [bulkActing, setBulkActing] = useState(false);

  async function handleBulkAction(action: "read" | "ack" | "dismiss") {
    if (action === "dismiss" && !window.confirm("Dismiss all visible notifications?")) return;
    setBulkActing(true);
    try {
      const targetStatus = statusFilter === "all" ? "pending" : statusFilter;
      await api.bulkNotificationAction(action, undefined, targetStatus);
      await load();
    } catch (e: unknown) {
      toast(e instanceof Error ? e.message : "Bulk action failed", "error");
    }
    setBulkActing(false);
  }

  const filtered = priorityFilter === "all"
    ? notifications
    : notifications.filter((n) => n.priority === priorityFilter);

  const needsAttention = filtered.filter((n) => n.status === "pending" || n.status === "delivered");
  const rest = filtered.filter((n) => n.status !== "pending" && n.status !== "delivered");

  return (
    <div>
      <div className="flex items-center justify-between mb-5 animate-in">
        <div>
          <h1 className="text-heading">Inbox</h1>
          <p className="text-caption mt-1">Triage notifications from your knowledge system</p>
        </div>
        <button onClick={load} className="btn-ghost text-[11px] font-medium px-3 py-1.5">
          Refresh
        </button>
      </div>

      <div className="flex flex-wrap items-center gap-3 mb-6 animate-in animate-in-delay-1">
        <FilterBar options={STATUS_FILTERS} value={statusFilter} onChange={setStatusFilter} />
        <FilterBar options={PRIORITY_FILTERS} value={priorityFilter} onChange={setPriorityFilter} />
        <span className="text-meta ml-auto">{filtered.length} notifications</span>
      </div>

      {needsAttention.length > 0 && (
        <div className="flex items-center gap-2 mb-4 animate-in animate-in-delay-2">
          <button
            onClick={() => handleBulkAction("read")}
            disabled={bulkActing}
            className="btn-ghost text-[11px] font-medium px-3 py-1.5 disabled:opacity-30"
          >
            Mark all read
          </button>
          <button
            onClick={() => handleBulkAction("dismiss")}
            disabled={bulkActing}
            className="btn-ghost text-[11px] font-medium px-3 py-1.5 disabled:opacity-30"
          >
            Dismiss all
          </button>
          {bulkActing && <span className="text-meta">Processing...</span>}
        </div>
      )}

      {error && (
        <div className="text-[12px] py-3 px-4 rounded-lg mb-4"
          style={{ background: "var(--status-high-bg)", color: "var(--status-high)" }}>
          {error}
        </div>
      )}

      {loading ? (
        <div className="py-16 text-center text-body" style={{ color: "var(--text-tertiary)" }}>Loading...</div>
      ) : filtered.length === 0 && !error ? (
        <div className="card p-12 text-center">
          <div className="text-body">No notifications</div>
          <div className="text-meta mt-1">
            {statusFilter === "all" && priorityFilter === "all"
              ? "Your inbox is empty. Notifications appear when signals are detected."
              : "No matching notifications."}
          </div>
        </div>
      ) : (
        <>
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
      className="notif-card px-5 py-4"
      data-highlight={highlight ? "true" : undefined}
    >
      <div className="flex items-start gap-3">
        <PriorityDot priority={n.priority} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <StatusLabel status={n.status} />
            <span className="text-meta">{n.id.slice(0, 7)}</span>
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

        <div className="flex flex-col gap-1.5 shrink-0">
          <button onClick={onContext} className="btn-accent text-[11px] font-medium px-2.5 py-1">
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
                    className="btn-ghost text-[11px] font-medium px-2.5 py-1 disabled:opacity-30"
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
