-- Cortex: initial schema
-- PostgreSQL 16+ with optional pgvector and zhparser

-- Try to enable pgvector (non-fatal if not installed)
DO $$ BEGIN
    CREATE EXTENSION IF NOT EXISTS vector;
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'pgvector not available — semantic search disabled until installed';
END $$;

-- Knowledge events (core table — works with or without pgvector)
CREATE TABLE IF NOT EXISTS events (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id  TEXT NOT NULL DEFAULT 'default',
    type          TEXT NOT NULL CHECK (type IN ('article','meeting','note','thesis','chat')),
    title         TEXT NOT NULL DEFAULT '',
    content       TEXT NOT NULL DEFAULT '',
    summary       TEXT NOT NULL DEFAULT '',
    tags          JSONB NOT NULL DEFAULT '[]',
    thesis_links  JSONB NOT NULL DEFAULT '[]',
    confidence    REAL NOT NULL DEFAULT 0.5,
    tier          INTEGER NOT NULL DEFAULT 0,
    source        TEXT NOT NULL DEFAULT '',
    source_path   TEXT NOT NULL DEFAULT '',
    metadata      JSONB NOT NULL DEFAULT '{}',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Add vector column only if pgvector is available
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') THEN
        ALTER TABLE events ADD COLUMN IF NOT EXISTS embedding vector(512);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_events_workspace ON events(workspace_id);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(workspace_id, type);
CREATE INDEX IF NOT EXISTS idx_events_source_path ON events(workspace_id, source_path);
CREATE UNIQUE INDEX IF NOT EXISTS idx_events_workspace_source ON events(workspace_id, source_path) WHERE source_path != '';
CREATE INDEX IF NOT EXISTS idx_events_created ON events(workspace_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_events_thesis ON events USING gin(thesis_links);
CREATE INDEX IF NOT EXISTS idx_events_tags ON events USING gin(tags);

-- Full-text search (use simple config as fallback if zhparser not available)
DO $$ BEGIN
    -- Try zhparser first
    CREATE EXTENSION IF NOT EXISTS zhparser;
    CREATE TEXT SEARCH CONFIGURATION zhcfg (PARSER = zhparser);
    ALTER TEXT SEARCH CONFIGURATION zhcfg ADD MAPPING FOR n,v,a,i,e,l,j WITH simple;
    ALTER TABLE events ADD COLUMN IF NOT EXISTS fts tsvector
        GENERATED ALWAYS AS (
            setweight(to_tsvector('zhcfg', coalesce(title, '')), 'A') ||
            setweight(to_tsvector('zhcfg', coalesce(summary, '')), 'B') ||
            setweight(to_tsvector('zhcfg', coalesce(content, '')), 'C')
        ) STORED;
EXCEPTION WHEN OTHERS THEN
    -- Fallback to simple English config
    RAISE NOTICE 'zhparser not available — using simple text search config';
    ALTER TABLE events ADD COLUMN IF NOT EXISTS fts tsvector
        GENERATED ALWAYS AS (
            setweight(to_tsvector('simple', coalesce(title, '')), 'A') ||
            setweight(to_tsvector('simple', coalesce(summary, '')), 'B') ||
            setweight(to_tsvector('simple', coalesce(content, '')), 'C')
        ) STORED;
END $$;
CREATE INDEX IF NOT EXISTS idx_events_fts ON events USING gin(fts);

-- Vector similarity index (only if pgvector is available)
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') THEN
        CREATE INDEX IF NOT EXISTS idx_events_embedding ON events
            USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 50);
    END IF;
END $$;

-- Entities
CREATE TABLE IF NOT EXISTS entities (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id  TEXT NOT NULL DEFAULT 'default',
    type          TEXT NOT NULL CHECK (type IN ('company','person','technology','concept','fund')),
    name          TEXT NOT NULL,
    aliases       JSONB NOT NULL DEFAULT '[]',
    properties    JSONB NOT NULL DEFAULT '{}',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Add vector column to entities if pgvector available
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') THEN
        ALTER TABLE entities ADD COLUMN IF NOT EXISTS embedding vector(512);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_entities_workspace ON entities(workspace_id);
CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(workspace_id, name);
CREATE UNIQUE INDEX IF NOT EXISTS idx_entities_unique_name ON entities(workspace_id, type, name);

-- Relations
CREATE TABLE IF NOT EXISTS relations (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id  TEXT NOT NULL DEFAULT 'default',
    source_type   TEXT NOT NULL CHECK (source_type IN ('event','entity')),
    source_id     UUID NOT NULL,
    target_type   TEXT NOT NULL CHECK (target_type IN ('event','entity')),
    target_id     UUID NOT NULL,
    relation      TEXT NOT NULL DEFAULT 'related_to',
    confidence    REAL NOT NULL DEFAULT 1.0,
    metadata      JSONB NOT NULL DEFAULT '{}',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_relations_workspace ON relations(workspace_id);
CREATE INDEX IF NOT EXISTS idx_relations_source ON relations(source_type, source_id);
CREATE INDEX IF NOT EXISTS idx_relations_target ON relations(target_type, target_id);

-- Updated_at trigger
CREATE OR REPLACE FUNCTION update_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$ BEGIN
    CREATE TRIGGER events_updated BEFORE UPDATE ON events
        FOR EACH ROW EXECUTE FUNCTION update_timestamp();
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TRIGGER entities_updated BEFORE UPDATE ON entities
        FOR EACH ROW EXECUTE FUNCTION update_timestamp();
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
