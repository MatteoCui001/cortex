"""Tests for domain entities and enums."""
import uuid
from datetime import datetime

import pytest

from cortex.domain.entities import (
    Annotation,
    ContradictionResult,
    Entity,
    EntityType,
    EventType,
    KnowledgeEvent,
    Notification,
    NotificationChannel,
    NotificationStatus,
    PushNotification,
    Relation,
    RelationType,
    SignalFeedback,
    VALID_TRANSITIONS,
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
    assert ann.created_at is not None


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


# ---------------------------------------------------------------------------
# Notification (Phase 4)
# ---------------------------------------------------------------------------

def test_notification_default_id_is_uuid():
    n = Notification(title="T", body="B", source_kind="signal")
    uuid.UUID(n.id)


def test_notification_dedup_key_defaults_from_source():
    n = Notification(title="T", body="B", source_kind="signal", source_id="abc")
    assert n.dedup_key == "signal:abc"


def test_notification_dedup_key_explicit_overrides_default():
    n = Notification(title="T", body="B", source_kind="signal", dedup_key="custom:key")
    assert n.dedup_key == "custom:key"


def test_notification_created_at_auto_set():
    n = Notification(title="T", body="B", source_kind="signal")
    assert isinstance(n.created_at, datetime)
    assert n.created_at.tzinfo is not None


def test_notification_default_status_pending():
    n = Notification(title="T", body="B", source_kind="signal")
    assert n.status == NotificationStatus.PENDING


def test_notification_default_channel_inbox():
    n = Notification(title="T", body="B", source_kind="signal")
    assert n.channel == NotificationChannel.INBOX


class TestNotificationStateMachine:

    def test_pending_to_delivered(self):
        n = Notification(title="T", body="B", source_kind="signal")
        n.transition(NotificationStatus.DELIVERED)
        assert n.status == NotificationStatus.DELIVERED

    def test_pending_to_acked(self):
        n = Notification(title="T", body="B", source_kind="signal")
        n.transition(NotificationStatus.ACKED)
        assert n.status == NotificationStatus.ACKED

    def test_pending_to_dismissed(self):
        n = Notification(title="T", body="B", source_kind="signal")
        n.transition(NotificationStatus.DISMISSED)
        assert n.status == NotificationStatus.DISMISSED

    def test_pending_to_failed(self):
        n = Notification(title="T", body="B", source_kind="signal")
        n.transition(NotificationStatus.FAILED)
        assert n.status == NotificationStatus.FAILED

    def test_delivered_to_read(self):
        n = Notification(title="T", body="B", source_kind="signal",
                         status=NotificationStatus.DELIVERED)
        n.transition(NotificationStatus.READ)
        assert n.status == NotificationStatus.READ

    def test_read_to_acked(self):
        n = Notification(title="T", body="B", source_kind="signal",
                         status=NotificationStatus.READ)
        n.transition(NotificationStatus.ACKED)
        assert n.status == NotificationStatus.ACKED

    def test_invalid_acked_to_pending_raises(self):
        n = Notification(title="T", body="B", source_kind="signal",
                         status=NotificationStatus.ACKED)
        with pytest.raises(ValueError, match="Cannot transition"):
            n.transition(NotificationStatus.PENDING)

    def test_invalid_dismissed_to_read_raises(self):
        n = Notification(title="T", body="B", source_kind="signal",
                         status=NotificationStatus.DISMISSED)
        with pytest.raises(ValueError, match="Cannot transition"):
            n.transition(NotificationStatus.READ)

    def test_invalid_failed_to_delivered_raises(self):
        n = Notification(title="T", body="B", source_kind="signal",
                         status=NotificationStatus.FAILED)
        with pytest.raises(ValueError, match="Cannot transition"):
            n.transition(NotificationStatus.DELIVERED)

    def test_all_terminal_states_have_no_transitions(self):
        for status in (NotificationStatus.ACKED, NotificationStatus.DISMISSED, NotificationStatus.FAILED):
            assert VALID_TRANSITIONS[status] == set()


# ---------------------------------------------------------------------------
# canonical_key unit tests
# ---------------------------------------------------------------------------

from cortex.domain.canonical import canonical_key


class TestCanonicalKey:

    def test_lowercase(self):
        assert canonical_key("OpenAI") == "openai"

    def test_strip_whitespace(self):
        assert canonical_key("  NVIDIA  ") == "nvidia"

    def test_hyphen_to_space(self):
        assert canonical_key("Open-AI") == "open ai"

    def test_underscore_to_space(self):
        assert canonical_key("open_ai") == "open ai"

    def test_corporate_suffix_inc(self):
        assert canonical_key("Tesla, Inc.") == "tesla"

    def test_corporate_suffix_ltd(self):
        assert canonical_key("Huawei Ltd") == "huawei"

    def test_corporate_suffix_corp(self):
        assert canonical_key("NVIDIA Corp.") == "nvidia"

    def test_fullwidth_chars(self):
        # Fullwidth O -> normal O
        assert canonical_key("\uff2f\uff50\uff45\uff4e\uff21\uff29") == "openai"

    def test_empty_string(self):
        assert canonical_key("") == ""

    def test_already_canonical(self):
        assert canonical_key("openai") == "openai"

    def test_multiple_spaces_collapsed(self):
        assert canonical_key("Sam   Altman") == "sam altman"
