import { useState } from "react";
import { api } from "../api";
import { useToast } from "../Toast";

type Step = "welcome" | "llm" | "test" | "done";

export default function Onboarding({ onComplete }: { onComplete: () => void }) {
  const [step, setStep] = useState<Step>("welcome");
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [saving, setSaving] = useState(false);
  const [testUrl, setTestUrl] = useState("");
  const [testText, setTestText] = useState("");
  const [ingesting, setIngesting] = useState(false);
  const [ingestResult, setIngestResult] = useState<string | null>(null);
  const { toast } = useToast();

  async function handleSaveLLM() {
    if (!apiKey.trim()) {
      setStep("test");
      return;
    }
    setSaving(true);
    try {
      await api.updateLLM(apiKey, model || undefined, baseUrl || undefined);
      toast("LLM configured", "success");
      setStep("test");
    } catch (e: unknown) {
      toast(e instanceof Error ? e.message : "Failed to save LLM config", "error");
    }
    setSaving(false);
  }

  async function handleTestIngest() {
    setIngesting(true);
    setIngestResult(null);
    try {
      const result = await api.ingest({
        url: testUrl.trim() || undefined,
        content: testUrl.trim() ? undefined : testText.trim() || undefined,
        source: "console",
      });
      setIngestResult(`Ingested: ${result.title}`);
      toast("Content ingested successfully", "success");
      setTimeout(() => setStep("done"), 1500);
    } catch (e: unknown) {
      toast(e instanceof Error ? e.message : "Ingestion failed", "error");
    }
    setIngesting(false);
  }

  return (
    <div style={{ maxWidth: 560, margin: "0 auto", padding: "60px 20px" }}>
      {step === "welcome" && (
        <div className="animate-in">
          <div className="brand-glyph mb-6" style={{ width: 48, height: 48, fontSize: 20 }}>C</div>
          <h1 className="text-heading mb-3">Welcome to Cortex</h1>
          <p className="text-body mb-2">
            Your personal knowledge engine. Cortex captures, analyzes, and connects
            information to surface insights for your investment decisions.
          </p>
          <p className="text-caption mb-8">
            Let's set up the basics in 2 minutes.
          </p>
          <button className="btn-primary" onClick={() => setStep("llm")}>
            Get Started
          </button>
        </div>
      )}

      {step === "llm" && (
        <div className="animate-in">
          <div className="text-meta mb-2">Step 1 of 2</div>
          <h2 className="text-heading mb-2">AI Configuration</h2>
          <p className="text-caption mb-6">
            Connect an LLM to enable entity extraction, signal detection, and thesis evaluation.
            You can skip this — search and ingestion work without it.
          </p>
          <div className="space-y-3 mb-6">
            <div>
              <label className="text-[11px] font-medium mb-1 block" style={{ color: "var(--text-secondary)" }}>
                API Key
              </label>
              <input
                className="input-field w-full px-3 py-2 text-[13px]"
                type="password"
                placeholder="sk-... or leave empty to skip"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-[11px] font-medium mb-1 block" style={{ color: "var(--text-secondary)" }}>
                  Base URL (optional)
                </label>
                <input
                  className="input-field w-full px-3 py-2 text-[13px]"
                  placeholder="https://api.minimaxi.chat/v1"
                  value={baseUrl}
                  onChange={(e) => setBaseUrl(e.target.value)}
                />
              </div>
              <div>
                <label className="text-[11px] font-medium mb-1 block" style={{ color: "var(--text-secondary)" }}>
                  Model (optional)
                </label>
                <input
                  className="input-field w-full px-3 py-2 text-[13px]"
                  placeholder="MiniMax-M2.7"
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                />
              </div>
            </div>
          </div>
          <div className="flex gap-3">
            <button className="btn-primary" onClick={handleSaveLLM} disabled={saving}>
              {apiKey.trim() ? (saving ? "Saving..." : "Save & Continue") : "Skip"}
            </button>
            <button className="btn-ghost" onClick={() => setStep("welcome")}>Back</button>
          </div>
        </div>
      )}

      {step === "test" && (
        <div className="animate-in">
          <div className="text-meta mb-2">Step 2 of 2</div>
          <h2 className="text-heading mb-2">Test Ingestion</h2>
          <p className="text-caption mb-6">
            Try sending some content to Cortex. Paste a URL or write a note.
          </p>
          <div className="space-y-3 mb-6">
            <input
              className="input-field w-full px-3 py-2 text-[13px]"
              placeholder="Paste a URL (e.g., https://example.com/article)"
              value={testUrl}
              onChange={(e) => setTestUrl(e.target.value)}
            />
            {!testUrl.trim() && (
              <textarea
                className="input-field w-full px-3 py-2 text-[13px]"
                rows={3}
                placeholder="Or type a note..."
                value={testText}
                onChange={(e) => setTestText(e.target.value)}
              />
            )}
          </div>
          {ingestResult && (
            <div className="text-[12px] py-2 px-3 rounded-lg mb-4" style={{
              background: "rgba(22,163,74,0.08)",
              color: "var(--status-success)"
            }}>
              {ingestResult}
            </div>
          )}
          <div className="flex gap-3">
            <button
              className="btn-primary"
              onClick={handleTestIngest}
              disabled={ingesting || (!testUrl.trim() && !testText.trim())}
            >
              {ingesting ? "Ingesting..." : "Ingest"}
            </button>
            <button className="btn-ghost" onClick={() => setStep("done")}>
              Skip
            </button>
          </div>
        </div>
      )}

      {step === "done" && (
        <div className="animate-in text-center">
          <div className="text-3xl mb-4" style={{ color: "var(--status-success)" }}>✓</div>
          <h2 className="text-heading mb-2">You're all set!</h2>
          <p className="text-caption mb-6">
            Start ingesting content via WeChat or the Ingest page.
            Cortex will analyze, connect, and surface insights automatically.
          </p>
          <button className="btn-primary" onClick={onComplete}>
            Open Dashboard
          </button>
        </div>
      )}
    </div>
  );
}
