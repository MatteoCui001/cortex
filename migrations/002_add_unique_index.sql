-- Cortex: incremental fixes for databases created with 001_init.sql
-- before the unique index was added.
--
-- Safe to run multiple times (IF NOT EXISTS / CREATE ... IF NOT EXISTS).

-- Unique index needed for ON CONFLICT upsert in insert_event()
CREATE UNIQUE INDEX IF NOT EXISTS idx_events_workspace_source
    ON events(workspace_id, source_path)
    WHERE source_path != '';
