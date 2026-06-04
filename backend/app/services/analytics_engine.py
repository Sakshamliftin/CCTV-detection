"""Analytics engine — computes and persists store metrics.

Maintains in-memory state updated by Kafka events, periodically
snapshotting to PostgreSQL for historical queries.

v1.1 upgrades:
- Staff excluded from all visitor/funnel metrics.
- Session management: ENTRY starts session, EXIT closes it; re-entry within
  REENTRY_WINDOW_SEC reopens without inflating the unique-visitor count.
- Idempotency: duplicate event_ids are silently ignored.
- New query methods: get_metrics(), get_funnel(), get_heatmap().
"""
import asyncio
import logging
import uuid
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Set

from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError

from app.config import settings, load_zones_config
from app.database import async_session
from app.models import StoreEvent, AnalyticsSnapshot, ZoneAnalytics

logger = logging.getLogger(__name__)

# Window within which a returning visitor is treated as re-entry (not new session).
REENTRY_WINDOW_SEC = 300


class SessionState:
    """Lightweight per-visitor session tracker."""

    def __init__(self, visitor_id: str):
        self.visitor_id = visitor_id
        self.session_count: int = 0
        self.active: bool = False
        self.enter_time: Optional[float] = None
        self.last_exit_time: Optional[float] = None
        self.zones_visited: Set[str] = set()
        self.reached_checkout: bool = False
        self.completed_purchase: bool = False


class AnalyticsEngine:
    """Processes store events and maintains analytics state."""

    def __init__(self):
        # Current state
        self._zone_occupancy: Dict[str, int] = defaultdict(int)
        self._total_occupancy: int = 0
        self._total_visitors: int = 0
        self._peak_occupancy: int = 0
        self._visitor_ids: Set[str] = set()          # unique visitor_id strings

        # Dwell tracking (staff excluded)
        self._dwell_times: Dict[str, List[float]] = defaultdict(list)
        self._total_dwell_times: List[float] = []

        # Zone traffic counters (all persons incl. staff for occupancy; visitors only for funnel)
        self._zone_entries: Dict[str, int] = defaultdict(int)
        self._zone_exits: Dict[str, int] = defaultdict(int)
        self._zone_visit_counts: Dict[str, int] = defaultdict(int)   # visitor-only

        # Hourly traffic
        self._hourly_visitors: Dict[str, int] = defaultdict(int)
        self._hourly_events: Dict[str, int] = defaultdict(int)

        # Session management (visitor_id -> SessionState)
        self._sessions: Dict[str, SessionState] = {}

        # Idempotency: seen event_ids (in-process cache)
        self._seen_event_ids: Set[str] = set()

        # Zone config
        self._zones_config = {z["id"]: z for z in load_zones_config()}

        # Snapshot task
        self._snapshot_task: Optional[asyncio.Task] = None
        self._total_events: int = 0

    # ------------------------------------------------------------------ #
    # Lifecycle                                                            #
    # ------------------------------------------------------------------ #

    async def start(self):
        self._snapshot_task = asyncio.create_task(self._snapshot_loop())
        logger.info("Analytics engine started")

    async def stop(self):
        if self._snapshot_task:
            self._snapshot_task.cancel()
            try:
                await self._snapshot_task
            except asyncio.CancelledError:
                pass
        logger.info("Analytics engine stopped")

    # ------------------------------------------------------------------ #
    # Event processing                                                     #
    # ------------------------------------------------------------------ #

    async def process_event(self, event: dict):
        """Process a single store event and update analytics state.

        Idempotent: duplicate event_ids are silently ignored.
        Staff events update occupancy but are excluded from visitor metrics.
        """
        event_id = event.get("event_id", "")
        if event_id and event_id in self._seen_event_ids:
            logger.debug(f"Duplicate event ignored: {event_id}")
            return
        if event_id:
            self._seen_event_ids.add(event_id)
            # Bound cache size to avoid unbounded growth
            if len(self._seen_event_ids) > 100_000:
                self._seen_event_ids.clear()

        event_type = event.get("event_type", "")
        zone_id = event.get("zone_id", "")
        visitor_id = event.get("visitor_id") or str(event.get("track_id", 0))
        is_staff = event.get("is_staff", False)
        metadata = event.get("metadata", {})
        dwell_ms = event.get("dwell_ms", 0)
        dwell_seconds = dwell_ms / 1000 if dwell_ms else metadata.get("dwell_seconds", 0)
        timestamp = event.get("timestamp", "")

        self._total_events += 1

        # Track hourly
        hour_key = timestamp[:13] if timestamp else datetime.now(timezone.utc).strftime("%Y-%m-%dT%H")
        self._hourly_events[hour_key] = self._hourly_events.get(hour_key, 0) + 1

        # --- Occupancy (all persons) ---
        if event_type == "person_entered":
            self._total_occupancy += 1
            self._peak_occupancy = max(self._peak_occupancy, self._total_occupancy)

            if not is_staff:
                self._visitor_ids.add(visitor_id)
                self._total_visitors = len(self._visitor_ids)
                self._hourly_visitors[hour_key] = self._hourly_visitors.get(hour_key, 0) + 1
                self._open_session(visitor_id)

        elif event_type == "person_exited":
            self._total_occupancy = max(0, self._total_occupancy - 1)
            if not is_staff and dwell_seconds > 0:
                self._total_dwell_times.append(dwell_seconds)
                self._close_session(visitor_id, dwell_seconds)

        elif event_type == "zone_entered":
            self._zone_occupancy[zone_id] = self._zone_occupancy.get(zone_id, 0) + 1
            self._zone_entries[zone_id] = self._zone_entries.get(zone_id, 0) + 1
            if not is_staff:
                self._zone_visit_counts[zone_id] = self._zone_visit_counts.get(zone_id, 0) + 1
                self._update_session_zone(visitor_id, zone_id)

        elif event_type == "zone_exited":
            self._zone_occupancy[zone_id] = max(0, self._zone_occupancy.get(zone_id, 0) - 1)
            self._zone_exits[zone_id] = self._zone_exits.get(zone_id, 0) + 1
            if not is_staff and dwell_seconds > 0:
                self._dwell_times[zone_id].append(dwell_seconds)

        elif event_type == "dwell_time_completed":
            if not is_staff and dwell_seconds > 0:
                self._dwell_times[zone_id].append(dwell_seconds)

        elif event_type == "purchase_completed":
            if not is_staff:
                self._mark_purchase(visitor_id)

        # Persist event to DB
        await self._persist_event(event)

    # ------------------------------------------------------------------ #
    # Session management                                                   #
    # ------------------------------------------------------------------ #

    def _open_session(self, visitor_id: str):
        import time as _time
        now = _time.time()
        sess = self._sessions.get(visitor_id)
        if sess is None:
            sess = SessionState(visitor_id)
            self._sessions[visitor_id] = sess

        if sess.active:
            return  # already in-store

        # Re-entry detection
        if sess.last_exit_time and (now - sess.last_exit_time) <= REENTRY_WINDOW_SEC:
            logger.debug(f"Re-entry detected for visitor={visitor_id}")
        else:
            sess.session_count += 1

        sess.active = True
        sess.enter_time = now
        sess.zones_visited.clear()

    def _close_session(self, visitor_id: str, dwell_seconds: float):
        import time as _time
        sess = self._sessions.get(visitor_id)
        if sess:
            sess.active = False
            sess.last_exit_time = _time.time()

    def _update_session_zone(self, visitor_id: str, zone_id: str):
        sess = self._sessions.get(visitor_id)
        if sess:
            sess.zones_visited.add(zone_id)
            if zone_id == "zone_checkout":
                sess.reached_checkout = True

    def _mark_purchase(self, visitor_id: str):
        sess = self._sessions.get(visitor_id)
        if sess:
            sess.completed_purchase = True

    # ------------------------------------------------------------------ #
    # DB helpers                                                           #
    # ------------------------------------------------------------------ #

    async def _persist_event(self, event: dict):
        """Save event to PostgreSQL, ignoring duplicates."""
        try:
            async with async_session() as session:
                from app.models import StoreEvent
                from dateutil.parser import isoparse

                # Re-check DB-level duplicate (catches cross-process duplicates)
                existing = await session.get(StoreEvent, event.get("event_id", ""))
                if existing:
                    return

                # Build metadata blob – preserve all upstream fields
                meta = event.get("metadata", {})
                meta["is_staff"] = event.get("is_staff", False)
                meta["confidence"] = event.get("confidence", 1.0)
                meta["dwell_ms"] = event.get("dwell_ms", 0)
                meta["visitor_id"] = event.get("visitor_id", "")
                meta["store_id"] = event.get("store_id", "store_01")

                db_event = StoreEvent(
                    id=event.get("event_id", str(uuid.uuid4())),
                    event_type=event["event_type"],
                    camera_id=event.get("camera_id", ""),
                    track_id=int(event.get("visitor_id", "visitor_0").split("_")[-1])
                        if "_" in event.get("visitor_id", "") else event.get("track_id", 0),
                    zone_id=event.get("zone_id", ""),
                    zone_name=event.get("metadata", {}).get("zone_name", ""),
                    timestamp=isoparse(event["timestamp"]) if event.get("timestamp") else datetime.now(timezone.utc),
                    metadata_=meta,
                )
                session.add(db_event)
                await session.commit()
        except SQLAlchemyError as e:
            logger.error(f"Failed to persist event: {e}")
        except Exception as e:
            logger.error(f"Failed to persist event (unexpected): {e}")

    async def _snapshot_loop(self):
        while True:
            await asyncio.sleep(settings.analytics_snapshot_interval)
            try:
                await self._save_snapshot()
            except Exception as e:
                logger.error(f"Snapshot error: {e}")

    async def _save_snapshot(self):
        try:
            async with async_session() as session:
                snapshot = AnalyticsSnapshot(
                    timestamp=datetime.now(timezone.utc),
                    total_occupancy=self._total_occupancy,
                    total_visitors=self._total_visitors,
                    avg_dwell_seconds=self._avg_dwell(),
                    peak_occupancy=self._peak_occupancy,
                    zone_occupancy=dict(self._zone_occupancy),
                )
                session.add(snapshot)
                await session.commit()
                logger.debug("Analytics snapshot saved")
        except Exception as e:
            logger.error(f"Failed to save snapshot: {e}")

    def _avg_dwell(self) -> float:
        if not self._total_dwell_times:
            return 0.0
        return round(sum(self._total_dwell_times) / len(self._total_dwell_times), 1)

    # ------------------------------------------------------------------ #
    # Query methods (used by API routes)                                  #
    # ------------------------------------------------------------------ #

    def get_occupancy(self) -> dict:
        total_capacity = sum(z.get("capacity", 0) for z in self._zones_config.values())
        zone_occ = []
        for zone_id, zone_cfg in self._zones_config.items():
            zone_occ.append({
                "zone_id": zone_id,
                "zone_name": zone_cfg["name"],
                "current": self._zone_occupancy.get(zone_id, 0),
                "capacity": zone_cfg.get("capacity", 50),
                "color": zone_cfg.get("color", "#06b6d4"),
            })
        return {
            "total_occupancy": self._total_occupancy,
            "capacity": total_capacity,
            "zone_occupancy": zone_occ,
        }

    def get_summary(self, total_anomalies: int = 0) -> dict:
        return {
            "total_visitors": self._total_visitors,
            "avg_dwell_seconds": self._avg_dwell(),
            "peak_occupancy": self._peak_occupancy,
            "current_occupancy": self._total_occupancy,
            "total_events": self._total_events,
            "total_anomalies": total_anomalies,
        }

    def get_hourly_traffic(self, hours: int = 24) -> list:
        now = datetime.now(timezone.utc)
        data = []
        for i in range(hours, 0, -1):
            hour = now - timedelta(hours=i)
            hour_key = hour.strftime("%Y-%m-%dT%H")
            data.append({
                "timestamp": hour.strftime("%Y-%m-%dT%H:00:00Z"),
                "visitors": self._hourly_visitors.get(hour_key, 0),
                "occupancy": self._total_occupancy if i == 1 else self._hourly_visitors.get(hour_key, 0) // 2,
                "events": self._hourly_events.get(hour_key, 0),
            })
        return data

    def get_zone_traffic(self) -> list:
        zones = []
        for zone_id, zone_cfg in self._zones_config.items():
            dwell_list = self._dwell_times.get(zone_id, [])
            avg_dwell = round(sum(dwell_list) / len(dwell_list), 1) if dwell_list else 0.0
            zones.append({
                "zone_id": zone_id,
                "zone_name": zone_cfg["name"],
                "entries": self._zone_entries.get(zone_id, 0),
                "exits": self._zone_exits.get(zone_id, 0),
                "avg_dwell_seconds": avg_dwell,
                "current_occupancy": self._zone_occupancy.get(zone_id, 0),
                "color": zone_cfg.get("color", "#06b6d4"),
            })
        return zones

    def get_metrics(self) -> dict:
        """Business metrics — staff excluded."""
        unique_visitors = self._total_visitors  # already excludes staff
        checkout_occupancy = self._zone_occupancy.get("zone_checkout", 0)

        sessions_with_purchase = sum(
            1 for s in self._sessions.values() if s.completed_purchase
        )
        sessions_that_entered = sum(
            1 for s in self._sessions.values() if s.session_count > 0
        )
        sessions_reached_checkout = sum(
            1 for s in self._sessions.values() if s.reached_checkout
        )

        conversion_rate = (
            sessions_with_purchase / sessions_that_entered
            if sessions_that_entered > 0 else 0.0
        )
        abandonment_rate = (
            1.0 - (sessions_with_purchase / sessions_reached_checkout)
            if sessions_reached_checkout > 0 else 0.0
        )
        avg_dwell_ms = self._avg_dwell() * 1000

        return {
            "unique_visitors": unique_visitors,
            "conversion_rate": round(conversion_rate, 4),
            "avg_dwell_ms": round(avg_dwell_ms, 1),
            "queue_depth": checkout_occupancy,
            "abandonment_rate": round(abandonment_rate, 4),
        }

    def get_funnel(self) -> dict:
        """Session-based funnel — no double-counting, re-entry aware."""
        entry_count = sum(1 for s in self._sessions.values() if s.session_count > 0)
        zone_visit_count = sum(
            1 for s in self._sessions.values()
            if s.session_count > 0 and len(s.zones_visited) > 1  # beyond entrance
        )
        checkout_count = sum(
            1 for s in self._sessions.values() if s.reached_checkout
        )
        purchase_count = sum(
            1 for s in self._sessions.values() if s.completed_purchase
        )
        return {
            "funnel": [
                {"step": "Entry", "count": entry_count},
                {"step": "Zone Visit", "count": zone_visit_count},
                {"step": "Billing Queue", "count": checkout_count},
                {"step": "Purchase", "count": purchase_count},
            ],
            "note": "Session-based, staff excluded, re-entry aware.",
        }

    def get_heatmap(self) -> dict:
        """Zone visit frequency heatmap with normalized scores."""
        visit_counts = {z: self._zone_visit_counts.get(z, 0) for z in self._zones_config}
        max_visits = max(visit_counts.values(), default=1) or 1
        total_sessions = sum(1 for s in self._sessions.values() if s.session_count > 0)

        zones = []
        for zone_id, zone_cfg in self._zones_config.items():
            dwell_list = self._dwell_times.get(zone_id, [])
            avg_dwell = round(sum(dwell_list) / len(dwell_list), 1) if dwell_list else 0.0
            visits = visit_counts.get(zone_id, 0)
            normalized = round((visits / max_visits) * 100, 1)
            zones.append({
                "zone_id": zone_id,
                "zone_name": zone_cfg["name"],
                "visit_count": visits,
                "avg_dwell_seconds": avg_dwell,
                "normalized_score": normalized,
            })

        data_confidence = "low" if total_sessions < 20 else "high"
        return {"zones": zones, "data_confidence": data_confidence}
