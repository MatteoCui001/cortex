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
        sem_results = await self.semantic(
            query, limit=limit * 2, type_filter=type_filter
        )
        ft_results = await self.fulltext(
            query, limit=limit * 2, type_filter=type_filter
        )

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
        """Hybrid entity search: text name match boosted, then vector fallback."""
        query_embedding = await self._embedding.embed(query)
        results = await self._storage.semantic_search_entities(
            query_embedding,
            workspace_id=self._workspace_id,
            entity_types=entity_types,
            limit=limit * 2,  # fetch more for re-ranking
        )

        # Boost results where query is a substring of entity name or alias
        q_lower = query.lower().strip()
        for r in results:
            name_lower = r.get("name", "").lower()
            aliases = r.get("aliases") or []
            alias_text = " ".join(a.lower() for a in aliases)
            if q_lower in name_lower or q_lower in alias_text:
                r["score"] = min(1.0, r["score"] + 0.3)
            elif name_lower in q_lower:
                r["score"] = min(1.0, r["score"] + 0.15)

        # Filter out low-relevance results that don't text-match
        filtered = []
        for r in results:
            name_lower = r.get("name", "").lower()
            aliases = r.get("aliases") or []
            alias_text = " ".join(a.lower() for a in aliases)
            has_text_match = q_lower in name_lower or q_lower in alias_text or name_lower in q_lower
            if has_text_match or r["score"] >= 0.5:
                filtered.append(r)

        filtered.sort(key=lambda r: r["score"], reverse=True)
        return filtered[:limit]

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