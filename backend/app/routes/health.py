"""Health check endpoint."""
from fastapi import APIRouter
from app.schemas import HealthResponse, ServiceStatus
from app.database import check_db_connection

router = APIRouter(prefix="/api/v1", tags=["Health"])

# This will be set by main.py at startup
_kafka_consumer = None

def set_kafka_consumer(consumer):
    global _kafka_consumer
    _kafka_consumer = consumer

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Check health of all service dependencies."""
    db_ok = await check_db_connection()
    kafka_ok = _kafka_consumer.is_connected if _kafka_consumer else False
    
    return HealthResponse(
        status="healthy" if db_ok else "degraded",
        services=ServiceStatus(
            database="connected" if db_ok else "disconnected",
            kafka="connected" if kafka_ok else "disconnected",
        ),
    )
