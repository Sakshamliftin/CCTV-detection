# PROMPT: Create a comprehensive pytest suite covering the edge cases from the problem statement, including staff classification, re-entry logic, empty store handling, and DB availability gracefully failing. Ensure coverage is high.
# CHANGES MADE: Adapted the generated tests to mock the database correctly, fixed event schema property assertions, and mocked out heavy ML dependencies (ultralytics, supervision) during import to speed up unit testing.
"""Shared test fixtures and helpers."""
import pytest
import asyncio


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


def make_event(
    event_type: str = "person_entered",
    visitor_id: str = "visitor_1",
    zone_id: str = "store",
    is_staff: bool = False,
    dwell_ms: int = 0,
    confidence: float = 0.91,
    event_id: str = None,
    camera_id: str = "cam_01",
) -> dict:
    """Helper to build a minimal valid store event."""
    import uuid
    from datetime import datetime, timezone
    return {
        "event_id": event_id or str(uuid.uuid4()),
        "store_id": "store_01",
        "camera_id": camera_id,
        "visitor_id": visitor_id,
        "event_type": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "zone_id": zone_id,
        "dwell_ms": dwell_ms,
        "is_staff": is_staff,
        "confidence": confidence,
        "metadata": {},
    }

