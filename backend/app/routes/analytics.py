"""Analytics API endpoints."""
from fastapi import APIRouter, Query
from app.schemas import (
    OccupancyResponse, AnalyticsSummary,
    HistoricalResponse, ZoneTrafficResponse,
    MetricsResponse, FunnelResponse, HeatmapResponse,
)

router = APIRouter(tags=["Analytics"])

# These will be set by main.py
_analytics_engine = None
_anomaly_engine = None

def set_engines(analytics, anomaly):
    global _analytics_engine, _anomaly_engine
    _analytics_engine = analytics
    _anomaly_engine = anomaly

@router.get("/stores/{store_id}/occupancy", response_model=OccupancyResponse)
async def get_occupancy():
    """Get current store occupancy — total and per zone."""
    return _analytics_engine.get_occupancy()


@router.get("/stores/{store_id}/summary", response_model=AnalyticsSummary)
async def get_summary(store_id: str):
    """Get analytics summary — visitors, dwell time, peak occupancy."""
    return _analytics_engine.get_summary(
        total_anomalies=_anomaly_engine.total_anomalies
    )


@router.get("/stores/{store_id}/historical", response_model=HistoricalResponse)
async def get_historical(
    store_id: str,
    hours: int = Query(default=24, ge=1, le=168, description="Hours of history"),
    granularity: str = Query(default="hour", description="Granularity: hour"),
):
    """Get historical analytics data for charting."""
    data = _analytics_engine.get_hourly_traffic(hours)
    return HistoricalResponse(data=data, hours=hours, granularity=granularity)


@router.get("/stores/{store_id}/zones", response_model=ZoneTrafficResponse)
async def get_zone_traffic(store_id: str):
    """Get per-zone traffic breakdown."""
    return ZoneTrafficResponse(zones=_analytics_engine.get_zone_traffic())


@router.get("/stores/{store_id}/metrics", response_model=MetricsResponse)
async def get_metrics(store_id: str):
    """Business metrics: unique visitors, conversion rate, avg dwell, queue depth, abandonment rate.
    Staff are excluded from all calculations.
    """
    return _analytics_engine.get_metrics()


@router.get("/stores/{store_id}/funnel", response_model=FunnelResponse)
async def get_funnel(store_id: str):
    """Visitor funnel: Entry → Zone Visit → Billing Queue → Purchase.
    Session-based, no double counting, re-entry aware.
    """
    return _analytics_engine.get_funnel()


@router.get("/stores/{store_id}/heatmap", response_model=HeatmapResponse)
async def get_heatmap(store_id: str):
    """Zone heatmap: visit frequency, average dwell, normalized score.
    Returns data_confidence='low' when session count < 20.
    """
    return _analytics_engine.get_heatmap()
