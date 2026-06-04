"""Events and anomalies API endpoints.

v1.1 additions:
- POST /api/v1/events/ingest — idempotent bulk event ingestion.
"""
import logging
from typing import List

from fastapi import APIRouter, Query, Depends, HTTPException
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError

from app.database import get_db
from app.models import StoreEvent, AnomalyEvent
from app.schemas import (
    EventsResponse, EventItem,
    AnomaliesResponse, AnomalyItem,
    EventIngestItem, EventIngestResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Events"])

# Injected by main.py after startup
_analytics_engine = None

def set_analytics_engine(engine):
    global _analytics_engine
    _analytics_engine = engine


# ------------------------------------------------------------------ #
# Ingest endpoint                                                      #
# ------------------------------------------------------------------ #

@router.post("/events/ingest", response_model=EventIngestResponse)
async def ingest_events(
    events: List[EventIngestItem],
    db: AsyncSession = Depends(get_db),
):
    """Idempotent bulk event ingestion.

    Duplicate event_ids (by primary key) are silently skipped.
    Accepted events are forwarded to the analytics engine in-process.
    """
    from dateutil.parser import isoparse
    from datetime import datetime, timezone

    accepted = 0
    duplicates = 0

    for ev in events:
        # Check PK collision in DB
        existing = await db.get(StoreEvent, ev.event_id)
        if existing:
            duplicates += 1
            continue

        meta = dict(ev.metadata)
        meta["is_staff"] = ev.is_staff
        meta["confidence"] = ev.confidence
        meta["dwell_ms"] = ev.dwell_ms
        meta["visitor_id"] = ev.visitor_id
        meta["store_id"] = ev.store_id

        # Parse timestamp
        try:
            ts = isoparse(ev.timestamp)
        except Exception:
            ts = datetime.now(timezone.utc)

        db_event = StoreEvent(
            id=ev.event_id,
            event_type=ev.event_type,
            camera_id=ev.camera_id,
            track_id=int(ev.visitor_id.split("_")[-1]) if "_" in ev.visitor_id else 0,
            zone_id=ev.zone_id,
            zone_name=meta.get("zone_name", ""),
            timestamp=ts,
            metadata_=meta,
        )
        db.add(db_event)
        accepted += 1

        # Also push to in-process analytics engine if available
        if _analytics_engine:
            await _analytics_engine.process_event(ev.model_dump())

    try:
        await db.commit()
    except SQLAlchemyError as exc:
        logger.error(f"Ingest DB commit failed: {exc}")
        raise HTTPException(status_code=503, detail="Database unavailable")

    logger.info(f"Ingest: accepted={accepted} duplicates={duplicates}")
    return EventIngestResponse(accepted=accepted, duplicates=duplicates)


# ------------------------------------------------------------------ #
# Query endpoints                                                      #
# ------------------------------------------------------------------ #

@router.get("/events/recent", response_model=EventsResponse)
async def get_recent_events(
    limit: int = Query(default=50, ge=1, le=200),
    type: str = Query(default=None, description="Filter by event type"),
    db: AsyncSession = Depends(get_db),
):
    """Get recent store events with optional type filtering."""
    query = select(StoreEvent).order_by(desc(StoreEvent.timestamp))
    count_query = select(func.count()).select_from(StoreEvent)

    if type:
        query = query.where(StoreEvent.event_type == type)
        count_query = count_query.where(StoreEvent.event_type == type)

    query = query.limit(limit)

    result = await db.execute(query)
    events = result.scalars().all()

    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    return EventsResponse(
        events=[
            EventItem(
                event_id=e.id,
                event_type=e.event_type,
                camera_id=e.camera_id or "",
                track_id=e.track_id or 0,
                zone_id=e.zone_id or "",
                zone_name=e.zone_name or "",
                timestamp=e.timestamp.isoformat() if e.timestamp else "",
                metadata=e.metadata_ or {},
            )
            for e in events
        ],
        total=total,
    )


@router.get("/stores/{store_id}/anomalies", response_model=AnomaliesResponse)
async def get_recent_anomalies(
    store_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    severity: str = Query(default=None, description="Filter by severity"),
    db: AsyncSession = Depends(get_db),
):
    """Get recent anomaly events with optional severity filtering."""
    query = select(AnomalyEvent).order_by(desc(AnomalyEvent.timestamp))
    count_query = select(func.count()).select_from(AnomalyEvent)

    if severity:
        query = query.where(AnomalyEvent.severity == severity)
        count_query = count_query.where(AnomalyEvent.severity == severity)

    query = query.limit(limit)

    result = await db.execute(query)
    anomalies = result.scalars().all()

    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    return AnomaliesResponse(
        anomalies=[
            AnomalyItem(
                anomaly_id=a.id,
                anomaly_type=a.anomaly_type,
                severity=a.severity,
                zone_id=a.zone_id or "",
                zone_name=a.zone_name or "",
                description=a.description or "",
                timestamp=a.timestamp.isoformat() if a.timestamp else "",
                suggested_action=(a.metadata_ or {}).get("suggested_action", ""),
                metadata=a.metadata_ or {},
            )
            for a in anomalies
        ],
        total=total,
    )
