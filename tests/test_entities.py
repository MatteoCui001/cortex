"""Tests for domain entities and enums."""
import uuid
from datetime import datetime

from cortex.domain.entities import (
    Annotation,
    ContradictionResult,
    Entity,
    EntityType,
    EventType,
    KnowledgeEvent,
    PushNotification,
    Relation,
    RelationType,
    SignalFeedback,
)


# ---------------------------------------------------------------------------
# EventType enum
# ---------------------------------------------------------------------------

def test_event_type_values():
    assert EventType.ARTICLE == "article"
    assert EventType.MEETING == "meeting"
    assert EventType.NOTE == "note"
    assert EventType.THESIS == "thesis"
    assert EventType.CHAT == "chat"
    assert EventType.VOICE_MEMO == "voice_memo"
    assert EventType.IMAGE == "image"
    assert EventType.DOCUMENT == "document"
    assert EventType.VIDEO == "video"
    assert EventType.AGENT_ANALYSIS == "agent_analysis"


def test_event_type_is_str():
    # EventType inherits from str, so it can be used as a plain string
    assert isinstance(EventType.NOTE, str)


# ---------------------------------------------------------------------------
# KnowledgeEvent defaults
# ---------------------------------------------------------------------------

def test_knowledge_event_default_id_is_uuid():
    event = KnowledgeEvent()
    uuid.UUID(event.id)  # raises ValueError if not a valid UUID


def test_knowledge_event_unique_ids():
    e1 = KnowledgeEvent()
    e2 = KnowledgeEvent()
    assert e1.id != e2.id


def test_knowledge_event_default_workspace():
    event = KnowledgeEvent()
    assert event.workspace_id == "default"


def test_knowledge_event_default_type():
    event = KnowledgeEvent()
    assert event.type == EventType.NOTE


def test_knowledge_event_default_confidence():
    event = KnowledgeEvent()
    assert event.confidence == 0.5


def test_knowledge_event_default_tags_empty():
    event = KnowledgeEvent()
    assert event.tags == []


def test_knowledge_event_default_embedding_empty():
    event = KnowledgeEvent()
    assert event.embedding == []


def test_knowledge_event_default_optional_fields_none():
    event = KnowledgeEvent()
    assert event.raw_input_type is None
    assert event.raw_input_ref is None
    assert event.source_type is None
    assert event.source_weight is None
    assert event.temporality is None
    assert event.expires_at is None
    assert event.user_annotation is None
    assert event.user_stance is None


def test_knowledge_event_created_at_is_datetime():
    event = KnowledgeEvent()
    assert isinstance(event.created_at, datetime)


def test_knowledge_event_custom_fields():
    event = KnowledgeEvent(
        title="Test Title",
        content="Some content",
        type=EventType.ARTICLE,
        confidence=0.9,
        tags=["ai", "ml"],
    )
    assert event.title == "Test Title"
    assert event.content == "Some content"
    assert event.type == EventType.ARTICLE
    assert event.confidence == 0.9
    assert event.tags == ["ai", "ml"]


# ---------------------------------------------------------------------------
# Entity
# ---------------------------------------------------------------------------

def test_entity_default_id_is_uuid():
    entity = Entity()
    uuid.UUID(entity.id)


def test_entity_default_type():
    entity = Entity()
    assert entity.type == EntityType.CONCEPT


def test_entity_custom_name():
    entity = Entity(name="OpenAI", type=EntityType.COMPANY)
    assert entity.name == "OpenAI"
    assert entity.type == EntityType.COMPANY


def test_entity_aliases_default_empty():
    entity = Entity()
    assert entity.aliases == []


# ---------------------------------------------------------------------------
# Relation
# ---------------------------------------------------------------------------

def test_relation_default_id_is_uuid():
    rel = Relation()
    uuid.UUID(rel.id)


def test_relation_default_relation_type():
    rel = Relation()
    assert rel.relation == RelationType.RELATED_TO


def test_relation_default_confidence():
    rel = Relation()
    assert rel.confidence == 1.0


def test_relation_custom_fields():
    rel = Relation(
        source_type="event",
        source_id="abc",
        target_type="entity",
        target_id="xyz",
        relation=RelationType.SUPPORTS,
    )
    assert rel.source_type == "event"
    assert rel.source_id == "abc"
    assert rel.target_type == "entity"
    assert rel.target_id == "xyz"
    assert rel.relation == RelationType.SUPPORTS


# ---------------------------------------------------------------------------
# Annotation
# ---------------------------------------------------------------------------

def test_annotation_default_id_is_uuid():
    ann = Annotation()
    uuid.UUID(ann.id)


def test_annotation_defaults():
    ann = Annotation()
    assert ann.workspace_id == "default"
    assert ann.annotation is None
    assert ann.stance is None
    assert ann.created_at is None


def test_annotation_custom_stance():
    ann = Annotation(stance="agree", target_type="event", target_id="123")
    assert ann.stance == "agree"
    assert ann.target_type == "event"
    assert ann.target_id == "123"


# ---------------------------------------------------------------------------
# ContradictionResult
# ---------------------------------------------------------------------------

def test_contradiction_result_default_priority_score():
    cr = ContradictionResult(
        new_event_id="a", existing_event_id="b", signal_type="new_signal"
    )
    assert cr.priority_score == 0.0


def test_contradiction_result_evidence_event_ids_default_empty():
    cr = ContradictionResult(
        new_event_id="a", existing_event_id="b", signal_type="contradiction"
    )
    assert cr.evidence_event_ids == []


def test_contradiction_result_rationale_default_none():
    cr = ContradictionResult(
        new_event_id="a", existing_event_id="b", signal_type="answer"
    )
    assert cr.rationale is None


def test_contradiction_result_evidence_strength_default_none():
    cr = ContradictionResult(
        new_event_id="a", existing_event_id="b", signal_type="bridge"
    )
    assert cr.evidence_strength is None


def test_contradiction_result_custom_fields():
    cr = ContradictionResult(
        new_event_id="a",
        existing_event_id="b",
        signal_type="contradiction",
        priority_score=0.87,
        evidence_event_ids=["b", "c"],
        rationale="Directly conflicts with prior claim",
        evidence_strength="strong",
    )
    assert cr.priority_score == 0.87
    assert cr.evidence_event_ids == ["b", "c"]
    assert cr.rationale == "Directly conflicts with prior claim"
    assert cr.evidence_strength == "strong"


# ---------------------------------------------------------------------------
# PushNotification
# ---------------------------------------------------------------------------

def test_push_notification_created_at_is_timezone_aware():
    notif = PushNotification(
        trigger_type="thesis_stale", title="Test", body="Test body"
    )
    assert notif.created_at.tzinfo is not None


# ---------------------------------------------------------------------------
# ContradictionResult persistence fields (Phase 3.6)
# ---------------------------------------------------------------------------

def test_contradiction_result_has_stable_uuid_id():
    cr = ContradictionResult(
        new_event_id="a", existing_event_id="b", signal_type="contradiction"
    )
    uuid.UUID(cr.id)  # valid UUID


def test_contradiction_result_ids_are_unique():
    cr1 = ContradictionResult(new_event_id="a", existing_event_id="b", signal_type="contradiction")
    cr2 = ContradictionResult(new_event_id="a", existing_event_id="b", signal_type="contradiction")
    assert cr1.id != cr2.id


def test_contradiction_result_default_workspace_id():
    cr = ContradictionResult(new_event_id="a", existing_event_id="b", signal_type="answer")
    assert cr.workspace_id == "default"


def test_contradiction_result_thesis_links_default_empty():
    cr = ContradictionResult(new_event_id="a", existing_event_id="b", signal_type="bridge")
    assert cr.thesis_links == []


# ---------------------------------------------------------------------------
# SignalFeedback (Phase 3.6)
# ---------------------------------------------------------------------------

def test_signal_feedback_default_id_is_uuid():
    fb = SignalFeedback(signal_id="sig-1", verdict="useful")
    uuid.UUID(fb.id)


def test_signal_feedback_defaults():
    fb = SignalFeedback(signal_id="sig-1", verdict="wrong")
    assert fb.workspace_id == "default"
    assert fb.note is None
    assert fb.created_at is None
