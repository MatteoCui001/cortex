"""
Cortex Domain Ports (Interfaces)
Abstract base classes that define contracts for adapters.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import Optional

from cortex.domain.entities import (
    ContradictionResult, KnowledgeEvent, Entity, Notification,
    NotificationStatus, Relation, SearchResult, SignalFeedback,
    ThesisCoverage,
)


class StoragePort(ABC):
    """Port for knowledge storage backend (PostgreSQL, SQLite, etc.)."""

    @abstractmethod
    async def insert_event(self, event: KnowledgeEvent) -> str:
        """Insert or upsert an event. Returns event id."""

    @abstractmethod
    async def insert_entity(self, entity: Entity) -> str:
        """Insert or upsert an entity. Returns entity id."""

    @abstractmethod
    async def insert_relation(self, relation: Relation) -> str:
        """Insert a relation. Returns relation id."""

    @abstractmethod
    async def get_event(self, event_id: str, workspace_id: str = "default") -> Optional[KnowledgeEvent]:
        """Get a single event by id."""

    @abstractmethod
    async def semantic_search(
        self,
        embedding: list[float],
        *,
        workspace_id: str = "default",
        limit: int = 10,
        type_filter: Optional[str] = None,
        min_score: float = 0.0,
    ) -> list[SearchResult]:
        """Vector similarity search."""

    @abstractmethod
    async def fulltext_search(
        self,
        query: str,
        *,
        workspace_id: str = "default",
        limit: int = 10,
        type_filter: Optional[str] = None,
    ) -> list[SearchResult]:
        """Full-text search (BM25 / tsvector)."""

    @abstractmethod
    async def get_by_thesis(
        self,
        thesis_name: str,
        workspace_id: str = "default",
    ) -> list[KnowledgeEvent]:
        """Get all events linked to a thesis."""

    @abstractmethod
    async def get_relations_for(
        self,
        object_id: str,
        workspace_id: str = "default",
    ) -> list[dict]:
        """Get all relations involving an event or entity."""

    @abstractmethod
    async def find_related(
        self,
        event_id: str,
        *,
        workspace_id: str = "default",
        limit: int = 10,
    ) -> list[SearchResult]:
        """Find events related to a given event via shared entities."""

    @abstractmethod
    async def stale_events(
        self,
        days: int = 30,
        workspace_id: str = "default",
    ) -> list[KnowledgeEvent]:
        """Find events not updated in N days (judgment decay)."""

    @abstractmethod
    async def thesis_coverage(
        self,
        workspace_id: str = "default",
    ) -> list[ThesisCoverage]:
        """Aggregate thesis coverage analysis."""

    @abstractmethod
    async def daily_events(
        self,
        target_date: date,
        workspace_id: str = "default",
    ) -> list[KnowledgeEvent]:
        """Get all events for a specific date."""

    @abstractmethod
    async def stats(self, workspace_id: str = "default") -> dict:
        """Return count statistics."""

    @abstractmethod
    async def event_exists(self, source_path: str, workspace_id: str = "default") -> bool:
        """Check if an event with this source_path already exists (dedup)."""

    # ------------------------------------------------------------------
    # Maintenance operations
    # ------------------------------------------------------------------

    @abstractmethod
    async def count_entities_without_embedding(self, workspace_id: str = "default") -> int:
        """Count entities missing embeddings."""

    @abstractmethod
    async def get_entities_without_embedding(self, workspace_id: str = "default", limit: int = 50) -> list[dict]:
        """Get entities missing embeddings."""

    @abstractmethod
    async def update_entity_embedding(self, entity_id: str, embedding: list[float]):
        """Update a single entity's embedding."""

    @abstractmethod
    async def get_all_events_with_tags(self, workspace_id: str = "default") -> list[dict]:
        """Get all events with their tags for normalization."""

    @abstractmethod
    async def update_event_tags(self, event_id: str, tags: list[str]):
        """Update an event's tags."""

    @abstractmethod
    async def get_all_entities(self, workspace_id: str = "default") -> list[dict]:
        """Get all entities with mention counts for deduplication."""

    @abstractmethod
    async def merge_entities(self, keep_id: str, remove_id: str):
        """Merge remove_id entity into keep_id, reparent relations."""

    # ------------------------------------------------------------------
    # Entity search operations
    # ------------------------------------------------------------------

    @abstractmethod
    async def semantic_search_entities(
        self,
        embedding: list[float],
        *,
        workspace_id: str = "default",
        entity_types: Optional[list[str]] = None,
        limit: int = 20,
    ) -> list[dict]:
        """Semantic search over entities."""

    @abstractmethod
    async def get_events_for_entity(
        self,
        entity_id: str,
        workspace_id: str = "default",
        limit: int = 50,
    ) -> list[KnowledgeEvent]:
        """Get all events mentioning a specific entity."""

    # ------------------------------------------------------------------
    # Digest operations
    # ------------------------------------------------------------------

    @abstractmethod
    async def recent_events_by_thesis(self, days: int = 1, workspace_id: str = "default") -> list[dict]:
        """Get recent events grouped by thesis and type."""

    @abstractmethod
    async def high_confidence_recent(
        self, days: int = 7, min_confidence: float = 0.8,
        workspace_id: str = "default", limit: int = 10,
    ) -> list[KnowledgeEvent]:
        """Get high-confidence recent events."""

    @abstractmethod
    async def entity_momentum(self, days: int = 7, workspace_id: str = "default", limit: int = 10) -> list[dict]:
        """Get most-mentioned entities in recent period."""

    @abstractmethod
    async def get_existing_source_paths(self, workspace_id: str = "default") -> dict[str, str]:
        """Return {source_path: updated_at_iso} for incremental sync."""


    # ------------------------------------------------------------------
    # Phase 3: Annotation operations
    # ------------------------------------------------------------------

    @abstractmethod
    async def create_annotation(self, annotation) -> str:
        """Create an annotation. Returns annotation id."""

    @abstractmethod
    async def get_annotations(
        self,
        workspace_id: str,
        target_type: str,
        target_id: str,
    ) -> list:
        """Get all annotations for a target."""

    # ------------------------------------------------------------------
    # Phase 3: Classification queries
    # ------------------------------------------------------------------

    @abstractmethod
    async def get_events_without_classification(
        self,
        workspace_id: str = "default",
        limit: int = 50,
    ) -> list[KnowledgeEvent]:
        """Get events missing source_type (for backfill)."""

    @abstractmethod
    async def update_event_classification(
        self,
        event_id: str,
        source_type: str,
        source_weight: float,
        nature_tags: list[str],
        temporality: str,
        key_points: list[dict],
        stance: dict,
    ):
        """Update Phase 3 classification fields on an event."""

    # ------------------------------------------------------------------
    # Phase 3.6: Signal operations
    # ------------------------------------------------------------------

    @abstractmethod
    async def upsert_signal(self, signal: ContradictionResult) -> str:
        """Persist a signal. Returns signal id."""

    @abstractmethod
    async def get_signals(
        self,
        workspace_id: str,
        *,
        event_id: Optional[str] = None,
        limit: int = 50,
    ) -> list[ContradictionResult]:
        """Get persisted signals, optionally filtered by originating event."""

    @abstractmethod
    async def create_signal_feedback(self, feedback: SignalFeedback) -> str:
        """Record user feedback on a signal. Returns feedback id."""

    @abstractmethod
    async def get_feedback_summary(
        self,
        workspace_id: str,
    ) -> dict[tuple[str, str], dict]:
        """Aggregated feedback by (signal_type, topic_normalized). Value: {useful, not_useful, wrong, save_for_later}."""

    @abstractmethod
    async def get_thesis_feedback_stats(
        self,
        workspace_id: str,
    ) -> list[dict]:
        """Per-thesis feedback stats: [{thesis_link, useful, not_useful, wrong}]."""

    # ------------------------------------------------------------------
    # Phase 4: Notification operations
    # ------------------------------------------------------------------

    @abstractmethod
    async def insert_notification(self, notification: Notification) -> str:
        """Insert a notification. Returns notification id."""

    @abstractmethod
    async def get_notifications(
        self,
        workspace_id: str,
        *,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> list[Notification]:
        """Get notifications, optionally filtered by status."""

    @abstractmethod
    async def get_notification(
        self,
        notification_id: str,
        workspace_id: str = "default",
    ) -> Optional[Notification]:
        """Get a single notification by id."""

    @abstractmethod
    async def update_notification_status(
        self,
        notification_id: str,
        new_status: NotificationStatus,
        *,
        delivered_at: Optional[object] = None,
        acted_at: Optional[object] = None,
    ) -> bool:
        """Update notification status. Returns True if row was updated."""

    @abstractmethod
    async def check_dedup(
        self,
        workspace_id: str,
        dedup_key: str,
    ) -> bool:
        """True if an active (non-terminal) notification with this dedup_key exists."""


class FileStorePort(ABC):
    """Port for file storage backend (local filesystem, S3, etc.)."""

    @abstractmethod
    def save(
        self,
        content: bytes,
        input_type: str,
        subject: str,
        ext: str,
        target_date: Optional[str] = None,
    ) -> str:
        """Save content and return the relative path from store root."""

    @abstractmethod
    def exists(self, rel_path: str) -> bool:
        """Return True if the file at rel_path exists."""

    @abstractmethod
    def read(self, rel_path: str) -> bytes:
        """Read and return raw bytes for the file at rel_path."""

    @abstractmethod
    def absolute(self, rel_path: str):
        """Return an absolute path object for the file at rel_path."""


class EmbeddingPort(ABC):
    """Port for text embedding generation."""

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """Generate embedding for a single text."""

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""

    @property
    @abstractmethod
    def dimensions(self) -> int:
        """Return the embedding dimension size."""


class LLMPort(ABC):
    """Port for LLM calls (metadata extraction, summarization)."""

    @abstractmethod
    async def extract_metadata(self, content: str) -> dict:
        """Extract structured metadata from content.
        Returns: {summary, tags, entities, thesis_links, confidence}
        """


    @abstractmethod
    async def classify_three_dimensions(self, content: str) -> dict:
        """Classify content along source, nature, temporality dimensions."""

    @abstractmethod
    async def parse_stance_llm(self, annotation: str) -> str:
        """Parse user stance from natural language annotation."""
    @abstractmethod
    async def chat(self, prompt: str) -> str:
        """Send a raw prompt and return the response string."""

    @abstractmethod
    async def summarize(self, content: str, max_length: int = 200) -> str:
        """Generate a summary of the content."""
