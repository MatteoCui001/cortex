-- Cortex: switch embedding from 384-dim (all-MiniLM-L6-v2) to 512-dim (bge-small-zh-v1.5)
-- WARNING: This invalidates all existing embeddings. Must re-import after running.

-- Drop old vector indexes (they reference vector(384))
DROP INDEX IF EXISTS idx_events_embedding;

-- Clear stale embeddings FIRST (must happen before ALTER when data exists)
UPDATE events SET embedding = NULL;
UPDATE entities SET embedding = NULL;

-- Alter column dimensions
ALTER TABLE events ALTER COLUMN embedding TYPE vector(512);
ALTER TABLE entities ALTER COLUMN embedding TYPE vector(512);

-- Rebuild IVFFlat index for new dimensions
CREATE INDEX idx_events_embedding ON events
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 50);
