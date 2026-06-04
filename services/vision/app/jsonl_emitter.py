import json
import logging
import os
from typing import Dict, Any

logger = logging.getLogger(__name__)

class JSONLEmitter:
    """Emits events exactly matching the provided JSONL sample schema."""
    
    def __init__(self, output_dir: str = "/app/outputs"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        
    def _write(self, store_id: str, payload: Dict[str, Any]):
        file_path = os.path.join(self.output_dir, f"{store_id}_events.jsonl")
        try:
            with open(file_path, "a") as f:
                f.write(json.dumps(payload) + "\n")
        except Exception as e:
            logger.error(f"Failed to write JSONL: {e}")
            
    def emit_entry_exit(self, store_code: str, event_type: str, track_id: int, camera_id: str, timestamp: str,
                       gender: str, age: int, age_bucket: str, group_id: str = None, group_size: int = None):
        """Emits an 'entry' or 'exit' event."""
        payload = {
            "event_type": event_type,
            "id_token": f"ID_6{track_id:04d}",
            "store_code": store_code,
            "camera_id": camera_id,
            "event_timestamp": timestamp,
            "is_staff": False,
            "gender_pred": gender,
            "age_pred": age,
            "age_bucket": age_bucket,
            "is_face_hidden": False,
            "group_id": group_id,
            "group_size": group_size
        }
        self._write(store_code, payload)
        return payload
        
    def emit_zone_event(self, store_id: str, event_type: str, track_id: int, camera_id: str, zone_id: str, 
                        zone_name: str, zone_type: str, is_revenue_zone: str, event_time: str,
                        hotspot_x: float, hotspot_y: float, gender: str, age: int, age_bucket: str):
        """Emits a 'zone_entered' or 'zone_exited' event."""
        payload = {
            "event_type": event_type,
            "track_id": track_id,
            "store_id": store_id,
            "camera_id": camera_id,
            "zone_id": zone_id,
            "zone_name": zone_name,
            "zone_type": zone_type,
            "is_revenue_zone": is_revenue_zone,
            "event_time": event_time,
            "zone_hotspot_x": round(hotspot_x, 1),
            "zone_hotspot_y": round(hotspot_y, 1),
            "gender": gender,
            "age": age,
            "age_bucket": age_bucket
        }
        self._write(store_id, payload)
        return payload
        
    def emit_queue_event(self, store_id: str, event_type: str, event_id: str, track_id: int, camera_id: str,
                         zone_id: str, zone_name: str, zone_type: str, is_revenue_zone: str,
                         join_ts: str, served_ts: str, exit_ts: str, wait_seconds: int, pos_at_join: int,
                         abandoned: bool, hotspot_x: float, hotspot_y: float, gender: str, age: int, age_bucket: str):
        """Emits a 'queue_completed' or 'queue_abandoned' event."""
        payload = {
            "queue_event_id": event_id,
            "event_type": event_type,
            "track_id": track_id,
            "store_id": store_id,
            "camera_id": camera_id,
            "zone_id": zone_id,
            "zone_name": zone_name,
            "zone_type": zone_type,
            "is_revenue_zone": is_revenue_zone,
            "queue_join_ts": join_ts,
            "queue_served_ts": served_ts,
            "queue_exit_ts": exit_ts,
            "wait_seconds": wait_seconds,
            "queue_position_at_join": pos_at_join,
            "abandoned": abandoned,
            "zone_hotspot_x": round(hotspot_x, 1),
            "zone_hotspot_y": round(hotspot_y, 1),
            "gender": gender,
            "age": age,
            "age_bucket": age_bucket
        }
        self._write(store_id, payload)
        return payload
