"""Tests for ThesisUseCase — CRUD + evidence evaluation."""
from __future__ import annotations

import pytest

from cortex.domain.entities import (
    EvidenceImpact, KnowledgeEvent, EventType, ThesisStance, ThesisStatus,
)
from cortex.use_cases.thesis import ThesisUseCase


@pytest.fixture
def storage(fake_storage):
    return fake_storage


@pytest.fixture
def llm(fake_llm):
    return fake_llm


@pytest.fixture
def uc(storage, llm):
    return ThesisUseCase(storage, "default", llm=llm)


@pytest.fixture
def uc_no_llm(storage):
    return ThesisUseCase(storage, "default")


# --- CRUD ---

@pytest.mark.anyio
async def test_create_and_get(uc):
    t = await uc.create("Solar will dominate by 2030", stance="bullish", theme="solar")
    assert t.text == "Solar will dominate by 2030"
    assert t.stance == ThesisStance.BULLISH
    assert t.theme == "solar"
    assert t.confirmed is True
    assert t.confidence == 0.5  # no evidence yet

    fetched = await uc.get(t.id)
    assert fetched is not None
    assert fetched.text == t.text


@pytest.mark.anyio
async def test_create_inferred_unconfirmed(uc):
    t = await uc.create("AI will replace jobs", created_by="inferred")
    assert t.confirmed is False


@pytest.mark.anyio
async def test_list_filter_by_status(uc):
    t1 = await uc.create("Active thesis", stance="bullish")
    t2 = await uc.create("Another thesis", stance="bearish")
    await uc.resolve(t2.id)

    active = await uc.list(status="active")
    assert len(active) == 1
    assert active[0].id == t1.id

    resolved = await uc.list(status="resolved")
    assert len(resolved) == 1
    assert resolved[0].id == t2.id


@pytest.mark.anyio
async def test_list_filter_by_theme(uc):
    await uc.create("T1", theme="AI")
    await uc.create("T2", theme="solar")
    result = await uc.list(theme="AI")
    assert len(result) == 1
    assert result[0].theme == "AI"


@pytest.mark.anyio
async def test_update(uc):
    t = await uc.create("Original text")
    ok = await uc.update(t.id, text="Updated text", stance="bearish")
    assert ok
    fetched = await uc.get(t.id)
    assert fetched.text == "Updated text"
    assert fetched.stance == ThesisStance.BEARISH


@pytest.mark.anyio
async def test_resolve_and_invalidate(uc):
    t = await uc.create("Test thesis")
    await uc.resolve(t.id)
    fetched = await uc.get(t.id)
    assert fetched.status == ThesisStatus.RESOLVED

    t2 = await uc.create("Another thesis")
    await uc.invalidate(t2.id)
    fetched2 = await uc.get(t2.id)
    assert fetched2.status == ThesisStatus.INVALIDATED


@pytest.mark.anyio
async def test_confirm(uc):
    t = await uc.create("Inferred", created_by="inferred")
    assert t.confirmed is False
    await uc.confirm(t.id)
    fetched = await uc.get(t.id)
    assert fetched.confirmed is True


@pytest.mark.anyio
async def test_delete(uc):
    t = await uc.create("To delete")
    ok = await uc.delete(t.id)
    assert ok
    assert await uc.get(t.id) is None


@pytest.mark.anyio
async def test_delete_nonexistent(uc):
    ok = await uc.delete("nonexistent-id")
    assert not ok


# --- Evidence ---

@pytest.mark.anyio
async def test_evidence_shifts_confidence(storage, uc):
    from cortex.domain.entities import ThesisEvidence
    t = await uc.create("Solar thesis", stance="bullish")

    # Record supporting evidence
    ev = ThesisEvidence(
        thesis_id=t.id,
        event_id="evt-1",
        impact=EvidenceImpact.SUPPORTS,
        confidence_delta=0.8,
    )
    await storage.record_evidence(ev)
    fetched = await uc.get(t.id)
    assert fetched.confidence > 0.5  # should have moved up

    # Record contradicting evidence
    ev2 = ThesisEvidence(
        thesis_id=t.id,
        event_id="evt-2",
        impact=EvidenceImpact.CONTRADICTS,
        confidence_delta=0.8,
    )
    await storage.record_evidence(ev2)
    fetched2 = await uc.get(t.id)
    # supports +0.08, contradicts -0.08 → back to 0.5
    assert abs(fetched2.confidence - 0.5) < 0.01


@pytest.mark.anyio
async def test_get_evidence(storage, uc):
    from cortex.domain.entities import ThesisEvidence
    t = await uc.create("Test")
    ev = ThesisEvidence(
        thesis_id=t.id,
        event_id="evt-1",
        impact=EvidenceImpact.SUPPORTS,
        confidence_delta=0.5,
        rationale="Strong data point",
    )
    await storage.record_evidence(ev)
    result = await uc.get_evidence(t.id)
    assert len(result) == 1
    assert result[0].rationale == "Strong data point"


# --- evaluate_event ---

@pytest.mark.anyio
async def test_evaluate_event_no_llm(storage, uc_no_llm):
    """Without LLM, evaluate_event returns empty."""
    t = await uc_no_llm.create("Some thesis")
    event = KnowledgeEvent(content="test", thesis_links=["AI"])
    result = await uc_no_llm.evaluate_event(event)
    assert result == []


@pytest.mark.anyio
async def test_evaluate_event_no_theses(uc):
    """With no active theses, evaluate_event returns empty."""
    event = KnowledgeEvent(content="test")
    result = await uc.evaluate_event(event)
    assert result == []


@pytest.mark.anyio
async def test_evaluate_event_stub_neutral(uc):
    """FakeLLM returns neutral/0.0, so evaluate_event skips it."""
    await uc.create("AI thesis", theme="AI")
    event = KnowledgeEvent(content="Some AI content", thesis_links=["AI"])
    result = await uc.evaluate_event(event)
    # FakeLLM returns neutral + 0.0 delta → skipped
    assert len(result) == 0
