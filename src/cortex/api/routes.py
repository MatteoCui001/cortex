"""
REST API routes -- the primary interface for both humans and agents.
"""
from __future__ import annotations

import logging
import uuid
from typing import Optional

logger = logging.getLogger(__name__)

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from cortex.use_cases.ingest import IngestUseCase
from cortex.use_cases.analyze import AnalyzeUseCase

router = APIRouter()


# ------------------------------------------------------------------
# Health / Readiness
# ------------------------------------------------------------------

@router.get("/health")
async def health():
    """Liveness probe -- always returns 200 if the process is up."""
    return {"status": "ok"}


@router.get("/ready")
async def ready(request: Request):
    """Readiness probe -- checks that storage is connected."""
    storage = getattr(request.app.state, "storage", None)
    if storage is None:
        return {"status": "unavailable", "storage": False}
    try:
        # Quick connectivity check
        await storage.get_notifications("__probe__", limit=1)
        return {"status": "ready", "storage": True}
    except Exception:
        logger.warning("Readiness probe failed", exc_info=True)
        return {"status": "degraded", "storage": False}


# ------------------------------------------------------------------
# Request/Response schemas
# ------------------------------------------------------------------

class SearchRequest(BaseModel):
    query: str
    mode: str = Field("hybrid", pattern="^(semantic|fulltext|hybrid)$")
    limit: int = Field(10, ge=1, le=100)
    type_filter: Optional[str] = None

class EventCreate(BaseModel):
    title: str
    content: str
    source: str = "api"
    event_type: str = "note"

class EventResponse(BaseModel):
    id: str
    type: str
    title: str
    summary: str
    content: str = ""
    tags: list[str]
    thesis_links: list[str]
    confidence: float
    source: str
    source_path: Optional[str] = None
    source_type: Optional[str] = None
    temporality: Optional[str] = None
    user_annotation: Optional[str] = None
    raw_input_type: Optional[str] = None
    created_at: str

class SearchResultResponse(BaseModel):
    event: EventResponse
    score: float
    match_type: str

class IngestRequest(BaseModel):
    content: Optional[str] = None
    url: Optional[str] = None
    title: str = ""
    source: str = "api"
    raw_input_type: str = "text"
    user_annotation: Optional[str] = None
    workspace_id: str = "default"

class EventPatchRequest(BaseModel):
    tags: Optional[list[str]] = None
    thesis_links: Optional[list[str]] = None
    title: Optional[str] = None

class BulkNotificationRequest(BaseModel):
    action: str = Field(..., pattern="^(read|ack|dismiss)$")
    ids: Optional[list[str]] = None
    status_filter: Optional[str] = None

class AnnotateRequest(BaseModel):
    annotation: str
    stance: Optional[str] = None

class AnnotationResponse(BaseModel):
    id: str
    target_type: str
    target_id: str
    annotation: Optional[str]
    stance: Optional[str]
    created_at: str

class NotificationResponse(BaseModel):
    trigger_type: str
    title: str
    body: str
    priority: str
    related_event_ids: list[str] = []


class NotificationDetailResponse(BaseModel):
    id: str
    source_kind: str
    source_id: str
    title: str
    body: str
    priority: str
    status: str
    channel: str
    signal_id: Optional[str] = None
    related_event_ids: list[str] = []
    created_at: str
    delivered_at: Optional[str] = None
    acted_at: Optional[str] = None


class SignalResponse(BaseModel):
    id: str
    new_event_id: str
    existing_event_id: str
    signal_type: str
    topic: Optional[str]
    summary: Optional[str]
    confidence: float
    priority_score: float
    evidence_strength: Optional[str]
    rationale: Optional[str]
    evidence_event_ids: list[str] = []
    thesis_links: list[str] = []
    created_at: str


class SignalFeedbackRequest(BaseModel):
    verdict: str = Field(..., pattern="^(useful|not_useful|wrong|save_for_later)$")
    note: Optional[str] = None


class SignalFeedbackResponse(BaseModel):
    id: str
    signal_id: str
    verdict: str
    note: Optional[str]
    created_at: str


class EntityResponse(BaseModel):
    id: str
    type: str
    name: str
    aliases: list[str]
    score: float
    mention_count: int


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------

# --- Search (Store -> Human + Agent) ---

@router.post("/search", response_model=list[SearchResultResponse])
async def search(req: SearchRequest, request: Request):
    """Unified search endpoint: semantic, fulltext, or hybrid."""
    search_uc = request.app.state.search
    if req.mode == "semantic":
        results = await search_uc.semantic(req.query, limit=req.limit, type_filter=req.type_filter)
    elif req.mode == "fulltext":
        results = await search_uc.fulltext(req.query, limit=req.limit, type_filter=req.type_filter)
    else:
        results = await search_uc.hybrid(req.query, limit=req.limit, type_filter=req.type_filter)

    return [
        SearchResultResponse(
            event=_event_to_response(r.event),
            score=r.score,
            match_type=r.match_type,
        )
        for r in results
    ]


@router.get("/search/related/{event_id}", response_model=list[SearchResultResponse])
async def related(event_id: str, request: Request, limit: int = 10):
    """Find events related through shared entities."""
    results = await request.app.state.search.related(event_id, limit=limit)
    return [
        SearchResultResponse(
            event=_event_to_response(r.event),
            score=r.score,
            match_type=r.match_type,
        )
        for r in results
    ]


# --- Entity Search ---

@router.get("/entities/search", response_model=list[EntityResponse])
async def search_entities(
    request: Request,
    q: str = Query(..., description="Search query"),
    types: Optional[str] = Query(None, description="Comma-separated entity types"),
    limit: int = Query(20, ge=1, le=100),
):
    """Semantic search over entities."""
    entity_types = [t.strip() for t in types.split(",")] if types else None
    results = await request.app.state.search.search_entities(
        q, entity_types=entity_types, limit=limit,
    )
    return [
        EntityResponse(
            id=r["id"],
            type=r["type"],
            name=r["name"],
            aliases=r.get("aliases", []),
            score=r["score"],
            mention_count=r["mention_count"],
        )
        for r in results
    ]


@router.get("/entities/{entity_id}/events")
async def entity_events(entity_id: str, request: Request, limit: int = 50):
    """Get all events mentioning a specific entity."""
    events = await request.app.state.search.entity_events(entity_id, limit=limit)
    return [_event_to_response(e) for e in events]


# --- Events (Agent -> Store write path) ---

@router.post("/events", response_model=EventResponse, status_code=201)
async def create_event(body: EventCreate, request: Request):
    """Create a new knowledge event. Primary agent write path."""
    ingest_uc = request.app.state.ingest
    event = await ingest_uc.import_text(
        title=body.title,
        content=body.content,
        source=body.source,
        event_type=body.event_type,
    )
    return _event_to_response(event)


@router.get("/events", response_model=list[EventResponse])
async def list_events(
    request: Request,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    days: Optional[int] = Query(None, ge=1, le=365),
):
    """List recent events, newest first."""
    workspace = request.app.state.config.get("workspace", "default")
    events = await request.app.state.storage.list_events(
        workspace_id=workspace, limit=limit, offset=offset, days=days,
    )
    return [_event_to_response(e) for e in events]


@router.get("/events/{event_id}", response_model=EventResponse)
async def get_event(event_id: str, request: Request):
    """Get a specific event by ID."""
    try:
        uuid.UUID(event_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Event not found")
    workspace = request.app.state.config.get("workspace", "default")
    event = await request.app.state.storage.get_event(event_id, workspace_id=workspace)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return _event_to_response(event)


# --- Analysis (Store -> Human + Agent) ---

@router.get("/thesis")
async def thesis_coverage(request: Request, trend_window_days: int = 14):
    """Thesis coverage report with confidence trend."""
    results = await request.app.state.analyze.thesis_coverage(
        trend_window_days=trend_window_days,
    )
    return [
        {
            "thesis": t.thesis_name,
            "event_count": t.event_count,
            "avg_confidence": round(t.avg_confidence, 3),
            "type_distribution": t.type_distribution,
            "latest_update": t.latest_update.isoformat() if t.latest_update else None,
            "days_since_update": t.days_since_update,
            "trend_direction": t.trend_direction,
            "confidence_delta": t.confidence_delta,
            "recent_avg_confidence": round(t.recent_avg_confidence, 3) if t.recent_avg_confidence is not None else None,
            "previous_avg_confidence": round(t.previous_avg_confidence, 3) if t.previous_avg_confidence is not None else None,
            "recent_event_count": t.recent_event_count,
        }
        for t in results
    ]


@router.get("/thesis/{thesis_name}")
async def thesis_evidence(thesis_name: str, request: Request):
    """All events supporting a specific thesis."""
    events = await request.app.state.analyze.thesis_evidence(thesis_name)
    return [_event_to_response(e) for e in events]


@router.get("/stale")
async def stale_events(request: Request, days: int = 30):
    """Events not updated in N days (need re-evaluation)."""
    events = await request.app.state.analyze.stale_events(days)
    return [_event_to_response(e) for e in events]


@router.get("/stats")
async def stats(request: Request):
    """Workspace statistics."""
    return await request.app.state.analyze.stats()


@router.get("/entity/{object_id}/graph")
async def entity_graph(object_id: str, request: Request):
    """Get all relations for an entity or event."""
    return await request.app.state.analyze.entity_graph(object_id)


@router.get("/digest")
async def digest(request: Request, days: int = 1):
    """Daily research digest."""
    result = await request.app.state.analyze.daily_digest(days)
    # Convert non-serializable objects
    if "high_confidence" in result:
        result["high_confidence"] = [_event_to_response(e) for e in result["high_confidence"]]
    if "stale_theses" in result:
        result["stale_theses"] = [
            {
                "thesis": t.thesis_name,
                "event_count": t.event_count,
                "days_since_update": t.days_since_update,
            }
            for t in result["stale_theses"]
        ]
    if "thesis_trends" in result:
        result["thesis_trends"] = [
            {
                "thesis": t.thesis_name,
                "trend_direction": t.trend_direction,
                "confidence_delta": t.confidence_delta,
                "recent_avg_confidence": round(t.recent_avg_confidence, 3) if t.recent_avg_confidence is not None else None,
                "recent_event_count": t.recent_event_count,
            }
            for t in result["thesis_trends"]
        ]
    return result


@router.post("/digest/push")
async def digest_push(request: Request, days: int = 1):
    """Generate today's digest and push it as a notification.

    Returns the notification if created, or a message if skipped (dedup/empty).
    """
    from cortex.use_cases.digest_push import push_digest

    workspace = request.app.state.config.get("workspace", "default")
    notif = await push_digest(
        request.app.state.storage,
        request.app.state.analyze,
        workspace_id=workspace,
        days=days,
    )
    if notif:
        return {
            "status": "created",
            "notification_id": notif.id,
            "title": notif.title,
        }
    return {"status": "skipped", "reason": "empty digest or already sent today"}


# --- Phase 3: Unified Ingest ---

@router.post("/events/ingest", response_model=EventResponse, status_code=201)
async def ingest_event(body: IngestRequest, request: Request):
    """Unified ingest endpoint: text or link."""
    workspace = body.workspace_id or request.app.state.workspace

    if body.url:
        from cortex.use_cases.ingest_link import IngestLinkUseCase
        link_uc = IngestLinkUseCase(
            request.app.state.storage,
            request.app.state.embedding,
            request.app.state.llm,
            request.app.state.file_store,
            workspace,
        )
        event = await link_uc.import_link(body.url, user_annotation=body.user_annotation)
    else:
        from cortex.use_cases.ingest import IngestUseCase
        text_uc = IngestUseCase(
            request.app.state.storage,
            request.app.state.embedding,
            request.app.state.llm,
            workspace,
        )
        event = await text_uc.import_text(
            title=body.title,
            content=body.content or "",
            source=body.source,
            raw_input_type=body.raw_input_type,
            user_annotation=body.user_annotation,
        )

    if not event:
        raise HTTPException(status_code=400, detail="Could not ingest content")

    # Run signal detection asynchronously (best-effort, don't block response)
    import asyncio
    async def _background_analyze():
        import logging
        log = logging.getLogger(__name__)
        try:
            from cortex.use_cases.ingest import IngestUseCase as _IUC
            ingest_uc = _IUC(
                request.app.state.storage,
                request.app.state.embedding,
                request.app.state.llm,
                workspace,
            )
            signals = await ingest_uc.post_ingest_analyze(event)
            if signals:
                from cortex.use_cases.push_detector import PushDetector
                from cortex.use_cases.notification_manager import NotificationManager
                detector = PushDetector(request.app.state.storage, workspace)
                webhook_cfg = request.app.state.config.get(
                    "notifications", {},
                ).get("webhook", {})
                nm = NotificationManager(
                    request.app.state.storage,
                    detector,
                    webhook_cfg=webhook_cfg,
                    workspace_id=workspace,
                )
                created = await nm.process(signals)
                if created:
                    log.info(
                        "post_ingest_analyze: %d notification(s) created for event %s",
                        len(created), event.id,
                    )
        except Exception:
            log.exception("post_ingest_analyze failed for event %s", event.id)

    asyncio.create_task(_background_analyze())

    return _event_to_response(event)


# --- Event editing ---

@router.patch("/events/{event_id}", response_model=EventResponse)
async def patch_event(event_id: str, body: EventPatchRequest, request: Request):
    """Partial update of event fields (tags, thesis_links, title)."""
    workspace = request.app.state.config.get("workspace", "default")
    updated = await request.app.state.storage.update_event_fields(
        event_id, workspace,
        tags=body.tags,
        thesis_links=body.thesis_links,
        title=body.title,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Event not found")
    event = await request.app.state.storage.get_event(event_id)
    return _event_to_response(event)


# --- Phase 3: Annotations ---

@router.post("/events/{event_id}/annotate", response_model=AnnotationResponse)
async def annotate_event(event_id: str, body: AnnotateRequest, request: Request):
    """Add user annotation to an event."""
    import uuid
    from cortex.domain.entities import Annotation
    from cortex.domain.stance import parse_user_stance

    workspace = request.app.state.config.get("workspace", "default")
    stance = body.stance or parse_user_stance(body.annotation)

    annotation = Annotation(
        id=str(uuid.uuid4()),
        workspace_id=workspace,
        target_type="event",
        target_id=event_id,
        annotation=body.annotation,
        stance=stance,
    )
    aid = await request.app.state.storage.create_annotation(annotation)

    # Sync user_stance back to the event so signal scoring picks it up
    if stance:
        await request.app.state.storage.update_event_user_stance(event_id, stance)

    return AnnotationResponse(
        id=aid,
        target_type="event",
        target_id=event_id,
        annotation=body.annotation,
        stance=stance,
        created_at=annotation.created_at.isoformat() if annotation.created_at else "",
    )


@router.get("/annotations/{target_type}/{target_id}")
async def get_annotations(target_type: str, target_id: str, request: Request):
    """Get all annotations for a target."""
    workspace = request.app.state.config.get("workspace", "default")
    annotations = await request.app.state.storage.get_annotations(workspace, target_type, target_id)
    return [
        AnnotationResponse(
            id=a.id,
            target_type=a.target_type,
            target_id=a.target_id,
            annotation=a.annotation,
            stance=a.stance,
            created_at=a.created_at.isoformat() if a.created_at else "",
        )
        for a in annotations
    ]


# --- Phase 4: Persistent Notifications ---

@router.get("/notifications", response_model=list[NotificationDetailResponse])
async def get_notifications(
    request: Request,
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    refresh: bool = Query(False),
):
    """Get persistent notifications (optionally refresh via detector first)."""
    workspace = request.app.state.config.get("workspace", "default")
    if refresh:
        from cortex.use_cases.push_detector import PushDetector
        from cortex.use_cases.notification_manager import NotificationManager
        detector = PushDetector(request.app.state.storage, workspace)
        webhook_cfg = request.app.state.config.get("notifications", {}).get("webhook", {})
        manager = NotificationManager(
            request.app.state.storage, detector,
            webhook_cfg=webhook_cfg, workspace_id=workspace,
        )
        await manager.process()
    results = await request.app.state.storage.get_notifications(
        workspace, status=status, limit=limit,
    )
    return [_notification_to_response(n) for n in results]


@router.post("/notifications/{notification_id}/read",
             response_model=NotificationDetailResponse)
async def mark_notification_read(notification_id: str, request: Request):
    """Mark a notification as read."""
    from cortex.domain.entities import NotificationStatus
    return await _transition_notification(request, notification_id, NotificationStatus.READ)


@router.post("/notifications/{notification_id}/ack",
             response_model=NotificationDetailResponse)
async def mark_notification_acked(notification_id: str, request: Request):
    """Mark a notification as acknowledged."""
    from cortex.domain.entities import NotificationStatus
    return await _transition_notification(request, notification_id, NotificationStatus.ACKED)


@router.post("/notifications/{notification_id}/dismiss",
             response_model=NotificationDetailResponse)
async def mark_notification_dismissed(notification_id: str, request: Request):
    """Dismiss a notification."""
    from cortex.domain.entities import NotificationStatus
    return await _transition_notification(request, notification_id, NotificationStatus.DISMISSED)


@router.post("/notifications/{notification_id}/deliver",
             response_model=NotificationDetailResponse)
async def mark_notification_delivered(notification_id: str, request: Request):
    """Confirm that a notification was successfully delivered to the user
    via an external channel (e.g. WeChat iLink push).

    Only valid for notifications in ``pending`` status.
    """
    from cortex.domain.entities import NotificationStatus
    return await _transition_notification(request, notification_id, NotificationStatus.DELIVERED)


@router.post("/notifications/bulk-action")
async def bulk_notification_action(body: BulkNotificationRequest, request: Request):
    """Bulk transition notifications by IDs or status filter."""
    from cortex.domain.entities import NotificationStatus
    from cortex.use_cases.push_detector import PushDetector
    from cortex.use_cases.notification_manager import NotificationManager

    action_map = {"read": NotificationStatus.READ, "ack": NotificationStatus.ACKED, "dismiss": NotificationStatus.DISMISSED}
    new_status = action_map[body.action]

    workspace = request.app.state.config.get("workspace", "default")
    storage = request.app.state.storage
    detector = PushDetector(storage, workspace)
    webhook_cfg = request.app.state.config.get("notifications", {}).get("webhook", {})
    manager = NotificationManager(storage, detector, webhook_cfg=webhook_cfg, workspace_id=workspace)

    # Resolve notification IDs
    ids = body.ids or []
    if not ids and body.status_filter:
        notifs = await storage.get_notifications(workspace, status=body.status_filter, limit=500)
        ids = [n.id for n in notifs]

    updated = 0
    failed = 0
    for nid in ids:
        try:
            await manager.transition(nid, new_status)
            updated += 1
        except (ValueError, Exception):
            failed += 1
    return {"updated": updated, "failed": failed}


async def _transition_notification(request, notification_id, new_status):
    """Shared transition logic for notification action endpoints."""
    from cortex.use_cases.push_detector import PushDetector
    from cortex.use_cases.notification_manager import NotificationManager
    workspace = request.app.state.config.get("workspace", "default")
    detector = PushDetector(request.app.state.storage, workspace)
    webhook_cfg = request.app.state.config.get("notifications", {}).get("webhook", {})
    manager = NotificationManager(
        request.app.state.storage, detector,
        webhook_cfg=webhook_cfg, workspace_id=workspace,
    )
    try:
        notif = await manager.transition(notification_id, new_status)
    except ValueError as exc:
        msg = str(exc)
        if "not found" in msg:
            raise HTTPException(status_code=404, detail=msg)
        raise HTTPException(status_code=409, detail=msg)
    except Exception:
        logger.exception("Unexpected error transitioning notification %s", notification_id)
        raise HTTPException(
            status_code=500,
            detail="Internal error processing notification",
        )
    return _notification_to_response(notif)


# --- Phase 3.6: Signals ---

@router.get("/signals", response_model=list[SignalResponse])
async def get_signals(
    request: Request,
    event_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    """Get persisted signals, optionally filtered by originating event."""
    workspace = request.app.state.config.get("workspace", "default")
    signals = await request.app.state.storage.get_signals(
        workspace, event_id=event_id, limit=limit,
    )
    return [_signal_to_response(s) for s in signals]


@router.post("/signals/{signal_id}/feedback",
             response_model=SignalFeedbackResponse, status_code=201)
async def submit_signal_feedback(
    signal_id: str,
    body: SignalFeedbackRequest,
    request: Request,
):
    """Submit feedback on a signal."""
    from cortex.domain.entities import SignalFeedback
    workspace = request.app.state.config.get("workspace", "default")
    feedback = SignalFeedback(
        signal_id=signal_id,
        verdict=body.verdict,
        workspace_id=workspace,
        note=body.note,
    )
    fid = await request.app.state.storage.create_signal_feedback(feedback)
    return SignalFeedbackResponse(
        id=fid,
        signal_id=signal_id,
        verdict=body.verdict,
        note=body.note,
        created_at=feedback.created_at.isoformat() if feedback.created_at else "",
    )


@router.get("/signals/thesis-feedback")
async def thesis_feedback_stats(request: Request):
    """Thesis-level feedback aggregation."""
    workspace = request.app.state.config.get("workspace", "default")
    return await request.app.state.storage.get_thesis_feedback_stats(workspace)


# --- Settings (runtime LLM configuration) ---

class LLMSettingsRequest(BaseModel):
    api_key: str = ""
    model: str = ""
    base_url: str = ""


@router.get("/settings")
async def get_settings(request: Request):
    """Get current system settings (LLM status, workspace info)."""
    llm = request.app.state.llm
    cfg = request.app.state.config
    llm_cfg = cfg.get("llm", {}).get("openrouter", {})
    return {
        "llm": {
            "configured": llm is not None,
            "model": getattr(llm, "_model", "") if llm else llm_cfg.get("model", ""),
            "base_url": getattr(llm, "_base_url", "") if llm else llm_cfg.get("base_url", ""),
            "thesis_list": getattr(llm, "_thesis_list", []) if llm else llm_cfg.get("thesis_list", []),
        },
        "workspace": cfg.get("workspace", "default"),
        "embedding_model": cfg.get("embedding", {}).get("local", {}).get("model", ""),
    }


@router.put("/settings/llm")
async def update_llm_settings(body: LLMSettingsRequest, request: Request):
    """Update LLM configuration at runtime. Reinitializes LLM adapter and use cases."""
    cfg = request.app.state.config
    llm_cfg = cfg.get("llm", {}).get("openrouter", {})
    workspace = cfg.get("workspace", "default")

    api_key = body.api_key.strip()
    if not api_key:
        # Clear LLM
        request.app.state.llm = None
        request.app.state.ingest = IngestUseCase(
            request.app.state.storage, request.app.state.embedding, None, workspace,
        )
        request.app.state.analyze = AnalyzeUseCase(
            request.app.state.storage, workspace, llm=None,
        )
        return {"status": "cleared", "llm_configured": False}

    from cortex.adapters.llm.adapter import OpenRouterLLM
    llm = OpenRouterLLM(
        api_key=api_key,
        model=body.model or llm_cfg.get("model", "anthropic/claude-haiku-4.5"),
        base_url=body.base_url or llm_cfg.get("base_url", "https://openrouter.ai/api/v1"),
        chat_endpoint=llm_cfg.get("chat_endpoint", "/chat/completions"),
        thesis_list=llm_cfg.get("thesis_list"),
    )

    request.app.state.llm = llm
    request.app.state.ingest = IngestUseCase(
        request.app.state.storage, request.app.state.embedding, llm, workspace,
    )
    request.app.state.analyze = AnalyzeUseCase(
        request.app.state.storage, workspace, llm=llm,
    )
    return {"status": "updated", "llm_configured": True, "model": llm._model}


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _signal_to_response(s) -> SignalResponse:
    return SignalResponse(
        id=s.id,
        new_event_id=s.new_event_id,
        existing_event_id=s.existing_event_id,
        signal_type=s.signal_type,
        topic=s.topic,
        summary=s.summary,
        confidence=s.confidence,
        priority_score=s.priority_score,
        evidence_strength=s.evidence_strength,
        rationale=s.rationale,
        evidence_event_ids=s.evidence_event_ids,
        thesis_links=getattr(s, "thesis_links", []),
        created_at=s.created_at.isoformat() if s.created_at else "",
    )


def _notification_to_response(n) -> NotificationDetailResponse:
    return NotificationDetailResponse(
        id=n.id,
        source_kind=n.source_kind,
        source_id=n.source_id,
        title=n.title,
        body=n.body,
        priority=n.priority,
        status=n.status.value if hasattr(n.status, "value") else str(n.status),
        channel=n.channel.value if hasattr(n.channel, "value") else str(n.channel),
        signal_id=n.signal_id,
        related_event_ids=n.related_event_ids,
        created_at=n.created_at.isoformat() if n.created_at else "",
        delivered_at=n.delivered_at.isoformat() if n.delivered_at else None,
        acted_at=n.acted_at.isoformat() if n.acted_at else None,
    )


def _event_to_response(event) -> EventResponse:
    return EventResponse(
        id=event.id,
        type=event.type.value if hasattr(event.type, "value") else str(event.type),
        title=event.title,
        summary=event.summary,
        content=getattr(event, "content", ""),
        tags=event.tags,
        thesis_links=event.thesis_links,
        confidence=event.confidence,
        source=event.source,
        source_path=getattr(event, "source_path", None),
        source_type=getattr(event, "source_type", None),
        temporality=getattr(event, "temporality", None),
        user_annotation=getattr(event, "user_annotation", None),
        raw_input_type=getattr(event, "raw_input_type", None),
        created_at=event.created_at.isoformat() if hasattr(event.created_at, "isoformat") else str(event.created_at),
    )