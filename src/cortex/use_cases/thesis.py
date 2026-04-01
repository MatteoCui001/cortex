"""
Thesis Use Case — CRUD + dynamic evidence evaluation.
"""
from __future__ import annotations

import logging
from typing import Optional

from cortex.domain.entities import (
    EvidenceImpact, KnowledgeEvent, Thesis, ThesisCreatedBy,
    ThesisEvidence, ThesisStance, ThesisStatus,
)
from cortex.domain.ports import LLMPort, StoragePort

log = logging.getLogger(__name__)

MAX_CANDIDATES_PER_EVENT = 10


class ThesisUseCase:

    def __init__(
        self,
        storage: StoragePort,
        workspace: str = "default",
        *,
        llm: Optional[LLMPort] = None,
    ):
        self._storage = storage
        self._workspace = workspace
        self._llm = llm

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def create(
        self,
        text: str,
        stance: str = "neutral",
        theme: Optional[str] = None,
        expires_at=None,
        created_by: str = "manual",
    ) -> Thesis:
        thesis = Thesis(
            text=text,
            workspace_id=self._workspace,
            stance=ThesisStance(stance),
            theme=theme,
            expires_at=expires_at,
            created_by=ThesisCreatedBy(created_by),
            confirmed=created_by == "manual",
        )
        await self._storage.create_thesis(thesis)
        return thesis

    async def get(self, thesis_id: str) -> Optional[Thesis]:
        return await self._storage.get_thesis(thesis_id, self._workspace)

    async def list(
        self, *, status: Optional[str] = None, theme: Optional[str] = None,
        confirmed_only: bool = False,
    ) -> list[Thesis]:
        return await self._storage.list_theses(
            self._workspace, status=status, theme=theme, confirmed_only=confirmed_only,
        )

    async def update(self, thesis_id: str, **fields) -> bool:
        return await self._storage.update_thesis(thesis_id, self._workspace, **fields)

    async def resolve(self, thesis_id: str) -> bool:
        return await self._storage.update_thesis(
            thesis_id, self._workspace, status="resolved",
        )

    async def invalidate(self, thesis_id: str) -> bool:
        return await self._storage.update_thesis(
            thesis_id, self._workspace, status="invalidated",
        )

    async def confirm(self, thesis_id: str) -> bool:
        return await self._storage.update_thesis(
            thesis_id, self._workspace, confirmed=True,
        )

    async def delete(self, thesis_id: str) -> bool:
        return await self._storage.delete_thesis(thesis_id, self._workspace)

    # ------------------------------------------------------------------
    # Thesis generation
    # ------------------------------------------------------------------

    async def generate_from_theme(self, theme: str) -> list[Thesis]:
        """Generate opinionated thesis statements from events under a theme.

        Uses LLM to analyze recent events tagged with this theme and produce
        specific, falsifiable investment theses. Created as unconfirmed.

        Returns list of newly created Thesis objects (pending user confirmation).
        """
        if not self._llm:
            return []

        # Get events tagged with this theme
        events = await self._storage.get_by_thesis(theme, self._workspace)
        if len(events) < 2:
            return []  # Not enough evidence to form theses

        # Build context text for LLM
        event_texts = []
        for e in events[:20]:  # Cap to avoid token overflow
            title = e.title or ""
            summary = e.summary or ""
            snippet = e.content[:300] if e.content else ""
            event_texts.append(f"- [{title}] {summary}\n  {snippet}")
        events_text = "\n".join(event_texts)

        # Fetch existing theses to pass to LLM for dedup
        existing = await self.list()
        existing_texts_list = [t.text for t in existing]
        existing_texts_lower = {t.text.lower().strip() for t in existing}

        # Generate via LLM (pass existing theses so it avoids duplicates)
        raw_theses = await self._llm.generate_theses(
            theme, events_text, existing_theses=existing_texts_list,
        )
        if not raw_theses:
            return []

        created = []
        for t in raw_theses:
            text = t.get("text", "").strip()
            if not text or text.lower() in existing_texts_lower:
                continue
            stance = t.get("stance", "neutral")
            if stance not in ("bullish", "bearish", "neutral"):
                stance = "neutral"
            thesis = await self.create(
                text=text,
                stance=stance,
                theme=theme,
                created_by="inferred",
            )
            created.append(thesis)
            existing_texts_lower.add(text.lower())

        log.info(
            "Generated %d theses for theme '%s' from %d events",
            len(created), theme, len(events),
        )
        return created

    async def generate_all_themes(self, themes: list[str], min_events: int = 3) -> dict:
        """Generate theses for all themes that have enough events.

        Returns {"theme": count_generated} summary.
        """
        results = {}
        for theme in themes:
            try:
                created = await self.generate_from_theme(theme)
                if created:
                    results[theme] = len(created)
            except Exception:
                log.exception("Thesis generation failed for theme '%s'", theme)
        return results

    # ------------------------------------------------------------------
    # Evidence
    # ------------------------------------------------------------------

    async def get_evidence(self, thesis_id: str, limit: int = 50) -> list[ThesisEvidence]:
        return await self._storage.get_evidence_for_thesis(thesis_id, self._workspace, limit)

    async def evaluate_event(self, event: KnowledgeEvent) -> list[ThesisEvidence]:
        """Assess event impact on all matching active theses. Returns recorded evidence."""
        if not self._llm:
            return []

        theses = await self._storage.list_theses(
            self._workspace, status="active", confirmed_only=True,
        )
        if not theses:
            return []

        # Pre-filter: only theses whose theme matches event's thesis_links
        event_themes = set(event.thesis_links or [])
        if event_themes:
            candidates = [t for t in theses if t.theme and t.theme in event_themes]
        else:
            candidates = []

        # If no theme match, fall back to all active theses (capped)
        if not candidates:
            candidates = theses

        candidates = candidates[:MAX_CANDIDATES_PER_EVENT]

        results: list[ThesisEvidence] = []
        for thesis in candidates:
            try:
                assessment = await self._llm.assess_thesis_impact(
                    event_content=event.content[:3000],
                    event_summary=event.summary or event.title,
                    thesis_text=thesis.text,
                    thesis_stance=thesis.stance.value if hasattr(thesis.stance, "value") else thesis.stance,
                )
                impact = assessment.get("impact", "neutral")
                if impact == "neutral" and assessment.get("confidence_delta", 0) == 0:
                    continue  # skip irrelevant assessments

                evidence = ThesisEvidence(
                    thesis_id=thesis.id,
                    event_id=event.id,
                    workspace_id=self._workspace,
                    impact=EvidenceImpact(impact),
                    confidence_delta=assessment.get("confidence_delta", 0.0),
                    rationale=assessment.get("rationale", ""),
                )
                await self._storage.record_evidence(evidence)
                results.append(evidence)
            except Exception:
                log.exception("Failed to assess thesis %s for event %s", thesis.id, event.id)

        return results