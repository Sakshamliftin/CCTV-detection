"""SQLAlchemy ORM models."""
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, JSON, ARRAY, Text, ForeignKey
from sqlalchemy.sql import func

from app.database import Base


class Camera(Base):
    __tablename__ = "cameras"
    
    id = Column(String(50), primary_key=True)
    name = Column(String(100), nullable=False)
    location = Column(String(200))
    rtsp_url = Column(String(500))
    zone_ids = Column(ARRAY(Text))
    status = Column(String(20), default="offline")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class StoreEvent(Base):
    __tablename__ = "store_events"
    
    id = Column(String(100), primary_key=True)
    event_type = Column(String(50), nullable=False)
    camera_id = Column(String(50), ForeignKey("cameras.id"))
    track_id = Column(Integer)
    zone_id = Column(String(50))
    zone_name = Column(String(100))
    timestamp = Column(DateTime(timezone=True), nullable=False)
    metadata_ = Column("metadata", JSON, default={})
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AnomalyEvent(Base):
    __tablename__ = "anomaly_events"
    
    id = Column(String(100), primary_key=True)
    anomaly_type = Column(String(50), nullable=False)
    severity = Column(String(20), nullable=False)
    zone_id = Column(String(50))
    zone_name = Column(String(100))
    description = Column(Text)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    metadata_ = Column("metadata", JSON, default={})
    resolved = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AnalyticsSnapshot(Base):
    __tablename__ = "analytics_snapshots"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    total_occupancy = Column(Integer, default=0)
    total_visitors = Column(Integer, default=0)
    avg_dwell_seconds = Column(Float, default=0)
    peak_occupancy = Column(Integer, default=0)
    zone_occupancy = Column(JSON, default={})
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ZoneAnalytics(Base):
    __tablename__ = "zone_analytics"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    zone_id = Column(String(50), nullable=False)
    zone_name = Column(String(100))
    hour_bucket = Column(DateTime(timezone=True), nullable=False)
    entries = Column(Integer, default=0)
    exits = Column(Integer, default=0)
    avg_dwell_seconds = Column(Float, default=0)
    peak_occupancy = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
