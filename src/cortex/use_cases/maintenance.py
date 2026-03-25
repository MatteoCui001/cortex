"""
Maintenance use case: entity embeddings, tag normalization, entity deduplication.
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Optional

from cortex.domain.ports import EmbeddingPort, StoragePort


class MaintenanceUseCase:

    def __init__(
        self,
        storage: StoragePort,
        embedding: EmbeddingPort,
        workspace_id: str = "default",
        tag_config: Optional[dict] = None,
    ):
        self._storage = storage
        self._embedding = embedding
        self._workspace_id = workspace_id
        self._tag_config = tag_config or {}

    async def backfill_entity_embeddings(
        self,
        batch_size: int = 50,
        on_progress: Optional[callable] = None,
    ) -> dict:
        """Generate embeddings for all entities that lack them."""
        stats = {"processed": 0, "total": 0}
        stats["total"] = await self._storage.count_entities_without_embedding(
            self._workspace_id
        )

        while True:
            entities = await self._storage.get_entities_without_embedding(
                self._workspace_id, limit=batch_size
            )
            if not entities:
                break

            texts = [e["name"] for e in entities]
            embeddings = await self._embedding.embed_batch(texts)

            for ent, emb in zip(entities, embeddings):
                await self._storage.update_entity_embedding(
                    ent["id"], emb
                )

            stats["processed"] += len(entities)
            if on_progress:
                on_progress(stats["processed"], stats["total"])

        return stats

    async def normalize_tags(
        self,
        on_progress: Optional[callable] = None,
    ) -> dict:
        """Normalize tags across all events using configured rules."""
        canonical_map: dict[str, str] = {}

        for canonical, variants in self._tag_config.get("canonical_forms", {}).items():
            for v in variants:
                canonical_map[v.lower().strip()] = canonical
            canonical_map[canonical.lower().strip()] = canonical

        for pair in self._tag_config.get("bilingual_pairs", []):
            if len(pair) >= 2:
                canonical = pair[0]
                for v in pair:
                    canonical_map[v.lower().strip()] = canonical

        events = await self._storage.get_all_events_with_tags(self._workspace_id)
        stats = {"events_checked": len(events), "events_updated": 0, "tags_changed": 0}

        for i, evt in enumerate(events):
            original_tags = evt["tags"]
            normalized = []
            changed = False
            for tag in original_tags:
                t = tag.lower().strip()
                t_unhyphen = t.replace("-", " ")
                t_deplural = re.sub(r"s$", "", t_unhyphen) if len(t_unhyphen) > 3 else t_unhyphen
                for candidate in [t, t_unhyphen, t_deplural]:
                    if candidate in canonical_map:
                        t = canonical_map[candidate]
                        break
                else:
                    t = t_unhyphen

                if t != tag:
                    changed = True
                normalized.append(t)

            seen = set()
            deduped = []
            for t in normalized:
                if t not in seen:
                    seen.add(t)
                    deduped.append(t)

            if changed or len(deduped) != len(normalized):
                stats["tags_changed"] += sum(1 for a, b in zip(original_tags, deduped) if a != b)
                stats["tags_changed"] += abs(len(original_tags) - len(deduped))
                await self._storage.update_event_tags(evt["id"], deduped)
                stats["events_updated"] += 1

            if on_progress and (i + 1) % 50 == 0:
                on_progress(i + 1, stats["events_checked"])

        return stats

    async def deduplicate_entities(
        self,
        on_progress: Optional[callable] = None,
    ) -> dict:
        """Find and merge duplicate entities (same name, different types or IDs)."""
        entities = await self._storage.get_all_entities(self._workspace_id)
        stats = {"candidates": 0, "merged": 0, "entities_before": len(entities)}

        groups: dict[str, list[dict]] = defaultdict(list)
        for ent in entities:
            key = ent["name"].lower().strip()
            groups[key].append(ent)

        for name, group in groups.items():
            if len(group) < 2:
                continue
            stats["candidates"] += len(group) - 1

            group.sort(key=lambda e: e.get("mention_count", 0), reverse=True)
            keep = group[0]
            for remove in group[1:]:
                await self._storage.merge_entities(keep["id"], remove["id"])
                stats["merged"] += 1
                if on_progress:
                    on_progress(stats["merged"], stats["candidates"])

        stats["entities_after"] = stats["entities_before"] - stats["merged"]
        return stats