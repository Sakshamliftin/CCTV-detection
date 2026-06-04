"""Health check endpoint.

v1.1 additions:
- Exposes last_event_timestamp.
- Reports feed=STALE_FEED when no events received for > 10 minutes.
- Returns HTTP 503 when database is unreachable.
"""
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from app.schemas import HealthResponse, ServiceStatus
from app.database import check_db_connection

router = APIRouter(tags=["Health"])

# Injected by main.py at startup
_kafka_consumer = None

STALE_FEED_THRESHOLD_SEC = 600   # 10 minutes


def set_kafka_consumer(consumer):
    global _kafka_consumer
    _kafka_consumer = consumer


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Check health of all service dependencies.

    Returns 503 if database is unreachable.
    Sets feed='STALE_FEED' if no events received in last 10 minutes.
    """
    db_ok = await check_db_connection()
    kafka_ok = _kafka_consumer.is_connected if _kafka_consumer else False

    # Stale feed detection
    last_ts = _kafka_consumer.last_event_timestamp if _kafka_consumer else None
    feed_status = "ok"
    if last_ts:
        try:
            last_dt = datetime.fromisoformat(last_ts)
            elapsed = (datetime.now(timezone.utc) - last_dt).total_seconds()
            if elapsed > STALE_FEED_THRESHOLD_SEC:
                feed_status = "STALE_FEED"
        except Exception:
            pass
    elif kafka_ok:
        # Connected but never received an event — treat as stale if consumer has been up
        feed_status = "STALE_FEED"

    if not db_ok:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "unhealthy",
                "services": {
                    "database": "disconnected",
                    "kafka": "connected" if kafka_ok else "disconnected",
                    "feed": feed_status,
                },
                "last_event_timestamp": last_ts,
                "version": "1.0.0",
            },
        )

    return HealthResponse(
        status="healthy",
        services=ServiceStatus(
            database="connected",
            kafka="connected" if kafka_ok else "disconnected",
            feed=feed_status,
        ),
        last_event_timestamp=last_ts,
    )
