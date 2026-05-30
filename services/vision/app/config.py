import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # YOLO
    yolo_model: str = "yolov8n.pt"
    yolo_confidence: float = 0.5
    yolo_device: str = "cpu"
    
    # Kafka
    kafka_bootstrap_servers: str = "kafka:9092"
    kafka_store_events_topic: str = "store_events"
    
    # Vision
    vision_port: int = 8001
    frame_skip: int = 3  # Process every Nth frame
    
    # Simulator
    enable_simulator: bool = False
    simulator_interval: float = 2.0
    
    # Paths
    zones_config_path: str = "/app/config/store_zones.json"
    cameras_config_path: str = "/app/config/cameras.json"
    
    class Config:
        env_file = ".env"

settings = Settings()
