"""Kafka consumer — subscribes to store_events and dispatches to engines.

v1.1: Tracks last_event_timestamp for stale feed detection.
"""
import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from aiokafka import AIOKafkaConsumer

from app.config import settings
from app.services.analytics_engine import AnalyticsEngine
from app.services.anomaly_engine import AnomalyEngine

logger = logging.getLogger(__name__)


class EventConsumer:
    """Consumes store events from Kafka and dispatches to processing engines."""

    def __init__(self, analytics: AnalyticsEngine, anomaly: AnomalyEngine):
        self.analytics = analytics
        self.anomaly = anomaly
        self._consumer: Optional[AIOKafkaConsumer] = None
        self._running = False
        self.last_event_timestamp: Optional[str] = None   # ISO string

    async def start(self):
        """Start consuming from Kafka."""
        retry_count = 0
        max_retries = 10

        while retry_count < max_retries:
            try:
                self._consumer = AIOKafkaConsumer(
                    settings.kafka_store_events_topic,
                    bootstrap_servers=settings.kafka_bootstrap_servers,
                    group_id=settings.kafka_group_id,
                    value_deserializer=lambda m: json.loads(m.decode("utf-8")),
                    auto_offset_reset="latest",
                    enable_auto_commit=True,
                )
                await self._consumer.start()
                self._running = True
                logger.info(
                    f"Kafka consumer started, subscribed to '{settings.kafka_store_events_topic}'"
                )
                await self._consume_loop()
                break

            except Exception as e:
                retry_count += 1
                wait_time = min(retry_count * 3, 30)
                logger.warning(
                    f"Kafka consumer connection attempt {retry_count}/{max_retries} "
                    f"failed: {e}. Retrying in {wait_time}s..."
                )
                await asyncio.sleep(wait_time)

        if retry_count >= max_retries:
            logger.error("Kafka consumer failed to connect after max retries")

    async def _consume_loop(self):
        """Main consumption loop."""
        try:
            async for message in self._consumer:
                if not self._running:
                    break
                try:
                    event = message.value
                    self.last_event_timestamp = datetime.now(timezone.utc).isoformat()
                    logger.debug(
                        f"Received event: {event.get('event_type')} from {message.topic}"
                    )

                    # Process through analytics engine
                    await self.analytics.process_event(event)

                    # Pass current metrics to anomaly engine for ConversionDropDetector
                    zone_occupancy = dict(self.analytics._zone_occupancy)
                    metrics = self.analytics.get_metrics()
                    await self.anomaly.evaluate(event, zone_occupancy, metrics)

                except Exception as e:
                    logger.error(f"Error processing event: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"Consumer loop error: {e}")
        finally:
            await self.stop()

    async def stop(self):
        self._running = False
        if self._consumer:
            try:
                await self._consumer.stop()
            except Exception:
                pass
            logger.info("Kafka consumer stopped")

    @property
    def is_connected(self) -> bool:
        return self._running and self._consumer is not None
