import { useEffect, useState } from "react";
import { api, type Event } from "../api";

const DAY_FILTERS = [
  { label: "7d", days: 7 },
  { label: "30d", days: 30 },
  { label: "All", days: undefined },
] as const;

const TYPE_COLORS: Record<string, string> = {
  article: "bg-blue-500/15 text-blue-400",
  meeting: "bg-green-500/15 text-green-400",
  note: "bg-yellow-500/15 text-yellow-400",
  thesis: "bg-purple-500/15 text-purple-400",
  chat: "bg-pink-500/15 text-pink-400",
  voice_memo: "bg-orange-500/15 text-orange-400",
  document: "bg-teal-500/15 text-teal-400",
};

function SourceLink({ path }: { path: string | null }) {
  if (!path) return null;
  const isUrl = path.startsWith("http://") || path.startsWith("https://") || path.startsWith("link:");
  const url = path.startsWith("link:") ? path.slice(5) : path;
  if (!isUrl) return <span className="text-[#555] text-xs font-mono truncate max-w-[300px] inline-block align-bottom">{path}</span>;
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="text-indigo-400/70 hover:text-indigo-400 text-xs truncate max-w-[300px] inline-block align-bottom underline decoration-indigo-400/30"
    >
      {url.replace(/^https?:\/\//, "").slice(0, 60)}
    </a>
  );
}

export default function Events() {
  const [events, setEvents] = useState<Event[]>([]);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState<number | undefined>(30);
  const [expanded, setExpanded] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    api.events(100, days).then(setEvents).finally(() => setLoading(false));
  }, [days]);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-semibold text-white">Events</h1>
        <div className="flex items-center gap-3">
          <span className="text-[#555] text-xs">{events.length} events</span>
          <div className="flex gap-1 bg-[#13151c] p-1 rounded-lg">
            {DAY_FILTERS.map((f) => (
              <button
                key={f.label}
                onClick={() => setDays(f.days)}
                className={`text-xs px-3 py-1.5 rounded-md transition-colors ${
                  days === f.days
                    ? "bg-[#2a2e3a] text-white"
                    : "text-[#8b8fa3] hover:text-white"
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {loading ? (
        <p className="text-[#8b8fa3] text-sm">Loading...</p>
      ) : events.length === 0 ? (
        <div className="bg-[#1a1d27] border border-[#2a2e3a] rounded-xl p-12 text-center">
          <div className="text-[#555] text-3xl mb-3">--</div>
          <p className="text-[#8b8fa3]">No events in this period</p>
          <p className="text-[#555] text-xs mt-1">Send content via WeChat or use the API to ingest knowledge</p>
        </div>
      ) : (
        <div className="space-y-2">
          {events.map((e) => (
            <div
              key={e.id}
              className="bg-[#1a1d27] border border-[#2a2e3a] rounded-xl hover:border-[#3a3e4a] transition-colors overflow-hidden"
            >
              <button
                onClick={() => setExpanded(expanded === e.id ? null : e.id)}
                className="w-full text-left p-4"
              >
                <div className="flex items-start gap-3">
                  <span className={`text-xs px-2 py-0.5 rounded shrink-0 mt-0.5 ${TYPE_COLORS[e.type] ?? "bg-[#2a2e3a] text-[#8b8fa3]"}`}>
                    {e.type}
                  </span>
                  <div className="flex-1 min-w-0">
                    <div className="text-white text-sm font-medium truncate">{e.title}</div>
                    <div className="flex items-center gap-2 mt-1 flex-wrap">
                      <span className="text-[#555] text-xs">
                        {new Date(e.created_at).toLocaleString()}
                      </span>
                      {e.source && (
                        <span className="text-[#555] text-xs">{e.source}</span>
                      )}
                      {e.raw_input_type && e.raw_input_type !== "text" && (
                        <span className="text-xs px-1.5 py-0 rounded bg-[#22262f] text-[#8b8fa3]">{e.raw_input_type}</span>
                      )}
                      {e.source_type && (
                        <span className="text-xs px-1.5 py-0 rounded bg-[#22262f] text-[#8b8fa3]">{e.source_type}</span>
                      )}
                      {e.temporality && e.temporality !== "permanent" && (
                        <span className="text-xs px-1.5 py-0 rounded bg-amber-500/10 text-amber-400/70">{e.temporality}</span>
                      )}
                    </div>
                    {e.user_annotation && (
                      <div className="text-indigo-300/70 text-xs mt-1.5 italic truncate">
                        &ldquo;{e.user_annotation}&rdquo;
                      </div>
                    )}
                  </div>
                  <span className="text-[#555] text-xs shrink-0 mt-1">
                    {expanded === e.id ? "\u25BC" : "\u25B6"}
                  </span>
                </div>
              </button>

              {/* Expanded detail */}
              {expanded === e.id && (
                <div className="px-4 pb-4 border-t border-[#2a2e3a] pt-3 ml-10 space-y-3">
                  {e.summary && (
                    <div className="text-[#c4c7d4] text-sm leading-relaxed">{e.summary}</div>
                  )}

                  {e.user_annotation && (
                    <div className="bg-indigo-500/5 border border-indigo-500/20 rounded-lg px-3 py-2">
                      <div className="text-[#8b8fa3] text-xs mb-1">Your annotation</div>
                      <div className="text-indigo-300 text-sm">{e.user_annotation}</div>
                    </div>
                  )}

                  {e.tags.length > 0 && (
                    <div className="flex flex-wrap gap-1.5">
                      {e.tags.map((t) => (
                        <span
                          key={t}
                          className="text-xs px-2 py-0.5 rounded-full bg-[#22262f] text-[#8b8fa3] border border-[#2a2e3a]"
                        >
                          {t}
                        </span>
                      ))}
                    </div>
                  )}

                  {e.thesis_links.length > 0 && (
                    <div className="flex flex-wrap gap-1.5">
                      {e.thesis_links.map((t) => (
                        <span
                          key={t}
                          className="text-xs px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-400"
                        >
                          {t}
                        </span>
                      ))}
                    </div>
                  )}

                  <div className="flex items-center gap-4 text-[#555] text-xs pt-1 border-t border-[#1e2130]">
                    <span className="font-mono">{e.id.slice(0, 8)}</span>
                    {e.confidence > 0 && <span>confidence: {e.confidence.toFixed(2)}</span>}
                    <SourceLink path={e.source_path} />
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
