import { useEffect, useState, useCallback } from "react";
import { api, type Notification } from "../api";

const STATUS_FILTERS = ["all", "pending", "delivered", "read", "acked", "dismissed"] as const;

function PriorityBadge({ priority }: { priority: string }) {
  const colors: Record<string, string> = {
    high: "bg-red-500/20 text-red-400 border-red-500/30",
    medium: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
    low: "bg-[#2a2e3a] text-[#8b8fa3] border-[#2a2e3a]",
  };
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full border ${colors[priority] ?? colors.low}`}>
      {priority}
    </span>
  );
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    pending: "text-yellow-400",
    delivered: "text-blue-400",
    read: "text-green-400",
    acked: "text-[#8b8fa3]",
    dismissed: "text-[#555]",
  };
  return <span className={`text-xs ${colors[status] ?? "text-[#8b8fa3]"}`}>{status}</span>;
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
    } catch {
      /* ignore */
    }
    setLoading(false);
  }, [filter]);

  useEffect(() => { load(); }, [load]);

  async function handleAction(id: string, action: "read" | "ack" | "dismiss") {
    setActing(id);
    try {
      const updated = await api.notificationAction(id, action);
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? updated : n))
      );
    } catch {
      /* ignore */
    }
    setActing(null);
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-semibold text-white">Inbox</h1>
        <button
          onClick={load}
          className="text-xs text-[#8b8fa3] hover:text-white bg-[#1a1d27] border border-[#2a2e3a] px-3 py-1.5 rounded-lg transition-colors"
        >
          Refresh
        </button>
      </div>

      {/* Filter tabs */}
      <div className="flex gap-1 mb-5 bg-[#13151c] p-1 rounded-lg w-fit">
        {STATUS_FILTERS.map((s) => (
          <button
            key={s}
            onClick={() => setFilter(s)}
            className={`text-xs px-3 py-1.5 rounded-md transition-colors ${
              filter === s
                ? "bg-[#2a2e3a] text-white"
                : "text-[#8b8fa3] hover:text-white"
            }`}
          >
            {s}
          </button>
        ))}
      </div>

      {loading ? (
        <p className="text-[#8b8fa3] text-sm">Loading...</p>
      ) : notifications.length === 0 ? (
        <div className="bg-[#1a1d27] border border-[#2a2e3a] rounded-xl p-8 text-center">
          <p className="text-[#8b8fa3]">No notifications</p>
        </div>
      ) : (
        <div className="space-y-2">
          {notifications.map((n) => (
            <div
              key={n.id}
              className="bg-[#1a1d27] border border-[#2a2e3a] rounded-xl p-4 hover:border-[#3a3e4a] transition-colors"
            >
              <div className="flex items-start gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <PriorityBadge priority={n.priority} />
                    <StatusBadge status={n.status} />
                    <span className="text-[#555] text-xs font-mono">{n.id.slice(0, 7)}</span>
                  </div>
                  <div className="text-white text-sm font-medium mb-1">{n.title}</div>
                  {n.body && (
                    <div className="text-[#8b8fa3] text-xs line-clamp-2">{n.body}</div>
                  )}
                  <div className="text-[#555] text-xs mt-2">
                    {new Date(n.created_at).toLocaleString()}
                    {n.source_kind && <span className="ml-2">{n.source_kind}</span>}
                  </div>
                </div>

                {/* Actions — only for actionable states */}
                {(n.status === "pending" || n.status === "delivered") && (
                  <div className="flex gap-1.5 shrink-0">
                    <ActionBtn
                      label="Read"
                      onClick={() => handleAction(n.id, "read")}
                      disabled={acting === n.id}
                      color="blue"
                    />
                    <ActionBtn
                      label="Ack"
                      onClick={() => handleAction(n.id, "ack")}
                      disabled={acting === n.id}
                      color="green"
                    />
                    <ActionBtn
                      label="Dismiss"
                      onClick={() => handleAction(n.id, "dismiss")}
                      disabled={acting === n.id}
                      color="gray"
                    />
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

function ActionBtn({
  label,
  onClick,
  disabled,
  color,
}: {
  label: string;
  onClick: () => void;
  disabled: boolean;
  color: "blue" | "green" | "gray";
}) {
  const colors = {
    blue: "text-blue-400 hover:bg-blue-500/20",
    green: "text-green-400 hover:bg-green-500/20",
    gray: "text-[#8b8fa3] hover:bg-[#2a2e3a]",
  };
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`text-xs px-2.5 py-1 rounded-md border border-[#2a2e3a] transition-colors disabled:opacity-40 ${colors[color]}`}
    >
      {label}
    </button>
  );
}
