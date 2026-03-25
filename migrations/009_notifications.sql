-- Phase 4: Persistent notifications with state machine lifecycle.

CREATE TABLE IF NOT EXISTS notifications (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id    TEXT NOT NULL DEFAULT 'default',
    source_kind     TEXT NOT NULL,
    source_id       TEXT NOT NULL DEFAULT '',
    dedup_key       TEXT NOT NULL,
    title           TEXT NOT NULL,
    body            TEXT NOT NULL DEFAULT '',
    priority        TEXT NOT NULL DEFAULT 'medium'
                    CHECK (priority IN ('low','medium','high')),
    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending','delivered','read','acked','dismissed','failed')),
    channel         TEXT NOT NULL DEFAULT 'inbox'
                    CHECK (channel IN ('inbox','webhook')),
    related_event_ids JSONB NOT NULL DEFAULT '[]',
    signal_id       UUID,
    cooldown_until  TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    delivered_at    TIMESTAMPTZ,
    acted_at        TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_notifications_workspace_status
    ON notifications(workspace_id, status, created_at DESC);

-- Partial unique index: only one active notification per dedup_key per workspace.
CREATE UNIQUE INDEX IF NOT EXISTS idx_notifications_dedup_active
    ON notifications(workspace_id, dedup_key)
    WHERE status NOT IN ('acked','dismissed','failed');
