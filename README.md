# Cortex

AI-native knowledge infrastructure: ingest, embed, search, and analyze information with a PostgreSQL-backed knowledge graph.

## Status

Active development. Core infrastructure and intelligence layer are largely complete. Extended I/O and any UI are not yet built.

- Phase 1 (Core Infrastructure): ~95% complete
- Phase 2 (Intelligence Layer): ~80% complete
- Phase 3 (Extended I/O + UI): ~30% complete

What works:
- Obsidian vault import and incremental sync
- Web article ingestion via URL (trafilatura extraction)
- PDF/DOCX/TXT file ingestion (optional extra)
- Hybrid search (semantic + full-text, Chinese and English)
- Entity extraction and deduplication
- Thesis tracking with confidence scoring
- Three-dimension classification (source type, nature tags, temporality)
- User annotations with stance detection
- Proactive push notifications (stale thesis, entity momentum, contradictions)
- Daily digest
- REST API (FastAPI) and CLI

What is not yet built:
- Web UI
- Browser extension
- WeChat / messaging channel integration
- Voice input and transcription
- Image OCR ingestion
- Agent/MCP server interface

## Architecture

Clean/Hexagonal architecture. Domain layer defines entities and port interfaces; use cases implement business logic; adapters implement ports (PostgreSQL, local embeddings, LLM, file store); API and CLI are thin entry points.

```
src/cortex/
  domain/       -- entities, ports, constants, stance parsing
  use_cases/    -- ingest, search, analyze, maintenance, push_detector, contradiction
  adapters/
    postgres/   -- asyncpg storage adapter
    embeddings/ -- local sentence-transformers adapter
    llm/        -- OpenRouter/MiniMax LLM adapter
    filestore/  -- local file store adapter
  api/          -- FastAPI app and routes
  cli/          -- CLI entry point
```

Tech stack:
- PostgreSQL 16+ with pgvector and zhparser extensions
- bge-small-zh-v1.5 embeddings (512 dimensions)
- FastAPI + uvicorn
- asyncpg (async PostgreSQL driver)
- sentence-transformers + torch (local embeddings, optional)
- trafilatura (web article extraction)

## Setup

### Prerequisites

- Python 3.11+
- PostgreSQL 16+ with the `pgvector` and `zhparser` extensions installed
- `uv` (recommended) or pip

### Install

```bash
# Core + local embeddings (required for search and ingest)
uv sync --extra local-embeddings

# Also add PDF/DOCX support
uv sync --extra local-embeddings --extra document-extraction

# Development tools
uv sync --extra dev
```

### Database Setup

```bash
createdb cortex

# Apply all migrations in order
for f in migrations/0*.sql; do psql -d cortex -f "$f"; done
```

The schema creates:
- `events` table with vector(512) embedding column, full-text search (zhparser), thesis links, tags, and Phase 3 classification columns
- `entities` table with embedding column
- `relations` table
- `annotations` table
- IVFFlat vector indexes and GIN indexes for FTS and JSONB columns

### Configuration

Copy `config.yaml` and adjust for your environment. The file is read from the current working directory. For local overrides, create `config.local.yaml` (gitignored); it is deep-merged on top of `config.yaml`.

Key settings:

```yaml
workspace: default          # logical workspace name

storage:
  postgres:
    dsn: postgresql://localhost:5432/cortex

embedding:
  local:
    model: BAAI/bge-small-zh-v1.5
    dimensions: 512         # must match schema vector(512)

llm:
  openrouter:
    api_key: ${LLM_API_KEY} # reads from environment variable
    model: MiniMax-M2.7
    base_url: https://api.minimaxi.com/v1/text
    chat_endpoint: /chatcompletion_v2
    thesis_list:            # investment/research theses to track
      - "AI Agent Infrastructure"

api:
  host: 127.0.0.1
  port: 8420

file_store:
  root: ~/.cortex/store     # local storage for original files (articles, PDFs)
```

The LLM is optional. Without an API key, entity extraction, classification, and thesis linking are skipped; embeddings and full-text search still work.

## Usage

### CLI

```bash
# Start the API server
cortex serve

# Import an Obsidian vault (full import)
cortex import --vault ~/Notes

# Incremental sync (new and changed files only)
cortex sync --vault ~/Notes

# Force re-import everything
cortex import --vault ~/Notes --force

# Import a web article
cortex import-link https://example.com/article
cortex import-link https://example.com/article --annotation "有道理"

# Import a PDF, DOCX, or TXT file
cortex import-file ~/reports/research.pdf
cortex import-file ~/reports/research.pdf --annotation "key data point"

# Search the knowledge base (hybrid: semantic + full-text)
cortex search "AI Agent infrastructure"

# Thesis coverage report
cortex thesis
cortex thesis "AI Agent Infrastructure"

# Workspace statistics
cortex stats

# Find events not updated in N days
cortex stale
cortex stale --days 60

# Data maintenance
cortex maintain embeddings      # backfill missing embeddings
cortex maintain tags            # normalize tag variants
cortex maintain classification  # LLM-classify unclassified events
cortex maintain dedupe          # merge duplicate entities
cortex maintain all             # run all of the above

# Daily digest
cortex digest
cortex digest --days 7

# Add annotation with stance to an event
cortex annotate <event-id> "disagree, silver reduction is slower than claimed"

# Proactive notifications (stale theses, entity momentum, contradictions)
cortex notifications
```

### API

```bash
cortex serve
# Listening on http://127.0.0.1:8420
# Docs at http://127.0.0.1:8420/docs
```

Key endpoints:

```bash
# Hybrid search
curl -X POST http://localhost:8420/search \
  -H "Content-Type: application/json" \
  -d '{"query": "AI Agent infrastructure", "mode": "hybrid", "limit": 10}'

# Semantic or full-text only
curl -X POST http://localhost:8420/search \
  -d '{"query": "...", "mode": "semantic"}'
curl -X POST http://localhost:8420/search \
  -d '{"query": "...", "mode": "fulltext"}'

# Find related events (via shared entities)
curl http://localhost:8420/search/related/<event-id>

# Create an event directly
curl -X POST http://localhost:8420/events \
  -H "Content-Type: application/json" \
  -d '{"title": "Note title", "content": "...", "event_type": "note"}'

# Unified ingest (text or URL)
curl -X POST http://localhost:8420/events/ingest \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/article", "user_annotation": "interesting"}'

curl -X POST http://localhost:8420/events/ingest \
  -d '{"title": "My note", "content": "...", "raw_input_type": "text"}'

# Get a specific event
curl http://localhost:8420/events/<event-id>

# Thesis coverage
curl http://localhost:8420/thesis
curl http://localhost:8420/thesis/AI%20Agent%20Infrastructure

# Stats and digest
curl http://localhost:8420/stats
curl http://localhost:8420/digest
curl "http://localhost:8420/digest?days=7"

# Stale events
curl "http://localhost:8420/stale?days=30"

# Entity search
curl "http://localhost:8420/entities/search?q=OpenAI&types=company&limit=10"

# Events mentioning an entity
curl http://localhost:8420/entities/<entity-id>/events

# Entity/event relation graph
curl http://localhost:8420/entity/<object-id>/graph

# Add annotation to an event
curl -X POST http://localhost:8420/events/<event-id>/annotate \
  -H "Content-Type: application/json" \
  -d '{"annotation": "disagree, data is from 2024", "stance": "disagree"}'

# Get annotations
curl http://localhost:8420/annotations/event/<event-id>

# Proactive notifications
curl http://localhost:8420/notifications
```

## Development

```bash
uv sync --extra dev --extra local-embeddings

# Lint
make lint

# Format
make format

# Test
make test

# Lint + test
make check

# Verify import works
make import-check
```

## Project Structure

```
cortex/
  src/cortex/
    domain/           -- Entity dataclasses, port ABCs, stance parser, constants
    use_cases/        -- Business logic (ingest, search, analyze, maintenance,
                         ingest_link, ingest_file, push_detector, contradiction)
    adapters/
      postgres/       -- asyncpg storage implementation
      embeddings/     -- Local sentence-transformers embedding adapter
      llm/            -- OpenRouter/MiniMax LLM adapter
      filestore/      -- Local file system store for original files
    api/              -- FastAPI application factory and routes
    cli/              -- CLI entry point (main.py)
  migrations/         -- SQL migration files (apply in order: 001..007)
  tests/              -- pytest test suite
  config.yaml         -- Default configuration (copy and override locally)
  pyproject.toml      -- Project metadata, dependencies, tool config
