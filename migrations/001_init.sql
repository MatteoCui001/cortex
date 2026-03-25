-- Cortex: initial schema
-- PostgreSQL 17 + pgvector + zhparser

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS zhparser;

-- Chinese text search configuration
CREATE TEXT SEARCH CONFIGURATION zhcfg (PARSER = zhparser);
ALTER TEXT SEARCH CONFIGURATION zhcfg ADD MAPPING FOR n,v,a,i,e,l,j WITH simple;


-- Knowledge events
CREATE TABLE events (
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
    -- NOTE: vector(512) matches all-MiniLM-L6-v2. Changing embedding model
    -- requires ALTER COLUMN embedding TYPE vector(N) and re-embedding all rows.
    embedding     vector(512),
    metadata      JSONB NOT NULL DEFAULT '{}',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_events_workspace ON events(workspace_id);
CREATE INDEX idx_events_type ON events(workspace_id, type);
CREATE INDEX idx_events_source_path ON events(workspace_id, source_path);
CREATE UNIQUE INDEX idx_events_workspace_source ON events(workspace_id, source_path) WHERE source_path != '';
CREATE INDEX idx_events_created ON events(workspace_id, created_at DESC);
CREATE INDEX idx_events_thesis ON events USING gin(thesis_links);
CREATE INDEX idx_events_tags ON events USING gin(tags);

-- Full-text search
ALTER TABLE events ADD COLUMN fts tsvector
    GENERATED ALWAYS AS (
        setweight(to_tsvector('zhcfg', coalesce(title, '')), 'A') ||
        setweight(to_tsvector('zhcfg', coalesce(summary, '')), 'B') ||
        setweight(to_tsvector('zhcfg', coalesce(content, '')), 'C')
    ) STORED;
CREATE INDEX idx_events_fts ON events USING gin(fts);

-- Vector similarity index (IVFFlat, good for <100K rows)
CREATE INDEX idx_events_embedding ON events
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 50);

-- Entities
CREATE TABLE entities (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id  TEXT NOT NULL DEFAULT 'default',
    type          TEXT NOT NULL CHECK (type IN ('company','person','technology','concept','fund')),
    name          TEXT NOT NULL,
    aliases       JSONB NOT NULL DEFAULT '[]',
    properties    JSONB NOT NULL DEFAULT '{}',
    embedding     vector(512),  -- must match events.embedding dimensions
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_entities_workspace ON entities(workspace_id);
CREATE INDEX idx_entities_name ON entities(workspace_id, name);
CREATE UNIQUE INDEX idx_entities_unique_name ON entities(workspace_id, type, name);

-- Relations
CREATE TABLE relations (
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

CREATE INDEX idx_relations_workspace ON relations(workspace_id);
CREATE INDEX idx_relations_source ON relations(source_type, source_id);
CREATE INDEX idx_relations_target ON relations(target_type, target_id);

-- Updated_at trigger
CREATE OR REPLACE FUNCTION update_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER events_updated BEFORE UPDATE ON events
    FOR EACH ROW EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER entities_updated BEFORE UPDATE ON entities
    FOR EACH ROW EXECUTE FUNCTION update_timestamp();

