# Cortex

> AI-native knowledge infrastructure for humans and agents.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-3776ab.svg)](https://www.python.org)
[![Docker](https://img.shields.io/badge/docker-compose-2496ed.svg)](docker-compose.yml)

Public `v1.0.0` release.

English | [中文说明](README_CN.md)

Cortex is a personal knowledge engine for high-information-density work.
It ingests notes, web pages, PDFs, WeChat messages, and meeting transcripts into a unified knowledge graph with semantic search, entity extraction, thesis tracking, signal detection, and proactive notifications.

It is not a note-taking app and not a generic "second brain."
It is closer to a cognitive backend for people whose job depends on judgment.

## What This Repo Contains

This is the main Cortex repository:

- Python backend API and CLI
- PostgreSQL + pgvector storage adapter
- local embedding + LLM integration
- React console for search, inbox, graph, and thesis views

For WeChat and agent integrations, see the sibling repo:
[`cortex-wechat`](https://github.com/MatteoCui001/cortex-wechat)

Recommended full setup:

```text
~/Projects/
├── cortex/
└── cortex-wechat/
```

## Who It Is For

- VCs and buy-side researchers
- founders and product leads
- analysts and operators working across fragmented inputs
- anyone tracking theses, evidence, and changing judgments over time

## Core Capabilities

- Multi-source ingestion: Obsidian, URLs, PDF/DOCX/TXT, WeChat, raw text
- Hybrid search: semantic + Chinese full-text search
- Entity extraction and alias resolution
- Knowledge graph: events, entities, relations, theses
- Thesis tracking: evidence, coverage, confidence shifts
- Signal detection: contradiction, answer, bridge, momentum
- Proactive notifications: stale theses, important signals, digest
- Web console: overview, inbox, signals, graph, search, events

## Quick Start

### Option A: macOS installer

```bash
git clone https://github.com/MatteoCui001/cortex.git
cd cortex
./install.sh
source ~/.cortex/env && uv run cortex serve
```

Open:

- Console: `http://localhost:8420/console/`
- API docs: `http://localhost:8420/docs`

### Option B: Docker

```bash
git clone https://github.com/MatteoCui001/cortex.git ~/Projects/cortex
git clone https://github.com/MatteoCui001/cortex-wechat.git ~/Projects/cortex-wechat
cd ~/Projects/cortex

export LLM_API_KEY=your-key-here
docker compose up -d db cortex
```

### Option C: manual setup

Prerequisites: Python 3.11+, PostgreSQL 16+ with pgvector, `uv`

```bash
uv sync --extra local-embeddings
createdb cortex
for f in migrations/0*.sql; do psql -d cortex -f "$f"; done
uv run cortex serve
```

## Main Interfaces

### CLI

```bash
cortex serve
cortex import --vault ~/Notes
cortex import-link https://example.com
cortex import-file ~/report.pdf
cortex search "AI agent infrastructure"
cortex thesis
cortex digest
cortex notifications
```

### API

The API serves on port `8420` with OpenAPI docs at `/docs`.

```bash
GET  /api/v1/health
POST /api/v1/events/ingest
POST /api/v1/search
GET  /api/v1/thesis
GET  /api/v1/signals
GET  /api/v1/notifications
```

All API endpoints except `/health` and `/ready` require a Bearer token when `CORTEX_API_TOKEN` is set.

## Repo Guide

- Main backend + console: [`cortex`](https://github.com/MatteoCui001/cortex)
- WeChat / agent bridge: [`cortex-wechat`](https://github.com/MatteoCui001/cortex-wechat)
- Public release notes / deployment notes: [`BETA.md`](BETA.md)
- Release smoke test: [`docs/release-smoke.md`](docs/release-smoke.md)

## License

MIT
