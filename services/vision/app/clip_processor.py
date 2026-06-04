import asyncio
import logging
import time
from typing import Dict, List, Optional
import cv2
import datetime

from app.config import settings
from app.detector import PersonDetector
from app.tracker import PersonTracker
from app.zones import ZoneManager
from app.event_producer import EventProducer
from app.jsonl_emitter import JSONLEmitter
from app.queue_detector import QueueDetector
from app.age_gender import AgeGenderPredictor

logger = logging.getLogger(__name__)


class ClipProcessor:
    """Processes a video clip and emits JSONL-compliant events."""

    def __init__(
        self,
        detector: PersonDetector,
        zone_manager: ZoneManager,
        producer: EventProducer,
        jsonl_emitter: JSONLEmitter
    ):
        self.detector = detector
        self.zone_manager = zone_manager
        self.producer = producer
        self.jsonl_emitter = jsonl_emitter

    async def process_clip(self, store_id: str, clip_type: str, camera_id: str, file_path: str):
        """Processes a single clip based on its type."""
        logger.info(f"Processing clip {file_path} (type: {clip_type}) for store {store_id}")
        
        tracker = PersonTracker()
        cap = await asyncio.to_thread(cv2.VideoCapture, file_path)
        
        if not cap.isOpened():
            logger.error(f"Could not open {file_path}")
            return
            
        frame_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        queue_detector = QueueDetector()
        
        frame_idx = 0
        running = True
        
        try:
            while running:
                ret, frame = await asyncio.to_thread(cap.read)
                if not ret:
                    break
                    
                frame_idx += 1
                if frame_idx % settings.frame_skip != 0:
                    continue
                    
                # Detect and track
                detections = await asyncio.to_thread(self.detector.detect, frame)
                tracked = await asyncio.to_thread(tracker.update, detections)
                
                # Base timestamp for events (simulated as current time if no video time available)
                # In real scenario, you'd use video metadata or start time + frame_offset
                current_time = time.time()
                ts_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
                
                hotspots = {}
                track_ids_in_billing = set()
                
                for person in tracked:
                    hotspot_x, hotspot_y = person.center
                    hotspots[person.track_id] = (hotspot_x, hotspot_y)
                    gender, age, age_bucket = AgeGenderPredictor.predict(person.track_id)
                    
                    if clip_type == "entry":
                        # Entry logic (using store entry zone or just detecting new tracks)
                        # Handled by zone_manager.check_zones returning 'person_entered'
                        pass
                        
                    elif clip_type == "billing":
                        # Check if person is in billing zone
                        nx = hotspot_x / frame_w
                        ny = hotspot_y / frame_h
                        
                        for z_id, z in self.zone_manager.zones.items():
                            if z.zone_type.lower() == "checkout" or "billing" in z.name.lower():
                                from app.zones import point_in_polygon
                                if point_in_polygon((nx, ny), z.polygon):
                                    track_ids_in_billing.add(person.track_id)
                                    
                if clip_type == "entry" or clip_type == "zone":
                    for person in tracked:
                        gender, age, age_bucket = AgeGenderPredictor.predict(person.track_id)
                        zone_events = self.zone_manager.check_zones(
                            track_id=person.track_id, center=person.center, frame_w=frame_w, frame_h=frame_h
                        )
                        
                        for evt in zone_events:
                            evt_type = evt["event_type"]
                            
                            # Standard internal Kafka event
                            await self.producer.publish_event(
                                event_type=evt_type,
                                camera_id=camera_id,
                                track_id=person.track_id,
                                zone_id=evt.get("zone_id", ""),
                                zone_name=evt.get("zone_name", ""),
                                confidence=person.confidence,
                                is_staff=False
                            )
                            
                            # JSONL compliant emission
                            if clip_type == "entry" and evt_type in ["person_entered", "person_exited"]:
                                out_type = "entry" if evt_type == "person_entered" else "exit"
                                self.jsonl_emitter.emit_entry_exit(
                                    store_code=store_id,
                                    event_type=out_type,
                                    track_id=person.track_id,
                                    camera_id=camera_id,
                                    timestamp=ts_iso,
                                    gender=gender,
                                    age=age,
                                    age_bucket=age_bucket
                                )
                            elif clip_type == "zone" and evt_type in ["zone_entered", "zone_exited"]:
                                z_id = evt.get("zone_id", "")
                                z = self.zone_manager.zones.get(z_id)
                                if z:
                                    self.jsonl_emitter.emit_zone_event(
                                        store_id=store_id,
                                        event_type=evt_type,
                                        track_id=person.track_id,
                                        camera_id=camera_id,
                                        zone_id=z.id,
                                        zone_name=z.name,
                                        zone_type=z.zone_type,
                                        is_revenue_zone="Yes" if z.zone_type == "retail" else "No",
                                        event_time=ts_iso,
                                        hotspot_x=person.center[0],
                                        hotspot_y=person.center[1],
                                        gender=gender,
                                        age=age,
                                        age_bucket=age_bucket
                                    )
                                    
                elif clip_type == "billing":
                    q_events = queue_detector.process(track_ids_in_billing, hotspots, current_time)
                    for qe in q_events:
                        gender, age, age_bucket = AgeGenderPredictor.predict(qe["track_id"])
                        
                        # Internal event
                        await self.producer.publish_event(
                            event_type=qe["event_type"],
                            camera_id=camera_id,
                            track_id=qe["track_id"],
                            zone_id="billing_zone",
                            zone_name="Billing Queue",
                            confidence=1.0,
                            is_staff=False
                        )
                        
                        # JSONL emission
                        # Format queue_join_ts, served_ts, exit_ts
                        def format_ts(ts):
                            if not ts: return None
                            return datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc).isoformat()
                            
                        self.jsonl_emitter.emit_queue_event(
                            store_id=store_id,
                            event_type=qe["event_type"],
                            event_id=qe["queue_event_id"],
                            track_id=qe["track_id"],
                            camera_id=camera_id,
                            zone_id="billing_zone",
                            zone_name="Billing Queue",
                            zone_type="BILLING",
                            is_revenue_zone="Yes",
                            join_ts=format_ts(qe["join_ts"]),
                            served_ts=format_ts(qe["served_ts"]),
                            exit_ts=format_ts(qe["exit_ts"]),
                            wait_seconds=qe["wait_seconds"],
                            pos_at_join=qe["position"],
                            abandoned=qe["abandoned"],
                            hotspot_x=qe["hotspot"][0],
                            hotspot_y=qe["hotspot"][1],
                            gender=gender,
                            age=age,
                            age_bucket=age_bucket
                        )
                        
                await asyncio.sleep(0)
                
        except Exception as e:
            logger.error(f"Error processing clip {file_path}: {e}")
        finally:
            await asyncio.to_thread(cap.release)
            logger.info(f"Finished processing clip {file_path}")
