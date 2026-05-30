"""Camera management endpoints."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Camera
from app.schemas import CamerasResponse, CameraItem

router = APIRouter(prefix="/api/v1", tags=["Cameras"])


@router.get("/cameras", response_model=CamerasResponse)
async def get_cameras(db: AsyncSession = Depends(get_db)):
    """List all configured cameras with status."""
    result = await db.execute(select(Camera))
    cameras = result.scalars().all()
    
    return CamerasResponse(
        cameras=[
            CameraItem(
                id=c.id,
                name=c.name,
                location=c.location or "",
                status=c.status or "offline",
                zone_ids=c.zone_ids or [],
            )
            for c in cameras
        ]
    )
