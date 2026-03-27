import { Routes, Route, NavLink, Navigate } from "react-router-dom";
import Overview from "./pages/Overview";
import Inbox from "./pages/Inbox";
import Signals from "./pages/Signals";
import Events from "./pages/Events";

const navItems = [
  { to: "/overview", label: "Overview" },
  { to: "/inbox", label: "Inbox" },
  { to: "/signals", label: "Signals" },
  { to: "/events", label: "Events" },
];

export default function App() {
  return (
    <div className="min-h-screen flex">
      {/* Sidebar */}
      <nav className="w-56 shrink-0 bg-[#13151c] border-r border-[#2a2e3a] px-3 py-5 flex flex-col gap-1">
        <div className="text-lg font-semibold text-white px-3 mb-4 tracking-tight">
          Cortex
        </div>
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              `block px-3 py-2 rounded-lg text-sm transition-colors ${
                isActive
                  ? "bg-indigo-600/20 text-indigo-400 font-medium"
                  : "text-[#8b8fa3] hover:bg-[#1e2130] hover:text-[#c4c7d4]"
              }`
            }
          >
            {item.label}
          </NavLink>
        ))}
      </nav>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <div className="max-w-6xl mx-auto px-6 py-6">
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
