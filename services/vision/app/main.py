"""Vision Service — YOLO + ByteTrack video intelligence pipeline."""
import asyncio
import json
import logging
import os
import tempfile
from contextlib import asynccontextmanager
from typing import Dict

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.config import settings
from app.detector import PersonDetector
from app.tracker import PersonTracker
from app.zones import ZoneManager
from app.event_producer import EventProducer
from app.pipeline import VideoPipeline
from app.simulator import EventSimulator
from app.jsonl_emitter import JSONLEmitter
from app.clip_processor import ClipProcessor

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

# Global state
detector: PersonDetector = None
producer = EventProducer()
zone_manager: ZoneManager = None
pipelines: Dict[str, VideoPipeline] = {}
simulator: EventSimulator = None
jsonl_emitter: JSONLEmitter = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — initialize and cleanup resources."""
    global detector, zone_manager, simulator

    logger.info("Starting Vision Service...")

    # Initialize Kafka producer
    await producer.start()

    # Load zone configuration
    zone_manager = ZoneManager(settings.zones_config_path)
    
    global jsonl_emitter
    jsonl_emitter = JSONLEmitter()

    # Initialize YOLO detector
    try:
        detector = PersonDetector()
    except Exception as e:
        logger.warning(f"Failed to load YOLO model: {e}. Video processing unavailable.")
        detector = None

    # Start simulator if enabled (fallback/dev mode)
    if settings.enable_simulator:
        logger.info("Simulator mode enabled — generating synthetic events")
        simulator = EventSimulator(producer)
        asyncio.create_task(simulator.start())
    elif detector is None:
        logger.warning("No YOLO model and simulator disabled. Enable ENABLE_SIMULATOR=true for demo mode.")

    yield

    # Cleanup
    logger.info("Shutting down Vision Service...")
    for pipeline in pipelines.values():
        pipeline.stop()
    if simulator:
        simulator.stop()
    await producer.stop()


app = FastAPI(
    title="Store Intelligence — Vision Service",
    description="YOLO + ByteTrack video processing pipeline for store analytics",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class StreamRequest(BaseModel):
    """Request to start processing an RTSP stream."""
    rtsp_url: str
    camera_id: str


@app.get("/health")
async def health():
    """Service health check."""
    return {
        "status": "healthy",
        "service": "vision",
        "yolo_loaded": detector is not None,
        "simulator_active": simulator is not None and simulator._running,
        "active_pipelines": {k: v.stats for k, v in pipelines.items()},
    }


@app.post("/process/video")
async def process_video(camera_id: str = "cam_01", file: UploadFile = File(...)):
    """Upload and process a video file through the CV pipeline."""
    if detector is None:
        raise HTTPException(status_code=503, detail="YOLO model not loaded. Cannot process video.")

    if camera_id in pipelines and pipelines[camera_id].is_running:
        raise HTTPException(status_code=409, detail=f"Pipeline already running for camera {camera_id}")

    # Save uploaded file
    # Note: In production, this would upload to S3/GCS using boto3/google-cloud-storage.
    # For this demo, we use local temporary files.
    suffix = os.path.splitext(file.filename)[1] if file.filename else ".mp4"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    # Create and start pipeline
    tracker = PersonTracker()
    pipeline = VideoPipeline(detector, tracker, zone_manager, producer)
    pipelines[camera_id] = pipeline

    # Run in background
    asyncio.create_task(pipeline.process_video(tmp_path, camera_id))

    return {
        "status": "processing",
        "camera_id": camera_id,
        "filename": file.filename,
        "message": "Video processing started. Events will be published to Kafka.",
    }


@app.post("/process/stream")
async def process_stream(request: StreamRequest):
    """Start processing an RTSP stream.
    
    RTSP URLs are configured in cameras.json.
    """
    if detector is None:
        raise HTTPException(status_code=503, detail="YOLO model not loaded")

    if request.camera_id in pipelines and pipelines[request.camera_id].is_running:
        raise HTTPException(status_code=409, detail=f"Pipeline already running for camera {request.camera_id}")

    tracker = PersonTracker()
    pipeline = VideoPipeline(detector, tracker, zone_manager, producer)
    pipelines[request.camera_id] = pipeline

    asyncio.create_task(pipeline.process_video(request.rtsp_url, request.camera_id))

    return {
        "status": "streaming",
        "camera_id": request.camera_id,
        "rtsp_url": request.rtsp_url,
    }


@app.post("/process/stop/{camera_id}")
async def stop_pipeline(camera_id: str):
    """Stop a running pipeline."""
    if camera_id not in pipelines:
        raise HTTPException(status_code=404, detail=f"No pipeline for camera {camera_id}")
    pipelines[camera_id].stop()
    return {"status": "stopping", "camera_id": camera_id}


class StoreProcessRequest(BaseModel):
    store_id: str
    clips: list
    zones: list

@app.post("/process/store")
async def process_store(request: StoreProcessRequest):
    """Process an entire store's uploaded clips using specific processors."""
    if detector is None:
        raise HTTPException(status_code=503, detail="YOLO model not loaded")
        
    store_zm = ZoneManager("")
    store_zm.load_store_zones(request.zones)
    
    processor = ClipProcessor(detector, store_zm, producer, jsonl_emitter)
    
    # Process each clip in background
    for clip in request.clips:
        asyncio.create_task(
            processor.process_clip(
                store_id=request.store_id,
                clip_type=clip.get("type", "zone"),
                camera_id=clip.get("camera", "cam_01"),
                file_path=clip.get("path")
            )
        )
        
    return {"status": "processing", "store_id": request.store_id, "clips": len(request.clips)}


@app.get("/pipelines")
async def list_pipelines():
    """List all active pipelines."""
    return {
        camera_id: pipeline.stats
        for camera_id, pipeline in pipelines.items()
    }


@app.get("/zones")
async def get_zones():
    """List configured store zones."""
    return {"zones": zone_manager.get_zone_info() if zone_manager else []}
