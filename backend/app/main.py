"""Store Intelligence Backend — FastAPI application.

v1.1 additions:
- Structured request logging middleware (trace_id, endpoint, store_id, latency_ms, status_code).
- Graceful degradation: SQLAlchemyError → HTTP 503, no stack traces exposed.
- Ingest route wired to analytics engine.
"""
# pyre-ignore [2]
import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager
# pyre-ignore [2]   
from fastapi import FastAPI, Request, Response
# pyrefly: ignore [missing-import]
from fastapi.middleware.cors import CORSMiddleware
# pyrefly: ignore [missing-import]
from fastapi.responses import JSONResponse
# pyrefly: ignore [missing-import]
from sqlalchemy.exc import SQLAlchemyError

from app.config import settings
from app.services.analytics_engine import AnalyticsEngine
from app.services.anomaly_engine import AnomalyEngine
from app.services.kafka_consumer import EventConsumer
from app.routes import health, analytics, events, cameras, stores

# ---------------------------------------------------------------------------
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
    events.set_analytics_engine(analytics_engine)
    stores.set_analytics_engine(analytics_engine)

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


# Structured logging middleware
@app.middleware("http")
async def structured_logging_middleware(request: Request, call_next):
    trace_id = str(uuid.uuid4())
    start = time.time()

    response: Response = await call_next(request)

    latency_ms = round((time.time() - start) * 1000, 1)
    store_id = request.headers.get("X-Store-ID", "unknown")
    endpoint = request.url.path

    log_data = {
        "trace_id": trace_id,
        "endpoint": endpoint,
        "method": request.method,
        "store_id": store_id,
        "latency_ms": latency_ms,
        "status_code": response.status_code,
    }

    # Extra field for ingest endpoint
    if endpoint.endswith("/ingest"):
        log_data["event_count"] = request.headers.get("X-Event-Count", "unknown")

    logger.info("REQUEST %s", log_data)
    response.headers["X-Trace-ID"] = trace_id
    return response


# ---------------------------------------------------------------------------
# Graceful degradation — DB errors never expose stack traces
# ---------------------------------------------------------------------------
@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    logger.error("Database error on %s: %s", request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=503,
        content={
            "error": "service_unavailable",
            "message": "Database is temporarily unavailable. Please retry shortly.",
        },
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled error on %s: %s", request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_error",
            "message": "An unexpected error occurred.",
        },
    )


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(health.router, prefix="/api/v1")
app.include_router(analytics.router, prefix="/api/v1")
app.include_router(events.router, prefix="/api/v1")
app.include_router(cameras.router, prefix="/api/v1")
app.include_router(stores.router, prefix="/api/v1")


@app.get("/")
async def root():
    return {
        "service": "Store Intelligence API",
        "version": "1.0.0",
        "docs": "/docs",
    }
