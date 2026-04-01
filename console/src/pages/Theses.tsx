import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  api,
  type ThesisCoverage,
  type StructuredThesis,
  type ThesisEvidence,
  type Event,
  type SettingsResponse,
} from "../api";
import TypeLabel from "../components/TypeLabel";
import DetailDrawer, { type DrawerTarget } from "../DetailDrawer";
import { useToast } from "../Toast";

// ---- Shared components ----

function TrendBadge({ direction, delta }: { direction: string; delta: number | null }) {
  if (direction === "up")
    return (
      <span className="text-[11px] font-medium" style={{ color: "var(--status-success)" }}>
        {delta !== null ? `+${(delta * 100).toFixed(1)}%` : "up"}
      </span>
    );
  if (direction === "down")
    return (
      <span className="text-[11px] font-medium" style={{ color: "var(--status-high)" }}>
        {delta !== null ? `${(delta * 100).toFixed(1)}%` : "down"}
      </span>
    );
  return <span className="text-meta text-[11px]">flat</span>;
}

function ConfBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const color = pct >= 70 ? "var(--status-success)" : pct >= 40 ? "var(--text-accent)" : "var(--text-tertiary)";
  return (
    <div className="flex items-center gap-2">
      <div className="progress-track w-20">
        <div className="progress-fill" style={{ width: `${pct}%`, background: color, opacity: 0.7 }} />
      </div>
      <span className="text-[11px] font-data" style={{ color }}>{pct}%</span>
    </div>
  );
}

function StanceBadge({ stance }: { stance: string }) {
  const colors: Record<string, { bg: string; fg: string }> = {
    bullish: { bg: "rgba(22,163,74,0.08)", fg: "var(--status-success)" },
    bearish: { bg: "rgba(220,38,38,0.08)", fg: "var(--status-high)" },
    neutral: { bg: "var(--bg-elevated)", fg: "var(--text-tertiary)" },
  };
  const c = colors[stance] || colors.neutral;
  return (
    <span
      className="text-[10px] font-medium px-2 py-0.5 rounded"
      style={{ background: c.bg, color: c.fg }}
    >
      {stance}
    </span>
  );
}

function ImpactIcon({ impact }: { impact: string }) {
  if (impact === "supports") return <span style={{ color: "var(--status-success)" }}>+</span>;
  if (impact === "contradicts") return <span style={{ color: "var(--status-high)" }}>-</span>;
  return <span style={{ color: "var(--text-quaternary)" }}>=</span>;
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, { bg: string; fg: string }> = {
    active: { bg: "rgba(22,163,74,0.08)", fg: "var(--status-success)" },
    resolved: { bg: "var(--bg-elevated)", fg: "var(--text-tertiary)" },
    invalidated: { bg: "rgba(220,38,38,0.06)", fg: "var(--status-high)" },
  };
  const c = colors[status] || colors.active;
  return (
    <span className="text-[10px] px-2 py-0.5 rounded" style={{ background: c.bg, color: c.fg }}>
      {status}
    </span>
  );
}

// ---- Generate theme row ----

function GenerateThemeRow({
  theme,
  eventCount,
  onGenerated,
  onError,
}: {
  theme: string;
  eventCount: number;
  onGenerated: (theses: StructuredThesis[]) => void;
  onError?: (msg: string) => void;
}) {
  const [generating, setGenerating] = useState(false);

  async function handleGenerate() {
    setGenerating(true);
    try {
      const created = await api.generateThesesForTheme(theme);
      onGenerated(created);
    } catch (e: unknown) {
      onError?.(e instanceof Error ? e.message : "Generation failed");
    } finally {
      setGenerating(false);
    }
  }

  return (
    <div className="thesis-row px-4 py-3 flex items-center justify-between gap-3">
      <div className="flex-1 min-w-0">
        <div className="text-[13px]" style={{ color: "var(--text-primary)" }}>{theme}</div>
        <span className="text-meta text-[10px]">{eventCount} events</span>
      </div>
      <button
        className="btn-accent text-[10px] py-0.5 shrink-0"
        disabled={generating}
        onClick={handleGenerate}
      >
        {generating ? "Generating..." : "Generate Theses"}
      </button>
    </div>
  );
}

// ---- Theses Tab (structured) ----

function ThesesTab() {
  const navigate = useNavigate();
  const { toast } = useToast();
  const [theses, setTheses] = useState<StructuredThesis[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [evidence, setEvidence] = useState<ThesisEvidence[]>([]);
  const [evidenceLoading, setEvidenceLoading] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [themes, setThemes] = useState<string[]>([]);
  const [suggestions, setSuggestions] = useState<{ theme: string; event_count: number }[]>([]);

  useEffect(() => {
    api.theses().then(setTheses).finally(() => setLoading(false));
    api.settings().then((s: SettingsResponse) => setThemes(s.llm?.thesis_list || [])).catch(() => {});
    api.thesisSuggestions(3).then(setSuggestions).catch(() => {});
  }, []);

  async function toggleExpand(id: string) {
    if (expanded === id) {
      setExpanded(null);
      return;
    }
    setExpanded(id);
    setEvidenceLoading(true);
    try {
      setEvidence(await api.thesisEvidenceList(id));
    } catch {
      setEvidence([]);
    } finally {
      setEvidenceLoading(false);
    }
  }

  async function handleCreate(data: { text: string; stance: string; theme: string }) {
    const t = await api.createThesis({
      text: data.text,
      stance: data.stance,
      theme: data.theme || undefined,
    });
    setTheses((prev) => [t, ...prev]);
    setShowCreate(false);
  }

  async function handleResolve(id: string) {
    try {
      const t = await api.resolveThesis(id);
      setTheses((prev) => prev.map((x) => (x.id === id ? t : x)));
    } catch (e: unknown) {
      toast(e instanceof Error ? e.message : "Failed to resolve thesis", "error");
    }
  }

  async function handleInvalidate(id: string) {
    try {
      const t = await api.invalidateThesis(id);
      setTheses((prev) => prev.map((x) => (x.id === id ? t : x)));
    } catch (e: unknown) {
      toast(e instanceof Error ? e.message : "Failed to invalidate thesis", "error");
    }
  }

  async function handleDelete(id: string) {
    try {
      await api.deleteThesis(id);
      setTheses((prev) => prev.filter((x) => x.id !== id));
      if (expanded === id) setExpanded(null);
    } catch (e: unknown) {
      toast(e instanceof Error ? e.message : "Failed to delete thesis", "error");
    }
  }

  async function handleConfirm(id: string) {
    try {
      const t = await api.confirmThesis(id);
      setTheses((prev) => prev.map((x) => (x.id === id ? t : x)));
    } catch (e: unknown) {
      toast(e instanceof Error ? e.message : "Failed to confirm thesis", "error");
    }
  }

  const pending = theses.filter((t) => !t.confirmed);
  const confirmed = theses.filter((t) => t.confirmed);

  if (loading) return <div className="py-16 text-center text-body" style={{ color: "var(--text-tertiary)" }}>Loading...</div>;

  return (
    <div>
      <div className="flex items-center justify-between mb-5">
        <span className="text-meta">{theses.length} theses</span>
        <button className="btn-primary text-[12px]" onClick={() => setShowCreate(!showCreate)}>
          {showCreate ? "Cancel" : "New Thesis"}
        </button>
      </div>

      {showCreate && <CreateForm themes={themes} onCreate={handleCreate} />}

      {pending.length > 0 && (
        <div className="mb-5">
          <div className="text-subheading mb-2">Pending Confirmation</div>
          <div className="space-y-1">
            {pending.map((t) => (
              <div key={t.id} className="thesis-row px-4 py-3 flex items-center justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="text-[13px] truncate" style={{ color: "var(--text-primary)" }}>{t.text}</div>
                  <div className="flex items-center gap-2 mt-1">
                    <StanceBadge stance={t.stance} />
                    {t.theme && <span className="thesis-chip text-[10px]">{t.theme}</span>}
                    <span className="text-meta text-[10px]">via {t.created_by}</span>
                  </div>
                </div>
                <div className="flex gap-1 shrink-0">
                  <button className="btn-accent text-[10px] py-0.5" onClick={() => handleConfirm(t.id)}>Confirm</button>
                  <button className="btn-ghost text-[10px] py-0.5" onClick={() => handleDelete(t.id)}>Dismiss</button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {suggestions.length > 0 && (
        <div className="mb-5">
          <div className="text-subheading mb-2">Generate from Themes</div>
          <div className="text-meta text-[11px] mb-2">Use LLM to generate opinionated theses from events under these themes</div>
          <div className="space-y-1">
            {suggestions.map((s) => (
              <GenerateThemeRow
                key={s.theme}
                theme={s.theme}
                eventCount={s.event_count}
                onError={(msg) => toast(msg, "error")}
                onGenerated={(newTheses) => {
                  setTheses((prev) => [...newTheses, ...prev]);
                  setSuggestions((prev) => prev.filter((x) => x.theme !== s.theme));
                }}
              />
            ))}
          </div>
        </div>
      )}

      {confirmed.length === 0 && pending.length === 0 ? (
        <div className="card p-12 text-center">
          <div className="text-2xl mb-3" style={{ color: "var(--text-quaternary)" }}>&mdash;</div>
          <div className="text-body">No theses yet</div>
          <div className="text-meta mt-2">Create a thesis to start tracking your investment convictions</div>
        </div>
      ) : (
        <div className="space-y-1">
          {confirmed.map((t) => (
            <div key={t.id} className="thesis-row" data-expanded={expanded === t.id ? "true" : undefined}>
              <button onClick={() => toggleExpand(t.id)} className="w-full text-left px-5 py-4">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1.5">
                      <span className="text-[14px] font-medium" style={{ color: "var(--text-primary)" }}>
                        {t.text}
                      </span>
                    </div>
                    <div className="flex items-center gap-3 flex-wrap">
                      <StanceBadge stance={t.stance} />
                      <ConfBar value={t.confidence} />
                      <StatusBadge status={t.status} />
                      {t.theme && <span className="thesis-chip text-[10px]">{t.theme}</span>}
                    </div>
                  </div>
                  <span className="text-meta shrink-0 mt-1">{expanded === t.id ? "\u25BC" : "\u25B6"}</span>
                </div>
              </button>

              {expanded === t.id && (
                <div className="px-5 pb-4 pt-1 border-t" style={{ borderColor: "var(--border-subtle)" }}>
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-[12px] font-medium" style={{ color: "var(--text-secondary)" }}>
                      Evidence ({evidence.length})
                    </span>
                    <div className="flex gap-1">
                      {t.status === "active" && (
                        <>
                          <button className="btn-accent text-[10px]" onClick={() => handleResolve(t.id)}>Resolve</button>
                          <button className="btn-ghost text-[10px]" onClick={() => handleInvalidate(t.id)}>Invalidate</button>
                        </>
                      )}
                      <button className="btn-ghost text-[10px]" style={{ color: "var(--status-high)" }} onClick={() => handleDelete(t.id)}>Delete</button>
                    </div>
                  </div>

                  {evidenceLoading ? (
                    <div className="text-meta py-4 text-center">Loading...</div>
                  ) : evidence.length === 0 ? (
                    <div className="text-meta py-4 text-center">No evidence recorded yet</div>
                  ) : (
                    <div className="space-y-1">
                      {evidence.map((e) => (
                        <button
                          key={e.id}
                          onClick={() => e.event_id && navigate(`/events/${e.event_id}`)}
                          className="event-row w-full text-left px-3 py-2 flex items-start gap-2"
                        >
                          <ImpactIcon impact={e.impact} />
                          <div className="flex-1 min-w-0">
                            {e.event_title && (
                              <div className="text-[13px] truncate mb-0.5" style={{ color: "var(--text-primary)" }}>
                                {e.event_title}
                              </div>
                            )}
                            <div className="text-[12px]" style={{ color: "var(--text-secondary)" }}>
                              {e.rationale || "No rationale"}
                            </div>
                            <div className="flex items-center gap-2 mt-0.5">
                              <span className="text-meta text-[10px]">{e.impact}</span>
                              <span className="text-meta text-[10px]">delta {(e.confidence_delta * 100).toFixed(0)}%</span>
                              <span className="text-meta text-[10px]">{new Date(e.created_at).toLocaleDateString()}</span>
                            </div>
                          </div>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function CreateForm({ themes, onCreate }: { themes: string[]; onCreate: (d: { text: string; stance: string; theme: string }) => void }) {
  const [text, setText] = useState("");
  const [stance, setStance] = useState("neutral");
  const [theme, setTheme] = useState("");

  return (
    <div className="card p-4 mb-4 space-y-3 animate-in">
      <textarea
        className="input-field w-full px-3 py-2 text-[13px]"
        rows={2}
        placeholder="Your thesis statement..."
        value={text}
        onChange={(e) => setText(e.target.value)}
      />
      <div className="flex items-center gap-3">
        <div className="segment-control">
          {["bullish", "neutral", "bearish"].map((s) => (
            <button key={s} className="segment-btn" data-active={stance === s ? "true" : undefined} onClick={() => setStance(s)}>
              {s}
            </button>
          ))}
        </div>
        <select
          className="input-field text-[12px] px-2 py-1"
          value={theme}
          onChange={(e) => setTheme(e.target.value)}
        >
          <option value="">No theme</option>
          {themes.map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
        <button className="btn-primary text-[12px] ml-auto" disabled={!text.trim()} onClick={() => onCreate({ text, stance, theme })}>
          Create
        </button>
      </div>
    </div>
  );
}

// ---- Themes Tab (existing coverage) ----

function ThemesTab() {
  const navigate = useNavigate();
  const [theses, setTheses] = useState<ThesisCoverage[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [evidence, setEvidence] = useState<Event[]>([]);
  const [evidenceLoading, setEvidenceLoading] = useState(false);
  const [drawer, setDrawer] = useState<DrawerTarget | null>(null);

  useEffect(() => {
    api.thesisCoverage().then(setTheses).finally(() => setLoading(false));
  }, []);

  async function toggleExpand(thesis: string) {
    if (expanded === thesis) {
      setExpanded(null);
      return;
    }
    setExpanded(thesis);
    setEvidenceLoading(true);
    try {
      setEvidence(await api.thesisEvidence(thesis));
    } catch {
      setEvidence([]);
    } finally {
      setEvidenceLoading(false);
    }
  }

  if (loading) return <div className="py-16 text-center text-body" style={{ color: "var(--text-tertiary)" }}>Loading...</div>;

  return (
    <div>
      <p className="text-caption mb-4">Auto-classified topic coverage from ingested content</p>
      {theses.length === 0 ? (
        <div className="card p-12 text-center">
          <div className="text-body">No themes tracked yet</div>
          <div className="text-meta mt-2">Ingest content to start building theme coverage</div>
        </div>
      ) : (
        <div className="space-y-1">
          {theses.sort((a, b) => b.event_count - a.event_count).map((t) => (
            <div key={t.thesis} className="thesis-row" data-expanded={expanded === t.thesis ? "true" : undefined}>
              <button onClick={() => toggleExpand(t.thesis)} className="w-full text-left px-5 py-4">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 mb-1.5">
                      <span className="text-[14px] font-medium" style={{ color: "var(--text-primary)" }}>{t.thesis}</span>
                      <TrendBadge direction={t.trend_direction} delta={t.confidence_delta} />
                    </div>
                    <div className="flex items-center gap-4">
                      <ConfBar value={t.avg_confidence} />
                      <span className="text-meta text-[11px]">{t.event_count} events</span>
                      <span className="text-meta text-[11px]">{t.recent_event_count} recent</span>
                      {t.days_since_update > 0 && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded" style={{
                          color: t.days_since_update > 30 ? "var(--status-high)" : "var(--text-tertiary)",
                          background: "var(--bg-elevated)",
                        }}>
                          {t.days_since_update}d ago
                        </span>
                      )}
                    </div>
                  </div>
                  <span className="text-meta shrink-0 mt-1">{expanded === t.thesis ? "\u25BC" : "\u25B6"}</span>
                </div>
              </button>

              {expanded === t.thesis && (
                <div className="px-5 pb-4 pt-1 border-t" style={{ borderColor: "var(--border-subtle)" }}>
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-[12px] font-medium" style={{ color: "var(--text-secondary)" }}>
                      Evidence ({evidence.length})
                    </span>
                    <button
                      onClick={() => navigate(`/events?thesis=${encodeURIComponent(t.thesis)}`)}
                      className="btn-accent text-[11px] font-medium px-2.5 py-1"
                    >
                      View all in Events
                    </button>
                  </div>
                  {evidenceLoading ? (
                    <div className="text-meta py-4 text-center">Loading...</div>
                  ) : evidence.length === 0 ? (
                    <div className="text-meta py-4 text-center">No evidence events found</div>
                  ) : (
                    <div className="space-y-1">
                      {evidence.slice(0, 8).map((e) => (
                        <button
                          key={e.id}
                          onClick={() => setDrawer({ kind: "event", id: e.id })}
                          className="event-row w-full text-left px-3 py-2 flex items-start gap-2"
                        >
                          <TypeLabel type={e.type} />
                          <div className="flex-1 min-w-0">
                            <div className="text-[13px] truncate" style={{ color: "var(--text-primary)" }}>{e.title || "\u2014"}</div>
                            <div className="flex items-center gap-2 mt-0.5">
                              <span className="text-meta text-[10px]">{new Date(e.created_at).toLocaleDateString()}</span>
                            </div>
                          </div>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
      <DetailDrawer target={drawer} onClose={() => setDrawer(null)} />
    </div>
  );
}

// ---- Main Page ----

export default function Theses() {
  const [tab, setTab] = useState<"theses" | "themes">("theses");

  return (
    <div>
      <div className="flex items-baseline justify-between mb-5 animate-in">
        <div>
          <h1 className="text-heading">Thesis Dashboard</h1>
          <p className="text-caption mt-1">Your intellectual portfolio</p>
        </div>
        <div className="segment-control">
          <button className="segment-btn" data-active={tab === "theses" ? "true" : undefined} onClick={() => setTab("theses")}>
            Theses
          </button>
          <button className="segment-btn" data-active={tab === "themes" ? "true" : undefined} onClick={() => setTab("themes")}>
            Themes
          </button>
        </div>
      </div>

      {tab === "theses" ? <ThesesTab /> : <ThemesTab />}
    </div>
  );
}
