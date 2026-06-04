import time
import uuid
from typing import Dict, List, Tuple
from dataclasses import dataclass, field

@dataclass
class QueuePerson:
    track_id: int
    join_ts: float = 0.0
    served_ts: float = None
    exit_ts: float = None
    position_at_join: int = 0
    abandoned: bool = False
    is_served: bool = False
    last_seen: float = 0.0
    hotspot: Tuple[float, float] = (0.0, 0.0)

class QueueDetector:
    """State machine for detecting queue joins, service, and abandonment."""
    
    def __init__(self, service_time_threshold: float = 5.0, abandon_threshold: float = 10.0):
        self.queue: List[int] = [] # ordered list of track_ids
        self.state: Dict[int, QueuePerson] = {}
        self.service_time_threshold = service_time_threshold
        self.abandon_threshold = abandon_threshold
        
    def process(self, track_ids_in_zone: set, hotspots: dict, current_time: float) -> List[dict]:
        """Update queue state based on who is currently in the billing zone."""
        events = []
        
        # 1. Handle new joins
        for tid in track_ids_in_zone:
            if tid not in self.state:
                pos = len(self.queue) + 1
                self.state[tid] = QueuePerson(
                    track_id=tid,
                    join_ts=current_time,
                    position_at_join=pos,
                    last_seen=current_time,
                    hotspot=hotspots.get(tid, (0.0, 0.0))
                )
                self.queue.append(tid)
            else:
                self.state[tid].last_seen = current_time
                self.state[tid].hotspot = hotspots.get(tid, self.state[tid].hotspot)
                
        # 2. Process active queue
        if self.queue:
            head_tid = self.queue[0]
            head = self.state[head_tid]
            
            # If the person at the front has been there long enough, they are being "served"
            if not head.is_served and (current_time - head.join_ts) >= self.service_time_threshold:
                head.is_served = True
                head.served_ts = current_time
                
        # 3. Handle exits
        for tid in list(self.state.keys()):
            person = self.state[tid]
            
            # If person hasn't been seen for a while, they exited
            if (current_time - person.last_seen) > 2.0 or tid not in track_ids_in_zone:
                person.exit_ts = current_time
                
                wait_seconds = int(person.exit_ts - person.join_ts)
                
                # Check if they abandoned
                if not person.is_served and wait_seconds < self.abandon_threshold:
                    # Just walked through the zone, not a real queue join
                    pass
                else:
                    if not person.is_served:
                        person.abandoned = True
                        
                    event_type = "queue_abandoned" if person.abandoned else "queue_completed"
                    
                    events.append({
                        "event_type": event_type,
                        "track_id": person.track_id,
                        "queue_event_id": str(uuid.uuid4()),
                        "join_ts": person.join_ts,
                        "served_ts": person.served_ts,
                        "exit_ts": person.exit_ts,
                        "wait_seconds": wait_seconds,
                        "position": person.position_at_join,
                        "abandoned": person.abandoned,
                        "hotspot": person.hotspot
                    })
                    
                # Clean up
                if tid in self.queue:
                    self.queue.remove(tid)
                del self.state[tid]
                
        return events
