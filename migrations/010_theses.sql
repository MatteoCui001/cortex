-- Phase 6: Structured Theses + Evidence tracking
-- Adds first-class thesis (user-driven predictions) and evidence linking.

BEGIN;

-- Structured theses (user-driven judgments/predictions)
CREATE TABLE IF NOT EXISTS theses (
    id              UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id    TEXT         NOT NULL DEFAULT 'default',
    text            TEXT         NOT NULL,
    stance          TEXT         NOT NULL DEFAULT 'neutral'
                    CHECK (stance IN ('bullish','bearish','neutral')),
    theme           TEXT,
    status          TEXT         NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active','resolved','invalidated')),
    expires_at      TIMESTAMPTZ,
    created_by      TEXT         NOT NULL DEFAULT 'manual'
                    CHECK (created_by IN ('manual','fleeting','inferred')),
    confirmed       BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_theses_workspace
    ON theses(workspace_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_theses_theme
    ON theses(workspace_id, theme)
    WHERE theme IS NOT NULL;

-- Evidence linking events to theses with assessed impact
CREATE TABLE IF NOT EXISTS thesis_evidence (
    id               UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id     TEXT         NOT NULL DEFAULT 'default',
    thesis_id        UUID         NOT NULL REFERENCES theses(id) ON DELETE CASCADE,
    event_id         UUID         NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    impact           TEXT         NOT NULL
                     CHECK (impact IN ('supports','contradicts','neutral')),
    confidence_delta REAL         NOT NULL DEFAULT 0.0,
    rationale        TEXT,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE (thesis_id, event_id)
);

CREATE INDEX IF NOT EXISTS idx_thesis_evidence_thesis
    ON thesis_evidence(thesis_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_thesis_evidence_event
    ON thesis_evidence(event_id);
CREATE INDEX IF NOT EXISTS idx_thesis_evidence_workspace
    ON thesis_evidence(workspace_id, created_at DESC);

-- Auto-update theses.updated_at when evidence is added
CREATE OR REPLACE FUNCTION thesis_evidence_touch_thesis()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE theses SET updated_at = NOW() WHERE id = NEW.thesis_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$ BEGIN
    CREATE TRIGGER thesis_evidence_after_upsert
        AFTER INSERT OR UPDATE ON thesis_evidence
        FOR EACH ROW EXECUTE FUNCTION thesis_evidence_touch_thesis();
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

COMMIT;
