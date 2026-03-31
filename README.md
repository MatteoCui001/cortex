# Cortex

> **v0.1.0-beta** -- AI-native knowledge infrastructure for humans and agents.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-3776ab.svg)](https://www.python.org)
[![Docker](https://img.shields.io/badge/docker-compose-2496ed.svg)](docker-compose.yml)

Cortex is a personal knowledge engine that ingests, analyzes, and connects information from heterogeneous sources — Obsidian notes, web articles, PDFs, WeChat messages, meeting transcripts — into a unified knowledge graph with semantic search, entity extraction, signal detection, and proactive notifications.

Built for knowledge workers who operate across languages (Chinese + English), formats, and tools. Designed to be extended by AI agents as a cognitive backend.

---

**Cortex 是一个 AI 原生的认知基础设施。** 它将 Obsidian 笔记、网页文章、PDF、微信消息、会议纪要等异构信息源，统一为一个支持语义搜索、实体抽取、信号检测和主动通知的知识图谱。

为跨语言（中英）、跨格式、跨工具的知识工作者而建。天然支持 AI Agent 作为认知后端扩展。

## Status / 状态

This is an early **beta** release. The core features work but the API surface may change. Bug reports and feature requests are welcome via [GitHub Issues](https://github.com/MatteoCui001/cortex/issues).

## Why Cortex / 为什么做 Cortex

Most knowledge tools are glorified file systems — they store but don't understand. Cortex treats every piece of information as an **event** in a knowledge graph: extracted, embedded, linked to entities and theses, scored for relevance, and surfaced when it matters.

大多数知识工具本质上是美化的文件系统——只存不懂。Cortex 把每条信息视为知识图谱中的一个 **event**：提取、向量化、关联实体和研究主题、评估重要性、在需要时主动推送。

## Architecture / 架构

Hexagonal (ports & adapters) architecture. Domain logic is isolated from infrastructure; every external dependency is behind an abstract port.

六边形架构（端口与适配器）。领域逻辑与基础设施隔离，每个外部依赖都在抽象端口之后。

```
┌─────────────────────────────────────────────────────┐
│  Entry Points                                       │
│  ┌──────────┐  ┌──────────┐  ┌───────────────────┐  │
│  │ REST API │  │   CLI    │  │  Agent (iLink)    │  │
│  └────┬─────┘  └────┬─────┘  └────────┬──────────┘  │
│       └──────────────┼────────────────┘              │
│                      ▼                               │
│  ┌─────────────────────────────────────────────┐     │
│  │            Use Cases                        │     │
│  │  ingest · search · analyze · signals ·      │     │
│  │  notifications · maintenance · digest       │     │
│  └────────────────────┬────────────────────────┘     │
│                       ▼                              │
│  ┌─────────────────────────────────────────────┐     │
│  │            Domain (Entities + Ports)         │     │
│  └────────────────────┬────────────────────────┘     │
│                       ▼                              │
│  ┌──────────┐  ┌───────────┐  ┌─────┐  ┌─────────┐  │
│  │ Postgres │  │ Embedding │  │ LLM │  │  Files  │  │
│  │ +pgvector│  │ bge-small │  │     │  │         │  │
│  └──────────┘  └───────────┘  └─────┘  └─────────┘  │
└─────────────────────────────────────────────────────┘
```

## Features / 功能

| Feature | Description |
|---------|-------------|
| **Multi-source ingestion** | Obsidian vault sync, web articles (trafilatura), PDF/DOCX/TXT, WeChat (via iLink agent), manual text |
| **Hybrid search** | Semantic (bge-small-zh-v1.5, 512d) + full-text (zhparser for Chinese) with score fusion |
| **Entity extraction** | LLM-powered NER with deduplication and alias resolution |
| **Knowledge graph** | Entities, relations, and events linked in PostgreSQL |
| **Thesis tracking** | Track investment/research theses with confidence scoring, coverage reports, and trend analysis |
| **Signal detection** | Automatically detect contradictions, entity momentum shifts, and thesis-relevant patterns |
| **Proactive notifications** | Stale theses, entity momentum, contradiction alerts with priority scoring |
| **Annotations** | User annotations with stance detection (agree/disagree/uncertain) |
| **Web console** | Real-time dashboard: events, signals, inbox, search, entity graph, thesis coverage |
| **REST API** | Full CRUD + search + bulk operations, OpenAPI docs |
| **CLI** | Import, sync, search, maintenance, digest — all from terminal |
| **Docker deployment** | Single `docker compose up` with pgvector |
| **Bilingual** | Native Chinese + English support throughout (search, extraction, UI) |

## Quick Start / 快速开始

### Option A: One-command install (macOS)

```bash
git clone https://github.com/MatteoCui001/cortex.git
cd cortex
./install.sh
```

This installs everything automatically: Homebrew, PostgreSQL 16, pgvector, Python 3.12, embedding model, web console. Takes ~5-10 minutes on first run. Idempotent (safe to re-run).

一条命令自动安装所有依赖。首次运行约 5-10 分钟。幂等设计，可安全重跑。

Then start:

```bash
source ~/.cortex/env && uv run cortex serve
# Open http://localhost:8420/console/
```

### Option B: Docker

```bash
git clone https://github.com/MatteoCui001/cortex.git
cd cortex

# Set your LLM API key (optional — search works without it)
export LLM_API_KEY=your-key-here

docker compose up -d
# Open http://localhost:8420/console/
```

### Option C: Manual setup

Prerequisites: Python 3.11+, PostgreSQL 16+ with pgvector (+ zhparser for Chinese FTS), uv

```bash
uv sync --extra local-embeddings
createdb cortex
for f in migrations/0*.sql; do psql -d cortex -f "$f"; done
uv run cortex serve
```

## CLI Reference / 命令行

```bash
# Server
cortex serve                              # Start API + console on :8420

# Ingestion
cortex import --vault ~/Notes             # Full Obsidian vault import
cortex sync --vault ~/Notes               # Incremental sync (new/changed only)
cortex import-link https://example.com    # Ingest web article
cortex import-file ~/report.pdf           # Ingest PDF/DOCX/TXT

# Search
cortex search "AI Agent infrastructure"   # Hybrid search (semantic + fulltext)

# Analysis
cortex thesis                             # Thesis coverage report
cortex digest                             # Daily knowledge digest
cortex stale --days 30                    # Find neglected topics
cortex notifications                      # View proactive alerts
cortex stats                              # Workspace statistics

# Maintenance
cortex maintain all                       # Run all maintenance tasks
cortex maintain embeddings                # Backfill missing embeddings
cortex maintain tags                      # Normalize tag variants
cortex maintain classification            # LLM-classify unclassified events
cortex maintain dedupe                    # Merge duplicate entities

# Annotation
cortex annotate <event-id> "disagree, data is outdated"
```

## API / 接口

The API serves on port 8420 with OpenAPI docs at `/docs`.

```bash
# Health check
GET  /api/v1/health

# Events
GET  /api/v1/events?limit=50&days=7
GET  /api/v1/events/{id}
POST /api/v1/events/ingest              # Unified ingest (text, URL, or file)
PATCH /api/v1/events/{id}               # Update tags, thesis_links, title

# Search
POST /api/v1/search                     # Hybrid/semantic/fulltext search
GET  /api/v1/search/related/{event_id}  # Find related events

# Entities
GET  /api/v1/entities/search?q=OpenAI
GET  /api/v1/entity/{id}/graph          # Relation graph

# Thesis
GET  /api/v1/thesis                     # Coverage report
GET  /api/v1/thesis/{name}              # Evidence for specific thesis

# Signals
GET  /api/v1/signals?limit=50

# Notifications
GET  /api/v1/notifications?status=pending&limit=50
POST /api/v1/notifications/{id}/read
POST /api/v1/notifications/{id}/ack
POST /api/v1/notifications/{id}/dismiss
POST /api/v1/notifications/bulk-action  # Batch read/ack/dismiss

# Annotations
POST /api/v1/events/{id}/annotate
GET  /api/v1/annotations/event/{id}

# Digest & Stats
GET  /api/v1/digest?days=7
GET  /api/v1/stats
```

## Authentication / 认证

All API endpoints except `/health` and `/ready` require a Bearer token:

```bash
curl -H "Authorization: Bearer $CORTEX_API_TOKEN" http://localhost:8420/api/v1/stats
```

The token is auto-generated by `install.sh` and stored in `~/.cortex/env`. The console served at `/console/` does not require authentication (same-origin).

## Configuration / 配置

Default config in `config.yaml`. Create `config.local.yaml` for local overrides (gitignored, deep-merged on top).

```yaml
workspace: default

storage:
  postgres:
    dsn: postgresql://localhost:5432/cortex

embedding:
  local:
    model: BAAI/bge-small-zh-v1.5
    dimensions: 512

llm:
  openrouter:
    api_key: ${LLM_API_KEY}    # From environment variable
    model: MiniMax-M2.7
    thesis_list:               # Your research/investment theses
      - "AI Agent Infrastructure"
      - "Open Source Commercialization"

api:
  host: 127.0.0.1
  port: 8420
  cors_origins:                # For external frontends
    - "http://localhost:5173"

notifications:
  webhook:
    enabled: false
    url: ""
```

The LLM is optional. Without an API key, entity extraction and classification are skipped; embeddings and full-text search still work.

LLM 是可选的。没有 API key 时，实体抽取和分类会跳过，但向量搜索和全文搜索正常工作。

## Project Structure / 项目结构

```
cortex/
├── src/cortex/
│   ├── domain/           # Entities, ports (ABCs), constants, stance parser
│   ├── use_cases/        # Business logic: ingest, search, analyze, signals,
│   │                     #   notifications, maintenance, digest, contradiction
│   ├── adapters/
│   │   ├── postgres/     # asyncpg storage (pgvector + zhparser)
│   │   ├── embeddings/   # Local sentence-transformers (bge-small-zh-v1.5)
│   │   ├── llm/          # LLM adapter (OpenRouter / MiniMax)
│   │   └── filestore/    # Local file store for originals
│   ├── api/              # FastAPI app, routes, static file serving
│   └── cli/              # CLI entry point
├── console/              # React + TypeScript + Vite web console
├── migrations/           # PostgreSQL migration files (001-009)
├── tests/                # pytest suite (365 tests)
├── config.yaml           # Default configuration
├── config.docker.yaml    # Docker overlay config
├── Dockerfile            # Multi-stage build (Node + Python)
└── docker-compose.yml    # PostgreSQL + Cortex orchestration
```

## Tech Stack / 技术栈

- **Runtime**: Python 3.11+, Node.js 22 (console build)
- **Database**: PostgreSQL 16 + pgvector + zhparser
- **Embeddings**: bge-small-zh-v1.5 (512 dimensions, local inference)
- **LLM**: MiniMax-M2.7 via OpenRouter (pluggable)
- **API**: FastAPI + uvicorn + asyncpg
- **Console**: React 19 + TypeScript + Vite + Tailwind CSS
- **Packaging**: uv + hatchling

## Development / 开发

```bash
# Install all dependencies
uv sync --extra dev --extra local-embeddings

# Run tests
python3 -m pytest tests/ -q

# Lint + format
ruff check src/ tests/
ruff format src/ tests/

# Build console
cd console && npm ci && npm run build
```

## License

MIT
