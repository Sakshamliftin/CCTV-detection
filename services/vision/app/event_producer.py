"""Kafka event producer for publishing store events."""
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from aiokafka import AIOKafkaProducer

from app.config import settings

logger = logging.getLogger(__name__)


class EventProducer:
    """Publishes structured business events to Kafka."""

    def __init__(self):
        self._producer: Optional[AIOKafkaProducer] = None

    async def start(self):
        """Initialize and start the Kafka producer."""
        try:
            self._producer = AIOKafkaProducer(
                bootstrap_servers=settings.kafka_bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                key_serializer=lambda k: k.encode("utf-8") if k else None,
            )
            await self._producer.start()
            logger.info(f"Kafka producer connected to {settings.kafka_bootstrap_servers}")
        except Exception as e:
            logger.error(f"Failed to start Kafka producer: {e}")
            self._producer = None

    async def stop(self):
        """Stop the Kafka producer."""
        if self._producer:
            await self._producer.stop()
            logger.info("Kafka producer stopped")

    async def publish_event(
        self,
        event_type: str,
        camera_id: str,
        track_id: int,
        zone_id: str = "",
        zone_name: str = "",
        metadata: Optional[dict] = None,
    ):
        """Publish a store event to Kafka."""
        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": event_type,
            "camera_id": camera_id,
            "track_id": track_id,
            "zone_id": zone_id,
            "zone_name": zone_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {},
        }

        if self._producer:
            try:
                await self._producer.send_and_wait(
                    settings.kafka_store_events_topic,
                    value=event,
                    key=camera_id,
                )
                logger.debug(f"Published event: {event_type} track={track_id} zone={zone_id}")
            except Exception as e:
                logger.error(f"Failed to publish event: {e}")
        else:
            logger.warning(f"Kafka unavailable — dropping event: {event_type}")
