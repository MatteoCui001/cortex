"""
CLI entry point -- thin client over the use cases.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import yaml

# Lazy imports to avoid loading heavy dependencies on --help


def load_config() -> dict:
    base = {}
    path = Path("config.yaml")
    if path.exists():
        with open(path) as f:
            base = yaml.safe_load(f) or {}
    local_path = Path("config.local.yaml")
    if local_path.exists():
        with open(local_path) as f:
            local = yaml.safe_load(f) or {}
        _deep_merge(base, local)
    return base


def _deep_merge(base: dict, override: dict) -> dict:
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


async def _init_storage_only(cfg: dict):
    """Initialize storage + analyze only (no model loading)."""
    from cortex.adapters.postgres.storage import PostgresStorage
    from cortex.use_cases.analyze import AnalyzeUseCase

    storage_cfg = cfg.get("storage", {}).get("postgres", {})
    workspace = cfg.get("workspace", "default")
    storage = PostgresStorage(storage_cfg.get("dsn", "postgresql://localhost:5432/cortex"))
    await storage.connect()
    analyze = AnalyzeUseCase(storage, workspace)
    return storage, analyze


async def _init_services(cfg: dict):
    """Initialize all adapters and return (storage, embedding, ingest, search, analyze)."""
    import logging
    import warnings

    warnings.filterwarnings("ignore", message=".*unauthenticated.*")
    logging.getLogger("mlx").setLevel(logging.ERROR)

    from cortex.adapters.embeddings.local import LocalEmbedding
    from cortex.adapters.llm.adapter import OpenRouterLLM
    from cortex.adapters.postgres.storage import PostgresStorage
    from cortex.use_cases.analyze import AnalyzeUseCase
    from cortex.use_cases.ingest import IngestUseCase
    from cortex.use_cases.search import SearchUseCase

    storage_cfg = cfg.get("storage", {}).get("postgres", {})
    embedding_cfg = cfg.get("embedding", {}).get("local", {})
    llm_cfg = cfg.get("llm", {}).get("openrouter", {})
    workspace = cfg.get("workspace", "default")

    storage = PostgresStorage(storage_cfg.get("dsn", "postgresql://localhost:5432/cortex"))
    await storage.connect()

    embedding = LocalEmbedding(
        model_name=embedding_cfg.get("model", "all-MiniLM-L6-v2"),
        dims=embedding_cfg.get("dimensions", 384),
    )

    api_key = llm_cfg.get("api_key", "") or ""
    # Resolve env var references like ${OPENROUTER_API_KEY}
    import os

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

    ingest = IngestUseCase(storage, embedding, llm, workspace)
    search = SearchUseCase(storage, embedding, workspace)
    analyze = AnalyzeUseCase(storage, workspace)

    return storage, embedding, ingest, search, analyze


def main():
    if len(sys.argv) < 2:
        _print_help()
        return

    command = sys.argv[1]

    if command == "serve":
        _cmd_serve()
    elif command == "import":
        asyncio.run(_cmd_import())
    elif command == "sync":
        asyncio.run(_cmd_sync())
    elif command == "search":
        asyncio.run(_cmd_search())
    elif command == "thesis":
        asyncio.run(_cmd_thesis())
    elif command == "stats":
        asyncio.run(_cmd_stats())
    elif command == "stale":
        asyncio.run(_cmd_stale())
    elif command == "maintain":
        asyncio.run(_cmd_maintain())
    elif command == "digest":
        asyncio.run(_cmd_digest())
    elif command == "import-link":
        asyncio.run(_cmd_import_link())
    elif command == "import-file":
        asyncio.run(_cmd_import_file())
    elif command == "annotate":
        asyncio.run(_cmd_annotate())
    elif command == "notifications":
        asyncio.run(_cmd_notifications())
    elif command in ("--help", "-h", "help"):
        _print_help()
    else:
        print(f"Unknown command: {command}")
        _print_help()
        sys.exit(1)


def _print_help():
    print("""Cortex - AI-native knowledge infrastructure

Usage: cortex <command> [options]

Commands:
  serve             Start the API server
  import --vault    Import Obsidian vault (full)
  sync --vault      Incremental sync (new/changed files only)
  search <query>    Search knowledge base
  thesis [name]     Thesis coverage report
  stats             Show workspace statistics
  stale [--days N]  Find stale judgments
  maintain <sub>    Data maintenance (embeddings|tags|dedupe|classification|all)
  digest [--days N] Daily research digest
  import-link <url> Import a web article (--annotation TEXT)
  import-file <path> Import a PDF/DOCX/TXT file (--annotation TEXT)
  annotate <id>     Add user annotation to an event
  notifications     Show proactive push notifications

Options:
  --force           Re-import all files (skip_existing=False)

Examples:
  cortex serve
  cortex import --vault ~/Notes
  cortex sync --vault ~/Notes
  cortex search "AI Agent infrastructure"
  cortex thesis
  cortex maintain all
  cortex digest --days 7""")


def _cmd_serve():
    import uvicorn

    cfg = load_config()
    api_cfg = cfg.get("api", {})
    host = api_cfg.get("host", "127.0.0.1")
    port = api_cfg.get("port", 8420)
    print(f"Starting Cortex API on {host}:{port}")
    print(f"OpenAPI docs: http://{host}:{port}/docs")
    uvicorn.run(
        "cortex.api.main:create_app",
        host=host,
        port=port,
        factory=True,
        reload=False,
    )


async def _cmd_import():
    vault_path = None
    force = "--force" in sys.argv
    for i, arg in enumerate(sys.argv):
        if arg == "--vault" and i + 1 < len(sys.argv):
            vault_path = sys.argv[i + 1]
    if not vault_path:
        print("Usage: cortex import --vault <path> [--force]")
        sys.exit(1)

    vault_path = str(Path(vault_path).expanduser().resolve())
    cfg = load_config()

    def on_progress(current, total, path, status):
        print(f"  [{current}/{total}] {status}: {path}")

    storage, _, ingest, _, _ = await _init_services(cfg)
    try:
        if force:
            print(f"Force re-importing from: {vault_path}")
        else:
            print(f"Importing from: {vault_path}")
        result = await ingest.import_vault(
            vault_path,
            skip_existing=not force,
            on_progress=on_progress,
        )
        print(
            f"\nDone: {result['imported']} imported, {result['skipped']} skipped,"
            f" {result['errors']} errors (of {result['total']} files)"
        )
    finally:
        await storage.close()


async def _cmd_sync():
    vault_path = None
    for i, arg in enumerate(sys.argv):
        if arg == "--vault" and i + 1 < len(sys.argv):
            vault_path = sys.argv[i + 1]
    if not vault_path:
        print("Usage: cortex sync --vault <path>")
        sys.exit(1)

    vault_path = str(Path(vault_path).expanduser().resolve())
    cfg = load_config()

    def on_progress(current, total, path, status):
        print(f"  [{current}/{total}] {status}: {path}")

    storage, _, ingest, _, _ = await _init_services(cfg)
    try:
        result = await ingest.sync_vault(vault_path, on_progress=on_progress)
        print(
            f"\nSync done: {result['imported']} new, {result['updated']} updated, "
            f"{result['unchanged']} unchanged, {result['errors']} errors"
        )
    finally:
        await storage.close()


async def _cmd_search():
    if len(sys.argv) < 3:
        print("Usage: cortex search <query>")
        sys.exit(1)

    query = " ".join(sys.argv[2:])
    cfg = load_config()
    storage, _, _, search, _ = await _init_services(cfg)
    try:
        results = await search.hybrid(query)
        if not results:
            print("No results found.")
            return
        for i, r in enumerate(results, 1):
            e = r.event
            print(f"\n{'=' * 60}")
            print(f"  [{i}] {e.title} ({r.match_type}, score={r.score:.3f})")
            print(f"      Type: {e.type.value}  |  Tags: {', '.join(e.tags) or '-'}")
            print(f"      Thesis: {', '.join(e.thesis_links) or '-'}")
            if e.summary:
                print(f"      {e.summary[:120]}...")
    finally:
        await storage.close()


async def _cmd_thesis():
    thesis_name = sys.argv[2] if len(sys.argv) > 2 else None
    cfg = load_config()
    storage, analyze = await _init_storage_only(cfg)
    try:
        if thesis_name:
            events = await analyze.thesis_evidence(thesis_name)
            print(f"\nEvidence for thesis: {thesis_name}")
            print(f"Found {len(events)} events\n")
            for e in events:
                print(f"  - [{e.type.value}] {e.title} (confidence={e.confidence:.2f})")
        else:
            coverage = await analyze.thesis_coverage()
            if not coverage:
                print("No thesis links found.")
                return
            print(f"\n{'Thesis':<40} {'Events':>6} {'Avg Conf':>9} {'Days Stale':>11}")
            print("-" * 70)
            for t in coverage:
                print(
                    f"  {t.thesis_name:<38} {t.event_count:>6}"
                    f" {t.avg_confidence:>8.2f} {t.days_since_update:>10}"
                )
    finally:
        await storage.close()


async def _cmd_stats():
    cfg = load_config()
    storage, analyze = await _init_storage_only(cfg)
    try:
        s = await analyze.stats()
        print("\nCortex Workspace Statistics")
        print(f"{'=' * 40}")
        print(f"  Events:    {s['events']}")
        print(f"  Entities:  {s['entities']}")
        print(f"  Relations: {s['relations']}")
        if s.get("events_by_type"):
            print("\n  Events by type:")
            for t, c in s["events_by_type"].items():
                print(f"    {t}: {c}")
    finally:
        await storage.close()


async def _cmd_stale():
    days = 30
    for i, arg in enumerate(sys.argv):
        if arg == "--days" and i + 1 < len(sys.argv):
            days = int(sys.argv[i + 1])

    cfg = load_config()
    storage, analyze = await _init_storage_only(cfg)
    try:
        events = await analyze.stale_events(days)
        print(f"\nEvents not updated in {days}+ days: {len(events)}\n")
        for e in events:
            age = e.updated_at.strftime("%Y-%m-%d") if e.updated_at else "?"
            print(f"  - [{e.type.value}] {e.title} (last updated: {age})")
    finally:
        await storage.close()


async def _cmd_maintain():
    sub = sys.argv[2] if len(sys.argv) > 2 else "all"
    if sub not in ("embeddings", "tags", "dedupe", "classification", "all"):
        print("Usage: cortex maintain <embeddings|tags|dedupe|classification|all>")
        sys.exit(1)

    cfg = load_config()
    from cortex.use_cases.maintenance import MaintenanceUseCase

    storage, embedding, _, _, _ = await _init_services(cfg)
    workspace = cfg.get("workspace", "default")
    tag_config = cfg.get("tag_normalization", {})
    maint = MaintenanceUseCase(storage, embedding, workspace, tag_config)

    # LLM for classification backfill
    llm_adapter = None
    llm_cfg = cfg.get("llm", {}).get("openrouter", {})
    import os

    api_key = llm_cfg.get("api_key", "") or ""
    if api_key.startswith("${") and api_key.endswith("}"):
        api_key = os.environ.get(api_key[2:-1], "")
    if api_key:
        from cortex.adapters.llm.adapter import OpenRouterLLM

        llm_adapter = OpenRouterLLM(
            api_key=api_key,
            model=llm_cfg.get("model", "anthropic/claude-haiku-4.5"),
            base_url=llm_cfg.get("base_url", "https://openrouter.ai/api/v1"),
            chat_endpoint=llm_cfg.get("chat_endpoint", "/chat/completions"),
        )

    try:
        if sub in ("embeddings", "all"):
            print("\n--- Backfilling entity embeddings ---")

            def emb_progress(done, total):
                print(f"  [{done}/{total}] entities embedded")

            result = await maint.backfill_entity_embeddings(on_progress=emb_progress)
            print(f"  Done: {result['processed']}/{result['total']} entities embedded")

        if sub in ("tags", "all"):
            print("\n--- Normalizing tags ---")
            result = await maint.normalize_tags()
            print(
                f"  Done: {result['events_updated']}/{result['events_checked']} events updated,"
                f"        {result['tags_changed']} tags changed"
            )

        if sub in ("classification", "all"):
            print("\n--- Classifying events (3 dimensions) ---")
            if not llm_adapter:
                print("  Skipped: no LLM API key configured.")
            else:
                events = await storage.get_events_without_classification(workspace, limit=50)
                if not events:
                    print("  All events already classified.")
                else:
                    from cortex.domain.constants import SOURCE_WEIGHTS

                    classified = 0
                    for i, evt in enumerate(events):
                        try:
                            cls = await llm_adapter.classify_three_dimensions(evt.content)
                            source_type = cls.get("source_type", "published")
                            await storage.update_event_classification(
                                evt.id,
                                source_type=source_type,
                                source_weight=SOURCE_WEIGHTS.get(source_type, 0.5),
                                nature_tags=cls.get("nature_tags", []),
                                temporality=cls.get("temporality", "trend"),
                                key_points=cls.get("key_points", []),
                                stance=cls.get("stance", {}),
                            )
                            classified += 1
                            if (i + 1) % 10 == 0:
                                print(f"  [{i + 1}/{len(events)}] classified")
                        except Exception as e:
                            print(f"  Error classifying {evt.title[:40]}: {e}")
                    print(f"  Done: {classified}/{len(events)} events classified")

        if sub in ("dedupe", "all"):
            print("\n--- Deduplicating entities ---")

            def dedupe_progress(done, total):
                print(f"  [{done}/{total}] entities merged")

            result = await maint.deduplicate_entities(on_progress=dedupe_progress)
            print(
                f"  Done: {result['merged']} merged"
                f"        ({result['entities_before']} -> {result['entities_after']})"
            )

        print("\nMaintenance complete.")
    finally:
        await storage.close()


async def _cmd_digest():
    days = 1
    for i, arg in enumerate(sys.argv):
        if arg == "--days" and i + 1 < len(sys.argv):
            days = int(sys.argv[i + 1])

    cfg = load_config()
    storage, analyze = await _init_storage_only(cfg)
    try:
        digest = await analyze.daily_digest(days)

        print(f"\n{'=' * 60}")
        print(f"  Cortex Daily Digest ({days} day{'s' if days > 1 else ''})")
        print(f"{'=' * 60}")

        # Thesis activity
        if digest.get("thesis_activity"):
            print("\n## Thesis Activity")
            for thesis, types in digest["thesis_activity"].items():
                total = sum(types.values())
                breakdown = ", ".join(f"{t}:{c}" for t, c in types.items())
                print(f"  {thesis}: {total} events ({breakdown})")

        # High confidence insights
        if digest.get("high_confidence"):
            print("\n## High Confidence Insights")
            for e in digest["high_confidence"]:
                print(f"  [{e.confidence:.2f}] {e.title}")
                if e.summary:
                    print(f"         {e.summary[:100]}...")

        # Stale theses
        if digest.get("stale_theses"):
            print("\n## Stale Theses (30+ days without new evidence)")
            for t in digest["stale_theses"]:
                print(
                    f"  {t.thesis_name}: {t.days_since_update} days stale ({t.event_count} events)"
                )

        # Entity momentum
        if digest.get("entity_momentum"):
            print("\n## Entity Momentum (most mentioned this week)")
            for ent in digest["entity_momentum"]:
                print(f"  {ent['name']} ({ent['type']}): {ent['mentions']} mentions")

        print(f"\n{'=' * 60}")
    finally:
        await storage.close()


async def _cmd_import_link():
    if len(sys.argv) < 3:
        print("Usage: cortex import-link <url> [--annotation TEXT]")
        sys.exit(1)

    url = sys.argv[2]
    annotation = None
    for i, arg in enumerate(sys.argv):
        if arg == "--annotation" and i + 1 < len(sys.argv):
            annotation = sys.argv[i + 1]

    cfg = load_config()
    storage, embedding, ingest, _, _ = await _init_services(cfg)

    try:
        from cortex.adapters.filestore.store import FileStore
        from cortex.use_cases.ingest_link import IngestLinkUseCase

        file_store = None
        fs_cfg = cfg.get("file_store", {})
        if fs_cfg.get("root"):
            file_store = FileStore(fs_cfg["root"])

        link_ingest = IngestLinkUseCase(
            storage,
            embedding,
            ingest._llm,
            file_store,
            cfg.get("workspace", "default"),
        )

        print(f"Fetching: {url}")
        event = await link_ingest.import_link(url, user_annotation=annotation)
        if event:
            print(f"Imported: {event.title}")
            print(f"  Type: {event.type.value}  |  Tags: {', '.join(event.tags)}")
            if event.source_type:
                print(f"  Source: {event.source_type} (weight={event.source_weight:.2f})")
            if event.nature_tags:
                print(f"  Nature: {', '.join(event.nature_tags)}")
            if event.temporality:
                print(f"  Temporality: {event.temporality}")
            if event.user_stance:
                print(f"  Your stance: {event.user_stance}")
            if event.key_points:
                print(f"  Key points: {len(event.key_points)}")
            # Run contradiction detection
            await _analyze_contradictions(ingest, event, storage)
        else:
            print("Could not extract content from URL.")
    finally:
        await storage.close()


async def _analyze_contradictions(ingest, event, storage):
    """Run contradiction detection and print results."""
    signals = await ingest.post_ingest_analyze(event)
    if signals:
        print(f"  Signals detected: {len(signals)}")
        for s in signals:
            print(f"    - [{s.signal_type}] {s.topic}: {s.summary}")
    return signals


async def _cmd_import_file():
    if len(sys.argv) < 3:
        print("Usage: cortex import-file <path> [--annotation TEXT]")
        sys.exit(1)

    file_path = sys.argv[2]
    annotation = None
    for i, arg in enumerate(sys.argv):
        if arg == "--annotation" and i + 1 < len(sys.argv):
            annotation = sys.argv[i + 1]

    cfg = load_config()
    storage, embedding, ingest, _, _ = await _init_services(cfg)

    try:
        from cortex.adapters.filestore.store import FileStore
        from cortex.use_cases.ingest_file import IngestFileUseCase

        file_store = None
        fs_cfg = cfg.get("file_store", {})
        if fs_cfg.get("root"):
            file_store = FileStore(fs_cfg["root"])

        file_ingest = IngestFileUseCase(
            storage,
            embedding,
            ingest._llm,
            file_store,
            cfg.get("workspace", "default"),
        )

        print(f"Importing: {file_path}")
        event = await file_ingest.import_file(file_path, user_annotation=annotation)
        if event:
            print(f"Imported: {event.title}")
            print(f"  Type: {event.type.value}  |  Tags: {', '.join(event.tags)}")
            if event.source_type:
                print(f"  Source: {event.source_type} (weight={event.source_weight:.2f})")
            if event.nature_tags:
                print(f"  Nature: {', '.join(event.nature_tags)}")
            if event.temporality:
                print(f"  Temporality: {event.temporality}")
            if event.user_stance:
                print(f"  Your stance: {event.user_stance}")
            if event.key_points:
                print(f"  Key points: {len(event.key_points)}")
            await _analyze_contradictions(ingest, event, storage)
        else:
            print("Could not extract content from file.")
    finally:
        await storage.close()


async def _cmd_annotate():
    if len(sys.argv) < 4:
        print("Usage: cortex annotate <event-id> <text>")
        sys.exit(1)

    event_id = sys.argv[2]
    text = " ".join(sys.argv[3:])

    cfg = load_config()
    storage, analyze = await _init_storage_only(cfg)
    workspace = cfg.get("workspace", "default")

    try:
        import uuid

        from cortex.domain.entities import Annotation
        from cortex.domain.stance import parse_user_stance

        stance = parse_user_stance(text)
        annotation = Annotation(
            id=str(uuid.uuid4()),
            workspace_id=workspace,
            target_type="event",
            target_id=event_id,
            annotation=text,
            stance=stance,
        )
        aid = await storage.create_annotation(annotation)
        print(f"Annotation added (id={aid[:8]}...)")
        if stance:
            print(f"  Detected stance: {stance}")
        else:
            print("  No stance detected (use agree/disagree/uncertain)")
    finally:
        await storage.close()


async def _cmd_notifications():
    cfg = load_config()
    storage, analyze = await _init_storage_only(cfg)
    workspace = cfg.get("workspace", "default")

    try:
        from cortex.use_cases.push_detector import PushDetector

        detector = PushDetector(storage, workspace)
        notifications = await detector.check_all()

        if not notifications:
            print("No notifications.")
            return

        print(f"\n{'=' * 60}")
        print(f"  Cortex Notifications ({len(notifications)})")
        print(f"{'=' * 60}")

        for n in notifications:
            priority_marker = {"high": "!!!", "medium": " ! ", "low": "   "}.get(n.priority, "   ")
            print(f"\n  [{priority_marker}] {n.title}")
            print(f"        {n.body}")

        print(f"\n{'=' * 60}")
    finally:
        await storage.close()


if __name__ == "__main__":
    main()
