# PROMPT: Create a comprehensive pytest suite covering the edge cases from the problem statement, including staff classification, re-entry logic, empty store handling, and DB availability gracefully failing. Ensure coverage is high.
# CHANGES MADE: Adapted the generated tests to mock the database correctly, fixed event schema property assertions, and mocked out heavy ML dependencies (ultralytics, supervision) during import to speed up unit testing.
"""Tests for event ingestion idempotency and DB-unavailable graceful degradation."""
# pyrefly: ignore [missing-import]
import pytest
import uuid
from datetime import datetime, timezone
from unittest.mock import patch, AsyncMock, MagicMock
from conftest import make_event


def _make_ingest_payload(event_id: str = None, visitor_id: str = "visitor_1"):
    eid = event_id or str(uuid.uuid4())
    return {
        "event_id": eid,
        "store_id": "store_01",
        "camera_id": "cam_01",
        "visitor_id": visitor_id,
        "event_type": "person_entered",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "zone_id": "store",
        "dwell_ms": 0,
        "is_staff": False,
        "confidence": 0.91,
        "metadata": {},
    }


# ------------------------------------------------------------------ #
# Analytics engine idempotency (in-memory dedup)                      #
# ------------------------------------------------------------------ #

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
        # pyrefly: ignore [missing-import]
        from app.services.analytics_engine import AnalyticsEngine
        e = AnalyticsEngine()
        yield e


@pytest.mark.asyncio
async def test_duplicate_event_id_ignored(engine):
    """Sending the same event_id twice must not create duplicate records."""
    eid = str(uuid.uuid4())
    ev = make_event("person_entered", visitor_id="v1", event_id=eid)
    await engine.process_event(ev)
    await engine.process_event(ev)   # exact duplicate

    # Only 1 visitor should be tracked
    assert engine.get_metrics()["unique_visitors"] == 1
    assert engine._total_events == 1   # processed count should be 1


@pytest.mark.asyncio
async def test_different_event_ids_both_processed(engine):
    """Two events with different IDs for the same visitor should both count."""
    await engine.process_event(make_event("person_entered", visitor_id="v1"))
    await engine.process_event(make_event("zone_entered", visitor_id="v1", zone_id="zone_grocery"))
    assert engine._total_events == 2


# ------------------------------------------------------------------ #
# Ingest endpoint DB-unavailable graceful degradation                 #
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_ingest_returns_503_on_db_failure():
    """When DB commit fails, ingest must return 503 with structured JSON."""
    # pyrefly: ignore [missing-import]
    # pyrefly: ignore [missing-import]
    from fastapi.testclient import TestClient
    # pyrefly: ignore [missing-import]
    from sqlalchemy.exc import SQLAlchemyError

    # Build a minimal app with just the events router
    # pyrefly: ignore [missing-import]
    from fastapi import FastAPI
    # pyrefly: ignore [missing-import]
    from app.routes.events import router, set_analytics_engine

    test_app = FastAPI()
    test_app.include_router(router)
    set_analytics_engine(None)

    with patch("app.routes.events.get_db") as mock_get_db:
        mock_db = AsyncMock()
        mock_db.get = AsyncMock(return_value=None)
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock(side_effect=SQLAlchemyError("DB down"))

        async def override_db():
            yield mock_db

        test_app.dependency_overrides[__import__("app.database", fromlist=["get_db"]).get_db] = override_db
        # pyrefly: ignore [missing-import]
        from fastapi.testclient import TestClient
        with TestClient(test_app, raise_server_exceptions=False) as client:
            payload = [_make_ingest_payload()]
            resp = client.post("/events/ingest", json=payload)
            assert resp.status_code == 503
            data = resp.json()
            assert "detail" in data
            # Must not contain stack trace
            assert "Traceback" not in resp.text


@pytest.mark.asyncio
async def test_ingest_deduplication_at_db_level():
    """DB-level duplicate (existing PK) must be counted as duplicate, not accepted."""
    # pyrefly: ignore [missing-import]
    from fastapi import FastAPI
    # pyrefly: ignore [missing-import]
    from app.routes.events import router, set_analytics_engine

    test_app = FastAPI()
    test_app.include_router(router)
    set_analytics_engine(None)

    existing_mock = MagicMock()  # simulates an existing DB row
    eid = str(uuid.uuid4())

    with patch("app.routes.events.get_db") as mock_get_db:
        mock_db = AsyncMock()
        mock_db.get = AsyncMock(return_value=existing_mock)
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()

        async def override_db():
            yield mock_db

        # pyrefly: ignore [missing-import]
        import app.database as db_module
        test_app.dependency_overrides[db_module.get_db] = override_db

        # pyrefly: ignore [missing-import]
        from fastapi.testclient import TestClient
        with TestClient(test_app) as client:
            payload = [_make_ingest_payload(event_id=eid)]
            resp = client.post("/events/ingest", json=payload)
            assert resp.status_code == 200
            data = resp.json()
            assert data["accepted"] == 0
            assert data["duplicates"] == 1

