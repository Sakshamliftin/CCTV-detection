"""Events and anomalies API endpoints."""
from fastapi import APIRouter, Query
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from app.database import get_db
from app.models import StoreEvent, AnomalyEvent
from app.schemas import EventsResponse, EventItem, AnomaliesResponse, AnomalyItem

router = APIRouter(prefix="/api/v1/events", tags=["Events"])


@router.get("/recent", response_model=EventsResponse)
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


@router.get("/anomalies", response_model=AnomaliesResponse)
async def get_recent_anomalies(
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
                metadata=a.metadata_ or {},
            )
            for a in anomalies
        ],
        total=total,
    )
