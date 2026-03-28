import { useEffect, useState } from "react";
import { api, type Event, type SearchResult, type RelationRow } from "./api";

/* ── Types ── */
export type DrawerTarget =
  | { kind: "event"; id: string }
  | { kind: "signal"; id: string; evidence_event_ids: string[]; new_event_id: string; existing_event_id: string }
  | { kind: "notification"; id: string; related_event_ids: string[]; signal_id: string | null };

interface Props {
  target: DrawerTarget | null;
  onClose: () => void;
}

/* ── Shared small components ── */

function TypeLabel({ type }: { type: string }) {
  const map: Record<string, { color: string; bg: string }> = {
    article: { color: "var(--type-article)", bg: "var(--type-article-bg)" },
    note: { color: "var(--type-note)", bg: "var(--type-note-bg)" },
    chat: { color: "var(--type-chat)", bg: "var(--type-chat-bg)" },
    meeting: { color: "var(--type-meeting)", bg: "var(--type-meeting-bg)" },
    thesis: { color: "var(--type-thesis)", bg: "var(--type-thesis-bg)" },
    voice_memo: { color: "var(--type-voice)", bg: "var(--type-voice-bg)" },
    document: { color: "var(--type-document)", bg: "var(--type-document-bg)" },
  };
  const s = map[type] ?? { color: "var(--text-tertiary)", bg: "var(--bg-elevated)" };
  return (
    <span className="text-[10px] font-medium px-1.5 py-0.5 rounded" style={{ color: s.color, background: s.bg }}>
      {type}
    </span>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-5">
      <div className="text-subheading mb-2">{title}</div>
      {children}
    </div>
  );
}

function EventMiniCard({ event, onClick }: { event: Event; onClick?: () => void }) {
  return (
    <button
      onClick={onClick}
      className="w-full text-left flex items-start gap-2.5 py-2 px-3 rounded-lg transition-colors"
      style={{ background: "var(--bg-elevated)" }}
      onMouseEnter={(e) => (e.currentTarget.style.background = "var(--bg-hover)")}
      onMouseLeave={(e) => (e.currentTarget.style.background = "var(--bg-elevated)")}
    >
      <TypeLabel type={event.type} />
      <div className="flex-1 min-w-0">
        <div className="text-[12px] font-medium truncate" style={{ color: "var(--text-primary)" }}>
          {event.title || "\u2014"}
        </div>
        <div className="text-meta mt-0.5">
          {new Date(event.created_at).toLocaleDateString()}
        </div>
      </div>
    </button>
  );
}

function RelationRow({ r }: { r: RelationRow }) {
  return (
    <div className="flex items-center gap-2 py-1.5 px-3 rounded-lg" style={{ background: "var(--bg-elevated)" }}>
      <span className="text-[11px] font-medium" style={{ color: "var(--text-primary)" }}>{r.source_name}</span>
      <span className="text-[10px] px-1.5 py-0.5 rounded" style={{ color: "var(--type-thesis)", background: "var(--type-thesis-bg)" }}>
        {r.relation}
      </span>
      <span className="text-[11px] font-medium" style={{ color: "var(--text-primary)" }}>{r.target_name}</span>
      <span className="text-meta ml-auto">{r.confidence.toFixed(2)}</span>
    </div>
  );
}

/* ── Main Drawer ── */

export default function DetailDrawer({ target, onClose }: Props) {
  const [event, setEvent] = useState<Event | null>(null);
  const [related, setRelated] = useState<SearchResult[]>([]);
  const [relations, setRelations] = useState<RelationRow[]>([]);
  const [evidenceEvents, setEvidenceEvents] = useState<Event[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!target) return;

    setLoading(true);
    setEvent(null);
    setRelated([]);
    setRelations([]);
    setEvidenceEvents([]);

    const eventId =
      target.kind === "event" ? target.id :
      target.kind === "signal" ? target.new_event_id :
      null; // notification — use related_event_ids

    const promises: Promise<void>[] = [];

    if (eventId) {
      promises.push(
        api.event(eventId).then(setEvent).catch(() => {}),
        api.eventRelated(eventId, 8).then(setRelated).catch(() => {}),
        api.entityGraph(eventId).then(setRelations).catch(() => {}),
      );
    }

    // For signals — load evidence events
    if (target.kind === "signal") {
      const ids = [...new Set([target.new_event_id, target.existing_event_id, ...target.evidence_event_ids])];
      promises.push(
        Promise.all(ids.map((id) => api.event(id).catch(() => null)))
          .then((results) => setEvidenceEvents(results.filter(Boolean) as Event[]))
      );
    }

    // For notifications — load related events
    if (target.kind === "notification" && target.related_event_ids.length > 0) {
      promises.push(
        Promise.all(target.related_event_ids.map((id) => api.event(id).catch(() => null)))
          .then((results) => setEvidenceEvents(results.filter(Boolean) as Event[]))
      );
    }

    Promise.all(promises).finally(() => setLoading(false));
  }, [target]);

  if (!target) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40"
        style={{ background: "rgba(0,0,0,0.4)" }}
        onClick={onClose}
      />

      {/* Drawer */}
      <div
        className="fixed top-0 right-0 z-50 h-full w-[420px] max-w-[85vw] overflow-y-auto"
        style={{
          background: "var(--bg-surface)",
          borderLeft: "1px solid var(--border-default)",
          boxShadow: "-8px 0 32px rgba(0,0,0,0.3)",
        }}
      >
        {/* Header */}
        <div
          className="sticky top-0 z-10 flex items-center justify-between px-5 py-4 border-b"
          style={{ background: "var(--bg-surface)", borderColor: "var(--border-subtle)" }}
        >
          <div className="text-subheading">
            {target.kind === "event" ? "Event Detail" :
             target.kind === "signal" ? "Signal Context" :
             "Notification Context"}
          </div>
          <button
            onClick={onClose}
            className="text-[13px] px-2 py-1 rounded-md transition-colors"
            style={{ color: "var(--text-tertiary)" }}
            onMouseEnter={(e) => { e.currentTarget.style.color = "var(--text-primary)"; e.currentTarget.style.background = "var(--bg-elevated)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.color = "var(--text-tertiary)"; e.currentTarget.style.background = ""; }}
          >
            Close
          </button>
        </div>

        {/* Content */}
        <div className="px-5 py-5">
          {loading ? (
            <div className="py-12 text-center text-body">Loading context...</div>
          ) : (
            <>
              {/* Primary event */}
              {event && (
                <Section title="Primary Event">
                  <div className="space-y-2">
                    <div className="flex items-center gap-2">
                      <TypeLabel type={event.type} />
                      <span className="text-meta font-mono">{event.id.slice(0, 8)}</span>
                    </div>
                    <div className="text-[15px] font-medium" style={{ color: "var(--text-primary)" }}>
                      {event.title || "\u2014"}
                    </div>
                    {event.summary && (
                      <p className="text-body leading-relaxed">{event.summary}</p>
                    )}
                    {event.user_annotation && (
                      <div
                        className="px-3 py-2 rounded-lg mt-2"
                        style={{ background: "rgba(165,180,252,0.04)", borderLeft: "2px solid var(--text-accent-dim)" }}
                      >
                        <div className="text-meta mb-0.5">Your annotation</div>
                        <div className="text-[13px]" style={{ color: "var(--text-accent)" }}>{event.user_annotation}</div>
                      </div>
                    )}
                    <div className="flex items-center gap-3 text-meta mt-1">
                      <span>{new Date(event.created_at).toLocaleString()}</span>
                      {event.source && <span>{event.source}</span>}
                      {event.source_type && <span>{event.source_type}</span>}
                      {event.temporality && event.temporality !== "permanent" && (
                        <span style={{ color: "var(--status-medium)" }}>{event.temporality}</span>
                      )}
                    </div>
                    {event.tags.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-2">
                        {event.tags.map((t) => (
                          <span key={t} className="text-[11px] px-2 py-0.5 rounded-full" style={{ color: "var(--text-tertiary)", background: "var(--bg-elevated)", border: "1px solid var(--border-subtle)" }}>{t}</span>
                        ))}
                      </div>
                    )}
                    {event.thesis_links.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-1">
                        {event.thesis_links.map((t) => (
                          <span key={t} className="text-[11px] px-2 py-0.5 rounded" style={{ color: "var(--text-accent)", background: "rgba(165,180,252,0.08)" }}>{t}</span>
                        ))}
                      </div>
                    )}
                    {event.source_path && (
                      <div className="mt-2">
                        {(event.source_path.startsWith("http") || event.source_path.startsWith("link:")) ? (
                          <a
                            href={event.source_path.startsWith("link:") ? event.source_path.slice(5) : event.source_path}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-[11px] transition-colors break-all"
                            style={{ color: "var(--text-accent-dim)", textDecoration: "underline" }}
                          >
                            {(event.source_path.startsWith("link:") ? event.source_path.slice(5) : event.source_path).replace(/^https?:\/\//, "").slice(0, 80)}
                          </a>
                        ) : (
                          <span className="text-meta font-mono break-all">{event.source_path}</span>
                        )}
                      </div>
                    )}
                  </div>
                </Section>
              )}

              {/* Evidence events (for signals/notifications) */}
              {evidenceEvents.length > 0 && (
                <Section title={target.kind === "signal" ? "Evidence Chain" : "Related Events"}>
                  <div className="space-y-1.5">
                    {evidenceEvents.map((e) => (
                      <EventMiniCard key={e.id} event={e} />
                    ))}
                  </div>
                </Section>
              )}

              {/* Related events (via entity graph) */}
              {related.length > 0 && (
                <Section title="Related by Shared Entities">
                  <div className="space-y-1.5">
                    {related.map((r) => (
                      <EventMiniCard key={r.event.id} event={r.event} />
                    ))}
                  </div>
                </Section>
              )}

              {/* Relations graph */}
              {relations.length > 0 && (
                <Section title="Relations">
                  <div className="space-y-1">
                    {relations.slice(0, 15).map((r) => (
                      <RelationRow key={r.id} r={r} />
                    ))}
                    {relations.length > 15 && (
                      <div className="text-meta text-center py-1">
                        +{relations.length - 15} more
                      </div>
                    )}
                  </div>
                </Section>
              )}

              {/* Empty state */}
              {!event && evidenceEvents.length === 0 && related.length === 0 && relations.length === 0 && !loading && (
                <div className="py-12 text-center">
                  <div className="text-body">No context available</div>
                  <div className="text-meta mt-1">This item has no linked events or relations yet</div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </>
  );
}
