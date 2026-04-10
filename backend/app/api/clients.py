"""Routes for client management"""

from datetime import datetime, timedelta
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
import routeros_api
import logging

from ..database import SessionLocal
from ..models import Host, RegistroTrafico
from ..config import CONFIG

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

router = APIRouter(prefix="", tags=["Clients"])


@router.post("/clients", response_class=HTMLResponse)
async def add_client(
    request: Request,
    nombre: str = Form(...),
    ip_address: str = Form(...),
    activo: str = Form(None),
):
    """Add new host to monitor"""
    is_active = True if activo == "on" else False
    
    db = SessionLocal()
    
    try:
        # Check if IP already exists
        ip_exists = db.query(Host).filter(Host.ip_address == ip_address).first()
        if ip_exists:
            db.close()
            # Return modal with error message
            return templates.TemplateResponse(request, "modals/modal_add_client.html", {
                "error": f"La dirección IP {ip_address} ya está siendo monitoreada por {ip_exists.nombre}",
                "nombre": nombre,
                "ip_address": ip_address,
                "activo": activo
            })
        
        new_host = Host(nombre=nombre, ip_address=ip_address, activo=is_active)
        db.add(new_host)
        db.commit()
    except SQLAlchemyError as e:
        db.rollback()
        print(f"Error al guardar: {e}")
    finally:
        clients_db = db.query(Host).all()
        db.close()
    
    # On success: show confirmation and reload clients
    return """
        <div class="fixed inset-0 bg-gray-900 bg-opacity-50 z-40 flex items-center justify-center animate-fade-in"
        hx-trigger="load" 
        hx-get="/api/views/clients" 
        hx-target="#main-content" 
        hx-swap="innerHTML"
        hx-on::htmx:afterSwap="document.getElementById('modal-container').innerHTML = ''">
        <div class="bg-white rounded-xl shadow-2xl max-w-md mx-4 p-6 text-center">
            <div class="mb-4">
                <i class="fa-solid fa-check-circle text-4xl text-green-500"></i>
            </div>
            <h3 class="text-lg font-semibold text-gray-800 mb-2">¡Éxito!</h3>
            <p class="text-gray-600 text-sm">Cliente registrado correctamente</p>
        </div>
    </div>
    """


@router.delete("/clients/{client_id}", response_class=HTMLResponse)
async def delete_client(request: Request, client_id: int, sort_by: str = "nombre", order: str = "asc", period: str = "daily"):
    """Delete host from monitoring"""
    db = SessionLocal()
    try:
        client = db.query(Host).filter(Host.id == client_id).first()
        if client:
            db.delete(client)
            db.commit()
            logger.info(f"Cliente {client.nombre} (ID: {client_id}) eliminado")
        db.close()
        # Return empty string to remove the row from DOM with HTMX outerHTML swap
        return ""
    except Exception as e:
        db.close()
        logger.error(f"Error deleting client {client_id}: {str(e)}")
        return f"<!-- Error eliminating client: {str(e)} -->"


@router.get("/views/modal_edit_client/{client_id}", response_class=HTMLResponse)
async def view_modal_edit(request: Request, client_id: int):
    """HTMX fragment: edit host modal form"""
    db = SessionLocal()
    client = db.query(Host).filter(Host.id == client_id).first()
    db.close()
    
    if not client:
        return templates.TemplateResponse(request, "modals/modal_edit_client.html", {
            "error": "Cliente no encontrado",
            "client_id": client_id
        })
    
    return templates.TemplateResponse(request, "modals/modal_edit_client.html", {
        "client_id": client_id,
        "nombre": client.nombre,
        "ip_address": client.ip_address,
        "activo": client.activo,
        "error": None
    })


@router.put("/clients/{client_id}", response_class=HTMLResponse)
async def update_client(
    request: Request,
    client_id: int,
    nombre: str = Form(...),
    ip_address: str = Form(...),
    activo: str = Form(None),
):
    """Update host information"""
    from sqlalchemy import func, desc, asc
    
    is_active = True if activo == "on" else False
    
    db = SessionLocal()
    
    try:
        client = db.query(Host).filter(Host.id == client_id).first()
        if not client:
            db.close()
            return templates.TemplateResponse(request, "modals/modal_edit_client.html", {
                "error": "Cliente no encontrado",
                "client_id": client_id
            })
        
        # Check if new IP is being used by another client
        if ip_address != client.ip_address:
            ip_exists = db.query(Host).filter(
                Host.ip_address == ip_address,
                Host.id != client_id
            ).first()
            if ip_exists:
                db.close()
                return templates.TemplateResponse(request, "modals/modal_edit_client.html", {
                    "error": f"La dirección IP {ip_address} ya está siendo monitoreada por {ip_exists.nombre}",
                    "client_id": client_id,
                    "nombre": nombre,
                    "ip_address": ip_address,
                    "activo": activo
                })
        
        # Update client
        client.nombre = nombre
        client.ip_address = ip_address
        client.activo = is_active
        db.commit()
        
        # Return updated clients view (default period=daily and sort_by=nombre)
        sort_by = "nombre"
        order = "asc"
        period = "daily"
        
        clients_db = db.query(Host).all()
        
        # Determine start date according to period
        now = datetime.utcnow()
        start_date = now - timedelta(days=1)  # daily by default
        
        # Calculate consumption per client
        clients_with_consumption = []
        for c in clients_db:
            consumption = db.query(
                func.sum(RegistroTrafico.bytes_descarga).label('total_descarga'),
                func.sum(RegistroTrafico.bytes_subida).label('total_subida')
            ).filter(
                RegistroTrafico.host_id == c.id,
                RegistroTrafico.timestamp >= start_date
            ).first()
            
            total_download = consumption.total_descarga or 0
            total_upload = consumption.total_subida or 0
            
            clients_with_consumption.append({
                'id': c.id,
                'nombre': c.nombre,
                'ip_address': c.ip_address,
                'activo': c.activo,
                'descarga': total_download,
                'subida': total_upload,
                'total': total_download + total_upload
            })
        
        # Apply sorting
        clients_with_consumption.sort(key=lambda x: x['nombre'].lower(), reverse=False)
        
        # Get general metrics
        total_hosts = db.query(Host).count()
        hosts_activos = db.query(Host).filter(Host.activo.is_(True)).count()
        hosts_inactivos = total_hosts - hosts_activos
        
        # Totals for the selected period
        total_period_download = db.query(func.coalesce(func.sum(RegistroTrafico.bytes_descarga), 0)).filter(
            RegistroTrafico.timestamp >= start_date
        ).scalar() or 0
        total_period_upload = db.query(func.coalesce(func.sum(RegistroTrafico.bytes_subida), 0)).filter(
            RegistroTrafico.timestamp >= start_date
        ).scalar() or 0
        
        db.close()
        
        period_labels = {
            "1h": "Última hora",
            "12h": "Últimas 12 horas",
            "daily": "Últimas 24 horas",
            "weekly": "Últimos 7 días",
            "monthly": "Últimos 30 días",
            "yearly": "Último año"
        }
        
        return templates.TemplateResponse(
            request, 
            "clients.html", 
            {
                "clientes": clients_with_consumption,
                "sort_by": sort_by,
                "order": order,
                "period": period,
                "period_label": period_labels.get(period, "Últimas 24 horas"),
                "total_hosts": total_hosts,
                "hosts_activos": hosts_activos,
                "hosts_inactivos": hosts_inactivos,
                "total_period_descarga": total_period_download,
                "total_period_subida": total_period_upload,
            }
        )
    
    except Exception as e:
        db.close()
        return templates.TemplateResponse(request, "modals/modal_edit_client.html", {
            "error": f"Error al actualizar cliente: {str(e)}",
            "client_id": client_id,
            "nombre": nombre,
            "ip_address": ip_address,
            "activo": activo
        })


@router.post("/clients/bulk-from-list")
async def add_bulk_clients_from_list(
    address_list_name: str = Form(...),
    activo: str = Form(None),
):
    """Add all IPs from an address list as clients"""
    is_active = True if activo == "on" else False
    
    db = SessionLocal()
    added_count = 0
    skipped_count = 0
    errors = []
    
    try:
        # Get IPs from the address list
        connection = routeros_api.RouterOsApiPool(
            CONFIG["MK_IP"],
            username=CONFIG["MK_USER"],
            password=CONFIG["MK_PASS"],
            plaintext_login=True,
        )
        api = connection.get_api()
        
        # Get addresses from the specified list
        address_lists_resource = api.get_resource('/ip/firewall/address-list')
        address_lists = address_lists_resource.get()
        
        connection.disconnect()
        
        # Filter addresses by list name
        ips_to_add = []
        for addr in address_lists:
            if addr.get('list') == address_list_name:
                ips_to_add.append(addr.get('address'))
        
        if not ips_to_add:
            db.close()
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "message": f"No se encontraron direcciones en la lista '{address_list_name}'",
                    "added": 0,
                    "skipped": 0
                }
            )
        
        # Try to add each IP as a client
        for ip_address in ips_to_add:
            try:
                # Check if IP already exists
                ip_exists = db.query(Host).filter(Host.ip_address == ip_address).first()
                if ip_exists:
                    skipped_count += 1
                    continue
                
                # Create client with name based on list name and IP
                client_name = f"{address_list_name} - {ip_address}"
                new_host = Host(nombre=client_name, ip_address=ip_address, activo=is_active)
                db.add(new_host)
                added_count += 1
                
            except Exception as e:
                logger.error(f"Error adding IP {ip_address}: {str(e)}")
                errors.append(f"{ip_address}: {str(e)}")
                skipped_count += 1
        
        db.commit()
        logger.info(f"Agregados {added_count} clientes de la lista '{address_list_name}'")
        
        db.close()
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": f"Se agregaron {added_count} cliente(s) de la lista '{address_list_name}'. {skipped_count} saltados (duplicados o errores).",
                "added": added_count,
                "skipped": skipped_count,
                "errors": errors if errors else None
            }
        )
        
    except Exception as e:
        db.close()
        logger.error(f"Error in bulk add: {type(e).__name__}: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"Error al agregar clientes: {str(e)}",
                "added": added_count,
                "skipped": skipped_count
            }
        )


@router.post("/clients/bulk-add")
async def add_bulk_clients(ips: str = Form(...)):
    """Add multiple IPs directly selected by user with optional names from comments"""
    import json
    
    db = SessionLocal()
    added_count = 0
    skipped_count = 0
    errors = []
    
    try:
        # Parse IPs from JSON string
        ips_list = json.loads(ips)
        
        if not ips_list:
            db.close()
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "message": "No hay IPs para agregar",
                    "added": 0,
                    "skipped": 0
                }
            )
        
        # Try to add each IP as a client
        for item in ips_list:
            try:
                # Handle both formats: simple IP string or object with {ip, nombre}
                if isinstance(item, dict):
                    ip_address = item.get('ip')
                    nombre = item.get('nombre') or item.get('comment') or ip_address
                else:
                    ip_address = item
                    nombre = ip_address
                
                # Check if IP already exists
                ip_exists = db.query(Host).filter(Host.ip_address == ip_address).first()
                if ip_exists:
                    skipped_count += 1
                    continue
                
                # Create client with name from comment or IP
                new_host = Host(nombre=nombre, ip_address=ip_address, activo=True)
                db.add(new_host)
                added_count += 1
                
            except Exception as e:
                logger.error(f"Error adding IP {ip_address if isinstance(item, dict) else item}: {str(e)}")
                errors.append(f"{ip_address if isinstance(item, dict) else item}: {str(e)}")
                skipped_count += 1
        
        db.commit()
        logger.info(f"Agregados {added_count} clientes en bulk")
        
        db.close()
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": f"Se agregaron {added_count} cliente(s). {skipped_count} saltados (duplicados o errores).",
                "added": added_count,
                "skipped": skipped_count,
                "errors": errors if errors else None
            }
        )
        
    except Exception as e:
        db.close()
        logger.error(f"Error in bulk add: {type(e).__name__}: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"Error al agregar clientes: {str(e)}",
                "added": 0,
                "skipped": skipped_count
            }
        )
