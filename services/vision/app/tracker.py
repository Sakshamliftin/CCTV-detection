"""ByteTrack multi-object tracker using supervision."""
import logging
from dataclasses import dataclass, field
from typing import Dict, List

import numpy as np
import supervision as sv

from app.detector import Detection

logger = logging.getLogger(__name__)


@dataclass
class TrackedPerson:
    """A tracked person with persistent identity."""
    track_id: int
    bbox: tuple[float, float, float, float]
    confidence: float
    center: tuple[float, float] = field(init=False)

    def __post_init__(self):
        x1, y1, x2, y2 = self.bbox
        self.center = ((x1 + x2) / 2, (y1 + y2) / 2)


class PersonTracker:
    """Wraps ByteTrack for persistent person tracking across frames."""

    def __init__(
        self,
        track_activation_threshold: float = 0.25,
        lost_track_buffer: int = 30,
        minimum_matching_threshold: float = 0.8,
        frame_rate: int = 30,
    ):
        self.tracker = sv.ByteTrack(
            track_activation_threshold=track_activation_threshold,
            lost_track_buffer=lost_track_buffer,
            minimum_matching_threshold=minimum_matching_threshold,
            frame_rate=frame_rate,
        )
        self._active_tracks: Dict[int, TrackedPerson] = {}
        logger.info("ByteTrack tracker initialized")

    def update(self, detections: List[Detection]) -> List[TrackedPerson]:
        """Update tracker with new detections, return tracked persons."""
        if not detections:
            # Pass empty detections to let tracker handle lost tracks
            sv_detections = sv.Detections.empty()
        else:
            bboxes = np.array([d.bbox for d in detections], dtype=np.float32)
            confidences = np.array([d.confidence for d in detections], dtype=np.float32)
            class_ids = np.array([d.class_id for d in detections], dtype=int)
            sv_detections = sv.Detections(
                xyxy=bboxes,
                confidence=confidences,
                class_id=class_ids,
            )

        tracked = self.tracker.update_with_detections(sv_detections)
        
        persons = []
        if tracked.tracker_id is not None:
            for i in range(len(tracked)):
                person = TrackedPerson(
                    track_id=int(tracked.tracker_id[i]),
                    bbox=tuple(tracked.xyxy[i].tolist()),
                    confidence=float(tracked.confidence[i]) if tracked.confidence is not None else 1.0,
                )
                persons.append(person)
        
        # Update active tracks map
        current_ids = {p.track_id for p in persons}
        lost_ids = set(self._active_tracks.keys()) - current_ids
        self._active_tracks = {p.track_id: p for p in persons}
        
        return persons

    def get_lost_track_ids(self) -> set:
        """Return IDs that were active but are no longer tracked."""
        current = set(self._active_tracks.keys())
        # This is called externally to detect exits
        return current

    def reset(self):
        """Reset tracker state."""
        self.tracker.reset()
        self._active_tracks.clear()
