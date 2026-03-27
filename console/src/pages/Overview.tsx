import { useEffect, useState } from "react";
import { api, type Stats, type Notification, type Signal, type Event } from "../api";
import { useNavigate } from "react-router-dom";

function StatCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="bg-[#1a1d27] border border-[#2a2e3a] rounded-xl p-5">
      <div className="text-[#8b8fa3] text-xs uppercase tracking-wider mb-1">{label}</div>
      <div className="text-2xl font-semibold text-white">{value}</div>
      {sub && <div className="text-[#555] text-xs mt-1">{sub}</div>}
    </div>
  );
}

function PriorityBadge({ priority }: { priority: string }) {
  const colors: Record<string, string> = {
    high: "bg-red-500/20 text-red-400",
    medium: "bg-yellow-500/20 text-yellow-400",
    low: "bg-[#2a2e3a] text-[#8b8fa3]",
  };
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full ${colors[priority] ?? colors.low}`}>
      {priority}
    </span>
  );
}

function TypeBar({ distribution }: { distribution: Record<string, number> }) {
  const entries = Object.entries(distribution).sort((a, b) => b[1] - a[1]);
  const total = entries.reduce((s, [, c]) => s + c, 0);
  if (total === 0) return null;

  const colors = [
    "bg-blue-500", "bg-green-500", "bg-yellow-500", "bg-purple-500",
    "bg-pink-500", "bg-orange-500", "bg-teal-500", "bg-red-500",
  ];

  return (
    <div>
      <div className="flex rounded-full overflow-hidden h-2 mb-3">
        {entries.map(([type, count], i) => (
          <div
            key={type}
            className={`${colors[i % colors.length]} opacity-70`}
            style={{ width: `${(count / total) * 100}%` }}
          />
        ))}
      </div>
      <div className="flex flex-wrap gap-x-4 gap-y-1">
        {entries.map(([type, count], i) => (
          <div key={type} className="flex items-center gap-1.5 text-xs">
            <div className={`w-2 h-2 rounded-full ${colors[i % colors.length]} opacity-70`} />
            <span className="text-[#8b8fa3]">{type}</span>
            <span className="text-white font-medium">{count}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

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

  const pendingCount = notifications.filter(n => n.status === "pending").length;
  const deliveredCount = notifications.filter(n => n.status === "delivered").length;

  if (loading) return <p className="text-[#8b8fa3] text-sm p-4">Loading...</p>;

  return (
    <div>
      <h1 className="text-xl font-semibold text-white mb-6">Overview</h1>

      {/* Stats row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <StatCard label="Total Events" value={stats?.events ?? 0} />
        <StatCard label="Entities" value={stats?.entities ?? 0} />
        <StatCard
          label="Pending"
          value={pendingCount}
          sub={deliveredCount > 0 ? `${deliveredCount} delivered` : undefined}
        />
        <StatCard label="Signals" value={signals.length} sub="last 50" />
      </div>

      {/* Type distribution */}
      {stats?.type_distribution && Object.keys(stats.type_distribution).length > 0 && (
        <div className="bg-[#1a1d27] border border-[#2a2e3a] rounded-xl p-5 mb-8">
          <h2 className="text-sm font-medium text-[#8b8fa3] uppercase tracking-wider mb-3">Knowledge Distribution</h2>
          <TypeBar distribution={stats.type_distribution} />
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Active notifications */}
        <div className="bg-[#1a1d27] border border-[#2a2e3a] rounded-xl p-5">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-medium text-[#8b8fa3] uppercase tracking-wider">Active Notifications</h2>
            <button onClick={() => navigate("/inbox")} className="text-xs text-indigo-400/70 hover:text-indigo-400">
              View all
            </button>
          </div>
          {notifications.filter(n => n.status === "pending" || n.status === "delivered").length === 0 ? (
            <p className="text-[#555] text-sm py-4 text-center">All clear</p>
          ) : (
            <div className="space-y-2">
              {notifications
                .filter(n => n.status === "pending" || n.status === "delivered")
                .slice(0, 6)
                .map((n) => (
                  <div key={n.id} className="flex items-center gap-3 text-sm py-1.5">
                    <PriorityBadge priority={n.priority} />
                    <span className="text-white flex-1 truncate">{n.title}</span>
                    <span className="text-[#555] text-xs">{n.status}</span>
                  </div>
                ))}
            </div>
          )}
        </div>

        {/* Recent events */}
        <div className="bg-[#1a1d27] border border-[#2a2e3a] rounded-xl p-5">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-medium text-[#8b8fa3] uppercase tracking-wider">Recent Ingests (7d)</h2>
            <button onClick={() => navigate("/events")} className="text-xs text-indigo-400/70 hover:text-indigo-400">
              View all
            </button>
          </div>
          {recentEvents.length === 0 ? (
            <p className="text-[#555] text-sm py-4 text-center">No recent ingests</p>
          ) : (
            <div className="space-y-2">
              {recentEvents.slice(0, 8).map((e) => (
                <div key={e.id} className="flex items-start gap-3 text-sm py-1.5">
                  <span className="text-indigo-400 text-xs bg-indigo-500/10 px-2 py-0.5 rounded shrink-0">{e.type}</span>
                  <span className="text-white flex-1 truncate">{e.title}</span>
                  <span className="text-[#555] text-xs shrink-0">{new Date(e.created_at).toLocaleDateString()}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Recent signals */}
      {signals.length > 0 && (
        <div className="bg-[#1a1d27] border border-[#2a2e3a] rounded-xl p-5 mt-6">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-medium text-[#8b8fa3] uppercase tracking-wider">Recent Signals</h2>
            <button onClick={() => navigate("/signals")} className="text-xs text-indigo-400/70 hover:text-indigo-400">
              View all
            </button>
          </div>
          <div className="space-y-2">
            {signals.slice(0, 5).map((s) => (
              <div key={s.id} className="flex items-center gap-3 text-sm py-1.5">
                <span className="text-xs px-2 py-0.5 rounded-full bg-purple-500/20 text-purple-400">
                  {s.signal_type}
                </span>
                <span className="text-white flex-1 truncate">{s.topic || s.summary || "—"}</span>
                <span className="text-[#555] text-xs">{s.priority_score.toFixed(2)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
