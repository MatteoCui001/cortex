-- Add relevance score to events (from LLM extraction)
ALTER TABLE events ADD COLUMN IF NOT EXISTS relevance REAL;
