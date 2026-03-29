-- Cortex: add zhparser for Chinese full-text search
-- Requires: zhparser extension installed (optional — skips gracefully)

DO $$ BEGIN
    CREATE EXTENSION IF NOT EXISTS zhparser;

    -- Chinese text search configuration
    CREATE TEXT SEARCH CONFIGURATION zhcfg (PARSER = zhparser);
    ALTER TEXT SEARCH CONFIGURATION zhcfg ADD MAPPING FOR n,v,a,i,e,l,j WITH simple;

    -- Rebuild FTS column using zhcfg instead of 'simple'
    DROP INDEX IF EXISTS idx_events_fts;
    ALTER TABLE events DROP COLUMN IF EXISTS fts;
    ALTER TABLE events ADD COLUMN fts tsvector
        GENERATED ALWAYS AS (
            setweight(to_tsvector('zhcfg', coalesce(title, '')), 'A') ||
            setweight(to_tsvector('zhcfg', coalesce(summary, '')), 'B') ||
            setweight(to_tsvector('zhcfg', coalesce(content, '')), 'C')
        ) STORED;
    CREATE INDEX idx_events_fts ON events USING gin(fts);
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'zhparser not available — keeping existing text search config';
END $$;
