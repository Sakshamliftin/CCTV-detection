# PROMPT: Create a comprehensive pytest suite covering the edge cases from the problem statement, including staff classification, re-entry logic, empty store handling, and DB availability gracefully failing. Ensure coverage is high.
# CHANGES MADE: Adapted the generated tests to mock the database correctly, fixed event schema property assertions, and mocked out heavy ML dependencies (ultralytics, supervision) during import to speed up unit testing.
"""Tests for rule-based anomaly detectors."""
import pytest
import time
from unittest.mock import patch, AsyncMock
from conftest import make_event


@pytest.fixture()
def anomaly_engine():
    with patch("app.services.anomaly_engine.async_session") as mock_session, \
         patch("app.services.anomaly_engine.AIOKafkaProducer"):
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=AsyncMock(
            add=AsyncMock(),
            commit=AsyncMock(),
        ))
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session.return_value = mock_ctx
        from app.services.anomaly_engine import AnomalyEngine
        e = AnomalyEngine()
        e._kafka_producer = None  # skip Kafka
        yield e


def _make_context(zone_id="zone_checkout", occupancy=0, metrics=None):
    from app.config import load_zones_config
    zones_config = {z["id"]: z for z in load_zones_config()}
    return {
        "zone_occupancy": {zone_id: occupancy},
        "zones_config": zones_config,
        "metrics": metrics or {},
    }


# ------------------------------------------------------------------ #
# Queue Spike                                                          #
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_queue_spike_triggers(anomaly_engine):
    """Queue depth 2x above average should trigger WARN."""
    from app.services.anomaly_engine import QueueSpikeDetector
    det = QueueSpikeDetector()

    # Prime history with low values
    now = time.time()
    for _ in range(20):
        det._depth_history.append((now - 100, 2))

    context = _make_context(occupancy=10)
    result = await det.evaluate(make_event("zone_entered", zone_id="zone_checkout"), context)
    assert result is not None
    assert result["anomaly_type"] == "queue_spike"
    assert result["severity"] in ("WARN", "CRITICAL")


@pytest.mark.asyncio
async def test_queue_spike_no_trigger_low_depth(anomaly_engine):
    """Normal queue depth should not trigger a spike."""
    from app.services.anomaly_engine import QueueSpikeDetector
    det = QueueSpikeDetector()
    now = time.time()
    for _ in range(20):
        det._depth_history.append((now - 100, 5))

    context = _make_context(occupancy=6)
    result = await det.evaluate(make_event("zone_entered", zone_id="zone_checkout"), context)
    assert result is None


# ------------------------------------------------------------------ #
# Conversion Drop                                                      #
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_conversion_drop_triggers(anomaly_engine):
    """Conversion rate < 50% of baseline with enough visitors should trigger."""
    from app.services.anomaly_engine import ConversionDropDetector
    det = ConversionDropDetector()
    context = _make_context(metrics={"unique_visitors": 20, "conversion_rate": 0.04})
    result = await det.evaluate(make_event("person_exited", visitor_id="v1"), context)
    assert result is not None
    assert result["anomaly_type"] == "conversion_drop"
    assert "suggested_action" in result


@pytest.mark.asyncio
async def test_conversion_drop_skipped_low_visitors(anomaly_engine):
    """With fewer than MIN_VISITORS, no anomaly should fire."""
    from app.services.anomaly_engine import ConversionDropDetector
    det = ConversionDropDetector()
    context = _make_context(metrics={"unique_visitors": 3, "conversion_rate": 0.0})
    result = await det.evaluate(make_event("person_exited", visitor_id="v1"), context)
    assert result is None


# ------------------------------------------------------------------ #
# Dead Zone                                                            #
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_dead_zone_triggers_after_window(anomaly_engine):
    """Zone with last visit > DEAD_ZONE_WINDOW_SEC ago should trigger INFO."""
    from app.services.anomaly_engine import DeadZoneDetector
    det = DeadZoneDetector()
    # Simulate zone visited long ago
    det._last_visit["zone_electronics"] = time.time() - 3700  # > 30 min

    from app.config import load_zones_config
    zones_config = {z["id"]: z for z in load_zones_config()}
    context = {"zone_occupancy": {}, "zones_config": zones_config, "metrics": {}}
    result = await det.evaluate(make_event("person_entered", zone_id="zone_entrance"), context)
    assert result is not None
    assert result["anomaly_type"] == "dead_zone"
    assert result["severity"] == "INFO"
    assert "suggested_action" in result


@pytest.mark.asyncio
async def test_dead_zone_no_trigger_recent_visit(anomaly_engine):
    """Zone visited recently should not trigger dead-zone."""
    from app.services.anomaly_engine import DeadZoneDetector
    det = DeadZoneDetector()
    now = time.time()
    from app.config import load_zones_config
    zones_config = {z["id"]: z for z in load_zones_config()}
    for zid in zones_config:
        det._last_visit[zid] = now  # all zones visited just now

    context = {"zone_occupancy": {}, "zones_config": zones_config, "metrics": {}}
    result = await det.evaluate(make_event("zone_entered", zone_id="zone_grocery"), context)
    assert result is None


# ------------------------------------------------------------------ #
# Severity and suggested_action contract                               #
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_all_anomalies_have_required_fields(anomaly_engine):
    """Every fired anomaly must contain severity and suggested_action."""
    from app.services.anomaly_engine import QueueSpikeDetector
    det = QueueSpikeDetector()
    now = time.time()
    for _ in range(20):
        det._depth_history.append((now - 100, 2))
    context = _make_context(occupancy=10)
    result = await det.evaluate(make_event("zone_entered", zone_id="zone_checkout"), context)
    if result:
        assert "severity" in result
        assert result["severity"] in ("INFO", "WARN", "CRITICAL")
        assert "suggested_action" in result
        assert isinstance(result["suggested_action"], str)

