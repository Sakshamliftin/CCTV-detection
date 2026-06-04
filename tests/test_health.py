# PROMPT: Create a comprehensive pytest suite covering the edge cases from the problem statement, including staff classification, re-entry logic, empty store handling, and DB availability gracefully failing. Ensure coverage is high.
# CHANGES MADE: Adapted the generated tests to mock the database correctly, fixed event schema property assertions, and mocked out heavy ML dependencies (ultralytics, supervision) during import to speed up unit testing.
"""Tests for health endpoint: service status, last_event_timestamp, and STALE_FEED."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta


def _make_consumer(connected: bool = True, last_event_ts: str = None):
    consumer = MagicMock()
    consumer.is_connected = connected
    consumer.last_event_timestamp = last_event_ts
    return consumer


@pytest.fixture()
def health_router():
    """Import health router fresh to allow consumer injection."""
    import importlib
    import app.routes.health as h
    importlib.reload(h)
    return h


@pytest.mark.asyncio
async def test_health_ok(health_router):
    """Healthy DB and recent event → status healthy, feed ok."""
    now = datetime.now(timezone.utc).isoformat()
    consumer = _make_consumer(connected=True, last_event_ts=now)
    health_router.set_kafka_consumer(consumer)

    with patch("app.routes.health.check_db_connection", new=AsyncMock(return_value=True)):
        result = await health_router.health_check()

    assert result.status == "healthy"
    assert result.services.feed == "ok"
    assert result.last_event_timestamp == now


@pytest.mark.asyncio
async def test_health_stale_feed(health_router):
    """Event timestamp > 10 minutes old → feed = STALE_FEED."""
    stale_ts = (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat()
    consumer = _make_consumer(connected=True, last_event_ts=stale_ts)
    health_router.set_kafka_consumer(consumer)

    with patch("app.routes.health.check_db_connection", new=AsyncMock(return_value=True)):
        result = await health_router.health_check()

    assert result.services.feed == "STALE_FEED"


@pytest.mark.asyncio
async def test_health_connected_never_received(health_router):
    """Consumer connected but last_event_timestamp is None → STALE_FEED."""
    consumer = _make_consumer(connected=True, last_event_ts=None)
    health_router.set_kafka_consumer(consumer)

    with patch("app.routes.health.check_db_connection", new=AsyncMock(return_value=True)):
        result = await health_router.health_check()

    assert result.services.feed == "STALE_FEED"


@pytest.mark.asyncio
async def test_health_db_down_returns_503(health_router):
    """Unreachable DB → HTTPException 503 with structured JSON."""
    from fastapi import HTTPException
    consumer = _make_consumer(connected=True, last_event_ts=datetime.now(timezone.utc).isoformat())
    health_router.set_kafka_consumer(consumer)

    with patch("app.routes.health.check_db_connection", new=AsyncMock(return_value=False)):
        with pytest.raises(HTTPException) as exc_info:
            await health_router.health_check()

    assert exc_info.value.status_code == 503
    detail = exc_info.value.detail
    assert "database" in str(detail).lower()
    # Must not expose Traceback
    assert "Traceback" not in str(detail)


@pytest.mark.asyncio
async def test_health_kafka_disconnected(health_router):
    """Kafka not connected → services.kafka = disconnected, still healthy if DB ok."""
    now = datetime.now(timezone.utc).isoformat()
    consumer = _make_consumer(connected=False, last_event_ts=now)
    health_router.set_kafka_consumer(consumer)

    with patch("app.routes.health.check_db_connection", new=AsyncMock(return_value=True)):
        result = await health_router.health_check()

    assert result.services.kafka == "disconnected"
    assert result.status == "healthy"

