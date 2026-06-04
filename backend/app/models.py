"""SQLAlchemy ORM models."""
from datetime import datetime
# pyrefly: ignore [missing-import]
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, JSON, ARRAY, Text, ForeignKey, Date, Time
# pyrefly: ignore [missing-import]
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


class Store(Base):
    __tablename__ = "stores"
    
    id = Column(String(50), primary_key=True)
    name = Column(String(100))
    layout_image_path = Column(String(500))
    status = Column(String(50), default="uploaded")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class StoreClip(Base):
    __tablename__ = "store_clips"
    
    id = Column(String(100), primary_key=True)
    store_id = Column(String(50), ForeignKey("stores.id"))
    filename = Column(String(200), nullable=False)
    clip_type = Column(String(50), nullable=False)
    camera_id = Column(String(50))
    file_path = Column(String(500), nullable=False)
    status = Column(String(50), default="pending")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class StoreZone(Base):
    __tablename__ = "store_zones"
    
    id = Column(String(100), primary_key=True)
    store_id = Column(String(50), ForeignKey("stores.id"))
    zone_id = Column(String(50), nullable=False)
    zone_name = Column(String(100))
    zone_type = Column(String(50))
    polygon = Column(JSON)
    is_revenue_zone = Column(Boolean, default=False)
    camera_id = Column(String(50))


class POSTransaction(Base):
    __tablename__ = "pos_transactions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    store_id = Column(String(50), ForeignKey("stores.id"))
    order_id = Column(String(50))
    order_date = Column(Date)
    order_time = Column(Time)
    product_id = Column(String(50))
    brand_name = Column(String(100))
    total_amount = Column(Float)


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
