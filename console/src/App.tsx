import { Routes, Route, NavLink, Navigate } from "react-router-dom";
import Overview from "./pages/Overview";
import Inbox from "./pages/Inbox";
import Signals from "./pages/Signals";
import Events from "./pages/Events";

const navItems = [
  { to: "/overview", label: "Overview", desc: "Dashboard" },
  { to: "/inbox", label: "Inbox", desc: "Notifications" },
  { to: "/signals", label: "Signals", desc: "Insights" },
  { to: "/events", label: "Events", desc: "Knowledge" },
];

export default function App() {
  return (
    <div className="min-h-screen flex" style={{ background: "var(--bg-base)" }}>
      {/* Sidebar */}
      <nav
        className="w-52 shrink-0 flex flex-col border-r"
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
      <main className="flex-1 overflow-auto">
        <div className="max-w-5xl mx-auto px-8 py-8">
          <Routes>
            <Route path="/" element={<Navigate to="/overview" replace />} />
            <Route path="/overview" element={<Overview />} />
            <Route path="/inbox" element={<Inbox />} />
            <Route path="/signals" element={<Signals />} />
            <Route path="/events" element={<Events />} />
          </Routes>
        </div>
      </main>
    </div>
  );
}
