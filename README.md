# Cortex

AI-native cognitive infrastructure for knowledge workers.

Cortex helps you maintain clear judgment amid information overload. It understands that not all information is equal -- a first-hand factory visit carries more weight than a third-hand blog post, a data point is different from an opinion, and some intelligence expires.

You feed it articles, notes, voice memos, meeting transcripts, and files from wherever you already work (WeChat, browser, Obsidian). It auto-extracts entities, relations, and thesis links, classifies each piece of information by source credibility, nature, and temporality, and proactively tells you when something matters -- a contradiction with your existing beliefs, an answer to a question you asked weeks ago, or a thesis going stale.

## Current Status

**Phase 1 ~95% | Phase 2 ~80% | Phase 3 ~30%.** 147 automated tests passing.

Working features:
- Obsidian vault import + incremental sync
- Chinese semantic search (bge-small-zh-v1.5 + zhparser FTS)
- AI metadata extraction (entities, thesis links, confidence)
- Thesis coverage analysis + stale judgment detection
- Entity semantic search + momentum tracking
- Daily research digest
- Data maintenance (embedding backfill, tag normalization, entity dedup)
- REST API (FastAPI, OpenAPI docs)
- CLI with optimized read/write command separation

## Quick Start

### Prerequisites

- macOS with Homebrew
- Python 3.11+ and [uv](https://docs.astral.sh/uv/)
- PostgreSQL 16 with pgvector + zhparser

### Install

```bash
git clone <repo-url> && cd cortex

# Install all dev dependencies (recommended)
make dev
# Or manually:
uv sync --extra dev --extra local-embeddings

# Create database and run migrations
createdb cortex
for f in migrations/*.sql; do psql -d cortex -f "$f"; done
```

> **Note:** `migrations/007_relations_unique.sql` adds a unique index on relations.
> If upgrading an existing database, first deduplicate:
> ```sql
> DELETE FROM relations a USING relations b
> WHERE a.id > b.id AND a.workspace_id = b.workspace_id
>   AND a.source_id = b.source_id AND a.target_id = b.target_id
>   AND a.relation = b.relation;
> ```
> Then apply `psql -d cortex -f migrations/007_relations_unique.sql`.

### Configure

```bash
cp config.yaml config.local.yaml
# Edit config.local.yaml: set LLM API key, adjust thesis list
```

### Development

```bash
make check    # lint + tests (the daily driver)
make test     # tests only
make lint     # ruff check only
make format   # ruff auto-fix
make serve    # start API server on :8420
```

### Use

```bash
# Import your Obsidian vault
cortex import --vault ~/path/to/vault

# Search
cortex search "AI Agent infrastructure"

# Import a web article
cortex import-link https://example.com/article

# Annotate an event
cortex annotate <event-id> "agree -- strong evidence"

# Thesis coverage
cortex thesis

# Daily digest
cortex digest --days 7

# Push notifications check
cortex notifications

# Stats
cortex stats

# Start API server
cortex serve
# OpenAPI docs at http://localhost:8420/docs
```

## Architecture

```
src/cortex/
  domain/          Pure entities + port interfaces (zero framework deps)
  use_cases/       Business logic (ingest, search, analyze, maintain)
  adapters/
    postgres/      PostgreSQL + pgvector storage
    embeddings/    Local embedding (bge-small-zh-v1.5)
    llm/           LLM adapter for metadata extraction
    filestore/     Human-readable file storage for originals
  api/             FastAPI REST endpoints
  cli/             Command-line interface
```

Clean Architecture / Hexagonal pattern. Domain has zero external imports. Adapters are swappable. All queries workspace-scoped for future multi-tenancy.

## Documentation

| Document | Purpose |
|---|---|
| [PRODUCT-DESIGN.md](docs/PRODUCT-DESIGN.md) | Product vision, information framework, target users, architecture |
| [PRD.md](PRD.md) | Requirements, MVP definition, success metrics |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Technical architecture, schema, conventions, constraints |
| [DATA-MODEL.md](docs/DATA-MODEL.md) | Storage architecture, migration plan, classification spec |
| [CHANGELOG.md](CHANGELOG.md) | Version history |

## License

MIT