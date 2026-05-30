"""Analytics engine — computes and persists store metrics.

Maintains in-memory state updated by Kafka events, periodically
snapshotting to PostgreSQL for historical queries.
"""
import asyncio
import logging
import uuid
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Set

from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings, load_zones_config
from app.database import async_session
from app.models import StoreEvent, AnalyticsSnapshot, ZoneAnalytics

logger = logging.getLogger(__name__)


class AnalyticsEngine:
    """Processes store events and maintains analytics state."""

    def __init__(self):
        # Current state
        self._zone_occupancy: Dict[str, int] = defaultdict(int)  # zone_id -> count
        self._total_occupancy: int = 0
        self._total_visitors: int = 0
        self._peak_occupancy: int = 0
        self._visitor_ids: Set[int] = set()
        
        # Dwell tracking
        self._dwell_times: Dict[str, List[float]] = defaultdict(list)  # zone_id -> list of dwell seconds
        self._total_dwell_times: List[float] = []
        
        # Zone traffic counters
        self._zone_entries: Dict[str, int] = defaultdict(int)
        self._zone_exits: Dict[str, int] = defaultdict(int)
        
        # Hourly traffic
        self._hourly_visitors: Dict[str, int] = defaultdict(int)  # hour_key -> count
        self._hourly_events: Dict[str, int] = defaultdict(int)
        
        # Zone config
        self._zones_config = {z["id"]: z for z in load_zones_config()}
        
        # Snapshot task
        self._snapshot_task: Optional[asyncio.Task] = None
        self._total_events: int = 0

    async def start(self):
        """Start periodic snapshot task."""
        self._snapshot_task = asyncio.create_task(self._snapshot_loop())
        logger.info("Analytics engine started")

    async def stop(self):
        """Stop the snapshot task."""
        if self._snapshot_task:
            self._snapshot_task.cancel()
            try:
                await self._snapshot_task
            except asyncio.CancelledError:
                pass
        logger.info("Analytics engine stopped")

    async def process_event(self, event: dict):
        """Process a single store event and update analytics state."""
        event_type = event.get("event_type", "")
        zone_id = event.get("zone_id", "")
        track_id = event.get("track_id", 0)
        metadata = event.get("metadata", {})
        timestamp = event.get("timestamp", "")
        
        self._total_events += 1
        
        # Track hourly
        hour_key = timestamp[:13] if timestamp else datetime.now(timezone.utc).strftime("%Y-%m-%dT%H")
        self._hourly_events[hour_key] = self._hourly_events.get(hour_key, 0) + 1

        if event_type == "person_entered":
            self._total_occupancy += 1
            self._visitor_ids.add(track_id)
            self._total_visitors = len(self._visitor_ids)
            self._peak_occupancy = max(self._peak_occupancy, self._total_occupancy)
            self._hourly_visitors[hour_key] = self._hourly_visitors.get(hour_key, 0) + 1

        elif event_type == "person_exited":
            self._total_occupancy = max(0, self._total_occupancy - 1)
            dwell = metadata.get("dwell_seconds", 0)
            if dwell > 0:
                self._total_dwell_times.append(dwell)

        elif event_type == "zone_entered":
            self._zone_occupancy[zone_id] = self._zone_occupancy.get(zone_id, 0) + 1
            self._zone_entries[zone_id] = self._zone_entries.get(zone_id, 0) + 1

        elif event_type == "zone_exited":
            self._zone_occupancy[zone_id] = max(0, self._zone_occupancy.get(zone_id, 0) - 1)
            self._zone_exits[zone_id] = self._zone_exits.get(zone_id, 0) + 1
            dwell = metadata.get("dwell_seconds", 0)
            if dwell > 0:
                self._dwell_times[zone_id].append(dwell)

        elif event_type == "dwell_time_completed":
            dwell = metadata.get("dwell_seconds", 0)
            if dwell > 0:
                self._dwell_times[zone_id].append(dwell)

        # Persist event to database
        await self._persist_event(event)

    async def _persist_event(self, event: dict):
        """Save event to PostgreSQL."""
        try:
            async with async_session() as session:
                from app.models import StoreEvent
                from dateutil.parser import isoparse
                
                db_event = StoreEvent(
                    id=event.get("event_id", str(uuid.uuid4())),
                    event_type=event["event_type"],
                    camera_id=event.get("camera_id", ""),
                    track_id=event.get("track_id", 0),
                    zone_id=event.get("zone_id", ""),
                    zone_name=event.get("zone_name", ""),
                    timestamp=isoparse(event["timestamp"]) if event.get("timestamp") else datetime.now(timezone.utc),
                    metadata_=event.get("metadata", {}),
                )
                session.add(db_event)
                await session.commit()
        except Exception as e:
            logger.error(f"Failed to persist event: {e}")

    async def _snapshot_loop(self):
        """Periodically save analytics snapshots."""
        while True:
            await asyncio.sleep(settings.analytics_snapshot_interval)
            try:
                await self._save_snapshot()
            except Exception as e:
                logger.error(f"Snapshot error: {e}")

    async def _save_snapshot(self):
        """Save current analytics state to database."""
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
        """Calculate average dwell time across all zones."""
        if not self._total_dwell_times:
            return 0.0
        return round(sum(self._total_dwell_times) / len(self._total_dwell_times), 1)

    # --- Query Methods (used by API routes) ---

    def get_occupancy(self) -> dict:
        """Get current occupancy data."""
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
        """Get analytics summary."""
        return {
            "total_visitors": self._total_visitors,
            "avg_dwell_seconds": self._avg_dwell(),
            "peak_occupancy": self._peak_occupancy,
            "current_occupancy": self._total_occupancy,
            "total_events": self._total_events,
            "total_anomalies": total_anomalies,
        }

    def get_hourly_traffic(self, hours: int = 24) -> list:
        """Get hourly visitor traffic for the last N hours."""
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
        """Get per-zone traffic statistics."""
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
