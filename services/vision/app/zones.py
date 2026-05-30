"""Zone management — geometry checks and zone transition tracking."""
import json
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import time

logger = logging.getLogger(__name__)


@dataclass
class Zone:
    """A store zone with polygon boundary."""
    id: str
    name: str
    zone_type: str
    polygon: List[Tuple[float, float]]
    capacity: int
    color: str


@dataclass
class PersonZoneState:
    """Tracks which zones a person is currently in."""
    track_id: int
    current_zones: set = field(default_factory=set)
    zone_enter_times: Dict[str, float] = field(default_factory=dict)
    in_store: bool = False
    store_enter_time: float = 0.0


def point_in_polygon(point: Tuple[float, float], polygon: List[Tuple[float, float]]) -> bool:
    """Ray-casting algorithm for point-in-polygon test."""
    x, y = point
    n = len(polygon)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


class ZoneManager:
    """Manages zone geometry and person-zone transition tracking."""

    def __init__(self, config_path: str):
        self.zones: Dict[str, Zone] = {}
        self._person_states: Dict[int, PersonZoneState] = {}
        self._load_zones(config_path)

    def _load_zones(self, config_path: str):
        """Load zone definitions from JSON config."""
        try:
            with open(config_path, 'r') as f:
                data = json.load(f)
            for z in data["zones"]:
                zone = Zone(
                    id=z["id"],
                    name=z["name"],
                    zone_type=z["type"],
                    polygon=[tuple(p) for p in z["polygon"]],
                    capacity=z["capacity"],
                    color=z["color"],
                )
                self.zones[zone.id] = zone
            logger.info(f"Loaded {len(self.zones)} zones from {config_path}")
        except Exception as e:
            logger.error(f"Failed to load zones from {config_path}: {e}")
            raise

    def check_zones(
        self, track_id: int, center: Tuple[float, float], frame_w: int, frame_h: int
    ) -> List[dict]:
        """Check zone transitions for a tracked person. Returns list of zone events."""
        # Normalize center to [0, 1]
        nx = center[0] / frame_w
        ny = center[1] / frame_h

        # Get or create person state
        if track_id not in self._person_states:
            self._person_states[track_id] = PersonZoneState(track_id=track_id)
        state = self._person_states[track_id]

        events = []
        now = time.time()

        # Check store entry (first time seen)
        if not state.in_store:
            state.in_store = True
            state.store_enter_time = now
            events.append({
                "event_type": "person_entered",
                "zone_id": "store",
                "zone_name": "Store",
            })

        # Check each zone
        current_zones = set()
        for zone_id, zone in self.zones.items():
            in_zone = point_in_polygon((nx, ny), zone.polygon)
            if in_zone:
                current_zones.add(zone_id)

            was_in = zone_id in state.current_zones

            if in_zone and not was_in:
                # Zone entered
                state.zone_enter_times[zone_id] = now
                events.append({
                    "event_type": "zone_entered",
                    "zone_id": zone_id,
                    "zone_name": zone.name,
                })
            elif not in_zone and was_in:
                # Zone exited
                enter_time = state.zone_enter_times.pop(zone_id, now)
                dwell = now - enter_time
                events.append({
                    "event_type": "zone_exited",
                    "zone_id": zone_id,
                    "zone_name": zone.name,
                    "dwell_seconds": round(dwell, 1),
                })
                # Dwell time event if significant
                if dwell >= 30:
                    events.append({
                        "event_type": "dwell_time_completed",
                        "zone_id": zone_id,
                        "zone_name": zone.name,
                        "dwell_seconds": round(dwell, 1),
                    })

        state.current_zones = current_zones
        return events

    def handle_person_exit(self, track_id: int) -> List[dict]:
        """Handle when a person is no longer tracked (exited store)."""
        state = self._person_states.pop(track_id, None)
        if state is None:
            return []

        events = []
        now = time.time()

        # Exit all current zones
        for zone_id in state.current_zones:
            zone = self.zones.get(zone_id)
            enter_time = state.zone_enter_times.get(zone_id, now)
            dwell = now - enter_time
            if zone:
                events.append({
                    "event_type": "zone_exited",
                    "zone_id": zone_id,
                    "zone_name": zone.name,
                    "dwell_seconds": round(dwell, 1),
                })

        # Store exit
        if state.in_store:
            dwell = now - state.store_enter_time
            events.append({
                "event_type": "person_exited",
                "zone_id": "store",
                "zone_name": "Store",
                "dwell_seconds": round(dwell, 1),
            })

        return events

    def get_zone_info(self) -> List[dict]:
        """Return zone metadata for API consumption."""
        return [
            {"id": z.id, "name": z.name, "type": z.zone_type,
             "capacity": z.capacity, "color": z.color, "polygon": z.polygon}
            for z in self.zones.values()
        ]
