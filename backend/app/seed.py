"""Seed sample data for development and demo.

Usage: python -m app.seed
"""
import asyncio
import random
import uuid
from datetime import datetime, timezone, timedelta

from app.database import async_session, engine
from app.models import StoreEvent, AnomalyEvent, AnalyticsSnapshot, ZoneAnalytics

ZONES = [
    ("zone_entrance", "Entrance"),
    ("zone_checkout", "Checkout"),
    ("zone_electronics", "Electronics"),
    ("zone_grocery", "Grocery"),
    ("zone_clothing", "Clothing"),
]

CAMERAS = ["cam_01", "cam_02", "cam_03", "cam_04"]

EVENT_TYPES = [
    "person_entered", "person_exited",
    "zone_entered", "zone_exited",
    "dwell_time_completed",
]


async def seed():
    """Generate sample data across 24 hours."""
    print("Seeding sample data...")
    
    now = datetime.now(timezone.utc)
    
    async with async_session() as session:
        # Generate ~500 store events across 24 hours
        events = []
        track_counter = 0
        
        for hour_offset in range(24, 0, -1):
            ts_base = now - timedelta(hours=hour_offset)
            # More events during peak hours (10am-2pm, 5pm-8pm)
            hour_of_day = ts_base.hour
            if 10 <= hour_of_day <= 14 or 17 <= hour_of_day <= 20:
                event_count = random.randint(15, 30)
            elif 8 <= hour_of_day <= 21:
                event_count = random.randint(8, 18)
            else:
                event_count = random.randint(1, 5)
            
            for i in range(event_count):
                track_counter += 1
                ts = ts_base + timedelta(minutes=random.randint(0, 59), seconds=random.randint(0, 59))
                zone_id, zone_name = random.choice(ZONES)
                event_type = random.choice(EVENT_TYPES)
                camera_id = random.choice(CAMERAS)
                
                metadata = {"confidence": round(random.uniform(0.6, 0.99), 2)}
                if event_type in ("zone_exited", "dwell_time_completed", "person_exited"):
                    metadata["dwell_seconds"] = round(random.uniform(10, 300), 1)
                
                events.append(StoreEvent(
                    id=str(uuid.uuid4()),
                    event_type=event_type,
                    camera_id=camera_id,
                    track_id=track_counter % 200,
                    zone_id=zone_id,
                    zone_name=zone_name,
                    timestamp=ts,
                    metadata_=metadata,
                ))
        
        session.add_all(events)
        print(f"  Created {len(events)} store events")
        
        # Generate some anomalies
        anomalies = []
        anomaly_types = [
            ("overcrowding", "critical", "Zone occupancy exceeded capacity"),
            ("excessive_dwell", "warning", "Person dwelled beyond threshold"),
            ("traffic_spike", "info", "Unusual traffic spike detected"),
        ]
        
        for i in range(15):
            ts = now - timedelta(hours=random.randint(1, 24), minutes=random.randint(0, 59))
            atype, severity, desc_base = random.choice(anomaly_types)
            zone_id, zone_name = random.choice(ZONES)
            
            anomalies.append(AnomalyEvent(
                id=str(uuid.uuid4()),
                anomaly_type=atype,
                severity=severity,
                zone_id=zone_id,
                zone_name=zone_name,
                description=f"{desc_base} in {zone_name}",
                timestamp=ts,
                metadata_={},
            ))
        
        session.add_all(anomalies)
        print(f"  Created {len(anomalies)} anomaly events")
        
        # Generate analytics snapshots (hourly)
        snapshots = []
        for hour_offset in range(24, 0, -1):
            ts = now - timedelta(hours=hour_offset)
            snapshots.append(AnalyticsSnapshot(
                timestamp=ts,
                total_occupancy=random.randint(10, 80),
                total_visitors=random.randint(50, 300),
                avg_dwell_seconds=round(random.uniform(60, 240), 1),
                peak_occupancy=random.randint(40, 120),
                zone_occupancy={
                    "zone_entrance": random.randint(2, 20),
                    "zone_checkout": random.randint(1, 15),
                    "zone_electronics": random.randint(3, 18),
                    "zone_grocery": random.randint(5, 25),
                    "zone_clothing": random.randint(2, 12),
                },
            ))
        
        session.add_all(snapshots)
        print(f"  Created {len(snapshots)} analytics snapshots")
        
        # Generate zone analytics
        zone_stats = []
        for hour_offset in range(24, 0, -1):
            ts = now - timedelta(hours=hour_offset)
            for zone_id, zone_name in ZONES:
                zone_stats.append(ZoneAnalytics(
                    zone_id=zone_id,
                    zone_name=zone_name,
                    hour_bucket=ts,
                    entries=random.randint(5, 40),
                    exits=random.randint(5, 35),
                    avg_dwell_seconds=round(random.uniform(20, 200), 1),
                    peak_occupancy=random.randint(3, 25),
                ))
        
        session.add_all(zone_stats)
        print(f"  Created {len(zone_stats)} zone analytics records")
        
        await session.commit()
        print("Seed data committed successfully!")


if __name__ == "__main__":
    asyncio.run(seed())
