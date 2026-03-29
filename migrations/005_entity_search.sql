-- Cortex: add entity embedding index for semantic entity search
-- Requires entity embeddings to be backfilled first (cortex maintain embeddings)
-- Skips gracefully if pgvector is not installed.

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') THEN
        RAISE NOTICE 'pgvector not installed — skipping entity embedding index';
        RETURN;
    END IF;

    CREATE INDEX IF NOT EXISTS idx_entities_embedding
    ON entities USING ivfflat (embedding vector_cosine_ops) WITH (lists = 50);
END $$;
