"""Pydantic request/response schemas."""
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


# --- Health ---
class ServiceStatus(BaseModel):
    database: str
    kafka: str

class HealthResponse(BaseModel):
    status: str
    services: ServiceStatus
    version: str = "1.0.0"


# --- Analytics ---
class ZoneOccupancy(BaseModel):
    zone_id: str
    zone_name: str
    current: int
    capacity: int
    color: str

class OccupancyResponse(BaseModel):
    total_occupancy: int
    capacity: int
    zone_occupancy: List[ZoneOccupancy]

class AnalyticsSummary(BaseModel):
    total_visitors: int
    avg_dwell_seconds: float
    peak_occupancy: int
    current_occupancy: int
    total_events: int
    total_anomalies: int

class HistoricalDataPoint(BaseModel):
    timestamp: str
    visitors: int
    occupancy: int
    events: int

class HistoricalResponse(BaseModel):
    data: List[HistoricalDataPoint]
    hours: int
    granularity: str

class ZoneTrafficItem(BaseModel):
    zone_id: str
    zone_name: str
    entries: int
    exits: int
    avg_dwell_seconds: float
    current_occupancy: int
    color: str

class ZoneTrafficResponse(BaseModel):
    zones: List[ZoneTrafficItem]


# --- Events ---
class EventItem(BaseModel):
    event_id: str
    event_type: str
    camera_id: str
    track_id: int
    zone_id: str
    zone_name: str
    timestamp: str
    metadata: Dict[str, Any] = {}

class EventsResponse(BaseModel):
    events: List[EventItem]
    total: int


# --- Anomalies ---
class AnomalyItem(BaseModel):
    anomaly_id: str
    anomaly_type: str
    severity: str
    zone_id: str
    zone_name: str
    description: str
    timestamp: str
    metadata: Dict[str, Any] = {}

class AnomaliesResponse(BaseModel):
    anomalies: List[AnomalyItem]
    total: int


# --- Cameras ---
class CameraItem(BaseModel):
    id: str
    name: str
    location: str
    status: str
    zone_ids: List[str]

class CamerasResponse(BaseModel):
    cameras: List[CameraItem]
