"""
FastAPI application factory.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

import yaml
from fastapi import FastAPI

from cortex.adapters.embeddings.local import LocalEmbedding
from cortex.adapters.filestore.store import FileStore
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

    # Initialize file store
    fs_root = cfg.get("file_store", {}).get("root")
    file_store = FileStore(root=fs_root) if fs_root else None

    # Initialize use cases
    app.state.storage = storage
    app.state.embedding = embedding
    app.state.llm = llm
    app.state.file_store = file_store
    app.state.workspace = workspace
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

    # CORS — allow local console dev server
    from fastapi.middleware.cors import CORSMiddleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router, prefix="/api/v1")

    # Serve console SPA if built static files exist
    import pathlib, os
    # Try multiple locations: CWD first (works with `uv run`), then relative to source
    _candidates = [
        pathlib.Path(os.getcwd()) / "console" / "dist",
        pathlib.Path(__file__).resolve().parent.parent.parent.parent / "console" / "dist",
    ]
    console_dist = next((p for p in _candidates if p.is_dir()), None)
    if console_dist:
        from fastapi.staticfiles import StaticFiles
        from fastapi.responses import FileResponse

        # Mount static assets first (more specific route takes priority)
        app.mount("/console/assets", StaticFiles(directory=str(console_dist / "assets")), name="console-assets")

        @app.get("/console/{path:path}")
        @app.get("/console")
        async def console_spa(path: str = ""):
            file = console_dist / path
            if file.is_file():
                return FileResponse(file)
            return FileResponse(console_dist / "index.html")

    return app
