import { useEffect, useState } from "react";
import { api, type SettingsResponse } from "../api";

export default function Settings() {
  const [settings, setSettings] = useState<SettingsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // LLM form
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    try {
      const s = await api.settings();
      setSettings(s);
      setModel(s.llm.model);
      setBaseUrl(s.llm.base_url);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load settings");
    }
    setLoading(false);
  }

  useEffect(() => { load(); }, []);

  async function handleSaveLLM() {
    setSaving(true);
    setSaveMsg(null);
    try {
      const result = await api.updateLLM(apiKey, model, baseUrl);
      setSaveMsg(result.llm_configured ? `LLM configured: ${result.model}` : "LLM cleared");
      setApiKey("");
      await load();
    } catch (e: unknown) {
      setSaveMsg(e instanceof Error ? e.message : "Failed to save");
    }
    setSaving(false);
  }

  async function handleClearLLM() {
    setSaving(true);
    setSaveMsg(null);
    try {
      await api.updateLLM("");
      setSaveMsg("LLM configuration cleared");
      await load();
    } catch (e: unknown) {
      setSaveMsg(e instanceof Error ? e.message : "Failed to clear");
    }
    setSaving(false);
  }

  if (loading) return <div className="py-16 text-center text-body" style={{ color: "var(--text-tertiary)" }}>Loading...</div>;

  return (
    <div>
      <div className="mb-6 animate-in">
        <h1 className="text-heading">Settings</h1>
        <p className="text-caption mt-1">Configure LLM, workspace, and system options</p>
      </div>

      {error && (
        <div className="text-[12px] py-3 px-4 rounded-lg mb-4"
          style={{ background: "var(--status-high-bg)", color: "var(--status-high)" }}>
          {error}
        </div>
      )}

      {/* System info */}
      <div className="animate-in animate-in-delay-1">
        <Section title="System">
          <InfoRow label="Workspace" value={settings?.workspace ?? "—"} />
          <InfoRow label="Embedding model" value={settings?.embedding_model ?? "—"} />
          <InfoRow
            label="LLM status"
            value={settings?.llm.configured ? "Connected" : "Not configured"}
            accent={settings?.llm.configured ? "var(--status-success)" : "var(--status-medium)"}
          />
          {settings?.llm.configured && (
            <>
              <InfoRow label="LLM model" value={settings.llm.model} />
              <InfoRow label="LLM endpoint" value={settings.llm.base_url} />
            </>
          )}
          {(settings?.llm.thesis_list?.length ?? 0) > 0 && (
            <InfoRow label="Tracked theses" value={settings!.llm.thesis_list.join(", ")} />
          )}
        </Section>
      </div>

      {/* LLM configuration */}
      <div className="animate-in animate-in-delay-2">
        <Section title="LLM Configuration">
          <p className="text-[12px] mb-4" style={{ color: "var(--text-tertiary)" }}>
            Provide your own LLM API key to enable entity extraction, classification, and signal detection.
            Supports any OpenAI-compatible API (OpenRouter, MiniMax, etc.).
            Without an API key, search and ingestion still work — only intelligence features are disabled.
          </p>

          <div className="space-y-3">
            <Field label="API Key" type="password" placeholder="sk-..." value={apiKey} onChange={setApiKey} />
            <Field label="Model" placeholder={settings?.llm.model || "e.g. MiniMax-M2.7"} value={model} onChange={setModel} />
            <Field label="Base URL" placeholder={settings?.llm.base_url || "e.g. https://openrouter.ai/api/v1"} value={baseUrl} onChange={setBaseUrl} />
          </div>

          <div className="flex items-center gap-2 mt-4">
            <button
              onClick={handleSaveLLM}
              disabled={saving || !apiKey.trim()}
              className="btn-primary text-[12px] px-4 py-2"
            >
              {saving ? "Saving..." : "Save"}
            </button>
            {settings?.llm.configured && (
              <button
                onClick={handleClearLLM}
                disabled={saving}
                className="btn-ghost text-[12px] font-medium px-4 py-2"
              >
                Clear LLM
              </button>
            )}
          </div>

          {saveMsg && (
            <div className="text-[12px] mt-3" style={{ color: "var(--text-accent-dim)" }}>
              {saveMsg}
            </div>
          )}
        </Section>
      </div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="card px-5 py-4 mb-4">
      <div className="text-subheading mb-3">{title}</div>
      {children}
    </div>
  );
}

function InfoRow({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <div className="flex items-baseline justify-between py-1.5">
      <span className="text-[12px]" style={{ color: "var(--text-tertiary)" }}>{label}</span>
      <span className="text-[12px] font-medium font-data" style={{ color: accent || "var(--text-primary)" }}>{value}</span>
    </div>
  );
}

function Field({ label, type, placeholder, value, onChange }: {
  label: string; type?: string; placeholder?: string; value: string; onChange: (v: string) => void;
}) {
  return (
    <div>
      <label className="text-[11px] font-medium block mb-1.5" style={{ color: "var(--text-secondary)" }}>{label}</label>
      <input
        type={type || "text"}
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="input-field w-full text-[12px] px-3 py-2"
      />
    </div>
  );
}