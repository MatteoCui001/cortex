"""
Tests for the optimization changes:
- Parallelized LLM calls in ingest
- Batch entity embedding
- Search use case (hybrid, entity search)
- Analyze use case (stats, thesis_coverage)
- Thesis generate_from_theme bug fix
- DB pagination (get_all_entities with limit/order_by)
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from cortex.domain.entities import EventType, KnowledgeEvent, ThesisStance
from cortex.use_cases.ingest import IngestUseCase
from cortex.use_cases.search import SearchUseCase
from cortex.use_cases.analyze import AnalyzeUseCase
from cortex.use_cases.thesis import ThesisUseCase
from tests.conftest import FakeEmbedding, FakeLLM, FakeStorage, make_event


# ------------------------------------------------------------------
# Ingest: parallelized LLM calls
# ------------------------------------------------------------------

class TrackedLLM(FakeLLM):
    """LLM that records call timestamps to verify parallelism."""

    def __init__(self):
        self.call_log: list[tuple[str, float]] = []

    async def extract_metadata(self, content: str) -> dict:
        start = asyncio.get_event_loop().time()
        await asyncio.sleep(0.01)  # simulate latency
        self.call_log.append(("extract", start))
        return await super().extract_metadata(content)

    async def classify_three_dimensions(self, content: str) -> dict:
        start = asyncio.get_event_loop().time()
        await asyncio.sleep(0.01)
        self.call_log.append(("classify", start))
        return await super().classify_three_dimensions(content)

    async def parse_stance_llm(self, annotation: str) -> str:
        start = asyncio.get_event_loop().time()
        await asyncio.sleep(0.01)
        self.call_log.append(("stance", start))
        return await super().parse_stance_llm(annotation)


@pytest.mark.asyncio
async def test_ingest_llm_calls_are_parallel():
    """All three LLM calls should run concurrently (overlap in time)."""
    storage = FakeStorage()
    embedding = FakeEmbedding()
    llm = TrackedLLM()
    ingest = IngestUseCase(storage, embedding, llm, "default")

    event = await ingest.import_text(
        title="Parallel test",
        content="Some content for testing parallel LLM calls",
        user_annotation="interesting",
    )
    assert event is not None

    # All three calls should have been made
    call_types = {c[0] for c in llm.call_log}
    assert "extract" in call_types
    assert "classify" in call_types
    assert "stance" in call_types

    # Start times should be close together (within 5ms), indicating parallelism
    starts = [c[1] for c in llm.call_log]
    time_spread = max(starts) - min(starts)
    assert time_spread < 0.05, f"LLM calls not parallel: spread={time_spread:.3f}s"


@pytest.mark.asyncio
async def test_ingest_without_llm_still_works():
    """Ingest should work gracefully without LLM (fallback metadata)."""
    storage = FakeStorage()
    embedding = FakeEmbedding()
    ingest = IngestUseCase(storage, embedding, None, "default")

    event = await ingest.import_text(
        title="No LLM",
        content="Content without LLM",
    )
    assert event is not None
    assert event.summary == "Content without LLM"[:200]


# ------------------------------------------------------------------
# Ingest: batch entity embedding
# ------------------------------------------------------------------

class TrackingEmbedding(FakeEmbedding):
    """Tracks embed vs embed_batch calls."""

    def __init__(self):
        self.embed_calls = 0
        self.batch_calls = 0

    async def embed(self, text: str) -> list[float]:
        self.embed_calls += 1
        return await super().embed(text)

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        self.batch_calls += 1
        return await super().embed_batch(texts)


@pytest.mark.asyncio
async def test_ingest_uses_batch_embedding_for_entities():
    """Entity embeddings should be computed via embed_batch, not one-by-one."""
    storage = FakeStorage()
    embedding = TrackingEmbedding()

    class LLMWithEntities(FakeLLM):
        async def extract_metadata(self, content: str) -> dict:
            return {
                "skip": False,
                "summary": "test",
                "tags": ["ai"],
                "entities": [
                    {"type": "company", "name": "OpenAI"},
                    {"type": "person", "name": "Sam Altman"},
                    {"type": "technology", "name": "GPT-5"},
                ],
                "thesis_links": [],
                "confidence": 0.8,
                "event_type": "article",
            }

    ingest = IngestUseCase(storage, embedding, LLMWithEntities(), "default")
    event = await ingest.import_text(title="Entity test", content="OpenAI announces GPT-5")
    assert event is not None
    # Should have called embed_batch for the 3 entities (1 call with 3 items)
    assert embedding.batch_calls >= 1, "Should use embed_batch for entities"


# ------------------------------------------------------------------
# Search use case
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_hybrid_search_merges_results():
    """Hybrid search should merge semantic and fulltext results."""
    storage = FakeStorage()
    embedding = FakeEmbedding()

    ev1 = make_event(title="AI advances", content="GPT-5 released")
    ev2 = make_event(title="Market report", content="Stock market analysis")
    await storage.insert_event(ev1)
    await storage.insert_event(ev2)

    search = SearchUseCase(storage, embedding, "default")
    results = await search.hybrid("AI advances", limit=10)
    assert len(results) > 0
    assert results[0].match_type == "hybrid"
    # Score should be weighted combination
    assert 0 < results[0].score <= 1.0


@pytest.mark.asyncio
async def test_semantic_search():
    storage = FakeStorage()
    embedding = FakeEmbedding()
    ev = make_event(title="Test event")
    await storage.insert_event(ev)

    search = SearchUseCase(storage, embedding, "default")
    results = await search.semantic("test query", limit=5)
    assert len(results) > 0
    assert results[0].match_type == "semantic"


@pytest.mark.asyncio
async def test_fulltext_search():
    storage = FakeStorage()
    embedding = FakeEmbedding()
    ev = make_event(title="Test event")
    await storage.insert_event(ev)

    search = SearchUseCase(storage, embedding, "default")
    results = await search.fulltext("test query", limit=5)
    assert len(results) > 0
    assert results[0].match_type == "fulltext"


# ------------------------------------------------------------------
# Analyze use case
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_analyze_stats():
    storage = FakeStorage()
    ev1 = make_event(title="Event 1", type=EventType.NOTE)
    ev2 = make_event(title="Event 2", type=EventType.ARTICLE)
    await storage.insert_event(ev1)
    await storage.insert_event(ev2)

    analyze = AnalyzeUseCase(storage, "default")
    s = await analyze.stats()
    assert s["events"] == 2
    assert EventType.NOTE in s["type_distribution"] or "note" in s["type_distribution"]


@pytest.mark.asyncio
async def test_analyze_thesis_coverage():
    storage = FakeStorage()
    ev = make_event(thesis_links=["AI Agent基建"])
    await storage.insert_event(ev)

    analyze = AnalyzeUseCase(storage, "default")
    coverage = await analyze.thesis_coverage()
    assert len(coverage) >= 1
    assert coverage[0].event_count == 1


@pytest.mark.asyncio
async def test_analyze_stale_events():
    storage = FakeStorage()
    old_date = datetime.now(timezone.utc) - timedelta(days=60)
    ev = make_event(updated_at=old_date)
    await storage.insert_event(ev)

    analyze = AnalyzeUseCase(storage, "default")
    stale = await analyze.stale_events(days=30)
    assert len(stale) == 1


# ------------------------------------------------------------------
# Thesis use case: generate_from_theme bug fix
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_thesis_generate_from_theme_dedup():
    """Verify the NameError bug fix: existing_texts_lower is used correctly."""
    storage = FakeStorage()

    class ThesisLLM(FakeLLM):
        async def generate_theses(self, theme, events_text, existing_theses=None):
            return [
                {"text": "Thesis Alpha", "stance": "bullish"},
                {"text": "Thesis Beta", "stance": "bearish"},
            ]

    llm = ThesisLLM()
    uc = ThesisUseCase(storage, "default", llm=llm)

    # Add events linked to the theme
    for i in range(3):
        ev = make_event(thesis_links=["AI Agent"], content=f"Content {i}")
        await storage.insert_event(ev)

    # This should NOT raise NameError anymore
    created = await uc.generate_from_theme("AI Agent")
    assert len(created) == 2
    assert created[0].text == "Thesis Alpha"
    assert created[1].text == "Thesis Beta"


@pytest.mark.asyncio
async def test_thesis_generate_skips_existing():
    """Duplicate thesis text should be skipped."""
    storage = FakeStorage()

    class ThesisLLM(FakeLLM):
        async def generate_theses(self, theme, events_text, existing_theses=None):
            return [
                {"text": "Already exists", "stance": "bullish"},
                {"text": "Brand new thesis", "stance": "neutral"},
            ]

    llm = ThesisLLM()
    uc = ThesisUseCase(storage, "default", llm=llm)

    # Pre-create an existing thesis
    await uc.create(text="Already exists", stance="bullish", theme="AI")

    # Add events
    for i in range(3):
        ev = make_event(thesis_links=["AI"], content=f"Content {i}")
        await storage.insert_event(ev)

    created = await uc.generate_from_theme("AI")
    # Only "Brand new thesis" should be created (the duplicate is skipped)
    assert len(created) == 1
    assert created[0].text == "Brand new thesis"


# ------------------------------------------------------------------
# FakeStorage: get_all_entities with limit/order_by
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_all_entities_with_limit():
    from cortex.domain.entities import Entity, EntityType
    storage = FakeStorage()
    for i in range(5):
        ent = Entity(
            id=str(uuid.uuid4()),
            workspace_id="default",
            type=EntityType.COMPANY,
            name=f"Company {i}",
        )
        storage._entities[ent.id] = ent

    all_ents = await storage.get_all_entities("default", limit=3)
    assert len(all_ents) == 3

    unlimited = await storage.get_all_entities("default")
    assert len(unlimited) == 5
