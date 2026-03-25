"""
Search use case: semantic, fulltext, hybrid search + entity search.
"""

from __future__ import annotations

from typing import Optional

from cortex.domain.entities import KnowledgeEvent, SearchResult
from cortex.domain.ports import EmbeddingPort, StoragePort


class SearchUseCase:
    def __init__(
        self,
        storage: StoragePort,
        embedding: EmbeddingPort,
        workspace_id: str = "default",
    ):
        self._storage = storage
        self._embedding = embedding
        self._workspace_id = workspace_id

    async def semantic(
        self,
        query: str,
        *,
        limit: int = 10,
        type_filter: Optional[str] = None,
        min_score: float = 0.0,
    ) -> list[SearchResult]:
        """Vector similarity search."""
        query_embedding = await self._embedding.embed(query)
        return await self._storage.semantic_search(
            query_embedding,
            workspace_id=self._workspace_id,
            limit=limit,
            type_filter=type_filter,
            min_score=min_score,
        )

    async def fulltext(
        self,
        query: str,
        *,
        limit: int = 10,
        type_filter: Optional[str] = None,
    ) -> list[SearchResult]:
        """PostgreSQL full-text search."""
        return await self._storage.fulltext_search(
            query,
            workspace_id=self._workspace_id,
            limit=limit,
            type_filter=type_filter,
        )

    async def hybrid(
        self,
        query: str,
        *,
        limit: int = 10,
        type_filter: Optional[str] = None,
        semantic_weight: float = 0.7,
    ) -> list[SearchResult]:
        """Combine semantic and fulltext results with weighted scoring."""
        sem_results = await self.semantic(query, limit=limit * 2, type_filter=type_filter)
        ft_results = await self.fulltext(query, limit=limit * 2, type_filter=type_filter)

        # Merge and re-rank
        scored: dict[str, tuple[SearchResult, float]] = {}

        # Normalize semantic scores
        sem_max = max((r.score for r in sem_results), default=1.0) or 1.0
        for r in sem_results:
            norm_score = r.score / sem_max
            scored[r.event.id] = (r, norm_score * semantic_weight)

        # Normalize fulltext scores
        ft_max = max((r.score for r in ft_results), default=1.0) or 1.0
        ft_weight = 1.0 - semantic_weight
        for r in ft_results:
            norm_score = r.score / ft_max
            if r.event.id in scored:
                existing = scored[r.event.id]
                scored[r.event.id] = (existing[0], existing[1] + norm_score * ft_weight)
            else:
                scored[r.event.id] = (r, norm_score * ft_weight)

        # Sort by combined score
        ranked = sorted(scored.values(), key=lambda x: x[1], reverse=True)

        return [
            SearchResult(
                event=item[0].event,
                score=item[1],
                match_type="hybrid",
            )
            for item in ranked[:limit]
        ]

    async def related(
        self,
        event_id: str,
        *,
        limit: int = 10,
    ) -> list[SearchResult]:
        """Find events related through shared entities."""
        return await self._storage.find_related(
            event_id,
            workspace_id=self._workspace_id,
            limit=limit,
        )

    async def search_entities(
        self,
        query: str,
        *,
        entity_types: Optional[list[str]] = None,
        limit: int = 20,
    ) -> list[dict]:
        """Semantic search over entities."""
        query_embedding = await self._embedding.embed(query)
        return await self._storage.semantic_search_entities(
            query_embedding,
            workspace_id=self._workspace_id,
            entity_types=entity_types,
            limit=limit,
        )

    async def entity_events(
        self,
        entity_id: str,
        *,
        limit: int = 50,
    ) -> list[KnowledgeEvent]:
        """Get all events mentioning a specific entity."""
        return await self._storage.get_events_for_entity(
            entity_id,
            workspace_id=self._workspace_id,
            limit=limit,
        )
