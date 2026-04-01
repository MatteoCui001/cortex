import { createContext, useContext, useState, useCallback, type ReactNode } from "react";

interface Toast {
  id: number;
  message: string;
  type: "error" | "success" | "info";
}

interface ToastContextValue {
  toast: (message: string, type?: "error" | "success" | "info") => void;
}

const ToastContext = createContext<ToastContextValue>({ toast: () => {} });

export function useToast() {
  return useContext(ToastContext);
}

let nextId = 0;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const toast = useCallback((message: string, type: "error" | "success" | "info" = "error") => {
    const id = nextId++;
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4000);
  }, []);

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      <div style={{
        position: "fixed",
        bottom: 80,
        right: 20,
        zIndex: 9999,
        display: "flex",
        flexDirection: "column",
        gap: 8,
        pointerEvents: "none",
      }}>
        {toasts.map((t) => (
          <div
            key={t.id}
            style={{
              padding: "10px 16px",
              borderRadius: 8,
              fontSize: 12,
              fontWeight: 500,
              color: t.type === "error" ? "var(--status-high)" : t.type === "success" ? "var(--status-success)" : "var(--text-accent)",
              background: t.type === "error" ? "var(--status-high-bg, rgba(220,38,38,0.08))" : t.type === "success" ? "rgba(22,163,74,0.08)" : "var(--bg-elevated)",
              border: `1px solid ${t.type === "error" ? "rgba(220,38,38,0.15)" : t.type === "success" ? "rgba(22,163,74,0.15)" : "var(--border-subtle)"}`,
              backdropFilter: "blur(12px)",
              maxWidth: 360,
              pointerEvents: "auto",
              animation: "fadeIn 200ms ease-out",
            }}
          >
            {t.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
