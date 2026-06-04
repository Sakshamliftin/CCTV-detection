# PROMPT: Create a comprehensive pytest suite covering the edge cases from the problem statement, including staff classification, re-entry logic, empty store handling, and DB availability gracefully failing. Ensure coverage is high.
# CHANGES MADE: Adapted the generated tests to mock the database correctly, fixed event schema property assertions, and mocked out heavy ML dependencies (ultralytics, supervision) during import to speed up unit testing.
"""Tests for business metrics: unique visitors, conversion, dwell, queue, abandonment."""
import pytest
from unittest.mock import patch, AsyncMock
from conftest import make_event


@pytest.fixture()
def engine():
    """Create an AnalyticsEngine with DB persistence mocked out."""
    with patch("app.services.analytics_engine.async_session") as mock_session:
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=AsyncMock(
            get=AsyncMock(return_value=None),
            add=AsyncMock(),
            commit=AsyncMock(),
        ))
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session.return_value = mock_ctx

        from app.services.analytics_engine import AnalyticsEngine
        e = AnalyticsEngine()
        yield e


@pytest.mark.asyncio
async def test_empty_store_metrics(engine):
    """Empty store should return all zeros without errors."""
    m = engine.get_metrics()
    assert m["unique_visitors"] == 0
    assert m["conversion_rate"] == 0.0
    assert m["avg_dwell_ms"] == 0.0
    assert m["queue_depth"] == 0
    assert m["abandonment_rate"] == 0.0


@pytest.mark.asyncio
async def test_unique_visitor_count(engine):
    """Each unique visitor_id should be counted once."""
    await engine.process_event(make_event("person_entered", visitor_id="visitor_1"))
    await engine.process_event(make_event("person_entered", visitor_id="visitor_2"))
    await engine.process_event(make_event("person_entered", visitor_id="visitor_1"))  # duplicate
    assert engine.get_metrics()["unique_visitors"] == 2


@pytest.mark.asyncio
async def test_staff_excluded_from_metrics(engine):
    """Staff entries must not increment unique_visitors."""
    await engine.process_event(make_event("person_entered", visitor_id="visitor_1"))
    await engine.process_event(make_event("person_entered", visitor_id="staff_1", is_staff=True))
    m = engine.get_metrics()
    assert m["unique_visitors"] == 1


@pytest.mark.asyncio
async def test_zero_purchases_no_crash(engine):
    """With visitors but zero purchases, conversion_rate should be 0.0."""
    await engine.process_event(make_event("person_entered", visitor_id="visitor_1"))
    await engine.process_event(make_event("person_entered", visitor_id="visitor_2"))
    m = engine.get_metrics()
    assert m["conversion_rate"] == 0.0


@pytest.mark.asyncio
async def test_avg_dwell_time(engine):
    """Average dwell should equal average of all visitor exit dwell_ms values."""
    await engine.process_event(make_event("person_entered", visitor_id="v1"))
    await engine.process_event(make_event("person_exited", visitor_id="v1", dwell_ms=60000))
    await engine.process_event(make_event("person_entered", visitor_id="v2"))
    await engine.process_event(make_event("person_exited", visitor_id="v2", dwell_ms=120000))
    m = engine.get_metrics()
    assert m["avg_dwell_ms"] == pytest.approx(90000.0, rel=0.01)


@pytest.mark.asyncio
async def test_queue_depth_updates(engine):
    """Queue depth should reflect zone_checkout occupancy."""
    await engine.process_event(make_event("zone_entered", visitor_id="v1", zone_id="zone_checkout"))
    await engine.process_event(make_event("zone_entered", visitor_id="v2", zone_id="zone_checkout"))
    assert engine.get_metrics()["queue_depth"] == 2

