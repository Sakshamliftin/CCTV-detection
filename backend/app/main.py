"""Store Intelligence Backend — FastAPI application.

Consolidates REST API, analytics processing, and anomaly detection.
"""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.services.analytics_engine import AnalyticsEngine
from app.services.anomaly_engine import AnomalyEngine
from app.services.kafka_consumer import EventConsumer
from app.routes import health, analytics, events, cameras

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

# Engines (module-level singletons)
analytics_engine = AnalyticsEngine()
anomaly_engine = AnomalyEngine()
event_consumer = EventConsumer(analytics_engine, anomaly_engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — start/stop background services."""
    logger.info("Starting Store Intelligence Backend...")
    
    # Wire engines into route modules
    analytics.set_engines(analytics_engine, anomaly_engine)
    health.set_kafka_consumer(event_consumer)
    
    # Start engines
    await analytics_engine.start()
    await anomaly_engine.start()
    
    # Start Kafka consumer in background
    consumer_task = asyncio.create_task(event_consumer.start())
    
    logger.info("Backend services started")
    yield
    
    # Shutdown
    logger.info("Shutting down...")
    await event_consumer.stop()
    await anomaly_engine.stop()
    await analytics_engine.stop()
    consumer_task.cancel()
    try:
        await consumer_task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="Store Intelligence API",
    description="REST API for store analytics, event streaming, and anomaly detection",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(health.router)
app.include_router(analytics.router)
app.include_router(events.router)
app.include_router(cameras.router)


@app.get("/")
async def root():
    return {
        "service": "Store Intelligence API",
        "version": "1.0.0",
        "docs": "/docs",
    }
