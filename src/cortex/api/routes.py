"""
REST API routes -- the primary interface for both humans and agents.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

router = APIRouter()


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
    tags: list[str]
    thesis_links: list[str]
    confidence: float
    source: str
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
        q,
        entity_types=entity_types,
        limit=limit,
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


@router.get("/events/{event_id}", response_model=EventResponse)
async def get_event(event_id: str, request: Request):
    """Get a specific event by ID."""
    workspace = request.app.state.config.get("workspace", "default")
    event = await request.app.state.storage.get_event(event_id, workspace_id=workspace)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return _event_to_response(event)


# --- Analysis (Store -> Human + Agent) ---


@router.get("/thesis")
async def thesis_coverage(request: Request):
    """Thesis coverage report across all events."""
    results = await request.app.state.analyze.thesis_coverage()
    return [
        {
            "thesis": t.thesis_name,
            "event_count": t.event_count,
            "avg_confidence": round(t.avg_confidence, 3),
            "type_distribution": t.type_distribution,
            "latest_update": t.latest_update.isoformat() if t.latest_update else None,
            "days_since_update": t.days_since_update,
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
    return result


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


# --- Phase 3: Notifications ---


@router.get("/notifications")
async def get_notifications(request: Request):
    """Get proactive push notifications."""
    from cortex.use_cases.push_detector import PushDetector

    workspace = request.app.state.config.get("workspace", "default")
    detector = PushDetector(request.app.state.storage, workspace)
    notifications = await detector.check_all()
    return [
        NotificationResponse(
            trigger_type=n.trigger_type,
            title=n.title,
            body=n.body,
            priority=n.priority,
            related_event_ids=n.related_event_ids,
        )
        for n in notifications
    ]


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _event_to_response(event) -> EventResponse:
    return EventResponse(
        id=event.id,
        type=event.type.value if hasattr(event.type, "value") else str(event.type),
        title=event.title,
        summary=event.summary,
        tags=event.tags,
        thesis_links=event.thesis_links,
        confidence=event.confidence,
        source=event.source,
        created_at=event.created_at.isoformat()
        if hasattr(event.created_at, "isoformat")
        else str(event.created_at),
    )
