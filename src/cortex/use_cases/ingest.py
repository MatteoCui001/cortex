"""
Ingestion use case: parse -> extract metadata -> classify -> embed -> store.
"""
from __future__ import annotations

import hashlib
import logging
import re
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

import yaml

from cortex.domain.canonical import canonical_key
from cortex.domain.constants import SOURCE_WEIGHTS, TEMPORALITY_TTL_DAYS

logger = logging.getLogger(__name__)
from cortex.domain.entities import Entity, EntityType, EventType, KnowledgeEvent, Relation
from cortex.domain.ports import EmbeddingPort, LLMPort, StoragePort


class IngestUseCase:

    def __init__(
        self,
        storage: StoragePort,
        embedding: EmbeddingPort,
        llm: Optional[LLMPort] = None,
        workspace_id: str = "default",
    ):
        self._storage = storage
        self._embedding = embedding
        self._llm = llm
        self._workspace_id = workspace_id

    async def import_vault(
        self,
        vault_path: str,
        *,
        skip_existing: bool = True,
        on_progress: Optional[callable] = None,
    ) -> dict:
        """Import all Markdown files from an Obsidian vault."""
        vault = Path(vault_path)
        if not vault.is_dir():
            raise ValueError(f"Vault path does not exist: {vault_path}")

        files = sorted(vault.rglob("*.md"))
        stats = {"total": len(files), "imported": 0, "skipped": 0, "errors": 0}

        for i, md_file in enumerate(files):
            rel_path = str(md_file.relative_to(vault))
            try:
                if skip_existing and await self._storage.event_exists(
                    rel_path, self._workspace_id
                ):
                    stats["skipped"] += 1
                    if on_progress:
                        on_progress(i + 1, stats["total"], rel_path, "skipped")
                    continue

                event = await self.import_file(md_file, source_path=rel_path)
                if event:
                    stats["imported"] += 1
                    status = "imported"
                else:
                    stats["skipped"] += 1
                    status = "skipped"

                if on_progress:
                    on_progress(i + 1, stats["total"], rel_path, status)

            except Exception as e:
                stats["errors"] += 1
                if on_progress:
                    on_progress(i + 1, stats["total"], rel_path, f"error: {e}")

        return stats

    async def import_file(
        self,
        file_path: Path,
        *,
        source: str = "obsidian",
        source_path: Optional[str] = None,
    ) -> Optional[KnowledgeEvent]:
        """Import a single Markdown file."""
        text = file_path.read_text(encoding="utf-8")
        if not text.strip():
            return None

        frontmatter, content = _parse_frontmatter(text)
        title = frontmatter.get("title") or file_path.stem.replace("-", " ").replace("_", " ")

        return await self.import_text(
            title=title,
            content=content,
            source=source,
            source_path=source_path or str(file_path),
            raw_input_type="file",
            _frontmatter=frontmatter,
        )

    async def import_text(
        self,
        title: str,
        content: str,
        *,
        source: str = "api",
        source_path: Optional[str] = None,
        event_type: str = "note",
        raw_input_type: str = "text",
        raw_input_ref: Optional[str] = None,
        user_annotation: Optional[str] = None,
        _frontmatter: Optional[dict] = None,
    ) -> KnowledgeEvent:
        """Import raw text with full Phase 3 classification pipeline."""
        frontmatter = _frontmatter or {}

        # 1. Extract metadata via LLM (graceful fallback if LLM fails)
        _fallback_metadata = {
            "summary": content[:200].replace("\n", " "),
            "tags": list(frontmatter.get("tags", [])) if frontmatter.get("tags") else [],
            "entities": [],
            "thesis_links": [],
            "confidence": 0.5,
            "event_type": event_type,
        }
        if self._llm:
            try:
                metadata = await self._llm.extract_metadata(content)
            except Exception as e:
                logger.warning("LLM metadata extraction failed, using fallback: %s", e)
                metadata = _fallback_metadata
        else:
            metadata = _fallback_metadata

        # 2. Classify three dimensions via LLM
        classification = {}
        if self._llm:
            try:
                classification = await self._llm.classify_three_dimensions(content)
            except Exception as e:
                logger.warning("Classification failed: %s", e)

        # 3. Parse user stance
        user_stance = None
        if user_annotation and self._llm:
            try:
                user_stance = await self._llm.parse_stance_llm(user_annotation)
            except Exception as e:
                logger.warning("Stance parsing failed: %s", e)
        elif user_annotation:
            from cortex.domain.stance import parse_user_stance
            user_stance = parse_user_stance(user_annotation)

        # 4. Map event type
        et = _map_event_type(
            metadata.get("event_type", event_type),
            frontmatter.get("type"),
        )

        # 5. Generate embedding
        embed_text = f"{title}\n{metadata.get('summary', '')}\n{content[:1000]}"
        embedding = await self._embedding.embed(embed_text)

        # 6. Generate source_path for dedup if not provided
        if not source_path:
            content_hash = hashlib.sha256(content[:200].encode()).hexdigest()[:16]
            source_path = f"{raw_input_type}:{content_hash}"

        # 7. Compute expires_at from temporality
        temporality = classification.get("temporality")
        expires_at = None
        if temporality:
            from datetime import timedelta
            ttl_days = TEMPORALITY_TTL_DAYS.get(temporality)
            if ttl_days is not None:
                expires_at = datetime.now(timezone.utc) + timedelta(days=ttl_days)

        # 8. Build event with all Phase 3 fields
        source_type = classification.get("source_type")
        event = KnowledgeEvent(
            id=str(uuid.uuid4()),
            workspace_id=self._workspace_id,
            type=et,
            title=title,
            content=content,
            summary=metadata.get("summary", ""),
            tags=metadata.get("tags", []),
            thesis_links=metadata.get("thesis_links", []),
            confidence=metadata.get("confidence", 0.5),
            tier=0,
            source=source,
            source_path=source_path,
            embedding=embedding,
            metadata={
                "frontmatter": _sanitize_for_json(frontmatter),
                "embedding_model": self._embedding.__class__.__name__,
                "tags_source": "ai" if self._llm else "frontmatter",
                "thesis_source": "ai" if self._llm else "none",
            },
            # Phase 3 fields
            raw_input_type=raw_input_type,
            raw_input_ref=raw_input_ref,
            key_points=classification.get("key_points", []),
            stance=classification.get("stance", {}),
            source_type=source_type,
            source_weight=SOURCE_WEIGHTS.get(source_type, 0.5) if source_type else None,
            nature_tags=classification.get("nature_tags", []),
            temporality=temporality,
            expires_at=expires_at,
            user_annotation=user_annotation,
            user_stance=user_stance,
        )

        event_id = await self._storage.insert_event(event)

        # 8. Extract and store entities + relations (with canonicalization + inline embedding)
        entities = metadata.get("entities", [])
        for ent_data in entities:
            ent_type = _map_entity_type(ent_data.get("type", "concept"))
            raw_name = ent_data.get("name", "").strip()
            if not raw_name:
                continue

            # Canonicalize: look up existing entity by canonical key
            canon = canonical_key(raw_name)
            entity_id = await self._resolve_or_create_entity(
                ent_type, raw_name, canon,
            )

            relation = Relation(
                id=str(uuid.uuid4()),
                workspace_id=self._workspace_id,
                source_type="event",
                source_id=event_id,
                target_type="entity",
                target_id=entity_id,
                relation="mentions",
                confidence=metadata.get("confidence", 0.5),
            )
            await self._storage.insert_relation(relation)

        return event

    async def _resolve_or_create_entity(
        self, ent_type, raw_name: str, canon: str,
    ) -> str:
        """Find existing entity by canonical key, or create a new one.

        Returns the entity id. Appends raw_name as alias if it differs from
        the canonical entity's stored name.
        """
        etype_str = ent_type.value if hasattr(ent_type, "value") else ent_type

        # Try to find an existing entity whose name matches the canonical key.
        # We look up by the canonical form first (the stored name IS canonical).
        existing = await self._storage.find_entity_by_name(
            self._workspace_id, etype_str, canon,
        )
        # Also try exact raw_name match (backward compat with pre-canon data)
        if not existing and raw_name != canon:
            existing = await self._storage.find_entity_by_name(
                self._workspace_id, etype_str, raw_name,
            )

        if existing:
            # Append the raw name as alias if it's not the canonical name
            if raw_name != existing.name and raw_name not in existing.aliases:
                await self._storage.append_entity_alias(existing.id, raw_name)
            return existing.id

        # Create new entity with canonical name; raw_name saved as alias if different
        aliases = [raw_name] if raw_name != canon else []
        entity = Entity(
            id=str(uuid.uuid4()),
            workspace_id=self._workspace_id,
            type=ent_type,
            name=canon,
            aliases=aliases,
        )
        # Generate embedding at ingest time; failure is non-blocking
        try:
            entity.embedding = await self._embedding.embed(canon)
        except Exception:
            logger.warning(
                "Entity embedding failed for '%s', will need backfill",
                canon, exc_info=True,
            )
        return await self._storage.insert_entity(entity)

    async def post_ingest_analyze(self, event: KnowledgeEvent) -> list:
        """Run contradiction detection on a newly ingested event. Returns signals."""
        if not self._llm:
            return []
        try:
            from cortex.use_cases.contradiction import ContradictionDetector
            detector = ContradictionDetector(self._storage, self._embedding, self._llm)
            results = await detector.analyze(event, workspace_id=self._workspace_id)

            # Apply feedback-based priority adjustment
            if results:
                from cortex.use_cases.feedback_adjuster import (
                    apply_feedback_multipliers,
                    build_feedback_multipliers,
                )
                summary = await self._storage.get_feedback_summary(self._workspace_id)
                if summary:
                    multipliers = build_feedback_multipliers(summary)
                    apply_feedback_multipliers(results, multipliers)

            return results
        except Exception:
            logger.exception("post_ingest_analyze failed for event %s", event.id)
            return []

    async def sync_vault(
        self,
        vault_path: str,
        *,
        on_progress=None,
    ) -> dict:
        """Incremental sync: only import new or modified files."""
        vault = Path(vault_path)
        if not vault.is_dir():
            raise ValueError(f"Vault path does not exist: {vault_path}")

        files = sorted(vault.rglob("*.md"))
        existing = await self._storage.get_existing_source_paths(self._workspace_id)
        stats = {"total": len(files), "imported": 0, "updated": 0, "unchanged": 0, "errors": 0}

        for i, md_file in enumerate(files):
            rel_path = str(md_file.relative_to(vault))
            try:
                file_mtime = datetime.fromtimestamp(md_file.stat().st_mtime, tz=timezone.utc)

                if rel_path in existing:
                    db_updated = datetime.fromisoformat(existing[rel_path])
                    # Ensure timezone-aware comparison (DB may return naive timestamps)
                    if db_updated.tzinfo is None:
                        db_updated = db_updated.replace(tzinfo=timezone.utc)
                    if file_mtime <= db_updated:
                        stats["unchanged"] += 1
                        if on_progress:
                            on_progress(i + 1, stats["total"], rel_path, "unchanged")
                        continue
                    event = await self.import_file(md_file, source_path=rel_path)
                    stats["updated"] += 1
                    status = "updated"
                else:
                    event = await self.import_file(md_file, source_path=rel_path)
                    if event:
                        stats["imported"] += 1
                        status = "imported"
                    else:
                        stats["unchanged"] += 1
                        status = "skipped"

                if on_progress:
                    on_progress(i + 1, stats["total"], rel_path, status)

            except Exception as e:
                stats["errors"] += 1
                if on_progress:
                    on_progress(i + 1, stats["total"], rel_path, f"error: {e}")

        return stats


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Split Obsidian YAML frontmatter from content."""
    match = _FRONTMATTER_RE.match(text)
    if match:
        try:
            fm = yaml.safe_load(match.group(1)) or {}
        except yaml.YAMLError:
            fm = {}
        content = text[match.end():]
    else:
        fm = {}
        content = text
    return fm, content.strip()


def _map_event_type(ai_type: str, frontmatter_type: Optional[str] = None) -> EventType:
    """Map string to EventType, preferring frontmatter over AI."""
    raw = (frontmatter_type or ai_type or "note").lower().strip()
    mapping = {
        "article": EventType.ARTICLE,
        "meeting": EventType.MEETING,
        "note": EventType.NOTE,
        "thesis": EventType.THESIS,
        "chat": EventType.CHAT,
        "voice_memo": EventType.VOICE_MEMO,
        "image": EventType.IMAGE,
        "document": EventType.DOCUMENT,
        "video": EventType.VIDEO,
        "agent_analysis": EventType.AGENT_ANALYSIS,
    }
    return mapping.get(raw, EventType.NOTE)


def _map_entity_type(raw: str) -> EntityType:
    """Map string to EntityType."""
    mapping = {
        "company": EntityType.COMPANY,
        "person": EntityType.PERSON,
        "technology": EntityType.TECHNOLOGY,
        "concept": EntityType.CONCEPT,
        "fund": EntityType.FUND,
    }
    return mapping.get(raw.lower().strip(), EntityType.CONCEPT)


def _sanitize_for_json(obj):
    """Convert date/datetime objects to ISO strings for JSON serialization."""
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize_for_json(v) for v in obj]
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    return obj
