import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { api, type Event, type SearchResult } from "../api";

export default function EventDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [event, setEvent] = useState<Event | null>(null);
  const [loading, setLoading] = useState(true);
  const [related, setRelated] = useState<SearchResult[]>([]);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    Promise.all([
      api.event(id).then(setEvent).catch(() => setEvent(null)),
      api.eventRelated(id, 6).then(setRelated).catch(() => setRelated([])),
    ]).finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return <div className="text-meta py-20 text-center">Loading...</div>;
  }

  if (!event) {
    return (
      <div className="py-20 text-center">
        <div className="text-meta mb-4">Event not found</div>
        <button onClick={() => navigate(-1)} className="btn-tertiary">Go back</button>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto">
      {/* Back button */}
      <button
        onClick={() => navigate(-1)}
        className="text-[13px] mb-4 hover:underline"
        style={{ color: "var(--text-tertiary)" }}
      >
        &larr; Back
      </button>

      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center gap-2 mb-2">
          <span
            className="px-2 py-0.5 rounded text-[11px] font-medium"
            style={{ background: "var(--bg-tag)", color: "var(--text-secondary)" }}
          >
            {event.type}
          </span>
          {event.source && (
            <span className="text-[11px]" style={{ color: "var(--text-quaternary)" }}>
              via {event.source}
            </span>
          )}
          <span className="text-[11px]" style={{ color: "var(--text-quaternary)" }}>
            {new Date(event.created_at).toLocaleString()}
          </span>
        </div>
        <h1 className="text-[22px] font-semibold leading-tight" style={{ color: "var(--text-primary)" }}>
          {event.title}
        </h1>
      </div>

      {/* Summary */}
      {event.summary && (
        <div
          className="mb-6 text-[14px] leading-relaxed rounded-lg px-4 py-3"
          style={{ background: "var(--bg-surface)", color: "var(--text-secondary)" }}
        >
          {event.summary}
        </div>
      )}

      {/* Content (full) */}
      <div
        className="mb-8 text-[14px] leading-relaxed whitespace-pre-wrap"
        style={{ color: "var(--text-primary)" }}
      >
        {event.content}
      </div>

      {/* Metadata */}
      <div
        className="mb-8 rounded-lg px-4 py-3 grid grid-cols-2 gap-3 text-[12px]"
        style={{ background: "var(--bg-surface)", border: "1px solid var(--border-subtle)" }}
      >
        {event.confidence != null && (
          <div>
            <span style={{ color: "var(--text-tertiary)" }}>Confidence: </span>
            <span style={{ color: "var(--text-primary)" }}>{(event.confidence * 100).toFixed(0)}%</span>
          </div>
        )}
        {event.relevance != null && (
          <div>
            <span style={{ color: "var(--text-tertiary)" }}>Relevance: </span>
            <span style={{ color: "var(--text-primary)" }}>{(event.relevance * 100).toFixed(0)}%</span>
          </div>
        )}
        {event.source_type && (
          <div>
            <span style={{ color: "var(--text-tertiary)" }}>Source type: </span>
            <span style={{ color: "var(--text-primary)" }}>{event.source_type}</span>
          </div>
        )}
        {event.temporality && (
          <div>
            <span style={{ color: "var(--text-tertiary)" }}>Temporality: </span>
            <span style={{ color: "var(--text-primary)" }}>{event.temporality}</span>
          </div>
        )}
        {event.source_path && (
          <div className="col-span-2">
            <span style={{ color: "var(--text-tertiary)" }}>Source: </span>
            <span style={{ color: "var(--text-primary)" }} className="break-all">{event.source_path}</span>
          </div>
        )}
      </div>

      {/* Tags + Thesis links */}
      <div className="mb-8 flex flex-wrap gap-2">
        {event.tags?.map((t) => (
          <span
            key={t}
            className="px-2 py-0.5 rounded text-[11px]"
            style={{ background: "var(--bg-tag)", color: "var(--text-secondary)" }}
          >
            {t}
          </span>
        ))}
        {event.thesis_links?.map((t) => (
          <span
            key={t}
            className="px-2 py-0.5 rounded text-[11px] font-medium"
            style={{ background: "var(--accent-blue-bg, rgba(56,120,200,0.1))", color: "var(--accent-blue, #3878c8)" }}
          >
            {t}
          </span>
        ))}
      </div>

      {/* Related events */}
      {related.length > 0 && (
        <div className="mb-8">
          <h2 className="text-subheading mb-3">Related Events</h2>
          <div className="space-y-2">
            {related.map((r) => (
              <button
                key={r.event.id}
                onClick={() => navigate(`/events/${r.event.id}`)}
                className="event-row w-full text-left px-3 py-2 rounded-lg"
              >
                <div className="text-[13px] font-medium truncate" style={{ color: "var(--text-primary)" }}>
                  {r.event.title}
                </div>
                <div className="text-[11px] mt-0.5 line-clamp-1" style={{ color: "var(--text-tertiary)" }}>
                  {r.event.summary}
                </div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
