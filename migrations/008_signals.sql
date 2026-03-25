-- Phase 3.6: Signal persistence and feedback tables
BEGIN;

CREATE TABLE IF NOT EXISTS signals (
    id                UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id      TEXT         NOT NULL DEFAULT 'default',
    new_event_id      UUID         NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    existing_event_id UUID         NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    signal_type       TEXT         NOT NULL
                      CHECK (signal_type IN ('new_signal','redundant','contradiction','answer','bridge')),
    topic             TEXT,
    topic_normalized  TEXT         GENERATED ALWAYS AS (lower(trim(topic))) STORED,
    summary           TEXT,
    confidence        REAL         NOT NULL DEFAULT 0.5,
    priority_score    REAL         NOT NULL DEFAULT 0.0,
    evidence_event_ids JSONB       NOT NULL DEFAULT '[]',
    rationale         TEXT,
    evidence_strength TEXT         CHECK (evidence_strength IS NULL
                                         OR evidence_strength IN ('strong','moderate','weak')),
    thesis_links      JSONB        NOT NULL DEFAULT '[]',
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_signals_workspace
    ON signals(workspace_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_signals_new_event
    ON signals(workspace_id, new_event_id);
CREATE INDEX IF NOT EXISTS idx_signals_type_topic
    ON signals(workspace_id, signal_type, topic_normalized);
CREATE INDEX IF NOT EXISTS idx_signals_thesis
    ON signals USING gin(thesis_links);

CREATE TABLE IF NOT EXISTS signal_feedback (
    id                UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id      TEXT         NOT NULL DEFAULT 'default',
    signal_id         UUID         NOT NULL REFERENCES signals(id) ON DELETE CASCADE,
    verdict           TEXT         NOT NULL
                      CHECK (verdict IN ('useful','not_useful','wrong','save_for_later')),
    note              TEXT,
    signal_type       TEXT         NOT NULL,
    topic_normalized  TEXT         NOT NULL,
    thesis_link       TEXT,
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_signal_feedback_signal
    ON signal_feedback(signal_id);
CREATE INDEX IF NOT EXISTS idx_signal_feedback_type_topic
    ON signal_feedback(workspace_id, signal_type, topic_normalized);
CREATE INDEX IF NOT EXISTS idx_signal_feedback_thesis
    ON signal_feedback(workspace_id, thesis_link)
    WHERE thesis_link IS NOT NULL;

COMMIT;
