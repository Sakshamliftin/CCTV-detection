"""Anomaly detection engine — rule-based with pluggable architecture.

Designed for extensibility: implement BaseDetector and register
via the DetectorRegistry to add new anomaly detection strategies.

TODO ====> Add ML-based anomaly detectors (e.g., isolation forest, autoencoder)
"""
import asyncio
import json
import logging
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
import random

from aiokafka import AIOKafkaProducer

from app.config import settings, load_zones_config
from app.database import async_session
from app.models import AnomalyEvent

logger = logging.getLogger(__name__)


# --- Base Detector Interface ---

class BaseDetector(ABC):
    """Abstract base class for anomaly detectors.
    
    Implement `evaluate()` to create custom anomaly detection logic.
    Register via DetectorRegistry for automatic evaluation.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique detector name."""
        ...

    @abstractmethod
    async def evaluate(self, event: dict, context: dict) -> Optional[dict]:
        """Evaluate an event for anomalies.
        
        Args:
            event: The store event to evaluate.
            context: Current analytics context (occupancy, traffic, etc.).
            
        Returns:
            Anomaly dict if detected, None otherwise.
            Expected format: {anomaly_type, severity, zone_id, zone_name, description, metadata}
        """
        ...


# --- Rule-Based Detectors ---

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
            severity = "critical" if current >= capacity else "warning"
            return {
                "anomaly_type": "overcrowding",
                "severity": severity,
                "zone_id": zone_id,
                "zone_name": zone_cfg.get("name", zone_id),
                "description": f"Zone '{zone_cfg.get('name', zone_id)}' occupancy ({current}) exceeds {int(settings.overcrowding_threshold * 100)}% of capacity ({capacity})",
                "metadata": {"current_occupancy": current, "capacity": capacity, "threshold": threshold},
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
                "severity": "warning",
                "zone_id": zone_id,
                "zone_name": event.get("zone_name", zone_id),
                "description": f"Person (track {event.get('track_id')}) dwelled {int(dwell_seconds)}s in '{event.get('zone_name', zone_id)}' (threshold: {settings.dwell_time_threshold}s)",
                "metadata": {"dwell_seconds": dwell_seconds, "track_id": event.get("track_id")},
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
        
        # Record entry
        self._entry_timestamps[zone_id].append(now)
        
        # Clean old entries
        self._entry_timestamps[zone_id] = [
            ts for ts in self._entry_timestamps[zone_id] if ts > window_start
        ]
        
        count = len(self._entry_timestamps[zone_id])
        if count >= settings.traffic_spike_threshold:
            return {
                "anomaly_type": "traffic_spike",
                "severity": "info" if count < settings.traffic_spike_threshold * 1.5 else "warning",
                "zone_id": zone_id,
                "zone_name": event.get("zone_name", zone_id),
                "description": f"Traffic spike in '{event.get('zone_name', zone_id)}': {count} entries in {settings.traffic_spike_window}s (threshold: {settings.traffic_spike_threshold})",
                "metadata": {"entry_count": count, "window_seconds": settings.traffic_spike_window},
            }
        return None

class IsolationForestDetector(BaseDetector):
    """Placeholder for ML-based anomaly detector (Isolation Forest)."""
    
    @property
    def name(self) -> str:
        return "ml_isolation_forest"

    async def evaluate(self, event: dict, context: dict) -> Optional[dict]:
        # Dummy ML prediction logic
        if random.random() < 0.001:  # 0.1% chance of random anomaly
            zone_id = event.get("zone_id", "unknown")
            return {
                "anomaly_type": "ml_behavior_anomaly",
                "severity": "warning",
                "zone_id": zone_id,
                "zone_name": event.get("zone_name", zone_id),
                "description": f"ML model detected unusual behavioral pattern in zone '{event.get('zone_name', zone_id)}'",
                "metadata": {"ml_model": "isolation_forest", "confidence_score": round(random.uniform(0.7, 0.99), 2)},
            }
        return None


# --- Detector Registry ---

class DetectorRegistry:
    """Registry of anomaly detectors. Supports pluggable detector architecture."""

    def __init__(self):
        self._detectors: List[BaseDetector] = []

    def register(self, detector: BaseDetector):
        """Register a detector for evaluation."""
        self._detectors.append(detector)
        logger.info(f"Registered anomaly detector: {detector.name}")

    async def evaluate_all(self, event: dict, context: dict) -> List[dict]:
        """Run all registered detectors against an event."""
        anomalies = []
        for detector in self._detectors:
            try:
                result = await detector.evaluate(event, context)
                if result:
                    anomalies.append(result)
            except Exception as e:
                logger.error(f"Detector '{detector.name}' error: {e}")
        return anomalies


# --- Anomaly Engine ---

class AnomalyEngine:
    """Anomaly detection engine — evaluates events and persists anomalies."""

    def __init__(self):
        self.registry = DetectorRegistry()
        self._kafka_producer: Optional[AIOKafkaProducer] = None
        self._total_anomalies: int = 0
        self._zones_config = {z["id"]: z for z in load_zones_config()}
        
        # Register built-in detectors
        self.registry.register(OvercrowdingDetector())
        self.registry.register(ExcessiveDwellDetector())
        self.registry.register(TrafficSpikeDetector())
        self.registry.register(IsolationForestDetector())

    async def start(self):
        """Start Kafka producer for anomaly events."""
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

    async def evaluate(self, event: dict, zone_occupancy: dict) -> List[dict]:
        """Evaluate an event for anomalies using all registered detectors."""
        context = {
            "zone_occupancy": zone_occupancy,
            "zones_config": self._zones_config,
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
        """Save anomaly to PostgreSQL."""
        try:
            async with async_session() as session:
                from dateutil.parser import isoparse
                db_anomaly = AnomalyEvent(
                    id=anomaly["anomaly_id"],
                    anomaly_type=anomaly["anomaly_type"],
                    severity=anomaly["severity"],
                    zone_id=anomaly.get("zone_id", ""),
                    zone_name=anomaly.get("zone_name", ""),
                    description=anomaly.get("description", ""),
                    timestamp=isoparse(anomaly["timestamp"]),
                    metadata_=anomaly.get("metadata", {}),
                )
                session.add(db_anomaly)
                await session.commit()
        except Exception as e:
            logger.error(f"Failed to persist anomaly: {e}")

    async def _publish_anomaly(self, anomaly: dict):
        """Publish anomaly to Kafka topic."""
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
