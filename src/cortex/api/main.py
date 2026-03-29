"""
FastAPI application factory.
"""
from __future__ import annotations

import asyncio
import hmac
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from starlette.responses import JSONResponse


# ------------------------------------------------------------------
# Bearer token authentication middleware
# ------------------------------------------------------------------
# Set CORTEX_API_TOKEN to require authentication on all /api/v1 routes
# except /health and /ready.  When unset, auth is disabled (backwards compat).

_API_TOKEN = os.environ.get("CORTEX_API_TOKEN", "")

_PUBLIC_PATHS = frozenset({"/api/v1/health", "/api/v1/ready"})


class _BearerAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: StarletteRequest, call_next):
        if not _API_TOKEN:
            return await call_next(request)
        if request.url.path in _PUBLIC_PATHS:
            return await call_next(request)
        if not request.url.path.startswith("/api/"):
            return await call_next(request)
        auth = request.headers.get("authorization", "")
        if hmac.compare_digest(auth, f"Bearer {_API_TOKEN}"):
            return await call_next(request)
        return JSONResponse({"detail": "Unauthorized"}, status_code=401)

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
    app.state.analyze = AnalyzeUseCase(storage, workspace, llm=llm)

    # Start digest push scheduler if enabled
    digest_task = None
    digest_cfg = cfg.get("notifications", {}).get("digest_push", {})
    if digest_cfg.get("enabled"):
        digest_task = asyncio.create_task(
            _digest_scheduler(storage, app.state.analyze, workspace, digest_cfg)
        )

    yield

    if digest_task and not digest_task.done():
        digest_task.cancel()
        try:
            await digest_task
        except asyncio.CancelledError:
            pass
    await storage.close()


_logger = logging.getLogger(__name__)


def _parse_cron_hm(cron: str) -> tuple[int, int]:
    """Parse simple 'M H * * *' cron expression, return (hour, minute)."""
    parts = cron.strip().split()
    if len(parts) < 2:
        return 9, 0
    try:
        return int(parts[1]), int(parts[0])
    except ValueError:
        return 9, 0


async def _digest_scheduler(storage, analyze, workspace: str, cfg: dict):
    """Background loop: push daily digest at the configured cron time."""
    from datetime import datetime, timezone
    from cortex.use_cases.digest_push import push_digest

    hour, minute = _parse_cron_hm(cfg.get("cron", "0 9 * * *"))
    days = cfg.get("days", 1)
    _logger.info("Digest push scheduler started: %02d:%02d daily, %dd window", hour, minute, days)

    last_push_date = None
    while True:
        try:
            now = datetime.now(timezone.utc)
            # Simple daily check: push once per day at or after the target time
            today = now.date()
            if today != last_push_date and now.hour >= hour and (now.hour > hour or now.minute >= minute):
                notif = await push_digest(storage, analyze, workspace_id=workspace, days=days)
                if notif:
                    _logger.info("Digest pushed: %s", notif.title)
                else:
                    _logger.debug("Digest push skipped (empty or dedup)")
                last_push_date = today
        except asyncio.CancelledError:
            raise
        except Exception:
            _logger.warning("Digest push failed", exc_info=True)
        await asyncio.sleep(60)  # Check every minute


def create_app() -> FastAPI:
    cfg = load_config()
    app = FastAPI(
        title="Cortex",
        description="AI-native knowledge infrastructure for humans and agents.",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.config = cfg

    # Auth middleware (must be added before CORS so it runs after CORS preflight)
    app.add_middleware(_BearerAuthMiddleware)

    # CORS — configurable origins, defaults to Vite dev server
    from fastapi.middleware.cors import CORSMiddleware
    cors_origins = cfg.get("api", {}).get("cors_origins", [
        "http://localhost:5173", "http://127.0.0.1:5173",
    ])
    if cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
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
        from starlette.responses import RedirectResponse

        @app.get("/")
        async def root_redirect():
            return RedirectResponse("/console/overview")

        # Mount static assets first (more specific route takes priority)
        app.mount("/console/assets", StaticFiles(directory=str(console_dist / "assets")), name="console-assets")

        @app.get("/console/{path:path}")
        @app.get("/console")
        async def console_spa(path: str = ""):
            file = (console_dist / path).resolve()
            if not str(file).startswith(str(console_dist.resolve())):
                return FileResponse(console_dist / "index.html")
            if file.is_file():
                return FileResponse(file)
            return FileResponse(console_dist / "index.html")

    return app
