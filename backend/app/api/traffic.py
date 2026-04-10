"""Routes for traffic data endpoints"""

from datetime import datetime, timedelta
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from ..database import SessionLocal
from ..models import RegistroTrafico

router = APIRouter(prefix="/traffic-data", tags=["Traffic"])


@router.get("/24h")
async def get_traffic_data_24h():
    """API endpoint: return traffic data for last 24 hours grouped by hour, including current hour with partial data"""
    db = SessionLocal()
    try:
        # Use local time instead of UTC
        now = datetime.now()
        ago_24h = now - timedelta(hours=24)
        
        # Get all traffic records for last 24 hours
        records = db.query(RegistroTrafico).filter(
            RegistroTrafico.timestamp >= ago_24h,
            RegistroTrafico.timestamp <= now
        ).all()
        
        # Group by hour - include current hour with partial data
        data_by_hour = {}
        for record in records:
            # Round to the hour using local time
            rounded_hour = record.timestamp.replace(minute=0, second=0, microsecond=0)
            hour_key = rounded_hour.isoformat()
            if hour_key not in data_by_hour:
                data_by_hour[hour_key] = {
                    "total": 0,
                    "timestamp": rounded_hour
                }
            data_by_hour[hour_key]["total"] += record.bytes_descarga + record.bytes_subida
        
        # Create entries for all 24 hours, starting from 24 hours ago UP TO current hour
        all_hours = {}
        # Start from 24 hours ago (rounded to hour)
        start_hour = ago_24h.replace(minute=0, second=0, microsecond=0)
        # End at current hour (rounded to hour)
        current_hour = now.replace(minute=0, second=0, microsecond=0)
        
        # Generate all hours from start to current
        temp_hour = start_hour
        while temp_hour <= current_hour:
            hour_key = temp_hour.isoformat()
            all_hours[hour_key] = {
                "total": data_by_hour.get(hour_key, {}).get("total", 0),
                "timestamp": temp_hour
            }
            temp_hour += timedelta(hours=1)
        
        # Sort by timestamp
        sorted_data = sorted(all_hours.items(), key=lambda x: x[1]["timestamp"])
        
        # Format for chart.js
        labels = [item[0] for item in sorted_data]  # ISO format timestamps
        total_gb = [round(item[1]["total"] / 1073741824, 2) for item in sorted_data]
        
        return JSONResponse({
            "labels": labels,
            "total": total_gb,
            "timestamp": now.isoformat()
        })
    finally:
        db.close()
