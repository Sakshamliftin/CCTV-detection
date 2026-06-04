"""Anomaly detection engine — rule-based with pluggable architecture.

v1.1 additions:
- QueueSpikeDetector: checkout depth vs. 1-hour rolling average.
- ConversionDropDetector: today's conversion vs. baseline threshold.
- DeadZoneDetector: zone with no visits in configurable window.
- All anomalies include `severity` (INFO|WARN|CRITICAL) and `suggested_action`.
"""
import asyncio
import json
import logging
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict, deque
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
import time

from aiokafka import AIOKafkaProducer

from app.config import settings, load_zones_config
from app.database import async_session
from app.models import AnomalyEvent

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
# Base interface                                                        #
# ------------------------------------------------------------------ #

class BaseDetector(ABC):
    """Abstract base class for anomaly detectors."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    async def evaluate(self, event: dict, context: dict) -> Optional[dict]: ...


# ------------------------------------------------------------------ #
# Existing detectors (unchanged)                                       #
# ------------------------------------------------------------------ #

class OvercrowdingDetector(BaseDetector):
    """Detects when zone occupancy exceeds safe capacity."""

    @property
    def name(self) -> str:
        return "overcrowding"

    async def evaluate(self, event: dict, context: dict) -> Optional[dict]:
        if event.get("event_type") not in ("person_entered", "zone_entered"):
            return None

        zone_id = event.get("zone_id", "")
        zone_occupancy = context.get("zone_occupancy", {})
        zones_config = context.get("zones_config", {})

        zone_cfg = zones_config.get(zone_id, {})
        capacity = zone_cfg.get("capacity", 50)
        current = zone_occupancy.get(zone_id, 0)
        threshold = capacity * settings.overcrowding_threshold

        if current >= threshold:
            severity = "CRITICAL" if current >= capacity else "WARN"
            return {
                "anomaly_type": "overcrowding",
                "severity": severity,
                "zone_id": zone_id,
                "zone_name": zone_cfg.get("name", zone_id),
                "description": (
                    f"Zone '{zone_cfg.get('name', zone_id)}' occupancy ({current}) "
                    f"exceeds {int(settings.overcrowding_threshold * 100)}% of capacity ({capacity})"
                ),
                "suggested_action": "Redirect visitors or open additional service points.",
                "metadata": {"current_occupancy": current, "capacity": capacity},
            }
        return None


class ExcessiveDwellDetector(BaseDetector):
    """Detects when a person dwells in a zone for too long."""

    @property
    def name(self) -> str:
        return "excessive_dwell"

    async def evaluate(self, event: dict, context: dict) -> Optional[dict]:
        if event.get("event_type") != "dwell_time_completed":
            return None

        dwell_seconds = event.get("metadata", {}).get("dwell_seconds", 0)
        if dwell_seconds >= settings.dwell_time_threshold:
            zone_id = event.get("zone_id", "")
            return {
                "anomaly_type": "excessive_dwell",
                "severity": "WARN",
                "zone_id": zone_id,
                "zone_name": event.get("zone_name", zone_id),
                "description": (
                    f"Visitor dwelled {int(dwell_seconds)}s in "
                    f"'{event.get('zone_name', zone_id)}' "
                    f"(threshold: {settings.dwell_time_threshold}s)"
                ),
                "suggested_action": "Check if visitor needs assistance.",
                "metadata": {"dwell_seconds": dwell_seconds},
            }
        return None


class TrafficSpikeDetector(BaseDetector):
    """Detects unusual traffic spikes within a time window."""

    def __init__(self):
        self._entry_timestamps: Dict[str, List[datetime]] = defaultdict(list)

    @property
    def name(self) -> str:
        return "traffic_spike"

    async def evaluate(self, event: dict, context: dict) -> Optional[dict]:
        if event.get("event_type") not in ("person_entered", "zone_entered"):
            return None

        zone_id = event.get("zone_id", "")
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(seconds=settings.traffic_spike_window)

        self._entry_timestamps[zone_id].append(now)
        self._entry_timestamps[zone_id] = [
            ts for ts in self._entry_timestamps[zone_id] if ts > window_start
        ]

        count = len(self._entry_timestamps[zone_id])
        if count >= settings.traffic_spike_threshold:
            severity = "INFO" if count < settings.traffic_spike_threshold * 1.5 else "WARN"
            return {
                "anomaly_type": "traffic_spike",
                "severity": severity,
                "zone_id": zone_id,
                "zone_name": event.get("zone_name", zone_id),
                "description": (
                    f"Traffic spike in '{event.get('zone_name', zone_id)}': "
                    f"{count} entries in {settings.traffic_spike_window}s"
                ),
                "suggested_action": "Consider opening more checkout lanes or adjusting staffing.",
                "metadata": {"entry_count": count, "window_seconds": settings.traffic_spike_window},
            }
        return None


# ------------------------------------------------------------------ #
# New v1.1 detectors                                                   #
# ------------------------------------------------------------------ #

class QueueSpikeDetector(BaseDetector):
    """Detects when checkout queue depth significantly exceeds the 1-hour rolling average."""

    def __init__(self):
        # Rolling window of (timestamp, queue_depth) pairs
        self._depth_history: deque = deque(maxlen=3600)   # one sample per second max

    @property
    def name(self) -> str:
        return "queue_spike"

    async def evaluate(self, event: dict, context: dict) -> Optional[dict]:
        current_queue = context.get("zone_occupancy", {}).get("zone_checkout", 0)
        now = time.time()
        self._depth_history.append((now, current_queue))

        # Keep only last 60 minutes
        one_hour_ago = now - 3600
        recent = [d for t, d in self._depth_history if t >= one_hour_ago]
        if len(recent) < 5:
            return None

        avg = sum(recent) / len(recent)
        if avg == 0:
            return None

        if current_queue >= avg * 2 and current_queue >= 3:
            return {
                "anomaly_type": "queue_spike",
                "severity": "WARN" if current_queue < avg * 3 else "CRITICAL",
                "zone_id": "zone_checkout",
                "zone_name": "Checkout",
                "description": (
                    f"Checkout queue ({current_queue}) is "
                    f"{current_queue / avg:.1f}x above 1-hour average ({avg:.1f})"
                ),
                "suggested_action": "Open additional checkout counters immediately.",
                "metadata": {"current_queue": current_queue, "avg_queue": round(avg, 1)},
            }
        return None


class ConversionDropDetector(BaseDetector):
    """Detects when today's conversion rate falls significantly below baseline."""

    BASELINE_CONVERSION = 0.15   # 15% expected baseline
    MIN_VISITORS = 10            # need enough data before alerting

    @property
    def name(self) -> str:
        return "conversion_drop"

    async def evaluate(self, event: dict, context: dict) -> Optional[dict]:
        # Only evaluate on person_exited events (end of visit)
        if event.get("event_type") != "person_exited":
            return None

        metrics = context.get("metrics", {})
        unique_visitors = metrics.get("unique_visitors", 0)
        conversion_rate = metrics.get("conversion_rate", self.BASELINE_CONVERSION)

        if unique_visitors < self.MIN_VISITORS:
            return None

        if conversion_rate < self.BASELINE_CONVERSION * 0.5:
            return {
                "anomaly_type": "conversion_drop",
                "severity": "WARN",
                "zone_id": "",
                "zone_name": "Store",
                "description": (
                    f"Conversion rate {conversion_rate:.1%} is below "
                    f"50% of baseline ({self.BASELINE_CONVERSION:.1%})"
                ),
                "suggested_action": "Review pricing, promotions, or staff assistance quality.",
                "metadata": {
                    "conversion_rate": conversion_rate,
                    "baseline": self.BASELINE_CONVERSION,
                    "unique_visitors": unique_visitors,
                },
            }
        return None


class DeadZoneDetector(BaseDetector):
    """Detects when a zone receives no visits within a configurable time window."""

    DEAD_ZONE_WINDOW_SEC = 1800   # 30 minutes

    def __init__(self):
        self._last_visit: Dict[str, float] = {}

    @property
    def name(self) -> str:
        return "dead_zone"

    async def evaluate(self, event: dict, context: dict) -> Optional[dict]:
        zone_id = event.get("zone_id", "")
        event_type = event.get("event_type", "")

        # Update last-visit timestamp on any zone entry
        if event_type in ("zone_entered", "person_entered") and zone_id:
            self._last_visit[zone_id] = time.time()

        now = time.time()
        zones_config = context.get("zones_config", {})

        anomalies = []
        for zid, zone_cfg in zones_config.items():
            if zid in ("store",):
                continue
            last = self._last_visit.get(zid)
            if last is None:
                # Never visited since startup — only flag after warm-up
                if now > self.DEAD_ZONE_WINDOW_SEC:
                    anomalies.append(zid)
            elif (now - last) > self.DEAD_ZONE_WINDOW_SEC:
                anomalies.append(zid)

        if anomalies:
            zid = anomalies[0]
            zone_cfg = zones_config.get(zid, {})
            return {
                "anomaly_type": "dead_zone",
                "severity": "INFO",
                "zone_id": zid,
                "zone_name": zone_cfg.get("name", zid),
                "description": (
                    f"Zone '{zone_cfg.get('name', zid)}' has had no visits "
                    f"in the last {self.DEAD_ZONE_WINDOW_SEC // 60} minutes."
                ),
                "suggested_action": "Check zone signage, lighting, or product availability.",
                "metadata": {"dead_zones": anomalies, "window_minutes": self.DEAD_ZONE_WINDOW_SEC // 60},
            }
        return None


# ------------------------------------------------------------------ #
# Registry                                                             #
# ------------------------------------------------------------------ #

class DetectorRegistry:
    def __init__(self):
        self._detectors: List[BaseDetector] = []

    def register(self, detector: BaseDetector):
        self._detectors.append(detector)
        logger.info(f"Registered anomaly detector: {detector.name}")

    async def evaluate_all(self, event: dict, context: dict) -> List[dict]:
        anomalies = []
        for detector in self._detectors:
            try:
                result = await detector.evaluate(event, context)
                if result:
                    anomalies.append(result)
            except Exception as e:
                logger.error(f"Detector '{detector.name}' error: {e}")
        return anomalies


# ------------------------------------------------------------------ #
# Engine                                                               #
# ------------------------------------------------------------------ #

class AnomalyEngine:
    """Anomaly detection engine — evaluates events and persists anomalies."""

    def __init__(self):
        self.registry = DetectorRegistry()
        self._kafka_producer: Optional[AIOKafkaProducer] = None
        self._total_anomalies: int = 0
        self._zones_config = {z["id"]: z for z in load_zones_config()}

        # Register all detectors
        self.registry.register(OvercrowdingDetector())
        self.registry.register(ExcessiveDwellDetector())
        self.registry.register(TrafficSpikeDetector())
        self.registry.register(QueueSpikeDetector())
        self.registry.register(ConversionDropDetector())
        self.registry.register(DeadZoneDetector())

    async def start(self):
        try:
            self._kafka_producer = AIOKafkaProducer(
                bootstrap_servers=settings.kafka_bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            )
            await self._kafka_producer.start()
            logger.info("Anomaly engine Kafka producer started")
        except Exception as e:
            logger.error(f"Anomaly engine Kafka producer failed: {e}")
            self._kafka_producer = None

    async def stop(self):
        if self._kafka_producer:
            await self._kafka_producer.stop()

    async def evaluate(self, event: dict, zone_occupancy: dict, metrics: dict = None) -> List[dict]:
        """Evaluate an event for anomalies using all registered detectors."""
        context = {
            "zone_occupancy": zone_occupancy,
            "zones_config": self._zones_config,
            "metrics": metrics or {},
        }

        anomalies = await self.registry.evaluate_all(event, context)

        for anomaly in anomalies:
            self._total_anomalies += 1
            anomaly_record = {
                "anomaly_id": str(uuid.uuid4()),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                **anomaly,
            }
            await self._persist_anomaly(anomaly_record)
            await self._publish_anomaly(anomaly_record)

        return anomalies

    async def _persist_anomaly(self, anomaly: dict):
        try:
            async with async_session() as session:
                from dateutil.parser import isoparse
                meta = dict(anomaly.get("metadata", {}))
                meta["suggested_action"] = anomaly.get("suggested_action", "")
                db_anomaly = AnomalyEvent(
                    id=anomaly["anomaly_id"],
                    anomaly_type=anomaly["anomaly_type"],
                    severity=anomaly["severity"],
                    zone_id=anomaly.get("zone_id", ""),
                    zone_name=anomaly.get("zone_name", ""),
                    description=anomaly.get("description", ""),
                    timestamp=isoparse(anomaly["timestamp"]),
                    metadata_=meta,
                )
                session.add(db_anomaly)
                await session.commit()
        except Exception as e:
            logger.error(f"Failed to persist anomaly: {e}")

    async def _publish_anomaly(self, anomaly: dict):
        if self._kafka_producer:
            try:
                await self._kafka_producer.send_and_wait(
                    settings.kafka_anomaly_events_topic,
                    value=anomaly,
                )
            except Exception as e:
                logger.error(f"Failed to publish anomaly to Kafka: {e}")

    @property
    def total_anomalies(self) -> int:
        return self._total_anomalies
