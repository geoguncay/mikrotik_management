"""FastAPI application with traffic monitoring routes"""
import asyncio
import os
from datetime import datetime, timedelta
from pathlib import Path

import routeros_api
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.exc import SQLAlchemyError

from .config import CONFIG
from .database import Base, SessionLocal, engine
from .models import Host, RegistroTrafico
from .api import api_router


# ==================== UTILITY FUNCTIONS ====================

def format_bytes(bytes_value):
    """Convert bytes to MB or GB based on size"""
    if bytes_value is None or bytes_value == 0:
        return "0.0 MB"
    
    # Convert to MB first
    mb = bytes_value / (1024 * 1024)
    
    # If >= 1024 MB, convert to GB
    if mb >= 1024:
        gb = mb / 1024
        return f"{gb:.2f} GB"
    else:
        return f"{mb:.2f} MB"

# Create tables
Base.metadata.create_all(bind=engine)

# Setup FastAPI app
app = FastAPI(
    title="MikroTik Traffic Counter",
    description="Real-time traffic monitoring for MikroTik networks"
)

# Setup templates from frontend directory
# Support both local development and Docker deployment
possible_frontend_paths = [
    Path(__file__).parent / "frontend",      # Docker: /app/app/frontend (since main.py is at /app/app/main.py)
    Path(__file__).parent.parent.parent / "frontend",  # Local: project_root/frontend
]

frontend_dir = None
for path in possible_frontend_paths:
    if (path / "templates").exists():
        frontend_dir = path
        break

if frontend_dir is None:
    raise RuntimeError(f"Frontend directory not found. Searched: {possible_frontend_paths}")

templates = Jinja2Templates(directory=str(frontend_dir / "templates"))

# Register custom filters
templates.env.filters['format_bytes'] = format_bytes

# Serve static files if they exist
static_dir = frontend_dir / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Include API router
app.include_router(api_router)

# Dictionary to remember last reading for each IP
last_readings = {}


# ==================== ROOT ROUTE ====================

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Root route - load base layout"""
    return templates.TemplateResponse(request, "base.html")




# ==================== BACKGROUND TASKS ====================

async def traffic_collector():
    """Background task: collect traffic data from multiple MikroTik routers"""
    from .models import Router
    
    while True:
        db = SessionLocal()
        try:
            active_routers = db.query(Router).filter(Router.activo == True).all()
            
            for router in active_routers:
                active_clients = db.query(Host).filter(
                    Host.activo == True,
                    Host.router_id == router.id
                ).all()
                
                if not active_clients:
                    continue
                
                print(f"[{datetime.utcnow()}] Collecting traffic for router '{router.nombre}' ({router.ip_address})...")
                
                connection = None
                try:
                    connection = routeros_api.RouterOsApiPool(
                        router.ip_address,
                        username=router.usuario,
                        password=router.password,
                        plaintext_login=True,
                    )
                    api = connection.get_api()
                    
                    list_queues = api.get_resource('/queue/simple')
                    queues = list_queues.get()
                    
                    for client in active_clients:
                        client_queue = next((q for q in queues if client.ip_address in q.get('target', '')), None)
                        
                        if client_queue:
                            bytes_str = client_queue.get('bytes', '0/0')
                            tx_str, rx_str = bytes_str.split('/')
                            current_tx, current_rx = int(tx_str), int(rx_str)
                            
                            ip = client.ip_address
                            tracking_key = f"{router.id}_{ip}"
                            
                            if tracking_key in last_readings:
                                delta_tx = current_tx - last_readings[tracking_key]['tx']
                                delta_rx = current_rx - last_readings[tracking_key]['rx']
                                
                                if delta_tx < 0 or delta_rx < 0:
                                    delta_tx, delta_rx = current_tx, current_rx
                                    
                                new_record = RegistroTrafico(
                                    host_id=client.id,
                                    bytes_descarga=delta_rx,
                                    bytes_subida=delta_tx
                                )
                                db.add(new_record)
                            
                            last_readings[tracking_key] = {'tx': current_tx, 'rx': current_rx}
                    
                    db.commit()
                except Exception as e:
                    print(f"Error collecting traffic for router '{router.nombre}': {e}")
                    db.rollback()
                finally:
                    if connection:
                        try:
                            connection.disconnect()
                        except:
                            pass
        except Exception as e:
            print(f"Error in traffic collector loop: {e}")
        finally:
            db.close()
            
        await asyncio.sleep(60)


@app.on_event("startup")
async def start_background_tasks():
    """Start background traffic collection on app startup"""
    asyncio.create_task(traffic_collector())
