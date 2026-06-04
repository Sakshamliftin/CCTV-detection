"""Pydantic request/response schemas."""
from datetime import datetime
from typing import Any, Dict, List, Optional
# pyrefly: ignore [missing-import]
from pydantic import BaseModel


# --- Health ---
class ServiceStatus(BaseModel):
    database: str
    kafka: str
    feed: str = "ok"  # "ok" | "STALE_FEED"

class HealthResponse(BaseModel):
    status: str
    services: ServiceStatus
    last_event_timestamp: Optional[str] = None
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


# --- Metrics ---
class MetricsResponse(BaseModel):
    unique_visitors: int
    conversion_rate: float          # fraction 0–1
    avg_dwell_ms: float             # milliseconds
    queue_depth: int                # current checkout occupancy
    abandonment_rate: float         # fraction 0–1


# --- Funnel ---
class FunnelStep(BaseModel):
    step: str
    count: int

class FunnelResponse(BaseModel):
    funnel: List[FunnelStep]
    note: str = ""


# --- Heatmap ---
class HeatmapZone(BaseModel):
    zone_id: str
    zone_name: str
    visit_count: int
    avg_dwell_seconds: float
    normalized_score: float         # 0–100

class HeatmapResponse(BaseModel):
    zones: List[HeatmapZone]
    data_confidence: str = "high"   # "high" | "low" (low when sessions < 20)


# --- Events ---
class EventIngestItem(BaseModel):
    """Single event payload for the ingest endpoint."""
    event_id: str
    store_id: str = "store_01"
    camera_id: str
    visitor_id: str
    event_type: str
    timestamp: str
    zone_id: str = ""
    dwell_ms: int = 0
    is_staff: bool = False
    confidence: float = 1.0
    metadata: Dict[str, Any] = {}

class EventIngestResponse(BaseModel):
    accepted: int
    duplicates: int

class EventItem(BaseModel):
    event_id: str
    event_type: str
    camera_id: str
    track_id: int = 0
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
    suggested_action: str = ""
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


# --- Stores ---
class ClipItem(BaseModel):
    id: str
    filename: str
    clip_type: str
    camera_id: Optional[str] = None
    status: str

class ZoneDefinition(BaseModel):
    zone_id: str
    zone_name: str
    zone_type: str
    polygon: List[List[float]]
    is_revenue_zone: bool = False
    camera_id: Optional[str] = None

class StoreItem(BaseModel):
    id: str
    name: str
    status: str
    created_at: str

class StoreListResponse(BaseModel):
    stores: List[StoreItem]

class StoreDetailResponse(BaseModel):
    id: str
    name: str
    layout_image_url: str
    status: str
    clips: List[ClipItem]
    zones: List[ZoneDefinition]

class StoreUploadResponse(BaseModel):
    store_id: str
    message: str
    clips_detected: int

class POSUploadResponse(BaseModel):
    store_id: str
    transactions_processed: int
    message: str

class ClipProcessingStatus(BaseModel):
    clip_id: str
    status: str

