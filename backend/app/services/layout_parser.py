# pyrefly: ignore [missing-import]
import cv2
# pyrefly: ignore [missing-import]
import numpy as np
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

class LayoutParser:
    """Uses lightweight CV to extract zones from a store layout image."""
    
    @staticmethod
    def extract_zones_from_image(image_path: str) -> List[Dict]:
        """
        Reads layout image and detects colored blocks as zones.
        Returns a list of zone definitions.
        """
        zones = []
        try:
            image = cv2.imread(image_path)
            if image is None:
                logger.error(f"Could not read layout image: {image_path}")
                return zones
                
            h, w = image.shape[:2]
            
            # Convert to HSV to find colored blocks (ignoring white/grey/black background)
            hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
            
            # Mask out white/grey/black (low saturation or very high/low value)
            lower = np.array([0, 50, 50])
            upper = np.array([180, 255, 255])
            mask = cv2.inRange(hsv, lower, upper)
            
            # Find contours on the mask
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            zone_count = 1
            for cnt in contours:
                area = cv2.contourArea(cnt)
                # Filter small noise
                if area > 1000:
                    # Get bounding box
                    x, y, bw, bh = cv2.boundingRect(cnt)
                    
                    # Compute mean color in this bounding box
                    roi_mask = np.zeros(mask.shape, dtype=np.uint8)
                    cv2.drawContours(roi_mask, [cnt], -1, 255, -1)
                    mean_color = cv2.mean(image, mask=roi_mask)[:3]
                    color_hex = '#{:02x}{:02x}{:02x}'.format(int(mean_color[2]), int(mean_color[1]), int(mean_color[0]))
                    
                    # Convert bounding box to normalized polygon coordinates [0, 1]
                    p1 = [round(x/w, 3), round(y/h, 3)]
                    p2 = [round((x+bw)/w, 3), round(y/h, 3)]
                    p3 = [round((x+bw)/w, 3), round((y+bh)/h, 3)]
                    p4 = [round(x/w, 3), round((y+bh)/h, 3)]
                    
                    zones.append({
                        "zone_id": f"zone_{zone_count}",
                        "zone_name": f"Auto Zone {zone_count}",
                        "zone_type": "retail",
                        "polygon": [p1, p2, p3, p4],
                        "color": color_hex,
                        "capacity": 20
                    })
                    zone_count += 1
                    
        except Exception as e:
            logger.error(f"Error extracting zones: {e}")
            
        # Fallback: if no zones found, create one big zone
        if not zones:
            zones.append({
                "zone_id": "zone_1",
                "zone_name": "Main Floor",
                "zone_type": "retail",
                "polygon": [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]],
                "color": "#8b5cf6",
                "capacity": 50
            })
            
        return zones
