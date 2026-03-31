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
  { to: "/digest", label: "Digest", desc: "Brief" },
  { to: "/theses", label: "Theses", desc: "Portfolio" },
  { to: "/inbox", label: "Inbox", desc: "Alerts" },
  { to: "/signals", label: "Signals", desc: "Insights" },
  { to: "/events", label: "Events", desc: "Store" },
  { to: "/graph", label: "Graph", desc: "Entities" },
  { to: "/search", label: "Search", desc: "Query" },
  { to: "/ingest", label: "Ingest", desc: "Add" },
  { to: "/settings", label: "Settings", desc: "Config" },
];

export default function App() {
  return (
    <div className="min-h-screen flex flex-col md:flex-row" style={{ background: "var(--bg-base)" }}>
      {/* Sidebar */}
      <nav
        className="hidden md:flex w-52 shrink-0 flex-col border-r"
        style={{ background: "var(--bg-base)", borderColor: "var(--border-subtle)" }}
      >
        {/* Brand */}
        <div className="px-4 pt-6 pb-5 flex items-center gap-3">
          <div className="brand-glyph">C</div>
          <div>
            <div className="text-[14px] font-bold tracking-tight" style={{ color: "var(--text-primary)" }}>
              Cortex
            </div>
            <div className="font-data text-[10px]" style={{ color: "var(--text-quaternary)" }}>
              v0.1.0-beta
            </div>
          </div>
        </div>

        {/* Nav */}
        <div className="flex-1 px-3 flex flex-col gap-0.5 overflow-y-auto">
          {navItems.map((item) => (
            <NavLink key={item.to} to={item.to} className="nav-item" data-active={undefined}>
              {({ isActive }) => (
                <div className="nav-item" data-active={isActive ? "true" : undefined} style={{ padding: 0, border: "none" }}>
                  <span className="nav-label">{item.label}</span>
                  <span className="nav-desc">{item.desc}</span>
                </div>
              )}
            </NavLink>
          ))}
        </div>

        {/* Footer */}
        <div className="px-4 py-3">
          <div className="text-[10px] font-data" style={{ color: "var(--text-quaternary)" }}>Knowledge Infrastructure</div>
        </div>
      </nav>

      {/* Main */}
      <main className="flex-1 overflow-auto pb-16 md:pb-0">
        <div className="max-w-5xl mx-auto px-4 py-5 md:px-10 md:py-8">
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

      {/* Mobile bottom tabs */}
      <nav
        className="md:hidden fixed bottom-0 left-0 right-0 flex border-t z-50"
        style={{ background: "var(--bg-glass)", borderColor: "var(--border-subtle)", backdropFilter: "blur(16px)" }}
      >
        {navItems.slice(0, 6).map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className="flex-1 flex flex-col items-center py-2.5"
            style={({ isActive }) => ({
              color: isActive ? "var(--text-accent)" : "var(--text-quaternary)",
            })}
          >
            <span className="text-[10px] font-medium">{item.label}</span>
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
