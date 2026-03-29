import { Routes, Route, NavLink, Navigate } from "react-router-dom";
import Overview from "./pages/Overview";
import Digest from "./pages/Digest";
import Inbox from "./pages/Inbox";
import Signals from "./pages/Signals";
import Events from "./pages/Events";
import Search from "./pages/Search";
import Graph from "./pages/Graph";
import Ingest from "./pages/Ingest";
import Theses from "./pages/Theses";
import Settings from "./pages/Settings";

const navItems = [
  { to: "/overview", label: "Overview", desc: "Dashboard" },
  { to: "/digest", label: "Digest", desc: "Daily Brief" },
  { to: "/theses", label: "Theses", desc: "Portfolio" },
  { to: "/inbox", label: "Inbox", desc: "Notifications" },
  { to: "/signals", label: "Signals", desc: "Insights" },
  { to: "/events", label: "Events", desc: "Knowledge" },
  { to: "/graph", label: "Graph", desc: "Entity Map" },
  { to: "/search", label: "Search", desc: "Find anything" },
  { to: "/ingest", label: "Ingest", desc: "Add content" },
  { to: "/settings", label: "Settings", desc: "Configuration" },
];

export default function App() {
  return (
    <div className="min-h-screen flex flex-col md:flex-row" style={{ background: "var(--bg-base)" }}>
      {/* Sidebar — hidden on mobile */}
      <nav
        className="hidden md:flex w-52 shrink-0 flex-col border-r"
        style={{
          background: "var(--bg-base)",
          borderColor: "var(--border-subtle)",
        }}
      >
        {/* Brand */}
        <div className="px-5 pt-6 pb-8">
          <div
            className="text-[15px] font-semibold tracking-tight"
            style={{ color: "var(--text-primary)" }}
          >
            Cortex
          </div>
          <div className="text-meta mt-0.5">Knowledge Infrastructure</div>
        </div>

        {/* Nav items */}
        <div className="flex-1 px-3 flex flex-col gap-0.5">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `group flex flex-col px-3 py-2 rounded-lg transition-all duration-150 ${
                  isActive ? "nav-active" : "nav-idle"
                }`
              }
              style={({ isActive }) => ({
                background: isActive ? "var(--bg-elevated)" : "transparent",
                borderLeft: isActive
                  ? "2px solid var(--text-accent)"
                  : "2px solid transparent",
              })}
            >
              {({ isActive }) => (
                <>
                  <span
                    className="text-[13px] font-medium"
                    style={{
                      color: isActive
                        ? "var(--text-primary)"
                        : "var(--text-secondary)",
                    }}
                  >
                    {item.label}
                  </span>
                  <span
                    className="text-[10px] mt-px"
                    style={{
                      color: isActive
                        ? "var(--text-tertiary)"
                        : "var(--text-quaternary)",
                    }}
                  >
                    {item.desc}
                  </span>
                </>
              )}
            </NavLink>
          ))}
        </div>

        {/* Footer */}
        <div className="px-5 py-4 border-t" style={{ borderColor: "var(--border-subtle)" }}>
          <div className="text-meta">v0.1.0</div>
        </div>
      </nav>

      {/* Main content */}
      <main className="flex-1 overflow-auto pb-16 md:pb-0">
        <div className="max-w-5xl mx-auto px-4 py-4 md:px-8 md:py-8">
          <Routes>
            <Route path="/" element={<Navigate to="/overview" replace />} />
            <Route path="/overview" element={<Overview />} />
            <Route path="/digest" element={<Digest />} />
            <Route path="/inbox" element={<Inbox />} />
            <Route path="/signals" element={<Signals />} />
            <Route path="/events" element={<Events />} />
            <Route path="/graph" element={<Graph />} />
            <Route path="/theses" element={<Theses />} />
            <Route path="/search" element={<Search />} />
            <Route path="/ingest" element={<Ingest />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </div>
      </main>

      {/* Mobile bottom tab bar */}
      <nav
        className="md:hidden fixed bottom-0 left-0 right-0 flex border-t z-50"
        style={{
          background: "var(--bg-base)",
          borderColor: "var(--border-subtle)",
        }}
      >
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className="flex-1 flex flex-col items-center py-2"
            style={({ isActive }) => ({
              color: isActive ? "var(--text-accent)" : "var(--text-quaternary)",
            })}
          >
            <span className="text-[11px] font-medium">{item.label}</span>
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
