"""Application configuration from environment variables."""
import json
# pyrefly: ignore [missing-import]
from pydantic_settings import BaseSettings
from typing import Dict, List, Any


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://storeiq:storeiq_secret@postgres:5432/storeiq"
    
    # Kafka
    kafka_bootstrap_servers: str = "kafka:9092"
    kafka_store_events_topic: str = "store_events"
    kafka_anomaly_events_topic: str = "anomaly_events"
    kafka_group_id: str = "backend-analytics"
    
    # Analytics
    analytics_snapshot_interval: int = 30  # seconds
    
    # Anomaly thresholds
    overcrowding_threshold: float = 0.9  # fraction of zone capacity
    dwell_time_threshold: int = 300  # seconds
    traffic_spike_window: int = 300  # seconds
    traffic_spike_threshold: int = 20  # entries in window
    
    # Server
    backend_port: int = 8000
    
    # Paths
    zones_config_path: str = "/app/config/store_zones.json"
    cameras_config_path: str = "/app/config/cameras.json"
    
    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()


def load_zones_config() -> List[Dict[str, Any]]:
    """Load zone configuration from JSON file."""
    try:
        with open(settings.zones_config_path, 'r') as f:
            data = json.load(f)
        return data.get("zones", [])
    except FileNotFoundError:
        return [
            {"id": "zone_entrance", "name": "Entrance", "type": "entrance", "capacity": 50, "color": "#06b6d4"},
            {"id": "zone_checkout", "name": "Checkout", "type": "checkout", "capacity": 30, "color": "#f59e0b"},
            {"id": "zone_electronics", "name": "Electronics", "type": "retail", "capacity": 40, "color": "#8b5cf6"},
            {"id": "zone_grocery", "name": "Grocery", "type": "retail", "capacity": 60, "color": "#10b981"},
            {"id": "zone_clothing", "name": "Clothing", "type": "retail", "capacity": 35, "color": "#ec4899"},
        ]
