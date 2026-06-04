from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Form
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from fastapi.responses import FileResponse
import os
import aiohttp
import json

from app.database import get_db
from app.models import Store, StoreClip, StoreZone
from app.schemas import (
    StoreUploadResponse, StoreListResponse, StoreItem, 
    StoreDetailResponse, ClipItem, ZoneDefinition, POSUploadResponse
)
from app.services.store_manager import StoreManager
from app.services.pos_processor import POSProcessor

router = APIRouter(tags=["Stores"])

# Set from main
_analytics_engine = None

def set_analytics_engine(engine):
    global _analytics_engine
    _analytics_engine = engine


@router.post("/stores/upload", response_model=StoreUploadResponse)
async def upload_store(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    """Upload a zipped store folder containing layout, clips, etc."""
    if not file.filename.endswith('.zip'):
        raise HTTPException(status_code=400, detail="Must be a .zip file")
        
    store_id, store_name, clips_detected = await StoreManager.process_zip_upload(db, file, file.filename)
    
    return StoreUploadResponse(
        store_id=store_id,
        message=f"Store '{store_name}' uploaded successfully.",
        clips_detected=clips_detected
    )


@router.get("/stores", response_model=StoreListResponse)
async def list_stores(db: AsyncSession = Depends(get_db)):
    """List all uploaded stores."""
    result = await db.execute(select(Store))
    stores = result.scalars().all()
    
    return StoreListResponse(stores=[
        StoreItem(
            id=s.id,
            name=s.name or s.id,
            status=s.status,
            created_at=str(s.created_at)
        ) for s in stores
    ])


@router.get("/stores/{store_id}", response_model=StoreDetailResponse)
async def get_store(store_id: str, db: AsyncSession = Depends(get_db)):
    """Get details of a specific store, including clips and zones."""
    store = await db.get(Store, store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
        
    clips = (await db.execute(select(StoreClip).where(StoreClip.store_id == store_id))).scalars().all()
    zones = (await db.execute(select(StoreZone).where(StoreZone.store_id == store_id))).scalars().all()
    
    return StoreDetailResponse(
        id=store.id,
        name=store.name or store.id,
        layout_image_url=f"/api/v1/stores/{store.id}/layout" if store.layout_image_path else "",
        status=store.status,
        clips=[ClipItem(
            id=c.id,
            filename=c.filename,
            clip_type=c.clip_type,
            camera_id=c.camera_id,
            status=c.status
        ) for c in clips],
        zones=[ZoneDefinition(
            zone_id=z.zone_id,
            zone_name=z.zone_name or z.zone_id,
            zone_type=z.zone_type or "retail",
            polygon=z.polygon,
            is_revenue_zone=z.is_revenue_zone,
            camera_id=z.camera_id
        ) for z in zones]
    )


@router.get("/stores/{store_id}/layout")
async def get_store_layout(store_id: str, db: AsyncSession = Depends(get_db)):
    """Serve the layout image for a store."""
    store = await db.get(Store, store_id)
    if not store or not store.layout_image_path or not os.path.exists(store.layout_image_path):
        raise HTTPException(status_code=404, detail="Layout image not found")
        
    return FileResponse(store.layout_image_path)


@router.post("/stores/{store_id}/zones")
async def update_zones(store_id: str, zones: List[ZoneDefinition], db: AsyncSession = Depends(get_db)):
    """Update zone definitions for a store."""
    store = await db.get(Store, store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
        
    # Delete existing zones
    existing = await db.execute(select(StoreZone).where(StoreZone.store_id == store_id))
    for z in existing.scalars().all():
        await db.delete(z)
        
    # Add new zones
    for z in zones:
        db.add(StoreZone(
            id=f"{store_id}_{z.zone_id}",
            store_id=store_id,
            zone_id=z.zone_id,
            zone_name=z.zone_name,
            zone_type=z.zone_type,
            polygon=z.polygon,
            is_revenue_zone=z.is_revenue_zone,
            camera_id=z.camera_id
        ))
        
    await db.commit()
    return {"message": "Zones updated successfully"}


@router.post("/stores/{store_id}/pos", response_model=POSUploadResponse)
async def upload_pos(store_id: str, file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    """Upload POS transactions CSV for a store."""
    store = await db.get(Store, store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
        
    content = (await file.read()).decode("utf-8")
    processed = await POSProcessor.process_csv(db, store_id, content, _analytics_engine)
    
    return POSUploadResponse(
        store_id=store_id,
        transactions_processed=processed,
        message="POS transactions processed successfully"
    )

@router.post("/stores/{store_id}/process")
async def process_store(store_id: str, db: AsyncSession = Depends(get_db)):
    """Trigger processing of all clips for a store via Vision service."""
    store = await db.get(Store, store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
        
    # Fetch clips
    clips = (await db.execute(select(StoreClip).where(StoreClip.store_id == store_id))).scalars().all()
    zones = (await db.execute(select(StoreZone).where(StoreZone.store_id == store_id))).scalars().all()
    
    # Update store status
    store.status = "processing"
    for c in clips:
        c.status = "processing"
    await db.commit()
    
    # Notify vision service (fire and forget)
    try:
        import os
        vision_url = f"http://vision:{os.getenv('VISION_PORT', 8001)}/process/store"
        
        payload = {
            "store_id": store_id,
            "clips": [{"id": c.id, "type": c.clip_type, "path": c.file_path, "camera": c.camera_id} for c in clips],
            "zones": [{"id": z.zone_id, "name": z.zone_name, "polygon": z.polygon} for z in zones]
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(vision_url, json=payload) as response:
                if response.status != 200:
                    print(f"Failed to trigger vision service: {await response.text()}")
    except Exception as e:
        print(f"Failed to communicate with vision service: {e}")
        
    return {"message": f"Processing started for store {store_id}"}
