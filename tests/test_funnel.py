# PROMPT: Create a comprehensive pytest suite covering the edge cases from the problem statement, including staff classification, re-entry logic, empty store handling, and DB availability gracefully failing. Ensure coverage is high.
# CHANGES MADE: Adapted the generated tests to mock the database correctly, fixed event schema property assertions, and mocked out heavy ML dependencies (ultralytics, supervision) during import to speed up unit testing.
"""Tests for session-based funnel logic and re-entry handling."""
import pytest
from unittest.mock import patch, AsyncMock
from conftest import make_event


@pytest.fixture()
def engine():
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
async def test_funnel_entry_only(engine):
    """A visitor who only enters should appear in Entry step, not others."""
    await engine.process_event(make_event("person_entered", visitor_id="v1"))
    funnel = {f["step"]: f["count"] for f in engine.get_funnel()["funnel"]}
    assert funnel["Entry"] == 1
    assert funnel["Billing Queue"] == 0
    assert funnel["Purchase"] == 0


@pytest.mark.asyncio
async def test_funnel_full_journey(engine):
    """Visitor who goes entry → zone → checkout → purchase should fill all steps."""
    await engine.process_event(make_event("person_entered", visitor_id="v1"))
    await engine.process_event(make_event("zone_entered", visitor_id="v1", zone_id="zone_grocery"))
    await engine.process_event(make_event("zone_entered", visitor_id="v1", zone_id="zone_checkout"))
    await engine.process_event(make_event("purchase_completed", visitor_id="v1"))

    funnel = {f["step"]: f["count"] for f in engine.get_funnel()["funnel"]}
    assert funnel["Entry"] == 1
    assert funnel["Zone Visit"] == 1
    assert funnel["Billing Queue"] == 1
    assert funnel["Purchase"] == 1


@pytest.mark.asyncio
async def test_funnel_no_double_counting(engine):
    """Two events for the same visitor should not double-count funnel steps."""
    await engine.process_event(make_event("person_entered", visitor_id="v1"))
    await engine.process_event(make_event("zone_entered", visitor_id="v1", zone_id="zone_checkout"))
    await engine.process_event(make_event("zone_entered", visitor_id="v1", zone_id="zone_checkout"))  # dup zone

    funnel = {f["step"]: f["count"] for f in engine.get_funnel()["funnel"]}
    assert funnel["Billing Queue"] == 1   # still just 1 session reached checkout


@pytest.mark.asyncio
async def test_reentry_does_not_inflate_unique_visitors(engine):
    """Re-entry within REENTRY_WINDOW_SEC must not count as a new unique visitor."""
    from app.services.analytics_engine import REENTRY_WINDOW_SEC

    await engine.process_event(make_event("person_entered", visitor_id="v1"))
    await engine.process_event(make_event("person_exited", visitor_id="v1", dwell_ms=30000))

    # Simulate re-entry: manipulate last_exit_time to be within window
    sess = engine._sessions["v1"]
    import time
    sess.last_exit_time = time.time() - (REENTRY_WINDOW_SEC - 10)  # within window

    await engine.process_event(make_event("person_entered", visitor_id="v1"))

    assert engine.get_metrics()["unique_visitors"] == 1   # still 1 unique


@pytest.mark.asyncio
async def test_reentry_outside_window_counts_new_session(engine):
    """Re-entry after REENTRY_WINDOW_SEC should open a new session."""
    from app.services.analytics_engine import REENTRY_WINDOW_SEC

    await engine.process_event(make_event("person_entered", visitor_id="v1"))
    await engine.process_event(make_event("person_exited", visitor_id="v1", dwell_ms=30000))

    # Force last exit time to be beyond window
    import time
    engine._sessions["v1"].last_exit_time = time.time() - (REENTRY_WINDOW_SEC + 60)

    await engine.process_event(make_event("person_entered", visitor_id="v1"))
    assert engine._sessions["v1"].session_count == 2


@pytest.mark.asyncio
async def test_all_staff_clip_zero_funnel(engine):
    """If all entrants are staff, funnel should show zeros."""
    for i in range(5):
        await engine.process_event(make_event("person_entered", visitor_id=f"staff_{i}", is_staff=True))

    funnel = {f["step"]: f["count"] for f in engine.get_funnel()["funnel"]}
    assert funnel["Entry"] == 0
    assert engine.get_metrics()["unique_visitors"] == 0

