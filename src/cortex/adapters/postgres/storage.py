"""
PostgreSQL + pgvector adapter implementing StoragePort.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from typing import Optional

import asyncpg

from cortex.domain.entities import (
    ContradictionResult, Entity, EntityType, EventType, KnowledgeEvent,
    Notification, NotificationChannel, NotificationStatus,
    Relation, RelationType, SearchResult, SignalFeedback, ThesisCoverage,
)
from cortex.domain.ports import StoragePort


class PostgresStorage(StoragePort):

    def __init__(self, dsn: str):
        self._dsn = dsn
        self._pool: Optional[asyncpg.Pool] = None
        self._fts_config = "simple"  # detected at connect time

    async def connect(self):
        self._pool = await asyncpg.create_pool(self._dsn, min_size=2, max_size=10)
        try:
            await self._pool.execute("CREATE EXTENSION IF NOT EXISTS vector")
        except Exception:
            pass  # pgvector not available — semantic search will fail gracefully
        # Detect which text search config is available
        row = await self._pool.fetchrow(
            "SELECT 1 FROM pg_ts_config WHERE cfgname = 'zhcfg'"
        )
        if row:
            self._fts_config = "zhcfg"

    async def close(self):
        if self._pool:
            await self._pool.close()

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    async def insert_event(self, event: KnowledgeEvent) -> str:
        sql = """
        INSERT INTO events (
            id, workspace_id, type, title, content, summary,
            tags, thesis_links, confidence, tier, source, source_path,
            embedding, metadata, created_at, updated_at,
            raw_input_type, raw_input_ref, key_points, stance,
            source_type, source_weight, nature_tags, temporality,
            expires_at, user_annotation, user_stance
        ) VALUES (
            $1, $2, $3, $4, $5, $6,
            $7, $8, $9, $10, $11, $12,
            $13, $14, $15, $16,
            $17, $18, $19, $20,
            $21, $22, $23, $24,
            $25, $26, $27
        )
        ON CONFLICT (workspace_id, source_path)
            WHERE source_path != ''
        DO UPDATE SET
            title = EXCLUDED.title,
            content = EXCLUDED.content,
            summary = EXCLUDED.summary,
            tags = CASE
                WHEN events.metadata->>'tags_source' = 'human' THEN events.tags
                ELSE EXCLUDED.tags
            END,
            thesis_links = CASE
                WHEN events.metadata->>'thesis_source' = 'human' THEN events.thesis_links
                ELSE EXCLUDED.thesis_links
            END,
            confidence = EXCLUDED.confidence,
            embedding = EXCLUDED.embedding,
            metadata = events.metadata || EXCLUDED.metadata,
            updated_at = now(),
            raw_input_type = COALESCE(EXCLUDED.raw_input_type, events.raw_input_type),
            raw_input_ref = COALESCE(EXCLUDED.raw_input_ref, events.raw_input_ref),
            key_points = CASE WHEN EXCLUDED.key_points IS NOT NULL AND EXCLUDED.key_points != '[]'::jsonb THEN EXCLUDED.key_points ELSE events.key_points END,
            stance = CASE WHEN EXCLUDED.stance IS NOT NULL AND EXCLUDED.stance != '{}'::jsonb THEN EXCLUDED.stance ELSE events.stance END,
            source_type = COALESCE(EXCLUDED.source_type, events.source_type),
            source_weight = COALESCE(EXCLUDED.source_weight, events.source_weight),
            nature_tags = CASE WHEN EXCLUDED.nature_tags IS NOT NULL AND EXCLUDED.nature_tags != '[]'::jsonb THEN EXCLUDED.nature_tags ELSE events.nature_tags END,
            temporality = COALESCE(EXCLUDED.temporality, events.temporality),
            expires_at = COALESCE(EXCLUDED.expires_at, events.expires_at),
            user_annotation = COALESCE(EXCLUDED.user_annotation, events.user_annotation),
            user_stance = COALESCE(EXCLUDED.user_stance, events.user_stance)
        RETURNING id
        """
        embedding_val = _to_pgvector(event.embedding) if event.embedding else None
        row = await self._pool.fetchrow(
            sql,
            event.id,
            event.workspace_id,
            event.type.value if isinstance(event.type, EventType) else event.type,
            event.title,
            event.content,
            event.summary,
            json.dumps(event.tags),
            json.dumps(event.thesis_links),
            event.confidence,
            event.tier,
            event.source,
            event.source_path,
            embedding_val,
            json.dumps(event.metadata),
            event.created_at,
            event.updated_at,
            getattr(event, 'raw_input_type', None),
            getattr(event, 'raw_input_ref', None),
            json.dumps(getattr(event, 'key_points', None) or []),
            json.dumps(getattr(event, 'stance', None) or {}),
            getattr(event, 'source_type', None),
            getattr(event, 'source_weight', None),
            json.dumps(getattr(event, 'nature_tags', None) or []),
            getattr(event, 'temporality', None),
            getattr(event, 'expires_at', None),
            getattr(event, 'user_annotation', None),
            getattr(event, 'user_stance', None),
        )
        return str(row["id"])

    async def insert_entity(self, entity: Entity) -> str:
        sql = """
        INSERT INTO entities (id, workspace_id, type, name, aliases, properties, embedding)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        ON CONFLICT (workspace_id, type, name) DO UPDATE SET
            aliases = EXCLUDED.aliases,
            properties = entities.properties || EXCLUDED.properties,
            embedding = COALESCE(EXCLUDED.embedding, entities.embedding),
            updated_at = now()
        RETURNING id
        """
        embedding_val = _to_pgvector(entity.embedding) if entity.embedding else None
        row = await self._pool.fetchrow(
            sql,
            entity.id,
            entity.workspace_id,
            entity.type.value if isinstance(entity.type, EntityType) else entity.type,
            entity.name,
            json.dumps(entity.aliases),
            json.dumps(entity.properties),
            embedding_val,
        )
        return str(row["id"])

    async def find_entity_by_name(
        self, workspace_id: str, entity_type: str, name: str,
    ) -> Optional[Entity]:
        sql = """
        SELECT id, workspace_id, type, name, aliases, properties, embedding,
               created_at, updated_at
        FROM entities
        WHERE workspace_id = $1 AND type = $2 AND name = $3
        LIMIT 1
        """
        row = await self._pool.fetchrow(sql, workspace_id, entity_type, name)
        if not row:
            return None
        aliases = json.loads(row["aliases"]) if row["aliases"] else []
        properties = json.loads(row["properties"]) if row["properties"] else {}
        return Entity(
            id=str(row["id"]),
            workspace_id=row["workspace_id"],
            type=EntityType(row["type"]),
            name=row["name"],
            aliases=aliases,
            properties=properties,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    async def append_entity_alias(self, entity_id: str, alias: str) -> None:
        sql = """
        UPDATE entities
        SET aliases = CASE
                WHEN NOT (aliases @> to_jsonb($2::text))
                THEN aliases || to_jsonb($2::text)
                ELSE aliases
            END,
            updated_at = now()
        WHERE id = $1::uuid
        """
        await self._pool.execute(sql, entity_id, alias)

    async def insert_relation(self, relation: Relation) -> str:
        sql = """
        INSERT INTO relations (
            id, workspace_id, source_type, source_id,
            target_type, target_id, relation, confidence, metadata
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        ON CONFLICT (workspace_id, source_id, target_id, relation) DO NOTHING
        RETURNING id
        """
        row = await self._pool.fetchrow(
            sql,
            relation.id,
            relation.workspace_id,
            relation.source_type,
            relation.source_id,
            relation.target_type,
            relation.target_id,
            relation.relation.value if isinstance(relation.relation, RelationType) else relation.relation,
            relation.confidence,
            json.dumps(relation.metadata),
        )
        # row is None when ON CONFLICT DO NOTHING fires (duplicate); return the supplied id
        return str(row["id"]) if row else relation.id

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    async def get_event(self, event_id: str, workspace_id: str = "default") -> Optional[KnowledgeEvent]:
        row = await self._pool.fetchrow(
            "SELECT * FROM events WHERE id = $1 AND workspace_id = $2",
            event_id, workspace_id,
        )
        return _row_to_event(row) if row else None

    async def list_events(
        self, workspace_id: str = "default", *, limit: int = 50, offset: int = 0, days: int | None = None,
    ) -> list[KnowledgeEvent]:
        params: list = [workspace_id, limit, offset]
        day_clause = ""
        if days is not None:
            day_clause = "AND created_at >= NOW() - $4 * INTERVAL '1 day'"
            params.append(days)
        sql = f"""
        SELECT * FROM events
        WHERE workspace_id = $1 {day_clause}
        ORDER BY created_at DESC
        LIMIT $2 OFFSET $3
        """
        rows = await self._pool.fetch(sql, *params)
        return [_row_to_event(r) for r in rows]

    async def semantic_search(
        self,
        embedding: list[float],
        *,
        workspace_id: str = "default",
        limit: int = 10,
        type_filter: Optional[str] = None,
        min_score: float = 0.0,
    ) -> list[SearchResult]:
        params: list = [_to_pgvector(embedding), workspace_id, limit]
        next_param = 4
        type_clause = ""
        if type_filter:
            type_clause = f"AND type = ${next_param}"
            params.append(type_filter)
            next_param += 1
        score_clause = ""
        if min_score > 0.0:
            score_clause = f"AND 1 - (embedding <=> $1) >= ${next_param}"
            params.append(min_score)

        sql = f"""
        SELECT *, 1 - (embedding <=> $1) AS score
        FROM events
        WHERE workspace_id = $2
          AND embedding IS NOT NULL
          {type_clause}
          {score_clause}
        ORDER BY embedding <=> $1
        LIMIT $3
        """
        rows = await self._pool.fetch(sql, *params)
        return [
            SearchResult(
                event=_row_to_event(row),
                score=float(row["score"]),
                match_type="semantic",
            )
            for row in rows
        ]

    async def fulltext_search(
        self,
        query: str,
        *,
        workspace_id: str = "default",
        limit: int = 10,
        type_filter: Optional[str] = None,
    ) -> list[SearchResult]:
        type_clause = "AND type = $4" if type_filter else ""
        params: list = [query, workspace_id, limit]
        if type_filter:
            params.append(type_filter)

        fts_cfg = self._fts_config
        sql = f"""
        SELECT *, ts_rank(fts, plainto_tsquery('{fts_cfg}', $1)) AS rank
        FROM events
        WHERE workspace_id = $2
          AND fts @@ plainto_tsquery('{fts_cfg}', $1)
          {type_clause}
        ORDER BY rank DESC
        LIMIT $3
        """
        rows = await self._pool.fetch(sql, *params)
        return [
            SearchResult(
                event=_row_to_event(row),
                score=float(row["rank"]),
                match_type="fulltext",
            )
            for row in rows
        ]

    async def get_by_thesis(
        self,
        thesis_name: str,
        workspace_id: str = "default",
    ) -> list[KnowledgeEvent]:
        sql = """
        SELECT * FROM events
        WHERE workspace_id = $1
          AND thesis_links @> $2::jsonb
        ORDER BY confidence DESC, created_at DESC
        """
        rows = await self._pool.fetch(sql, workspace_id, json.dumps([thesis_name]))
        return [_row_to_event(row) for row in rows]

    async def get_relations_for(
        self,
        object_id: str,
        workspace_id: str = "default",
    ) -> list[dict]:
        sql = """
        SELECT r.*,
            COALESCE(e_src.title, ent_src.name) AS source_name,
            COALESCE(e_tgt.title, ent_tgt.name) AS target_name
        FROM relations r
        LEFT JOIN events e_src ON r.source_type = 'event' AND r.source_id = e_src.id
        LEFT JOIN entities ent_src ON r.source_type = 'entity' AND r.source_id = ent_src.id
        LEFT JOIN events e_tgt ON r.target_type = 'event' AND r.target_id = e_tgt.id
        LEFT JOIN entities ent_tgt ON r.target_type = 'entity' AND r.target_id = ent_tgt.id
        WHERE r.workspace_id = $1
          AND (r.source_id = $2 OR r.target_id = $2)
        """
        rows = await self._pool.fetch(sql, workspace_id, object_id)
        return [dict(row) for row in rows]

    async def find_related(
        self,
        event_id: str,
        *,
        workspace_id: str = "default",
        limit: int = 10,
    ) -> list[SearchResult]:
        sql = """
        SELECT DISTINCT e2.*, 1.0 AS score
        FROM relations r1
        JOIN relations r2
            ON r1.target_id = r2.target_id
            AND r1.target_type = 'entity'
            AND r2.target_type = 'entity'
        JOIN events e2
            ON r2.source_id = e2.id
            AND r2.source_type = 'event'
        WHERE r1.source_id = $1
          AND r1.source_type = 'event'
          AND r2.source_id != $1
          AND e2.workspace_id = $2
        LIMIT $3
        """
        rows = await self._pool.fetch(sql, event_id, workspace_id, limit)
        return [
            SearchResult(event=_row_to_event(row), score=1.0, match_type="related")
            for row in rows
        ]

    async def stale_events(
        self,
        days: int = 30,
        workspace_id: str = "default",
    ) -> list[KnowledgeEvent]:
        sql = """
        SELECT * FROM events
        WHERE workspace_id = $1
          AND type IN ('thesis', 'note')
          AND updated_at < now() - make_interval(days => $2)
        ORDER BY updated_at ASC
        """
        rows = await self._pool.fetch(sql, workspace_id, days)
        return [_row_to_event(row) for row in rows]

    async def thesis_coverage(
        self,
        workspace_id: str = "default",
    ) -> list[ThesisCoverage]:
        sql = """
        SELECT
            thesis,
            COUNT(*) AS cnt,
            AVG(confidence) AS avg_conf,
            MAX(updated_at) AS latest,
            jsonb_object_agg(type, type_count) AS type_dist
        FROM (
            SELECT
                jsonb_array_elements_text(thesis_links) AS thesis,
                type,
                confidence,
                updated_at,
                COUNT(*) OVER (
                    PARTITION BY jsonb_array_elements_text(thesis_links), type
                ) AS type_count
            FROM events
            WHERE workspace_id = $1 AND thesis_links != '[]'::jsonb
        ) sub
        GROUP BY thesis
        ORDER BY cnt DESC
        """
        rows = await self._pool.fetch(sql, workspace_id)
        now = datetime.now(timezone.utc)
        results = []
        for row in rows:
            latest = row["latest"]
            days_since = (now - latest).days if latest else 0
            results.append(ThesisCoverage(
                thesis_name=row["thesis"],
                event_count=row["cnt"],
                avg_confidence=float(row["avg_conf"]),
                type_distribution=json.loads(row["type_dist"]) if row["type_dist"] else {},
                latest_update=latest,
                days_since_update=days_since,
            ))
        return results

    async def thesis_trend(
        self,
        workspace_id: str = "default",
        window_days: int = 14,
    ) -> dict[str, dict]:
        """Compute per-thesis confidence trend: recent window vs previous window.

        Returns {thesis_name: {recent_avg, previous_avg, recent_count, previous_count}}.
        """
        sql = """
        WITH unnested AS (
            SELECT
                jsonb_array_elements_text(thesis_links) AS thesis,
                confidence,
                created_at
            FROM events
            WHERE workspace_id = $1
              AND thesis_links != '[]'::jsonb
              AND created_at >= now() - make_interval(days => $2 * 2)
        )
        SELECT
            thesis,
            AVG(CASE WHEN created_at >= now() - make_interval(days => $2)
                     THEN confidence END) AS recent_avg,
            COUNT(CASE WHEN created_at >= now() - make_interval(days => $2)
                       THEN 1 END) AS recent_count,
            AVG(CASE WHEN created_at < now() - make_interval(days => $2)
                     THEN confidence END) AS previous_avg,
            COUNT(CASE WHEN created_at < now() - make_interval(days => $2)
                       THEN 1 END) AS previous_count
        FROM unnested
        GROUP BY thesis
        """
        rows = await self._pool.fetch(sql, workspace_id, window_days)
        result = {}
        for r in rows:
            result[r["thesis"]] = {
                "recent_avg": float(r["recent_avg"]) if r["recent_avg"] is not None else None,
                "previous_avg": float(r["previous_avg"]) if r["previous_avg"] is not None else None,
                "recent_count": r["recent_count"],
                "previous_count": r["previous_count"],
            }
        return result

    async def daily_events(
        self,
        target_date: date | None = None,
        workspace_id: str = "default",
    ) -> list[KnowledgeEvent]:
        if target_date is None:
            # No date filter: return most recent events
            sql = """
            SELECT * FROM events
            WHERE workspace_id = $1
            ORDER BY created_at DESC
            LIMIT 50
            """
            rows = await self._pool.fetch(sql, workspace_id)
        else:
            sql = """
            SELECT * FROM events
            WHERE workspace_id = $1
              AND created_at::date = $2
            ORDER BY created_at
            """
            rows = await self._pool.fetch(sql, workspace_id, target_date)
        return [_row_to_event(row) for row in rows]

    async def stats(self, workspace_id: str = "default") -> dict:
        sql = """
        SELECT
            (SELECT COUNT(*) FROM events WHERE workspace_id = $1) AS events,
            (SELECT COUNT(*) FROM entities WHERE workspace_id = $1) AS entities,
            (SELECT COUNT(*) FROM relations WHERE workspace_id = $1) AS relations,
            (SELECT jsonb_object_agg(type, cnt) FROM (
                SELECT type, COUNT(*) AS cnt FROM events WHERE workspace_id = $1 GROUP BY type
            ) t) AS events_by_type
        """
        row = await self._pool.fetchrow(sql, workspace_id)
        return {
            "events": row["events"],
            "entities": row["entities"],
            "relations": row["relations"],
            "type_distribution": json.loads(row["events_by_type"]) if row["events_by_type"] else {},
        }

    async def event_exists(self, source_path: str, workspace_id: str = "default") -> bool:
        row = await self._pool.fetchrow(
            "SELECT 1 FROM events WHERE workspace_id = $1 AND source_path = $2",
            workspace_id, source_path,
        )
        return row is not None


    # ------------------------------------------------------------------
    # Maintenance operations
    # ------------------------------------------------------------------

    async def count_entities_without_embedding(self, workspace_id: str = "default") -> int:
        row = await self._pool.fetchrow(
            "SELECT COUNT(*) AS cnt FROM entities WHERE workspace_id = $1 AND embedding IS NULL",
            workspace_id,
        )
        return row["cnt"]

    async def get_entities_without_embedding(
        self, workspace_id: str = "default", limit: int = 50,
    ) -> list[dict]:
        rows = await self._pool.fetch(
            "SELECT id, name FROM entities WHERE workspace_id = $1 AND embedding IS NULL ORDER BY id LIMIT $2",
            workspace_id, limit,
        )
        return [dict(r) for r in rows]

    async def update_entity_embedding(self, entity_id: str, embedding: list[float]):
        await self._pool.execute(
            "UPDATE entities SET embedding = $1, updated_at = now() WHERE id = $2",
            _to_pgvector(embedding), entity_id,
        )

    async def get_all_events_with_tags(self, workspace_id: str = "default") -> list[dict]:
        rows = await self._pool.fetch(
            "SELECT id, tags FROM events WHERE workspace_id = $1 AND tags != '[]'::jsonb",
            workspace_id,
        )
        return [{"id": str(r["id"]), "tags": json.loads(r["tags"]) if isinstance(r["tags"], str) else r["tags"]} for r in rows]

    async def update_event_fields(
        self,
        event_id: str,
        workspace_id: str,
        *,
        tags: list[str] | None = None,
        thesis_links: list[str] | None = None,
        title: str | None = None,
    ) -> bool:
        sets: list[str] = []
        args: list = []
        idx = 1
        if tags is not None:
            sets.append(f"tags = ${idx}::jsonb")
            args.append(json.dumps(tags))
            idx += 1
        if thesis_links is not None:
            sets.append(f"thesis_links = ${idx}::jsonb")
            args.append(json.dumps(thesis_links))
            idx += 1
        if title is not None:
            sets.append(f"title = ${idx}")
            args.append(title)
            idx += 1
        if not sets:
            return False
        sets.append("updated_at = now()")
        args.extend([event_id, workspace_id])
        sql = f"UPDATE events SET {', '.join(sets)} WHERE id = ${idx} AND workspace_id = ${idx + 1}"
        result = await self._pool.execute(sql, *args)
        return result.endswith("1")

    async def update_event_tags(self, event_id: str, tags: list[str]):
        await self._pool.execute(
            "UPDATE events SET tags = $1, updated_at = now() WHERE id = $2",
            json.dumps(tags), event_id,
        )

    async def get_all_entities(self, workspace_id: str = "default") -> list[dict]:
        rows = await self._pool.fetch("""
            SELECT e.id, e.type, e.name,
                   COUNT(r.id) AS mention_count
            FROM entities e
            LEFT JOIN relations r ON r.target_id = e.id AND r.target_type = 'entity'
            WHERE e.workspace_id = $1
            GROUP BY e.id, e.type, e.name
            ORDER BY e.name
        """, workspace_id)
        return [{"id": str(r["id"]), "type": r["type"], "name": r["name"], "mention_count": r["mention_count"]} for r in rows]

    async def merge_entities(self, keep_id: str, remove_id: str):
        """Merge remove_id into keep_id: reparent relations, delete duplicate."""
        # Reparent relations pointing to the removed entity
        await self._pool.execute(
            "UPDATE relations SET target_id = $1 WHERE target_id = $2 AND target_type = 'entity'",
            keep_id, remove_id,
        )
        await self._pool.execute(
            "UPDATE relations SET source_id = $1 WHERE source_id = $2 AND source_type = 'entity'",
            keep_id, remove_id,
        )
        # Delete the duplicate entity
        await self._pool.execute("DELETE FROM entities WHERE id = $1", remove_id)

    # ------------------------------------------------------------------
    # Entity search operations
    # ------------------------------------------------------------------

    async def semantic_search_entities(
        self,
        embedding: list[float],
        *,
        workspace_id: str = "default",
        entity_types: Optional[list[str]] = None,
        limit: int = 20,
    ) -> list[dict]:
        type_clause = ""
        params: list = [_to_pgvector(embedding), workspace_id, limit]
        if entity_types:
            placeholders = ", ".join(f"${i+4}" for i in range(len(entity_types)))
            type_clause = f"AND e.type IN ({placeholders})"
            params.extend(entity_types)

        sql = f"""
        SELECT e.id, e.type, e.name, e.aliases, e.properties,
               1 - (e.embedding <=> $1) AS score,
               COUNT(r.id) AS mention_count
        FROM entities e
        LEFT JOIN relations r ON r.target_id = e.id AND r.target_type = 'entity'
        WHERE e.workspace_id = $2
          AND e.embedding IS NOT NULL
          {type_clause}
        GROUP BY e.id
        ORDER BY e.embedding <=> $1
        LIMIT $3
        """
        rows = await self._pool.fetch(sql, *params)
        return [
            {
                "id": str(r["id"]),
                "type": r["type"],
                "name": r["name"],
                "aliases": json.loads(r["aliases"]) if isinstance(r["aliases"], str) else r["aliases"],
                "score": float(r["score"]),
                "mention_count": r["mention_count"],
            }
            for r in rows
        ]

    async def get_events_for_entity(
        self,
        entity_id: str,
        workspace_id: str = "default",
        limit: int = 50,
    ) -> list[KnowledgeEvent]:
        sql = """
        SELECT e.* FROM events e
        JOIN relations r ON r.source_id = e.id AND r.source_type = 'event'
        WHERE r.target_id = $1 AND r.target_type = 'entity'
          AND e.workspace_id = $2
        ORDER BY e.created_at DESC
        LIMIT $3
        """
        rows = await self._pool.fetch(sql, entity_id, workspace_id, limit)
        return [_row_to_event(r) for r in rows]

    # ------------------------------------------------------------------
    # Digest / analysis operations
    # ------------------------------------------------------------------

    async def recent_events_by_thesis(
        self, days: int = 1, workspace_id: str = "default",
    ) -> list[dict]:
        sql = """
        SELECT
            jsonb_array_elements_text(thesis_links) AS thesis,
            type, COUNT(*) AS cnt
        FROM events
        WHERE workspace_id = $1
          AND created_at >= now() - make_interval(days => $2)
          AND thesis_links != '[]'::jsonb
        GROUP BY thesis, type
        ORDER BY thesis, cnt DESC
        """
        rows = await self._pool.fetch(sql, workspace_id, days)
        return [dict(r) for r in rows]

    async def high_confidence_recent(
        self, days: int = 7, min_confidence: float = 0.8, workspace_id: str = "default", limit: int = 10,
    ) -> list[KnowledgeEvent]:
        sql = """
        SELECT * FROM events
        WHERE workspace_id = $1
          AND created_at >= now() - make_interval(days => $2)
          AND confidence >= $3
        ORDER BY confidence DESC, created_at DESC
        LIMIT $4
        """
        rows = await self._pool.fetch(sql, workspace_id, days, min_confidence, limit)
        return [_row_to_event(r) for r in rows]

    async def entity_momentum(
        self, days: int = 7, workspace_id: str = "default", limit: int = 10,
    ) -> list[dict]:
        sql = """
        SELECT ent.name, ent.type, COUNT(*) AS mentions
        FROM relations r
        JOIN events e ON r.source_id = e.id AND r.source_type = 'event'
        JOIN entities ent ON r.target_id = ent.id AND r.target_type = 'entity'
        WHERE e.workspace_id = $1
          AND e.created_at >= now() - make_interval(days => $2)
        GROUP BY ent.id, ent.name, ent.type
        ORDER BY mentions DESC
        LIMIT $3
        """
        rows = await self._pool.fetch(sql, workspace_id, days, limit)
        return [dict(r) for r in rows]

    async def get_existing_source_paths(self, workspace_id: str = "default") -> dict[str, str]:
        """Return {source_path: updated_at_iso} for all events."""
        rows = await self._pool.fetch(
            "SELECT source_path, updated_at FROM events WHERE workspace_id = $1 AND source_path != ''",
            workspace_id,
        )
        return {r["source_path"]: r["updated_at"].isoformat() for r in rows}


    # ------------------------------------------------------------------
    # Phase 3: Annotation operations
    # ------------------------------------------------------------------

    async def create_annotation(self, annotation) -> str:
        sql = """
        INSERT INTO annotations (id, workspace_id, target_type, target_id, annotation, stance, context)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        RETURNING id
        """
        row = await self._pool.fetchrow(
            sql,
            annotation.id,
            annotation.workspace_id,
            annotation.target_type,
            annotation.target_id,
            annotation.annotation,
            annotation.stance,
            json.dumps(annotation.context),
        )
        return str(row["id"])

    async def get_annotations(self, workspace_id: str, target_type: str, target_id: str) -> list:
        from cortex.domain.entities import Annotation
        rows = await self._pool.fetch(
            "SELECT * FROM annotations WHERE workspace_id = $1 AND target_type = $2 AND target_id = $3::uuid ORDER BY created_at",
            workspace_id, target_type, target_id,
        )
        return [
            Annotation(
                id=str(r["id"]),
                workspace_id=r["workspace_id"],
                target_type=r["target_type"],
                target_id=str(r["target_id"]),
                annotation=r["annotation"],
                stance=r["stance"],
                context=json.loads(r["context"]) if isinstance(r["context"], str) else (r["context"] or {}),
                created_at=r["created_at"],
            )
            for r in rows
        ]

    async def get_events_without_classification(self, workspace_id: str = "default", limit: int = 50) -> list:
        sql = """
        SELECT * FROM events
        WHERE workspace_id = $1 AND (
            source_type IS NULL
            OR key_points IS NULL OR key_points = '[]'::jsonb
            OR temporality IS NULL
            OR nature_tags IS NULL OR nature_tags = '[]'::jsonb
        )
        ORDER BY created_at DESC LIMIT $2
        """
        rows = await self._pool.fetch(sql, workspace_id, limit)
        return [_row_to_event(row) for row in rows]

    async def update_event_user_stance(self, event_id: str, user_stance: str):
        """Update user_stance on an event (e.g. after annotation)."""
        await self._pool.execute(
            "UPDATE events SET user_stance = $1, updated_at = now() WHERE id = $2::uuid",
            user_stance, event_id,
        )

    async def update_event_classification(
        self, event_id: str, source_type: str, source_weight: float,
        nature_tags: list, temporality: str, key_points: list, stance: dict,
    ):
        await self._pool.execute(
            """UPDATE events SET
                source_type = $1, source_weight = $2, nature_tags = $3,
                temporality = $4, key_points = $5, stance = $6, updated_at = now()
            WHERE id = $7""",
            source_type, source_weight, json.dumps(nature_tags),
            temporality, json.dumps(key_points), json.dumps(stance), event_id,
        )

    # ------------------------------------------------------------------
    # Phase 3.6: Signal operations
    # ------------------------------------------------------------------

    async def upsert_signal(self, signal: ContradictionResult) -> str:
        sql = """
        INSERT INTO signals (
            id, workspace_id, new_event_id, existing_event_id,
            signal_type, topic, summary, confidence, priority_score,
            evidence_event_ids, rationale, evidence_strength, thesis_links
        ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
        ON CONFLICT (id) DO UPDATE SET
            priority_score = EXCLUDED.priority_score,
            summary = COALESCE(EXCLUDED.summary, signals.summary)
        RETURNING id
        """
        row = await self._pool.fetchrow(
            sql,
            signal.id, signal.workspace_id,
            signal.new_event_id, signal.existing_event_id,
            signal.signal_type, signal.topic, signal.summary,
            signal.confidence, signal.priority_score,
            json.dumps(signal.evidence_event_ids),
            signal.rationale, signal.evidence_strength,
            json.dumps(signal.thesis_links),
        )
        return str(row["id"])

    async def get_signals(
        self,
        workspace_id: str,
        *,
        event_id: Optional[str] = None,
        limit: int = 50,
    ) -> list[ContradictionResult]:
        if event_id:
            sql = """
            SELECT * FROM signals
            WHERE workspace_id = $1 AND new_event_id = $2::uuid
            ORDER BY priority_score DESC LIMIT $3
            """
            rows = await self._pool.fetch(sql, workspace_id, event_id, limit)
        else:
            sql = """
            SELECT * FROM signals
            WHERE workspace_id = $1
            ORDER BY created_at DESC LIMIT $2
            """
            rows = await self._pool.fetch(sql, workspace_id, limit)
        return [_row_to_signal(row) for row in rows]

    async def create_signal_feedback(self, feedback: SignalFeedback) -> str:
        sql = """
        INSERT INTO signal_feedback (
            id, workspace_id, signal_id, verdict, note,
            signal_type, topic_normalized, thesis_link
        )
        SELECT $1, $2, $3, $4, $5,
               s.signal_type, lower(trim(s.topic)), s.thesis_links->>0
        FROM signals s WHERE s.id = $3
        RETURNING id
        """
        row = await self._pool.fetchrow(
            sql,
            feedback.id, feedback.workspace_id,
            feedback.signal_id, feedback.verdict, feedback.note,
        )
        return str(row["id"])

    async def get_feedback_summary(
        self,
        workspace_id: str,
    ) -> dict[tuple[str, str], dict]:
        sql = """
        SELECT signal_type, topic_normalized,
            SUM(CASE WHEN verdict='useful' THEN 1 ELSE 0 END) AS useful,
            SUM(CASE WHEN verdict='not_useful' THEN 1 ELSE 0 END) AS not_useful,
            SUM(CASE WHEN verdict='wrong' THEN 1 ELSE 0 END) AS wrong,
            SUM(CASE WHEN verdict='save_for_later' THEN 1 ELSE 0 END) AS save_for_later
        FROM signal_feedback
        WHERE workspace_id = $1
        GROUP BY signal_type, topic_normalized
        """
        rows = await self._pool.fetch(sql, workspace_id)
        result = {}
        for r in rows:
            key = (r["signal_type"], r["topic_normalized"] or "")
            result[key] = {
                "useful": r["useful"],
                "not_useful": r["not_useful"],
                "wrong": r["wrong"],
                "save_for_later": r["save_for_later"],
            }
        return result

    async def get_thesis_feedback_stats(
        self,
        workspace_id: str,
    ) -> list[dict]:
        sql = """
        SELECT thesis_link,
            SUM(CASE WHEN verdict='useful' THEN 1 ELSE 0 END) AS useful,
            SUM(CASE WHEN verdict='not_useful' THEN 1 ELSE 0 END) AS not_useful,
            SUM(CASE WHEN verdict='wrong' THEN 1 ELSE 0 END) AS wrong
        FROM signal_feedback
        WHERE workspace_id = $1 AND thesis_link IS NOT NULL
        GROUP BY thesis_link
        ORDER BY (SUM(CASE WHEN verdict='useful' THEN 1 ELSE 0 END)
                + SUM(CASE WHEN verdict='not_useful' THEN 1 ELSE 0 END)
                + SUM(CASE WHEN verdict='wrong' THEN 1 ELSE 0 END)) DESC
        """
        rows = await self._pool.fetch(sql, workspace_id)
        return [
            {
                "thesis_link": r["thesis_link"],
                "useful": r["useful"],
                "not_useful": r["not_useful"],
                "wrong": r["wrong"],
            }
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Phase 4: Notification operations
    # ------------------------------------------------------------------

    async def insert_notification(self, notification: Notification) -> str:
        sql = """
        INSERT INTO notifications (
            id, workspace_id, source_kind, source_id, dedup_key,
            title, body, priority, status, channel,
            related_event_ids, signal_id, cooldown_until,
            created_at, delivered_at, acted_at
        ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16)
        ON CONFLICT (workspace_id, dedup_key)
            WHERE status NOT IN ('acked','dismissed','failed')
        DO NOTHING
        RETURNING id
        """
        row = await self._pool.fetchrow(
            sql,
            notification.id, notification.workspace_id,
            notification.source_kind, notification.source_id,
            notification.dedup_key,
            notification.title, notification.body,
            notification.priority, notification.status.value,
            notification.channel.value,
            json.dumps(notification.related_event_ids),
            notification.signal_id, notification.cooldown_until,
            notification.created_at, notification.delivered_at,
            notification.acted_at,
        )
        return str(row["id"]) if row else notification.id

    async def get_notifications(
        self,
        workspace_id: str,
        *,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> list[Notification]:
        if status:
            sql = """
            SELECT * FROM notifications
            WHERE workspace_id = $1 AND status = $2
            ORDER BY created_at DESC LIMIT $3
            """
            rows = await self._pool.fetch(sql, workspace_id, status, limit)
        else:
            sql = """
            SELECT * FROM notifications
            WHERE workspace_id = $1
            ORDER BY created_at DESC LIMIT $2
            """
            rows = await self._pool.fetch(sql, workspace_id, limit)
        return [_row_to_notification(row) for row in rows]

    async def get_notification(
        self,
        notification_id: str,
        workspace_id: str = "default",
    ) -> Optional[Notification]:
        row = await self._pool.fetchrow(
            "SELECT * FROM notifications WHERE id = $1::uuid AND workspace_id = $2",
            notification_id, workspace_id,
        )
        return _row_to_notification(row) if row else None

    async def update_notification_status(
        self,
        notification_id: str,
        new_status: NotificationStatus,
        *,
        delivered_at=None,
        acted_at=None,
    ) -> bool:
        sql = """
        UPDATE notifications
        SET status = $1, delivered_at = COALESCE($2, delivered_at),
            acted_at = COALESCE($3, acted_at)
        WHERE id = $4::uuid
        """
        result = await self._pool.execute(
            sql, new_status.value, delivered_at, acted_at, notification_id,
        )
        return result.endswith("1")  # "UPDATE 1"

    async def check_dedup(self, workspace_id: str, dedup_key: str) -> bool:
        row = await self._pool.fetchrow(
            """SELECT 1 FROM notifications
               WHERE workspace_id = $1 AND dedup_key = $2
                 AND status NOT IN ('acked','dismissed','failed')""",
            workspace_id, dedup_key,
        )
        return row is not None


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _safe_col(row, name, default=None):
    """Safely get a column that may not exist in the query result."""
    try:
        return row[name]
    except (KeyError, ValueError):
        return default


def _safe_json_col(row, name, default=None):
    """Safely get and parse a JSONB column."""
    val = _safe_col(row, name)
    if val is None:
        return default if default is not None else None
    if isinstance(val, str):
        return json.loads(val)
    return val


def _to_pgvector(embedding: list[float]) -> str:
    """Convert Python list to pgvector string format."""
    return "[" + ",".join(str(x) for x in embedding) + "]"


def _row_to_event(row: asyncpg.Record) -> KnowledgeEvent:
    """Convert a database row to a KnowledgeEvent."""
    return KnowledgeEvent(
        id=str(row["id"]),
        workspace_id=row["workspace_id"],
        type=EventType(row["type"]),
        title=row["title"],
        content=row["content"],
        summary=row["summary"],
        tags=json.loads(row["tags"]) if isinstance(row["tags"], str) else row["tags"],
        thesis_links=json.loads(row["thesis_links"]) if isinstance(row["thesis_links"], str) else row["thesis_links"],
        confidence=float(row["confidence"]),
        tier=row["tier"],
        source=row["source"],
        source_path=row["source_path"],
        embedding=[],  # don't load embedding into memory by default
        metadata=json.loads(row["metadata"]) if isinstance(row["metadata"], str) else row["metadata"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        # Phase 3 fields (safe access for old queries)
        raw_input_type=_safe_col(row, "raw_input_type"),
        raw_input_ref=_safe_col(row, "raw_input_ref"),
        key_points=_safe_json_col(row, "key_points", []),
        stance=_safe_json_col(row, "stance", {}),
        source_type=_safe_col(row, "source_type"),
        source_weight=float(row["source_weight"]) if _safe_col(row, "source_weight") is not None else None,
        nature_tags=_safe_json_col(row, "nature_tags", []),
        temporality=_safe_col(row, "temporality"),
        expires_at=_safe_col(row, "expires_at"),
        user_annotation=_safe_col(row, "user_annotation"),
        user_stance=_safe_col(row, "user_stance"),
    )


def _row_to_signal(row: asyncpg.Record) -> ContradictionResult:
    """Convert a database row to a ContradictionResult."""
    evidence = _safe_json_col(row, "evidence_event_ids", [])
    thesis = _safe_json_col(row, "thesis_links", [])
    return ContradictionResult(
        new_event_id=str(row["new_event_id"]),
        existing_event_id=str(row["existing_event_id"]),
        signal_type=row["signal_type"],
        topic=row["topic"],
        summary=row["summary"],
        confidence=float(row["confidence"]),
        priority_score=float(row["priority_score"]),
        evidence_event_ids=evidence,
        rationale=_safe_col(row, "rationale"),
        evidence_strength=_safe_col(row, "evidence_strength"),
        id=str(row["id"]),
        workspace_id=row["workspace_id"],
        created_at=row["created_at"],
        thesis_links=thesis,
    )


def _row_to_notification(row: asyncpg.Record) -> Notification:
    """Convert a database row to a Notification."""
    related = _safe_json_col(row, "related_event_ids", [])
    return Notification(
        title=row["title"],
        body=row["body"],
        source_kind=row["source_kind"],
        source_id=row["source_id"],
        dedup_key=row["dedup_key"],
        id=str(row["id"]),
        workspace_id=row["workspace_id"],
        priority=row["priority"],
        status=NotificationStatus(row["status"]),
        channel=NotificationChannel(row["channel"]),
        related_event_ids=related,
        signal_id=str(row["signal_id"]) if row["signal_id"] else None,
        cooldown_until=row["cooldown_until"],
        created_at=row["created_at"],
        delivered_at=row["delivered_at"],
        acted_at=row["acted_at"],
    )