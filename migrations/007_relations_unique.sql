-- Add unique index on relations to prevent duplicate (source, target, relation) rows.
-- Required for ON CONFLICT DO NOTHING in insert_relation().
CREATE UNIQUE INDEX IF NOT EXISTS idx_relations_unique
    ON relations(workspace_id, source_id, target_id, relation);
