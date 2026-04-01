"""
REST API routes -- the primary interface for both humans and agents.
"""
from __future__ import annotations

import logging
import uuid
from typing import Optional

logger = logging.getLogger(__name__)

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request
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
    relevance: Optional[float] = None
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


@router.get("/graph/overview")
async def graph_overview(request: Request):
    """Get thesis-centered entity graph for the overview page."""
    storage = request.app.state.storage
    workspace_id = getattr(request.state, "workspace_id", "default")
    data = await storage.get_thesis_entity_graph(
        workspace_id, entity_limit=50, per_thesis_limit=8
    )
    # Include all configured theses so frontend can show them even without entities
    llm = request.app.state.llm
    cfg = request.app.state.config
    llm_cfg = cfg.get("llm", {}).get("openrouter", {})
    all_theses = getattr(llm, "_thesis_list", []) if llm else llm_cfg.get("thesis_list", [])
    data["all_theses"] = all_theses or []
    return data


@router.get("/entities/top", response_model=list[EntityResponse])
async def top_entities(request: Request, limit: int = Query(30, ge=1, le=200)):
    """Get top entities by mention count for overview graph."""
    all_entities = await request.app.state.storage.get_all_entities()
    sorted_ents = sorted(all_entities, key=lambda e: e["mention_count"], reverse=True)[:limit]
    return [
        EntityResponse(
            id=e["id"],
            type=e["type"],
            name=e["name"],
            aliases=[],
            score=1.0,
            mention_count=e["mention_count"],
        )
        for e in sorted_ents
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
    import asyncio as _aio
    ingest_uc = request.app.state.ingest
    event = await ingest_uc.import_text(
        title=body.title,
        content=body.content,
        source=body.source,
        event_type=body.event_type,
    )
    if not event:
        raise HTTPException(status_code=422, detail="Content filtered by quality gate")

    # Background: thesis evaluation + contradiction detection (same as /events/ingest)
    workspace = request.app.state.config.get("workspace", "default")

    async def _bg_evaluate():
        log = logging.getLogger(__name__)
        # Thesis impact
        try:
            from cortex.use_cases.thesis import ThesisUseCase
            thesis_uc = ThesisUseCase(
                request.app.state.storage, workspace,
                llm=request.app.state.llm,
            )
            evidence = await thesis_uc.evaluate_event(event)
            if evidence:
                log.info("POST /events thesis_evaluate: %d evidence(s) for %s", len(evidence), event.id)
        except Exception:
            log.exception("POST /events thesis evaluate failed for %s", event.id)
        # Contradiction detection
        try:
            signals = await ingest_uc.post_ingest_analyze(event)
            if signals:
                log.info("POST /events post_ingest_analyze: %d signal(s) for %s", len(signals), event.id)
        except Exception:
            log.exception("POST /events post_ingest_analyze failed for %s", event.id)

    _aio.create_task(_bg_evaluate())
    return _event_to_response(event)


@router.get("/events", response_model=list[EventResponse])
async def list_events(
    request: Request,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    days: Optional[int] = Query(None, ge=1, le=365),
    sort: str = Query("recent", pattern="^(recent|relevance)$"),
):
    """List events. sort=recent (default) or sort=relevance."""
    workspace = request.app.state.config.get("workspace", "default")
    events = await request.app.state.storage.list_events(
        workspace_id=workspace, limit=limit, offset=offset, days=days,
        sort=sort,
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

        # Thesis impact evaluation
        try:
            from cortex.use_cases.thesis import ThesisUseCase
            thesis_uc = ThesisUseCase(
                request.app.state.storage, workspace,
                llm=request.app.state.llm,
            )
            evidence = await thesis_uc.evaluate_event(event)
            if evidence:
                log.info(
                    "thesis_evaluate: %d evidence(s) for event %s",
                    len(evidence), event.id,
                )
                # Create notifications for significant thesis evidence
                from cortex.use_cases.push_detector import PushDetector as _PD
                from cortex.use_cases.notification_manager import NotificationManager as _NM
                _det = _PD(request.app.state.storage, workspace)
                # Build thesis_id -> text lookup
                theses = await request.app.state.storage.list_theses(workspace, confirmed_only=True)
                thesis_texts = {t.id: t.text for t in theses}
                thesis_pushes = _det.check_thesis_evidence(evidence, thesis_texts)
                if thesis_pushes:
                    _wh = request.app.state.config.get("notifications", {}).get("webhook", {})
                    _nm = _NM(request.app.state.storage, _det, webhook_cfg=_wh, workspace_id=workspace)
                    for push in thesis_pushes:
                        dedup_key = f"thesis_evidence:{push.related_event_ids[0]}:{push.title[:30]}"
                        if await request.app.state.storage.check_dedup(workspace, dedup_key):
                            continue
                        notif = _nm._push_to_notification(push, dedup_key)
                        await request.app.state.storage.insert_notification(notif)
                    log.info(
                        "thesis_evidence: %d notification(s) for event %s",
                        len(thesis_pushes), event.id,
                    )
        except Exception:
            log.exception("thesis evaluate_event failed for event %s", event.id)

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
        relevance=getattr(event, "relevance", None),
        created_at=event.created_at.isoformat() if hasattr(event.created_at, "isoformat") else str(event.created_at),
    )


# ------------------------------------------------------------------
# Phase 6: Structured Theses
# ------------------------------------------------------------------

class ThesisCreate(BaseModel):
    text: str
    stance: str = "neutral"
    theme: Optional[str] = None
    expires_at: Optional[str] = None
    created_by: str = "manual"

class ThesisPatch(BaseModel):
    text: Optional[str] = None
    stance: Optional[str] = None
    theme: Optional[str] = None
    expires_at: Optional[str] = None
    confirmed: Optional[bool] = None

class ThesisResponse(BaseModel):
    id: str
    text: str
    stance: str
    theme: Optional[str] = None
    status: str
    expires_at: Optional[str] = None
    created_by: str
    confirmed: bool
    confidence: float
    created_at: str
    updated_at: str

class ThesisEvidenceResponse(BaseModel):
    id: str
    thesis_id: str
    event_id: str
    impact: str
    confidence_delta: float
    rationale: Optional[str] = None
    created_at: str
    event_title: Optional[str] = None
    event_summary: Optional[str] = None


def _thesis_to_response(t) -> dict:
    return ThesisResponse(
        id=t.id,
        text=t.text,
        stance=t.stance.value if hasattr(t.stance, "value") else t.stance,
        theme=t.theme,
        status=t.status.value if hasattr(t.status, "value") else t.status,
        expires_at=t.expires_at.isoformat() if t.expires_at and hasattr(t.expires_at, "isoformat") else None,
        created_by=t.created_by.value if hasattr(t.created_by, "value") else t.created_by,
        confirmed=t.confirmed,
        confidence=round(t.confidence, 4),
        created_at=t.created_at.isoformat() if t.created_at and hasattr(t.created_at, "isoformat") else "",
        updated_at=t.updated_at.isoformat() if t.updated_at and hasattr(t.updated_at, "isoformat") else "",
    )


def _evidence_to_response(e) -> dict:
    return ThesisEvidenceResponse(
        id=e.id,
        thesis_id=e.thesis_id,
        event_id=e.event_id,
        impact=e.impact.value if hasattr(e.impact, "value") else e.impact,
        confidence_delta=round(e.confidence_delta, 4),
        rationale=e.rationale,
        created_at=e.created_at.isoformat() if e.created_at and hasattr(e.created_at, "isoformat") else "",
    )


def _get_thesis_uc(request: Request):
    from cortex.use_cases.thesis import ThesisUseCase
    storage = request.app.state.storage
    workspace = request.app.state.workspace
    llm = getattr(request.app.state, "llm", None)
    return ThesisUseCase(storage, workspace, llm=llm)


@router.get("/theses", response_model=list[ThesisResponse])
async def list_theses(
    request: Request,
    status: Optional[str] = None,
    theme: Optional[str] = None,
    confirmed_only: bool = False,
):
    uc = _get_thesis_uc(request)
    theses = await uc.list(status=status, theme=theme, confirmed_only=confirmed_only)
    return [_thesis_to_response(t) for t in theses]


@router.post("/theses", response_model=ThesisResponse, status_code=201)
async def create_thesis(body: ThesisCreate, request: Request):
    from datetime import datetime, timezone
    uc = _get_thesis_uc(request)
    expires = None
    if body.expires_at:
        expires = datetime.fromisoformat(body.expires_at)
    thesis = await uc.create(
        text=body.text,
        stance=body.stance,
        theme=body.theme,
        expires_at=expires,
        created_by=body.created_by,
    )
    return _thesis_to_response(thesis)


@router.post("/theses/generate/{theme}")
async def generate_theses_for_theme(theme: str, request: Request):
    """Generate opinionated thesis statements from events under a theme using LLM."""
    if not getattr(request.app.state, "llm", None):
        raise HTTPException(503, "LLM not configured — set LLM_API_KEY to enable thesis generation")
    uc = _get_thesis_uc(request)
    created = await uc.generate_from_theme(theme)
    return [_thesis_to_response(t) for t in created]


@router.post("/theses/generate-all")
async def generate_theses_all(request: Request):
    """Generate theses for all configured themes."""
    cfg = request.app.state.config
    themes = cfg.get("llm", {}).get("openrouter", {}).get("thesis_list", [])
    if not themes:
        return {"generated": {}}
    uc = _get_thesis_uc(request)
    results = await uc.generate_all_themes(themes)
    return {"generated": results}


@router.get("/theses/suggestions")
async def thesis_suggestions(request: Request, min_events: int = Query(3, ge=1)):
    """Return themes with enough events that could be used to generate theses."""
    storage = request.app.state.storage
    workspace = request.app.state.workspace
    coverages = await storage.thesis_coverage(workspace)
    # Filter to themes with enough events
    suggestions = [
        {"theme": tc.thesis_name, "event_count": tc.event_count}
        for tc in coverages
        if tc.event_count >= min_events
    ]
    return suggestions


@router.get("/theses/{thesis_id}", response_model=ThesisResponse)
async def get_thesis(thesis_id: str, request: Request):
    uc = _get_thesis_uc(request)
    t = await uc.get(thesis_id)
    if not t:
        raise HTTPException(404, "Thesis not found")
    return _thesis_to_response(t)


@router.patch("/theses/{thesis_id}", response_model=ThesisResponse)
async def update_thesis(thesis_id: str, body: ThesisPatch, request: Request):
    from datetime import datetime
    uc = _get_thesis_uc(request)
    fields = {}
    if body.text is not None:
        fields["text"] = body.text
    if body.stance is not None:
        fields["stance"] = body.stance
    if body.theme is not None:
        fields["theme"] = body.theme
    if body.expires_at is not None:
        fields["expires_at"] = datetime.fromisoformat(body.expires_at)
    if body.confirmed is not None:
        fields["confirmed"] = body.confirmed
    if not fields:
        raise HTTPException(400, "No fields to update")
    ok = await uc.update(thesis_id, **fields)
    if not ok:
        raise HTTPException(404, "Thesis not found")
    t = await uc.get(thesis_id)
    return _thesis_to_response(t)


@router.post("/theses/{thesis_id}/resolve", response_model=ThesisResponse)
async def resolve_thesis(thesis_id: str, request: Request):
    uc = _get_thesis_uc(request)
    ok = await uc.resolve(thesis_id)
    if not ok:
        raise HTTPException(404, "Thesis not found")
    t = await uc.get(thesis_id)
    return _thesis_to_response(t)


@router.post("/theses/{thesis_id}/invalidate", response_model=ThesisResponse)
async def invalidate_thesis(thesis_id: str, request: Request):
    uc = _get_thesis_uc(request)
    ok = await uc.invalidate(thesis_id)
    if not ok:
        raise HTTPException(404, "Thesis not found")
    t = await uc.get(thesis_id)
    return _thesis_to_response(t)


@router.post("/theses/{thesis_id}/confirm", response_model=ThesisResponse)
async def confirm_thesis(thesis_id: str, request: Request, background_tasks: BackgroundTasks):
    uc = _get_thesis_uc(request)
    ok = await uc.confirm(thesis_id)
    if not ok:
        raise HTTPException(404, "Thesis not found")
    t = await uc.get(thesis_id)

    # Auto-backfill: evaluate recent events against newly confirmed thesis
    llm = getattr(request.app.state, "llm", None)
    if llm:
        storage = request.app.state.storage
        workspace = request.app.state.workspace

        async def _backfill_for_thesis():
            from cortex.use_cases.thesis import ThesisUseCase
            thesis_uc = ThesisUseCase(storage, workspace, llm=llm)
            events = await storage.list_events(workspace_id=workspace, limit=50, offset=0, sort="recent")
            count = 0
            for event in events:
                try:
                    evidence = await thesis_uc.evaluate_event(event)
                    count += len(evidence)
                except Exception:
                    pass
            if count:
                logger.info("Backfill after confirm: %d evidence(s) for thesis '%s'", count, t.text[:60])

        background_tasks.add_task(_backfill_for_thesis)

    return _thesis_to_response(t)


@router.delete("/theses/{thesis_id}")
async def delete_thesis(thesis_id: str, request: Request):
    uc = _get_thesis_uc(request)
    ok = await uc.delete(thesis_id)
    if not ok:
        raise HTTPException(404, "Thesis not found")
    return {"status": "deleted"}


@router.get("/theses/{thesis_id}/evidence", response_model=list[ThesisEvidenceResponse])
async def thesis_evidence_list(thesis_id: str, request: Request, limit: int = 50):
    uc = _get_thesis_uc(request)
    storage = request.app.state.storage
    workspace = request.app.state.workspace
    evidence = await uc.get_evidence(thesis_id, limit=limit)
    # Enrich evidence with event title/summary
    results = []
    for e in evidence:
        resp = _evidence_to_response(e)
        try:
            event = await storage.get_event(e.event_id, workspace)
            if event:
                resp.event_title = event.title
                resp.event_summary = event.summary
        except Exception:
            pass
        results.append(resp)
    return results


@router.post("/admin/backfill-evidence")
async def backfill_thesis_evidence(
    request: Request,
    limit: int = Query(100, ge=1, le=1000),
):
    """Backfill thesis evidence for existing events that have thesis_links but no evidence."""
    workspace = request.app.state.config.get("workspace", "default")
    storage = request.app.state.storage
    llm = request.app.state.llm
    if not llm:
        raise HTTPException(400, "LLM not configured — cannot evaluate theses")

    from cortex.use_cases.thesis import ThesisUseCase
    thesis_uc = ThesisUseCase(storage, workspace, llm=llm)

    # Get events that have thesis_links (candidates for evidence)
    events = await storage.list_events(
        workspace_id=workspace, limit=limit, offset=0, sort="recent",
    )
    stats = {"evaluated": 0, "evidence_created": 0, "skipped": 0, "errors": 0}
    for event in events:
        try:
            evidence = await thesis_uc.evaluate_event(event)
            if evidence:
                stats["evaluated"] += 1
                stats["evidence_created"] += len(evidence)
            else:
                stats["skipped"] += 1
        except Exception as e:
            logger.warning("Backfill failed for event %s: %s", event.id, e)
            stats["errors"] += 1
    return stats