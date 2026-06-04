import csv
import logging
import uuid
from typing import List, Dict
from datetime import datetime, timezone
from dateutil.parser import parse as parse_date
import io

from app.models import POSTransaction
from app.services.analytics_engine import AnalyticsEngine

logger = logging.getLogger(__name__)

class POSProcessor:
    """Processes POS CSV files to generate purchase events."""
    
    @staticmethod
    async def process_csv(db, store_id: str, csv_content: str, analytics_engine: AnalyticsEngine) -> int:
        """Parses CSV, saves to DB, emits purchase events."""
        reader = csv.DictReader(io.StringIO(csv_content))
        transactions = []
        orders_processed = set()
        
        for row in reader:
            try:
                # order_id,order_date,order_time,store_id,product_id,brand_name,total_amount
                order_id = row.get("order_id")
                order_date = parse_date(row.get("order_date")).date() if row.get("order_date") else None
                order_time = parse_date(row.get("order_time")).time() if row.get("order_time") else None
                total_amount = float(row.get("total_amount", 0))
                
                pt = POSTransaction(
                    store_id=store_id,
                    order_id=order_id,
                    order_date=order_date,
                    order_time=order_time,
                    product_id=row.get("product_id"),
                    brand_name=row.get("brand_name"),
                    total_amount=total_amount
                )
                db.add(pt)
                transactions.append(pt)
                
                # Independent stream logic (Option C): Emit a purchase event per unique order
                # Combine date and time
                if order_date and order_time:
                    dt = datetime.combine(order_date, order_time)
                else:
                    dt = datetime.now()
                    
                order_key = f"{order_id}_{dt.isoformat()}"
                
                if order_key not in orders_processed:
                    orders_processed.add(order_key)
                    # Create an independent purchase_completed event
                    event = {
                        "event_id": str(uuid.uuid4()),
                        "event_type": "purchase_completed",
                        "store_id": store_id,
                        "visitor_id": f"buyer_{order_id}", # Aggregate/independent identifier
                        "timestamp": dt.replace(tzinfo=timezone.utc).isoformat(),
                        "is_staff": False,
                        "metadata": {
                            "order_id": order_id,
                            "amount": total_amount
                        }
                    }
                    if analytics_engine:
                        await analytics_engine.process_event(event)
                        
            except Exception as e:
                logger.error(f"Error processing POS row {row}: {e}")
                
        await db.commit()
        return len(transactions)
