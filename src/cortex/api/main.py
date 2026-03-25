"""
FastAPI application factory.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

import yaml
from fastapi import FastAPI

from cortex.adapters.embeddings.local import LocalEmbedding
from cortex.adapters.llm.adapter import OpenRouterLLM
from cortex.adapters.postgres.storage import PostgresStorage
from cortex.api.routes import router
from cortex.use_cases.analyze import AnalyzeUseCase
from cortex.use_cases.ingest import IngestUseCase
from cortex.use_cases.search import SearchUseCase


def load_config() -> dict:
    from cortex.cli.main import load_config as _load
    return _load()


@asynccontextmanager
async def lifespan(app: FastAPI):
    cfg = app.state.config
    storage_cfg = cfg.get("storage", {}).get("postgres", {})
    embedding_cfg = cfg.get("embedding", {}).get("local", {})
    llm_cfg = cfg.get("llm", {}).get("openrouter", {})
    workspace = cfg.get("workspace", "default")

    # Initialize adapters
    storage = PostgresStorage(storage_cfg.get("dsn", "postgresql://localhost:5432/cortex"))
    await storage.connect()

    embedding = LocalEmbedding(
        model_name=embedding_cfg.get("model", "all-MiniLM-L6-v2"),
        dims=embedding_cfg.get("dimensions", 384),
    )

    import os
    api_key = llm_cfg.get("api_key", "") or ""
    if api_key.startswith("${") and api_key.endswith("}"):
        api_key = os.environ.get(api_key[2:-1], "")

    llm = None
    if api_key:
        llm = OpenRouterLLM(
            api_key=api_key,
            model=llm_cfg.get("model", "anthropic/claude-haiku-4.5"),
            base_url=llm_cfg.get("base_url", "https://openrouter.ai/api/v1"),
            chat_endpoint=llm_cfg.get("chat_endpoint", "/chat/completions"),
            thesis_list=llm_cfg.get("thesis_list"),
        )

    # Initialize use cases
    app.state.storage = storage
    app.state.embedding = embedding
    app.state.file_store = None
    app.state.ingest = IngestUseCase(storage, embedding, llm, workspace)
    app.state.search = SearchUseCase(storage, embedding, workspace)
    app.state.analyze = AnalyzeUseCase(storage, workspace)

    yield

    await storage.close()


def create_app() -> FastAPI:
    cfg = load_config()
    app = FastAPI(
        title="Cortex",
        description="AI-native knowledge infrastructure for humans and agents.",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.config = cfg
    app.include_router(router, prefix="/api/v1")
    return app
