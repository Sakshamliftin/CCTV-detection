"""Video processing pipeline: frame → detect → track → zone check → events.

Upgrades (v1.1):
- Staff classification: track IDs where track_id % 10 == 0 are treated as staff.
- Group entry detection: persons entering within 2s of each other share a group_id.
- Direction metadata forwarded from zone events.
- is_staff + confidence forwarded to publish_event.
"""
import asyncio
import logging
import time
import uuid
from typing import Dict, Optional, Set, List

import cv2
import numpy as np

from app.config import settings
from app.detector import PersonDetector
from app.tracker import PersonTracker
from app.zones import ZoneManager
from app.event_producer import EventProducer

logger = logging.getLogger(__name__)


def _is_staff(track_id: int) -> bool:
    """Lightweight staff heuristic.

    In production, replace with uniform-colour classifier or badge detection.
    Here, track IDs divisible by 10 are treated as staff for deterministic
    testing (0.1 false-positive rate on a uniform track counter).
    """
    return track_id % 10 == 0


class VideoPipeline:
    """Processes video frames through the full CV pipeline."""

    def __init__(
        self,
        detector: PersonDetector,
        tracker: PersonTracker,
        zone_manager: ZoneManager,
        event_producer: EventProducer,
    ):
        self.detector = detector
        self.tracker = tracker
        self.zone_manager = zone_manager
        self.producer = event_producer
        self._active_tracks: Set[int] = set()
        self._running = False
        self._frame_count = 0
        self._fps = 0.0
        # Group entry tracking: track_id -> group_id for persons entering close together
        self._recent_entries: List[Dict] = []  # [{track_id, time, group_id}]

    def _assign_group(self, track_id: int) -> Optional[str]:
        """Assign a group_id if this entry occurs within 2s of a recent entry."""
        now = time.time()
        window = 2.0
        # Prune stale entries
        self._recent_entries = [
            e for e in self._recent_entries if now - e["time"] <= window
        ]
        if self._recent_entries:
            # Reuse the group_id of the most-recent entry
            group_id = self._recent_entries[-1]["group_id"]
        else:
            group_id = str(uuid.uuid4())

        self._recent_entries.append({"track_id": track_id, "time": now, "group_id": group_id})
        return group_id if len(self._recent_entries) > 1 else None

    async def process_video(self, source: str, camera_id: str):
        """Process a video file or RTSP stream.

        Args:
            source: Path to video file or RTSP URL
            camera_id: Camera identifier for event tagging
        """
        logger.info(f"Starting pipeline for camera={camera_id} source={source}")
        self._running = True
        self._frame_count = 0

        # Open video source in a thread to avoid blocking
        cap = await asyncio.to_thread(cv2.VideoCapture, source)

        if not cap.isOpened():
            logger.error(f"Failed to open video source: {source}")
            self._running = False
            return

        frame_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        source_fps = cap.get(cv2.CAP_PROP_FPS) or 30
        logger.info(f"Video opened: {frame_w}x{frame_h} @ {source_fps:.1f}fps")

        frame_idx = 0
        start_time = time.time()

        try:
            while self._running:
                ret, frame = await asyncio.to_thread(cap.read)
                if not ret:
                    logger.info(f"Video source ended for camera={camera_id}")
                    break

                frame_idx += 1
                # Skip frames for performance
                if frame_idx % settings.frame_skip != 0:
                    continue

                self._frame_count += 1

                # Detect persons
                detections = await asyncio.to_thread(self.detector.detect, frame)

                # Track across frames
                tracked = await asyncio.to_thread(self.tracker.update, detections)
                current_ids = {p.track_id for p in tracked}

                # Detect exits (previously active, now gone)
                lost_ids = self._active_tracks - current_ids
                for lost_id in lost_ids:
                    exit_events = self.zone_manager.handle_person_exit(lost_id)
                    staff = _is_staff(lost_id)
                    for evt in exit_events:
                        await self.producer.publish_event(
                            event_type=evt["event_type"],
                            camera_id=camera_id,
                            track_id=lost_id,
                            zone_id=evt.get("zone_id", ""),
                            zone_name=evt.get("zone_name", ""),
                            metadata={
                                "dwell_seconds": evt.get("dwell_seconds", 0),
                                "direction": evt.get("direction", "unknown"),
                            },
                            confidence=1.0,
                            is_staff=staff,
                        )

                # Check zone transitions for active tracks
                for person in tracked:
                    staff = _is_staff(person.track_id)
                    zone_events = self.zone_manager.check_zones(
                        track_id=person.track_id,
                        center=person.center,
                        frame_w=frame_w,
                        frame_h=frame_h,
                    )
                    for evt in zone_events:
                        extra_meta: dict = {
                            "dwell_seconds": evt.get("dwell_seconds", 0),
                            "direction": evt.get("direction", "unknown"),
                        }
                        # Group entry detection only on person_entered events
                        if evt["event_type"] == "person_entered":
                            group_id = self._assign_group(person.track_id)
                            if group_id:
                                extra_meta["group_id"] = group_id
                                extra_meta["is_group"] = True

                        await self.producer.publish_event(
                            event_type=evt["event_type"],
                            camera_id=camera_id,
                            track_id=person.track_id,
                            zone_id=evt.get("zone_id", ""),
                            zone_name=evt.get("zone_name", ""),
                            metadata=extra_meta,
                            confidence=person.confidence,
                            is_staff=staff,
                        )

                self._active_tracks = current_ids

                # Calculate processing FPS
                elapsed = time.time() - start_time
                if elapsed > 0:
                    self._fps = self._frame_count / elapsed

                # Yield control to event loop
                await asyncio.sleep(0)

        except Exception as e:
            logger.error(f"Pipeline error for camera={camera_id}: {e}", exc_info=True)
        finally:
            await asyncio.to_thread(cap.release)
            self._running = False
            # Handle remaining active tracks as exits
            for track_id in self._active_tracks:
                exit_events = self.zone_manager.handle_person_exit(track_id)
                staff = _is_staff(track_id)
                for evt in exit_events:
                    await self.producer.publish_event(
                        event_type=evt["event_type"],
                        camera_id=camera_id,
                        track_id=track_id,
                        zone_id=evt.get("zone_id", ""),
                        zone_name=evt.get("zone_name", ""),
                        metadata={
                            "dwell_seconds": evt.get("dwell_seconds", 0),
                            "direction": evt.get("direction", "unknown"),
                        },
                        confidence=1.0,
                        is_staff=staff,
                    )
            self._active_tracks.clear()
            logger.info(
                f"Pipeline stopped for camera={camera_id}. "
                f"Processed {self._frame_count} frames at {self._fps:.1f} fps"
            )

    def stop(self):
        """Signal the pipeline to stop processing."""
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def stats(self) -> dict:
        return {
            "running": self._running,
            "frames_processed": self._frame_count,
            "fps": round(self._fps, 1),
        }
