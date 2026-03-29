import { useEffect, useState, useRef } from "react";
import { api, type Event, type Signal, type SearchResult, type RelationRow, type Annotation } from "./api";
import TypeLabel from "./components/TypeLabel";

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

/* ── Editable chips ── */

function EditableChips({
  items,
  onUpdate,
  color,
  bg,
}: {
  items: string[];
  onUpdate: (items: string[]) => void;
  color: string;
  bg: string;
}) {
  const [adding, setAdding] = useState(false);
  const [input, setInput] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const remove = (item: string) => onUpdate(items.filter((i) => i !== item));
  const add = () => {
    const val = input.trim();
    if (val && !items.includes(val)) {
      onUpdate([...items, val]);
    }
    setInput("");
    setAdding(false);
  };

  useEffect(() => {
    if (adding) inputRef.current?.focus();
  }, [adding]);

  return (
    <div className="flex flex-wrap gap-1 items-center">
      {items.map((item) => (
        <span
          key={item}
          className="text-[11px] px-2 py-0.5 rounded-full inline-flex items-center gap-1"
          style={{ color, background: bg, border: "1px solid transparent" }}
        >
          {item}
          <button
            onClick={() => remove(item)}
            className="opacity-50 hover:opacity-100 text-[10px] leading-none"
          >
            x
          </button>
        </span>
      ))}
      {adding ? (
        <input
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") add(); if (e.key === "Escape") setAdding(false); }}
          onBlur={add}
          className="text-[11px] px-2 py-0.5 rounded-full outline-none w-24"
          style={{ background: "var(--bg-elevated)", color: "var(--text-primary)", border: "1px solid var(--border-subtle)" }}
          placeholder="add..."
        />
      ) : (
        <button
          onClick={() => setAdding(true)}
          className="text-[11px] px-1.5 py-0.5 rounded-full opacity-40 hover:opacity-80 transition-opacity"
          style={{ border: "1px dashed var(--border-subtle)", color: "var(--text-tertiary)" }}
        >
          +
        </button>
      )}
    </div>
  );
}

/* ── Annotation form ── */

function AnnotationForm({ eventId, onSaved }: { eventId: string; onSaved: () => void }) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [stance, setStance] = useState<string>("");
  const [saving, setSaving] = useState(false);
  const [annotations, setAnnotations] = useState<Annotation[]>([]);

  useEffect(() => {
    api.annotations(eventId).then(setAnnotations).catch(() => {});
  }, [eventId]);

  const submit = async () => {
    if (!text.trim()) return;
    setSaving(true);
    try {
      await api.annotate(eventId, text.trim(), stance || undefined);
      setText("");
      setStance("");
      setOpen(false);
      onSaved();
      api.annotations(eventId).then(setAnnotations).catch(() => {});
    } catch { /* ignore */ }
    setSaving(false);
  };

  const stances = ["agree", "disagree", "uncertain", "skip"];

  return (
    <div className="mt-3">
      {annotations.length > 0 && (
        <div className="space-y-1.5 mb-3">
          {annotations.map((a) => (
            <div
              key={a.id}
              className="px-3 py-2 rounded-lg"
              style={{ background: "rgba(165,180,252,0.04)", borderLeft: "2px solid var(--text-accent-dim)" }}
            >
              <div className="flex items-center gap-2 mb-0.5">
                <span className="text-meta">{new Date(a.created_at).toLocaleDateString()}</span>
                {a.stance && (
                  <span className="text-[10px] px-1.5 py-0.5 rounded" style={{ color: "var(--type-thesis)", background: "var(--type-thesis-bg)" }}>
                    {a.stance}
                  </span>
                )}
              </div>
              {a.annotation && (
                <div className="text-[12px]" style={{ color: "var(--text-accent)" }}>{a.annotation}</div>
              )}
            </div>
          ))}
        </div>
      )}
      {!open ? (
        <button
          onClick={() => setOpen(true)}
          className="text-[11px] px-3 py-1.5 rounded-lg transition-colors"
          style={{ color: "var(--text-accent-dim)", border: "1px dashed var(--border-subtle)" }}
          onMouseEnter={(e) => (e.currentTarget.style.borderColor = "var(--text-accent-dim)")}
          onMouseLeave={(e) => (e.currentTarget.style.borderColor = "var(--border-subtle)")}
        >
          Add note
        </button>
      ) : (
        <div className="space-y-2">
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Your thoughts on this event..."
            rows={3}
            className="w-full text-[12px] px-3 py-2 rounded-lg resize-none outline-none"
            style={{ background: "var(--bg-elevated)", color: "var(--text-primary)", border: "1px solid var(--border-subtle)" }}
          />
          <div className="flex items-center gap-1.5">
            {stances.map((s) => (
              <button
                key={s}
                onClick={() => setStance(stance === s ? "" : s)}
                className="text-[10px] px-2 py-0.5 rounded-full transition-colors"
                style={{
                  color: stance === s ? "var(--text-primary)" : "var(--text-tertiary)",
                  background: stance === s ? "var(--bg-active)" : "var(--bg-elevated)",
                  border: `1px solid ${stance === s ? "var(--border-default)" : "var(--border-subtle)"}`,
                }}
              >
                {s}
              </button>
            ))}
            <div className="flex-1" />
            <button
              onClick={() => { setOpen(false); setText(""); setStance(""); }}
              className="text-[11px] px-2 py-1 rounded"
              style={{ color: "var(--text-tertiary)" }}
            >
              Cancel
            </button>
            <button
              onClick={submit}
              disabled={saving || !text.trim()}
              className="text-[11px] px-3 py-1 rounded-lg font-medium transition-colors"
              style={{
                color: "var(--text-primary)",
                background: "var(--bg-active)",
                opacity: saving || !text.trim() ? 0.4 : 1,
              }}
            >
              {saving ? "Saving..." : "Save"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

/* ── Inline editable title ── */

function EditableTitle({ value, onSave }: { value: string; onSave: (v: string) => void }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editing) inputRef.current?.focus();
  }, [editing]);

  const save = () => {
    if (draft.trim() && draft.trim() !== value) onSave(draft.trim());
    setEditing(false);
  };

  if (editing) {
    return (
      <input
        ref={inputRef}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => { if (e.key === "Enter") save(); if (e.key === "Escape") { setDraft(value); setEditing(false); } }}
        onBlur={save}
        className="text-[15px] font-medium w-full px-1 py-0.5 rounded outline-none"
        style={{ color: "var(--text-primary)", background: "var(--bg-elevated)", border: "1px solid var(--border-subtle)" }}
      />
    );
  }

  return (
    <div
      onClick={() => { setDraft(value); setEditing(true); }}
      className="text-[15px] font-medium cursor-pointer rounded px-1 py-0.5 -mx-1 transition-colors"
      style={{ color: "var(--text-primary)" }}
      onMouseEnter={(e) => (e.currentTarget.style.background = "var(--bg-elevated)")}
      onMouseLeave={(e) => (e.currentTarget.style.background = "")}
      title="Click to edit"
    >
      {value || "\u2014"}
    </div>
  );
}

/* ── Main Drawer ── */

export default function DetailDrawer({ target, onClose }: Props) {
  const [event, setEvent] = useState<Event | null>(null);
  const [related, setRelated] = useState<SearchResult[]>([]);
  const [relations, setRelations] = useState<RelationRow[]>([]);
  const [evidenceEvents, setEvidenceEvents] = useState<Event[]>([]);
  const [linkedSignal, setLinkedSignal] = useState<Signal | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!target) return;

    setLoading(true);
    setEvent(null);
    setRelated([]);
    setRelations([]);
    setEvidenceEvents([]);
    setLinkedSignal(null);

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

    // For notifications — load related events and linked signal
    if (target.kind === "notification") {
      if (target.related_event_ids.length > 0) {
        promises.push(
          Promise.all(target.related_event_ids.map((id) => api.event(id).catch(() => null)))
            .then((results) => setEvidenceEvents(results.filter(Boolean) as Event[]))
        );
      }
      // Fetch the linked signal for context (why was this notification generated?)
      if (target.signal_id) {
        promises.push(
          api.signals(100)
            .then((sigs) => {
              const match = sigs.find((s) => s.id === target.signal_id);
              if (match) setLinkedSignal(match);
            })
            .catch(() => {})
        );
      }
    }

    Promise.all(promises).finally(() => setLoading(false));
  }, [target]);

  const refreshEvent = () => {
    if (!event) return;
    api.event(event.id).then(setEvent).catch(() => {});
  };

  const handleUpdateField = async (fields: { tags?: string[]; thesis_links?: string[]; title?: string }) => {
    if (!event) return;
    try {
      const updated = await api.updateEvent(event.id, fields);
      setEvent(updated);
    } catch { /* ignore */ }
  };

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
                    <EditableTitle
                      value={event.title || ""}
                      onSave={(title) => handleUpdateField({ title })}
                    />
                    {event.summary && (
                      <p className="text-body leading-relaxed">{event.summary}</p>
                    )}
                    <AnnotationForm eventId={event.id} onSaved={refreshEvent} />
                    <div className="flex items-center gap-3 text-meta mt-1">
                      <span>{new Date(event.created_at).toLocaleString()}</span>
                      {event.source && <span>{event.source}</span>}
                      {event.source_type && <span>{event.source_type}</span>}
                      {event.temporality && event.temporality !== "permanent" && (
                        <span style={{ color: "var(--status-medium)" }}>{event.temporality}</span>
                      )}
                    </div>
                    <div className="mt-2">
                      <div className="text-meta text-[10px] mb-1">Tags</div>
                      <EditableChips
                        items={event.tags}
                        onUpdate={(tags) => handleUpdateField({ tags })}
                        color="var(--text-tertiary)"
                        bg="var(--bg-elevated)"
                      />
                    </div>
                    <div className="mt-2">
                      <div className="text-meta text-[10px] mb-1">Thesis Links</div>
                      <EditableChips
                        items={event.thesis_links}
                        onUpdate={(thesis_links) => handleUpdateField({ thesis_links })}
                        color="var(--text-accent)"
                        bg="rgba(165,180,252,0.08)"
                      />
                    </div>
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

              {/* Signal context (for notifications linked to a signal) */}
              {linkedSignal && (
                <Section title="Why This Notification">
                  <div className="space-y-2 px-3 py-2.5 rounded-lg" style={{ background: "var(--bg-elevated)" }}>
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded"
                        style={{
                          color: linkedSignal.signal_type === "contradiction" ? "var(--status-high)" :
                                 linkedSignal.signal_type === "answer" ? "var(--status-success)" :
                                 "var(--text-accent)",
                          background: linkedSignal.signal_type === "contradiction" ? "rgba(248,113,113,0.1)" :
                                      linkedSignal.signal_type === "answer" ? "rgba(74,222,128,0.1)" :
                                      "rgba(165,180,252,0.08)",
                        }}
                      >
                        {linkedSignal.signal_type}
                      </span>
                      {linkedSignal.evidence_strength && (
                        <span className="text-meta">{linkedSignal.evidence_strength}</span>
                      )}
                      <span className="text-meta ml-auto">score: {linkedSignal.priority_score.toFixed(2)}</span>
                    </div>
                    {linkedSignal.topic && (
                      <div className="text-[12px] font-medium" style={{ color: "var(--text-primary)" }}>
                        {linkedSignal.topic}
                      </div>
                    )}
                    {linkedSignal.summary && (
                      <p className="text-body text-[12px] leading-relaxed">{linkedSignal.summary}</p>
                    )}
                    {linkedSignal.rationale && (
                      <p className="text-meta text-[11px] italic">{linkedSignal.rationale}</p>
                    )}
                    {linkedSignal.thesis_links.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-1">
                        {linkedSignal.thesis_links.map((t) => (
                          <span key={t} className="text-[10px] px-1.5 py-0.5 rounded"
                            style={{ color: "var(--text-accent)", background: "rgba(165,180,252,0.08)" }}
                          >{t}</span>
                        ))}
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
