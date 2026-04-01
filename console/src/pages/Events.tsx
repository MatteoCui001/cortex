import { useEffect, useState } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { api, type Event } from "../api";
import TypeLabel from "../components/TypeLabel";
import DetailDrawer, { type DrawerTarget } from "../DetailDrawer";

const DAY_FILTERS = [
  { label: "7d", days: 7 },
  { label: "30d", days: 30 },
  { label: "All", days: undefined },
] as const;

function MetaBadge({ children }: { children: string }) {
  return (
    <span className="text-[10px] px-1.5 py-0.5 rounded" style={{ color: "var(--text-tertiary)", background: "var(--bg-elevated)" }}>
      {children}
    </span>
  );
}

function TemporalityBadge({ value }: { value: string }) {
  const isWarm = value === "time_sensitive" || value === "prediction" || value === "trend";
  return (
    <span
      className="text-[10px] px-1.5 py-0.5 rounded"
      style={{
        color: isWarm ? "var(--status-medium)" : "var(--text-tertiary)",
        background: isWarm ? "var(--status-medium-bg)" : "var(--bg-elevated)",
      }}
    >
      {value}
    </span>
  );
}

function SourceLink({ path }: { path: string | null }) {
  if (!path) return null;
  const isUrl = path.startsWith("http") || path.startsWith("link:");
  const url = path.startsWith("link:") ? path.slice(5) : path;
  if (!isUrl) return <span className="text-meta truncate max-w-[280px] inline-block align-bottom">{path}</span>;
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="text-[11px] truncate max-w-[280px] inline-block align-bottom transition-colors"
      style={{ color: "var(--text-accent-dim)", textDecoration: "underline", textDecorationColor: "rgba(180,90,56,0.15)" }}
    >
      {url.replace(/^https?:\/\//, "").slice(0, 55)}
    </a>
  );
}

export default function Events() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const thesisFilter = searchParams.get("thesis");

  const [events, setEvents] = useState<Event[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [days, setDays] = useState<number | undefined>(30);
  const [sort, setSort] = useState<"recent" | "relevance">("recent");
  const [expanded, setExpanded] = useState<string | null>(null);
  const [drawer, setDrawer] = useState<DrawerTarget | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const PAGE_SIZE = 50;

  useEffect(() => {
    setLoading(true);
    setError(null);
    const req = thesisFilter
      ? api.thesisEvidence(thesisFilter)
      : api.events(PAGE_SIZE, days, sort, 0);
    req
      .then((data) => {
        setEvents(data);
        setHasMore(!thesisFilter && data.length >= PAGE_SIZE);
      })
      .catch((e) => setError(e.message || "Failed to load events"))
      .finally(() => setLoading(false));
  }, [days, sort, thesisFilter]);

  const loadMore = () => {
    if (loadingMore || !hasMore) return;
    setLoadingMore(true);
    api.events(PAGE_SIZE, days, sort, events.length)
      .then((data) => {
        setEvents((prev) => [...prev, ...data]);
        setHasMore(data.length >= PAGE_SIZE);
      })
      .catch((e) => setError(e.message || "Failed to load more"))
      .finally(() => setLoadingMore(false));
  };

  return (
    <div>
      <div className="flex items-baseline justify-between mb-6 animate-in">
        <div>
          <h1 className="text-heading">Events</h1>
          <p className="text-caption mt-1">
            {thesisFilter
              ? <>Evidence for <span style={{ color: "var(--text-accent)" }}>{thesisFilter}</span></>
              : "Everything your system has ingested"
            }
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-meta">{events.length} events</span>
          {thesisFilter ? (
            <button
              onClick={() => setSearchParams({})}
              className="btn-accent text-[11px] font-medium px-2.5 py-1"
            >
              Clear filter
            </button>
          ) : (
            <>
              <div className="segment-control">
                {(["recent", "relevance"] as const).map((s) => (
                  <button
                    key={s}
                    onClick={() => setSort(s)}
                    className="segment-btn"
                    data-active={sort === s ? "true" : undefined}
                  >
                    {s === "recent" ? "Recent" : "Relevant"}
                  </button>
                ))}
              </div>
              <div className="segment-control">
                {DAY_FILTERS.map((f) => (
                  <button
                    key={f.label}
                    onClick={() => setDays(f.days)}
                    className="segment-btn"
                    data-active={days === f.days ? "true" : undefined}
                  >
                    {f.label}
                  </button>
                ))}
              </div>
            </>
          )}
        </div>
      </div>

      {error && (
        <div className="text-[12px] py-3 px-4 rounded-lg mb-4"
          style={{ background: "var(--status-high-bg)", color: "var(--status-high)" }}>
          {error}
        </div>
      )}

      {loading ? (
        <div className="py-16 text-center text-body" style={{ color: "var(--text-tertiary)" }}>Loading...</div>
      ) : events.length === 0 && !error ? (
        <div className="card p-16 text-center">
          <div className="text-2xl mb-3" style={{ color: "var(--text-quaternary)" }}>&mdash;</div>
          <div className="text-body">No events in this period</div>
          <div className="text-meta mt-2">Send content via the API or use Ingest to add knowledge</div>
        </div>
      ) : (
        <div className="space-y-px">
          {events.map((e) => (
            <div
              key={e.id}
              className="event-row"
              data-expanded={expanded === e.id ? "true" : undefined}
            >
              <button
                onClick={() => setExpanded(expanded === e.id ? null : e.id)}
                className="w-full text-left px-4 py-3 rounded-xl transition-colors"
              >
                <div className="flex items-start gap-3">
                  <TypeLabel type={e.type} />
                  <div className="flex-1 min-w-0">
                    <div className="text-[13px] font-medium" style={{ color: e.title ? "var(--text-primary)" : "var(--text-tertiary)" }}>
                      {e.title || "\u2014"}
                    </div>
                    <div className="flex items-center gap-2 mt-1 flex-wrap">
                      <span className="text-meta">{new Date(e.created_at).toLocaleString()}</span>
                      {e.source && <span className="text-meta">{e.source}</span>}
                      {e.raw_input_type && e.raw_input_type !== "text" && <MetaBadge>{e.raw_input_type}</MetaBadge>}
                      {e.source_type && <MetaBadge>{e.source_type}</MetaBadge>}
                      {e.temporality && e.temporality !== "permanent" && <TemporalityBadge value={e.temporality} />}
                      {e.relevance != null && e.relevance > 0 && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded" style={{
                          color: e.relevance >= 0.7 ? "var(--status-high)" : "var(--text-tertiary)",
                          background: e.relevance >= 0.7 ? "var(--status-high-bg)" : "var(--bg-elevated)",
                        }}>
                          rel {e.relevance.toFixed(1)}
                        </span>
                      )}
                    </div>
                    {e.user_annotation && (
                      <div className="mt-1.5 text-[12px] italic" style={{ color: "var(--text-accent-dim)" }}>
                        &ldquo;{e.user_annotation}&rdquo;
                      </div>
                    )}
                  </div>
                  <span className="text-meta shrink-0 mt-0.5">{expanded === e.id ? "\u25BC" : "\u25B6"}</span>
                </div>
              </button>

              {expanded === e.id && (
                <div className="px-4 pb-4 pt-2 ml-12 space-y-3 border-t" style={{ borderColor: "var(--border-subtle)" }}>
                  {e.summary && <p className="text-body leading-relaxed">{e.summary}</p>}

                  {e.user_annotation && (
                    <div className="annotation-block">
                      <div className="text-meta mb-0.5">Your annotation</div>
                      <div className="text-[13px]" style={{ color: "var(--text-accent)" }}>{e.user_annotation}</div>
                    </div>
                  )}

                  {e.tags.length > 0 && (
                    <div className="flex flex-wrap gap-1.5">
                      {e.tags.map((t) => (
                        <span key={t} className="chip" style={{ color: "var(--text-tertiary)", background: "var(--bg-elevated)", border: "1px solid var(--border-subtle)" }}>{t}</span>
                      ))}
                    </div>
                  )}

                  {e.thesis_links.length > 0 && (
                    <div className="flex flex-wrap gap-1.5">
                      {e.thesis_links.map((t) => (
                        <span key={t} className="thesis-chip">{t}</span>
                      ))}
                    </div>
                  )}

                  <div className="flex items-center gap-4 pt-2 border-t" style={{ borderColor: "var(--border-subtle)" }}>
                    <span className="text-meta">{e.id.slice(0, 8)}</span>
                    {e.confidence > 0 && <span className="text-meta">conf {e.confidence.toFixed(2)}</span>}
                    <SourceLink path={e.source_path} />
                    <button
                      onClick={(ev) => { ev.stopPropagation(); navigate(`/events/${e.id}`); }}
                      className="ml-auto btn-accent text-[11px] font-medium px-2.5 py-1"
                    >
                      View
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {hasMore && !loading && (
        <div className="text-center mt-6">
          <button
            onClick={loadMore}
            disabled={loadingMore}
            className="btn-accent text-[12px] font-medium px-4 py-2"
          >
            {loadingMore ? "Loading..." : "Load more"}
          </button>
        </div>
      )}

      <DetailDrawer target={drawer} onClose={() => setDrawer(null)} />
    </div>
  );
}
