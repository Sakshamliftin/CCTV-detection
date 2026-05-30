"""YOLOv8 person detector using ultralytics."""
import logging
from dataclasses import dataclass
from typing import List

import numpy as np
from ultralytics import YOLO

from app.config import settings

logger = logging.getLogger(__name__)

PERSON_CLASS_ID = 0  # COCO class index for 'person'


@dataclass
class Detection:
    """A single person detection."""
    bbox: tuple[float, float, float, float]  # x1, y1, x2, y2
    confidence: float
    class_id: int = PERSON_CLASS_ID


class PersonDetector:
    """Wraps YOLOv8 for person detection."""

    def __init__(self):
        logger.info(f"Loading YOLO model: {settings.yolo_model} on {settings.yolo_device}")
        self.model = YOLO(settings.yolo_model)
        self.confidence = settings.yolo_confidence
        self.device = settings.yolo_device
        logger.info("YOLO model loaded successfully")

    def detect(self, frame: np.ndarray) -> List[Detection]:
        """Run detection on a single frame, returning only person detections."""
        results = self.model(
            frame,
            conf=self.confidence,
            device=self.device,
            classes=[PERSON_CLASS_ID],
            verbose=False,
        )
        
        detections = []
        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue
            for i in range(len(boxes)):
                bbox = boxes.xyxy[i].cpu().numpy()
                conf = float(boxes.conf[i].cpu().numpy())
                detections.append(Detection(
                    bbox=(float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])),
                    confidence=conf,
                ))
        
        return detections
