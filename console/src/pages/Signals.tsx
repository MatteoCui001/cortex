import { useEffect, useState } from "react";
import { api, type Signal } from "../api";

const VERDICTS = ["useful", "not_useful", "wrong", "save_for_later"] as const;

export default function Signals() {
  const [signals, setSignals] = useState<Signal[]>([]);
  const [loading, setLoading] = useState(true);
  const [feedbackFor, setFeedbackFor] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    api.signals(100).then(setSignals).finally(() => setLoading(false));
  }, []);

  async function submitFeedback(signalId: string, verdict: string) {
    setSubmitting(true);
    try {
      await api.signalFeedback(signalId, verdict);
      setFeedbackFor(null);
    } catch {
      /* ignore */
    }
    setSubmitting(false);
  }

  return (
    <div>
      <h1 className="text-xl font-semibold text-white mb-6">Signals</h1>

      {loading ? (
        <p className="text-[#8b8fa3] text-sm">Loading...</p>
      ) : signals.length === 0 ? (
        <div className="bg-[#1a1d27] border border-[#2a2e3a] rounded-xl p-8 text-center">
          <p className="text-[#8b8fa3]">No signals detected yet</p>
        </div>
      ) : (
        <div className="space-y-3">
          {signals.map((s) => (
            <div
              key={s.id}
              className="bg-[#1a1d27] border border-[#2a2e3a] rounded-xl p-4 hover:border-[#3a3e4a] transition-colors"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1.5">
                    <span className="text-xs px-2 py-0.5 rounded-full bg-purple-500/20 text-purple-400 border border-purple-500/30">
                      {s.signal_type}
                    </span>
                    <PriorityBar score={s.priority_score} />
                    {s.evidence_strength && (
                      <span className="text-xs text-[#8b8fa3]">{s.evidence_strength}</span>
                    )}
                  </div>

                  {s.topic && (
                    <div className="text-white text-sm font-medium mb-1">{s.topic}</div>
                  )}
                  {s.summary && (
                    <div className="text-[#8b8fa3] text-sm mb-2">{s.summary}</div>
                  )}
                  {s.rationale && (
                    <div className="text-[#555] text-xs italic mb-2">{s.rationale}</div>
                  )}

                  {s.thesis_links.length > 0 && (
                    <div className="flex gap-1.5 flex-wrap mb-2">
                      {s.thesis_links.map((t) => (
                        <span
                          key={t}
                          className="text-xs px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-400"
                        >
                          {t}
                        </span>
                      ))}
                    </div>
                  )}

                  <div className="text-[#555] text-xs">
                    {new Date(s.created_at).toLocaleString()}
                    <span className="ml-2 font-mono">{s.id.slice(0, 7)}</span>
                  </div>
                </div>

                {/* Feedback button */}
                <div className="shrink-0">
                  {feedbackFor === s.id ? (
                    <div className="flex flex-col gap-1">
                      {VERDICTS.map((v) => (
                        <button
                          key={v}
                          onClick={() => submitFeedback(s.id, v)}
                          disabled={submitting}
                          className="text-xs px-3 py-1 rounded border border-[#2a2e3a] text-[#8b8fa3] hover:text-white hover:bg-[#2a2e3a] transition-colors disabled:opacity-40"
                        >
                          {v.replace("_", " ")}
                        </button>
                      ))}
                      <button
                        onClick={() => setFeedbackFor(null)}
                        className="text-xs text-[#555] hover:text-white mt-1"
                      >
                        cancel
                      </button>
                    </div>
                  ) : (
                    <button
                      onClick={() => setFeedbackFor(s.id)}
                      className="text-xs px-3 py-1.5 rounded-lg border border-[#2a2e3a] text-[#8b8fa3] hover:text-white hover:bg-[#2a2e3a] transition-colors"
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
    </div>
  );
}

function PriorityBar({ score }: { score: number }) {
  const pct = Math.min(100, Math.max(0, score * 100));
  const color = pct >= 70 ? "bg-red-500" : pct >= 40 ? "bg-yellow-500" : "bg-green-500";
  return (
    <div className="flex items-center gap-1.5">
      <div className="w-16 h-1.5 bg-[#2a2e3a] rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-[#8b8fa3]">{score.toFixed(2)}</span>
    </div>
  );
}
