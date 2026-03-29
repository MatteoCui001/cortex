const TYPE_STYLES: Record<string, { color: string; bg: string }> = {
  article: { color: "var(--type-article)", bg: "var(--type-article-bg)" },
  note: { color: "var(--type-note)", bg: "var(--type-note-bg)" },
  chat: { color: "var(--type-chat)", bg: "var(--type-chat-bg)" },
  meeting: { color: "var(--type-meeting)", bg: "var(--type-meeting-bg)" },
  thesis: { color: "var(--type-thesis)", bg: "var(--type-thesis-bg)" },
  voice_memo: { color: "var(--type-voice)", bg: "var(--type-voice-bg)" },
  document: { color: "var(--type-document)", bg: "var(--type-document-bg)" },
};

export default function TypeLabel({ type }: { type: string }) {
  const s = TYPE_STYLES[type] ?? { color: "var(--text-tertiary)", bg: "var(--bg-elevated)" };
  return (
    <span
      className="text-[10px] font-medium px-1.5 py-0.5 rounded"
      style={{ color: s.color, background: s.bg }}
    >
      {type}
    </span>
  );
}
