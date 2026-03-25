"""
Cortex Domain Entities
Pure Python dataclasses - no framework dependencies.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class EventType(str, Enum):
    ARTICLE = "article"
    MEETING = "meeting"
    NOTE = "note"
    THESIS = "thesis"
    CHAT = "chat"
    VOICE_MEMO = "voice_memo"
    IMAGE = "image"
    DOCUMENT = "document"
    VIDEO = "video"
    AGENT_ANALYSIS = "agent_analysis"


class EntityType(str, Enum):
    COMPANY = "company"
    PERSON = "person"
    TECHNOLOGY = "technology"
    CONCEPT = "concept"
    FUND = "fund"


class RelationType(str, Enum):
    MENTIONS = "mentions"
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    RELATED_TO = "related_to"
    INVESTED_IN = "invested_in"
    FOUNDED_BY = "founded_by"


@dataclass
class KnowledgeEvent:
    """A piece of knowledge: article, meeting, note, thesis, or chat."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    workspace_id: str = "default"
    type: EventType = EventType.NOTE
    title: str = ""
    content: str = ""
    summary: str = ""
    tags: list[str] = field(default_factory=list)
    thesis_links: list[str] = field(default_factory=list)
    confidence: float = 0.5
    tier: int = 0
    source: str = ""
    source_path: str = ""
    embedding: list[float] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Phase 3: Raw input provenance
    raw_input_type: Optional[str] = None  # text|link|audio|image|file|video
    raw_input_ref: Optional[str] = None  # path or URL to original file

    # Phase 3: Enriched representations
    key_points: list[dict] = field(default_factory=list)
    # [{"text": "...", "type": "data|claim|prediction|question"}]
    stance: dict[str, str] = field(default_factory=dict)
    # {"topic": "bearish|bullish|neutral|cautious"}

    # Phase 3: Three-dimension classification
    source_type: Optional[str] = None  # first_hand|expert|curated|published|ambient
    source_weight: Optional[float] = None  # 0.0 - 1.0
    nature_tags: list[str] = field(default_factory=list)
    # claim|fact|method|question|intuition|synthesis
    temporality: Optional[str] = None  # permanent|trend|time_sensitive|prediction
    expires_at: Optional[datetime] = None

    # Phase 3: User reaction
    user_annotation: Optional[str] = None  # raw natural language
    user_stance: Optional[str] = None  # agree|disagree|uncertain|skip


@dataclass
class Entity:
    """An extracted entity: company, person, technology, etc."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    workspace_id: str = "default"
    type: EntityType = EntityType.CONCEPT
    name: str = ""
    aliases: list[str] = field(default_factory=list)
    properties: dict = field(default_factory=dict)
    embedding: list[float] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Relation:
    """A typed relation between any two objects (event or entity)."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    workspace_id: str = "default"
    source_type: str = ""
    source_id: str = ""
    target_type: str = ""
    target_id: str = ""
    relation: RelationType = RelationType.RELATED_TO
    confidence: float = 1.0
    metadata: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class Annotation:
    """A user annotation on an event, entity, or thesis."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    workspace_id: str = "default"
    target_type: str = ""  # event|entity|thesis
    target_id: str = ""
    annotation: Optional[str] = None
    stance: Optional[str] = None  # agree|disagree|uncertain|skip
    context: dict = field(default_factory=dict)
    created_at: Optional[datetime] = None


@dataclass
class SearchResult:
    """Wrapper for search results with score."""

    event: KnowledgeEvent
    score: float = 0.0
    match_type: str = ""


@dataclass
class ThesisCoverage:
    """Aggregated view of evidence for a thesis."""

    thesis_name: str
    event_count: int = 0
    type_distribution: dict[str, int] = field(default_factory=dict)
    avg_confidence: float = 0.0
    latest_update: Optional[datetime] = None
    days_since_update: int = 0


@dataclass
class ContradictionResult:
    """Result of comparing a new event against existing knowledge."""

    new_event_id: str
    existing_event_id: str
    signal_type: str  # new_signal|redundant|contradiction|answer|bridge
    topic: Optional[str] = None
    summary: Optional[str] = None
    confidence: float = 0.5


@dataclass
class PushNotification:
    """A proactive notification for the user."""

    trigger_type: str  # contradiction_detected|question_answered|thesis_stale|entity_momentum_spike
    title: str
    body: str
    related_event_ids: list[str] = field(default_factory=list)
    priority: str = "medium"  # high|medium|low
    workspace_id: str = "default"
    created_at: datetime = field(default_factory=datetime.now)
