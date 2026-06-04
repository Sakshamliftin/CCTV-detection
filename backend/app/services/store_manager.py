import os
import uuid
import shutil
from typing import List, Dict, Tuple
from werkzeug.utils import secure_filename
import logging
import zipfile

from app.models import Store, StoreClip, StoreZone
from app.services.layout_parser import LayoutParser

logger = logging.getLogger(__name__)

UPLOAD_DIR = "/app/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

class StoreManager:
    """Manages store ingestion, file classification, and database records."""
    
    @staticmethod
    async def process_zip_upload(db, file_obj, filename: str) -> Tuple[str, str, int]:
        """Extracts ZIP, classifies files, creates Store & StoreClip records."""
        store_id = f"store_{uuid.uuid4().hex[:8]}"
        store_dir = os.path.join(UPLOAD_DIR, store_id)
        os.makedirs(store_dir, exist_ok=True)
        
        zip_path = os.path.join(store_dir, secure_filename(filename))
        
        # Write zip to disk
        content = await file_obj.read()
        with open(zip_path, "wb") as f:
            f.write(content)
            
        # Extract
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(store_dir)
            
        # Clean up zip
        os.remove(zip_path)
        
        # Find files recursively
        all_files = []
        for root, _, files in os.walk(store_dir):
            for file in files:
                all_files.append(os.path.join(root, file))
                
        # Classify files
        layout_img = None
        clips = []
        
        for fp in all_files:
            fname = os.path.basename(fp).lower()
            if "layout" in fname and fname.endswith(('.png', '.jpg', '.jpeg')):
                layout_img = fp
            elif fname.endswith(('.mp4', '.avi', '.mov')):
                if "entry" in fname:
                    clips.append((fp, "entry"))
                elif "zone" in fname:
                    clips.append((fp, "zone"))
                elif "billing" in fname:
                    clips.append((fp, "billing"))
                else:
                    clips.append((fp, "zone")) # Default to zone
                    
        # Create Store DB record
        store_name = os.path.splitext(filename)[0]
        new_store = Store(
            id=store_id,
            name=store_name,
            layout_image_path=layout_img,
            status="uploaded"
        )
        db.add(new_store)
        
        # Create StoreClip records
        clip_records = []
        camera_counter = 1
        for fp, ctype in clips:
            clip_id = str(uuid.uuid4())
            cam_id = f"cam_{camera_counter:02d}"
            sc = StoreClip(
                id=clip_id,
                store_id=store_id,
                filename=os.path.basename(fp),
                clip_type=ctype,
                camera_id=cam_id,
                file_path=fp,
                status="pending"
            )
            db.add(sc)
            clip_records.append(sc)
            camera_counter += 1
            
        # Auto-extract zones if layout exists
        if layout_img:
            zones_data = LayoutParser.extract_zones_from_image(layout_img)
            for z in zones_data:
                db.add(StoreZone(
                    id=str(uuid.uuid4()),
                    store_id=store_id,
                    zone_id=z["zone_id"],
                    zone_name=z["zone_name"],
                    zone_type=z["zone_type"],
                    polygon=z["polygon"],
                    is_revenue_zone=(z["zone_type"] == "retail")
                ))
                
        await db.commit()
        return store_id, store_name, len(clip_records)
