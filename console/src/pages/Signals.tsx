import { useEffect, useState } from "react";
import { api, type Signal } from "../api";
import DetailDrawer, { type DrawerTarget } from "../DetailDrawer";

const VERDICTS = ["useful", "not_useful", "wrong", "save_for_later"] as const;
const VERDICT_LABELS: Record<string, string> = {
  useful: "Useful",
  not_useful: "Not useful",
  wrong: "Wrong",
  save_for_later: "Save for later",
};

function PriorityBar({ score }: { score: number }) {
  const pct = Math.min(100, Math.max(0, score * 100));
  const color = pct >= 70 ? "var(--status-high)" : pct >= 40 ? "var(--status-medium)" : "var(--status-success)";
  return (
    <div className="flex items-center gap-1.5">
      <div className="w-14 h-1 rounded-full overflow-hidden" style={{ background: "var(--bg-active)" }}>
        <div className="h-full rounded-full" style={{ width: `${pct}%`, background: color, opacity: 0.7 }} />
      </div>
      <span className="text-meta">{score.toFixed(2)}</span>
    </div>
  );
}

export default function Signals() {
  const [signals, setSignals] = useState<Signal[]>([]);
  const [loading, setLoading] = useState(true);
  const [feedbackFor, setFeedbackFor] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [drawer, setDrawer] = useState<DrawerTarget | null>(null);

  useEffect(() => {
    api.signals(100).then(setSignals).finally(() => setLoading(false));
  }, []);

  async function submitFeedback(signalId: string, verdict: string) {
    setSubmitting(true);
    try {
      await api.signalFeedback(signalId, verdict);
      setFeedbackFor(null);
    } catch { /* ignore */ }
    setSubmitting(false);
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-heading">Signals</h1>
        <p className="text-caption mt-1">Connections and patterns detected across your knowledge</p>
      </div>

      {loading ? (
        <div className="py-16 text-center text-body">Loading...</div>
      ) : signals.length === 0 ? (
        <div
          className="rounded-xl p-12"
          style={{ background: "var(--bg-surface)", border: "1px solid var(--border-subtle)" }}
        >
          <div className="max-w-md mx-auto text-center">
            <div className="text-3xl mb-4" style={{ color: "var(--text-quaternary)" }}>&mdash;</div>
            <div className="text-[15px] font-medium mb-2" style={{ color: "var(--text-primary)" }}>
              No signals yet
            </div>
            <div className="text-body mb-6">
              Signals emerge when your knowledge system detects meaningful patterns: contradictions between sources, converging evidence on a topic, or answers to questions you've noted.
            </div>
            <div
              className="rounded-lg p-4 text-left space-y-2"
              style={{ background: "var(--bg-elevated)", border: "1px solid var(--border-subtle)" }}
            >
              <div className="text-subheading mb-2">How signals are generated</div>
              <div className="flex items-start gap-2">
                <span className="text-meta mt-0.5">1.</span>
                <span className="text-caption">New content is ingested and analyzed for entities, tags, and thesis links</span>
              </div>
              <div className="flex items-start gap-2">
                <span className="text-meta mt-0.5">2.</span>
                <span className="text-caption">The system compares it against existing knowledge for overlaps and tensions</span>
              </div>
              <div className="flex items-start gap-2">
                <span className="text-meta mt-0.5">3.</span>
                <span className="text-caption">When confidence is high enough, a signal is created and pushed to your inbox</span>
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div className="space-y-2">
          {signals.map((s) => (
            <div
              key={s.id}
              className="rounded-xl px-5 py-4 transition-all duration-150"
              style={{
                background: "var(--bg-surface)",
                border: "1px solid var(--border-subtle)",
              }}
              onMouseEnter={(e) => (e.currentTarget.style.borderColor = "var(--border-default)")}
              onMouseLeave={(e) => (e.currentTarget.style.borderColor = "var(--border-subtle)")}
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-2">
                    <span
                      className="text-[10px] font-medium px-1.5 py-0.5 rounded"
                      style={{ color: "var(--type-thesis)", background: "var(--type-thesis-bg)" }}
                    >
                      {s.signal_type}
                    </span>
                    <PriorityBar score={s.priority_score} />
                    {s.evidence_strength && <span className="text-meta">{s.evidence_strength}</span>}
                  </div>

                  {s.topic && (
                    <div className="text-[14px] font-medium mb-1" style={{ color: "var(--text-primary)" }}>
                      {s.topic}
                    </div>
                  )}
                  {s.summary && <div className="text-body mb-2">{s.summary}</div>}
                  {s.rationale && (
                    <div className="text-[12px] italic mb-2" style={{ color: "var(--text-quaternary)" }}>
                      {s.rationale}
                    </div>
                  )}

                  {s.thesis_links.length > 0 && (
                    <div className="flex gap-1.5 flex-wrap mb-2">
                      {s.thesis_links.map((t) => (
                        <span key={t} className="text-[11px] px-2 py-0.5 rounded" style={{ color: "var(--text-accent)", background: "rgba(165,180,252,0.08)" }}>
                          {t}
                        </span>
                      ))}
                    </div>
                  )}

                  <div className="text-meta">
                    {new Date(s.created_at).toLocaleString()}
                    <span className="ml-2 font-mono">{s.id.slice(0, 7)}</span>
                    {s.evidence_event_ids.length > 0 && (
                      <span className="ml-2">{s.evidence_event_ids.length} evidence event{s.evidence_event_ids.length > 1 ? "s" : ""}</span>
                    )}
                  </div>
                </div>

                {/* Actions column */}
                <div className="shrink-0 flex flex-col gap-1.5">
                  {/* Context button */}
                  <button
                    onClick={() => setDrawer({
                      kind: "signal",
                      id: s.id,
                      evidence_event_ids: s.evidence_event_ids,
                      new_event_id: s.new_event_id,
                      existing_event_id: s.existing_event_id,
                    })}
                    className="text-[11px] font-medium px-2.5 py-1 rounded-md transition-colors"
                    style={{ color: "var(--text-accent-dim)", border: "1px solid var(--border-accent)" }}
                    onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(129,140,248,0.08)"; e.currentTarget.style.color = "var(--text-accent)"; }}
                    onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; e.currentTarget.style.color = "var(--text-accent-dim)"; }}
                  >
                    Context
                  </button>

                  {/* Feedback */}
                  {feedbackFor === s.id ? (
                    <>
                      {VERDICTS.map((v) => (
                        <button
                          key={v}
                          onClick={() => submitFeedback(s.id, v)}
                          disabled={submitting}
                          className="text-[11px] px-2.5 py-1 rounded-md transition-colors disabled:opacity-30 text-left"
                          style={{ color: "var(--text-secondary)", border: "1px solid var(--border-default)" }}
                          onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-elevated)"; e.currentTarget.style.color = "var(--text-primary)"; }}
                          onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; e.currentTarget.style.color = "var(--text-secondary)"; }}
                        >
                          {VERDICT_LABELS[v]}
                        </button>
                      ))}
                      <button onClick={() => setFeedbackFor(null)} className="text-[10px] text-center" style={{ color: "var(--text-quaternary)" }}>cancel</button>
                    </>
                  ) : (
                    <button
                      onClick={() => setFeedbackFor(s.id)}
                      className="text-[11px] font-medium px-2.5 py-1 rounded-md transition-colors"
                      style={{ color: "var(--text-secondary)", border: "1px solid var(--border-default)" }}
                      onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-elevated)"; e.currentTarget.style.color = "var(--text-primary)"; }}
                      onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; e.currentTarget.style.color = "var(--text-secondary)"; }}
                    >
                      Feedback
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      <DetailDrawer target={drawer} onClose={() => setDrawer(null)} />
    </div>
  );
}
