"""Fallback event simulator for development/demo when no video source is available.

Activated only when ENABLE_SIMULATOR=true. The primary workflow is real
YOLOv8 + ByteTrack processing of actual video or RTSP streams.
"""
import asyncio
import logging
import random
import time
from typing import List

from app.config import settings
from app.event_producer import EventProducer

logger = logging.getLogger(__name__)

# Realistic zone visit weights (probability a person visits each zone)
ZONE_WEIGHTS = {
    "zone_entrance": 1.0,
    "zone_grocery": 0.6,
    "zone_electronics": 0.35,
    "zone_clothing": 0.3,
    "zone_checkout": 0.7,
}

ZONE_NAMES = {
    "zone_entrance": "Entrance",
    "zone_grocery": "Grocery",
    "zone_electronics": "Electronics",
    "zone_clothing": "Clothing",
    "zone_checkout": "Checkout",
}

CAMERA_IDS = ["cam_01", "cam_02", "cam_03", "cam_04"]
CAMERA_ZONE_MAP = {
    "cam_01": ["zone_entrance"],
    "cam_02": ["zone_checkout"],
    "cam_03": ["zone_electronics", "zone_grocery"],
    "cam_04": ["zone_clothing"],
}


class EventSimulator:
    """Generates realistic synthetic store events for development."""

    def __init__(self, producer: EventProducer):
        self.producer = producer
        self._running = False
        self._track_counter = 0
        self._active_persons: dict = {}  # track_id -> {zones, enter_time}

    async def start(self):
        """Start the simulation loop."""
        self._running = True
        logger.info("Event simulator started (fallback/dev mode)")

        while self._running:
            try:
                await self._simulate_tick()
                await asyncio.sleep(settings.simulator_interval)
            except Exception as e:
                logger.error(f"Simulator error: {e}")
                await asyncio.sleep(5)

    async def _simulate_tick(self):
        """Simulate one tick of store activity."""
        # Simulate 1-3 new people entering per tick
        new_count = random.choices([0, 1, 2, 3], weights=[0.2, 0.4, 0.3, 0.1])[0]
        for _ in range(new_count):
            self._track_counter += 1
            track_id = self._track_counter
            camera_id = random.choice(CAMERA_IDS)

            # Person enters store
            await self.producer.publish_event(
                event_type="person_entered",
                camera_id="cam_01",  # Always enter via entrance camera
                track_id=track_id,
                zone_id="zone_entrance",
                zone_name="Entrance",
                metadata={"confidence": round(random.uniform(0.7, 0.98), 2)},
            )

            # Plan a zone visit path
            visit_zones = ["zone_entrance"]
            for zone_id, weight in ZONE_WEIGHTS.items():
                if zone_id != "zone_entrance" and random.random() < weight:
                    visit_zones.append(zone_id)

            self._active_persons[track_id] = {
                "zones_to_visit": visit_zones[1:],  # Remaining zones after entrance
                "current_zone": "zone_entrance",
                "enter_time": time.time(),
                "ticks_remaining": random.randint(3, 15),
            }

        # Progress existing persons
        exited = []
        for track_id, state in self._active_persons.items():
            state["ticks_remaining"] -= 1

            if state["zones_to_visit"] and random.random() < 0.4:
                # Move to next zone
                old_zone = state["current_zone"]
                new_zone = state["zones_to_visit"].pop(0)
                camera_id = self._zone_to_camera(new_zone)

                # Exit old zone
                dwell = round(random.uniform(15, 180), 1)
                await self.producer.publish_event(
                    event_type="zone_exited",
                    camera_id=self._zone_to_camera(old_zone),
                    track_id=track_id,
                    zone_id=old_zone,
                    zone_name=ZONE_NAMES[old_zone],
                    metadata={"dwell_seconds": dwell},
                )

                if dwell >= 30:
                    await self.producer.publish_event(
                        event_type="dwell_time_completed",
                        camera_id=self._zone_to_camera(old_zone),
                        track_id=track_id,
                        zone_id=old_zone,
                        zone_name=ZONE_NAMES[old_zone],
                        metadata={"dwell_seconds": dwell},
                    )

                # Enter new zone
                await self.producer.publish_event(
                    event_type="zone_entered",
                    camera_id=camera_id,
                    track_id=track_id,
                    zone_id=new_zone,
                    zone_name=ZONE_NAMES[new_zone],
                    metadata={"confidence": round(random.uniform(0.7, 0.98), 2)},
                )
                state["current_zone"] = new_zone

            elif state["ticks_remaining"] <= 0:
                # Person exits store
                dwell = round(time.time() - state["enter_time"], 1)
                await self.producer.publish_event(
                    event_type="zone_exited",
                    camera_id=self._zone_to_camera(state["current_zone"]),
                    track_id=track_id,
                    zone_id=state["current_zone"],
                    zone_name=ZONE_NAMES[state["current_zone"]],
                    metadata={"dwell_seconds": round(random.uniform(10, 60), 1)},
                )
                await self.producer.publish_event(
                    event_type="person_exited",
                    camera_id="cam_01",
                    track_id=track_id,
                    zone_id="zone_entrance",
                    zone_name="Entrance",
                    metadata={"dwell_seconds": dwell},
                )
                exited.append(track_id)

        for tid in exited:
            del self._active_persons[tid]

    def _zone_to_camera(self, zone_id: str) -> str:
        """Map zone to most likely camera."""
        for cam_id, zones in CAMERA_ZONE_MAP.items():
            if zone_id in zones:
                return cam_id
        return "cam_01"

    def stop(self):
        self._running = False
        logger.info("Event simulator stopped")
