-- Cortex: add entity embedding index for semantic entity search
-- Requires entity embeddings to be backfilled first (cortex maintain embeddings)

CREATE INDEX IF NOT EXISTS idx_entities_embedding
ON entities USING ivfflat (embedding vector_cosine_ops) WITH (lists = 50);
