"""Routes for demo data management"""

import random
import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from sqlalchemy import func

from ..database import SessionLocal
from ..models import Host, RegistroTrafico

# Setup logging
logger = logging.getLogger(__name__)

# Setup templates - support both Docker and local development
possible_frontend_paths = [
    Path(__file__).parent.parent / "frontend",      # Docker: /app/app/frontend
    Path(__file__).parent.parent.parent.parent / "frontend",  # Local: project_root/frontend
]

frontend_dir = None
for path in possible_frontend_paths:
    if (path / "templates").exists():
        frontend_dir = path
        break

if frontend_dir is None:
    raise RuntimeError(f"Frontend directory not found. Searched: {possible_frontend_paths}")

templates = Jinja2Templates(directory=str(frontend_dir / "templates"))

router = APIRouter(prefix="/demo", tags=["Demo"])


@router.post("/generate", response_class=HTMLResponse)
async def generate_demo(request: Request):
    """Generate demo clients with random data"""
    db = SessionLocal()
    
    # Demo names
    demo_names = [
        "DEMO_Casa_Principal",
        "DEMO_Oficina_Centro",
        "DEMO_Sucursal_Este",
        "DEMO_Almacen",
        "DEMO_Retail"
    ]
    
    # Demo IPs
    demo_ips = [
        "192.168.100.50",
        "192.168.100.51",
        "192.168.100.52",
        "192.168.100.53",
        "192.168.100.54"
    ]
    
    now = datetime.utcnow()
    
    # Create demo clients
    for name, ip in zip(demo_names, demo_ips):
        # Check if already exists
        exists = db.query(Host).filter(Host.nombre == name).first()
        if not exists:
            new_host = Host(nombre=name, ip_address=ip, activo=True)
            db.add(new_host)
            db.flush()
            
            # Generate random data for the last 7 days
            for i in range(1, 8):
                date = now - timedelta(days=i)
                random_download = random.randint(1000000000, 10000000000)  # 1GB to 10GB
                random_upload = random.randint(500000000, 5000000000)  # 500MB to 5GB
                
                record = RegistroTrafico(
                    host_id=new_host.id,
                    timestamp=date,
                    bytes_descarga=random_download,
                    bytes_subida=random_upload
                )
                db.add(record)
    
    db.commit()
    
    # Recalculate view
    total_clients = db.query(Host).count()
    demo_clients_list = db.query(Host).filter(Host.nombre.like("DEMO_%")).all()
    demo_count = len(demo_clients_list)
    records_count = db.query(RegistroTrafico).count()
    
    demo_clients_with_consumption = []
    for client in demo_clients_list:
        consumption = db.query(
            func.sum(RegistroTrafico.bytes_descarga + RegistroTrafico.bytes_subida).label('total')
        ).filter(RegistroTrafico.host_id == client.id).first()
        
        total_consumption = consumption.total or 0
        
        demo_clients_with_consumption.append({
            'id': client.id,
            'nombre': client.nombre,
            'ip_address': client.ip_address,
            'activo': client.activo,
            'consumo': total_consumption
        })
    
    db.close()
    
    return templates.TemplateResponse(
        request,
        "demo.html",
        {
            "demo_clientes": demo_clients_with_consumption,
            "demo_count": demo_count,
            "total_count": total_clients,
            "records_count": records_count
        }
    )


@router.delete("/clients/{client_id}", response_class=HTMLResponse)
async def delete_demo_client(request: Request, client_id: int):
    """Delete a demo client"""
    db = SessionLocal()
    try:
        client = db.query(Host).filter(Host.id == client_id).first()
        if client and client.nombre.startswith("DEMO_"):
            db.delete(client)
            db.commit()
            logger.info(f"Demo cliente {client.nombre} (ID: {client_id}) eliminado")
        db.close()
        # Return empty string to remove the row from DOM with HTMX outerHTML swap
        return ""
    except Exception as e:
        db.close()
        logger.error(f"Error deleting demo client {client_id}: {str(e)}")
        return f"<!-- Error eliminating client: {str(e)} -->"


@router.post("/clear", response_class=HTMLResponse)
async def clear_demo(request: Request):
    """Clear all demo clients"""
    db = SessionLocal()
    
    # Delete all demo clients
    demo_clients = db.query(Host).filter(Host.nombre.like("DEMO_%")).all()
    for client in demo_clients:
        db.delete(client)
    
    db.commit()
    
    # Recalculate view
    total_clients = db.query(Host).count()
    demo_clients_list = db.query(Host).filter(Host.nombre.like("DEMO_%")).all()
    demo_count = len(demo_clients_list)
    records_count = db.query(RegistroTrafico).count()
    
    db.close()
    
    return templates.TemplateResponse(
        request,
        "demo.html",
        {
            "demo_clientes": demo_clients_list,
            "demo_count": demo_count,
            "total_count": total_clients,
            "records_count": records_count
        }
    )
