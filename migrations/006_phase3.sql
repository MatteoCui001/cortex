-- Phase 3: Information framework + annotations
-- Adds three-dimension classification, key_points, stance, user reactions

BEGIN;

-- 1. Add new columns to events (all nullable with defaults)
ALTER TABLE events
  ADD COLUMN IF NOT EXISTS raw_input_type   TEXT,
  ADD COLUMN IF NOT EXISTS raw_input_ref    TEXT,
  ADD COLUMN IF NOT EXISTS key_points       JSONB    DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS stance           JSONB    DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS source_type      TEXT,
  ADD COLUMN IF NOT EXISTS source_weight    REAL,
  ADD COLUMN IF NOT EXISTS nature_tags      JSONB    DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS temporality      TEXT,
  ADD COLUMN IF NOT EXISTS expires_at       TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS user_annotation  TEXT,
  ADD COLUMN IF NOT EXISTS user_stance      TEXT;

-- 2. Expand type constraint to include new input types
DO $$
DECLARE
    con_name TEXT;
BEGIN
    SELECT conname INTO con_name
    FROM pg_constraint
    WHERE conrelid = 'events'::regclass
      AND contype = 'c'
      AND pg_get_constraintdef(oid) LIKE '%type%IN%';
    IF con_name IS NOT NULL THEN
        EXECUTE 'ALTER TABLE events DROP CONSTRAINT ' || con_name;
    END IF;
END $$;

ALTER TABLE events ADD CONSTRAINT events_type_check
  CHECK (type IN (
    'article','meeting','note','thesis','chat',
    'voice_memo','image','document','video','agent_analysis'
  ));

-- 3. Create annotations table
CREATE TABLE IF NOT EXISTS annotations (
  id            UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id  TEXT         NOT NULL DEFAULT 'default',
  target_type   TEXT         NOT NULL CHECK (target_type IN ('event','entity','thesis')),
  target_id     UUID         NOT NULL,
  annotation    TEXT,
  stance        TEXT         CHECK (stance IS NULL OR stance IN ('agree','disagree','uncertain','skip')),
  context       JSONB        DEFAULT '{}'::jsonb,
  created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_annotations_target
  ON annotations(workspace_id, target_type, target_id);

-- 4. Indexes for new query patterns
CREATE INDEX IF NOT EXISTS idx_events_source_type ON events(source_type)
  WHERE source_type IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_events_temporality ON events(temporality)
  WHERE temporality IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_events_expires_at ON events(expires_at)
  WHERE expires_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_events_user_stance ON events(workspace_id, user_stance)
  WHERE user_stance IS NOT NULL;

COMMIT;
