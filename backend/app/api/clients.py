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

# Register format_bytes filter (same as views.py and config.py)
def format_bytes(bytes_value):
    """Convert bytes to MB or GB based on size"""
    if bytes_value is None or bytes_value == 0:
        return "0.0 MB"
    mb = bytes_value / (1024 * 1024)
    if mb >= 1024:
        gb = mb / 1024
        return f"{gb:.2f} GB"
    else:
        return f"{mb:.2f} MB"

templates.env.filters['format_bytes'] = format_bytes

router = APIRouter(prefix="", tags=["Clients"])


# ==================== HELPER FUNCTIONS ====================
import time
from typing import Dict, Any

# Simple in-memory cache for router queues to avoid hitting the router API dozens of times concurrently
QUEUES_CACHE: Dict[int, Dict[str, Any]] = {}
ADDRESS_LISTS_CACHE: Dict[int, Dict[str, Any]] = {}
CACHE_TTL = 10 # 10 seconds

def get_router_queues(router_obj):
    if not router_obj:
        return []
    now = time.time()
    cache_entry = QUEUES_CACHE.get(router_obj.id)
    if cache_entry and (now - cache_entry["timestamp"] < CACHE_TTL):
        return cache_entry["queues"]
        
    try:
        connection = routeros_api.RouterOsApiPool(
            router_obj.ip_address.strip(),
            username=router_obj.usuario.strip(),
            password=router_obj.password,
            plaintext_login=True,
        )
        api = connection.get_api()
        list_queues = api.get_resource('/queue/simple')
        queues = list_queues.get()
        connection.disconnect()
        
        QUEUES_CACHE[router_obj.id] = {
            "queues": queues,
            "timestamp": now
        }
        return queues
    except Exception as e:
        logger.error(f"Error checking queues for router {router_obj.ip_address}: {e}")
        # If call fails, fall back to stale cache if available, else empty list
        if cache_entry:
            return cache_entry["queues"]
        return []


def get_router_address_lists(router_obj) -> list:
    """Fetch address lists for a router, cached for CACHE_TTL seconds"""
    if not router_obj:
        return []
    now = time.time()
    cache_entry = ADDRESS_LISTS_CACHE.get(router_obj.id)
    if cache_entry and (now - cache_entry["timestamp"] < CACHE_TTL):
        return cache_entry["address_lists"]
        
    try:
        connection = routeros_api.RouterOsApiPool(
            router_obj.ip_address.strip(),
            username=router_obj.usuario.strip(),
            password=router_obj.password,
            plaintext_login=True,
        )
        api = connection.get_api()
        address_lists_resource = api.get_resource('/ip/firewall/address-list')
        address_lists = address_lists_resource.get()
        connection.disconnect()
        
        ADDRESS_LISTS_CACHE[router_obj.id] = {
            "address_lists": address_lists,
            "timestamp": now
        }
        return address_lists
    except Exception as e:
        logger.error(f"Error checking address lists for router {router_obj.ip_address}: {e}")
        if cache_entry:
            return cache_entry["address_lists"]
        return []


def is_client_suspended(ip_address: str, router_obj=None) -> bool:
    """Check if a client IP is active (disabled=false) in the '1CLIENTES' address list on MikroTik"""
    if not router_obj:
        return False
    address_lists = get_router_address_lists(router_obj)
    
    for addr in address_lists:
        addr_ip = addr.get('address', '')
        if ip_address == addr_ip:
            list_name = addr.get('list', '')
            if list_name == '1CLIENTES':
                disabled = addr.get('disabled', 'false')
                if isinstance(disabled, str):
                    disabled = disabled.lower() == 'true'
                
                # If the entry is enabled (disabled=False) in '1CLIENTES', it is suspended
                if not disabled:
                    return True
    return False


def sync_client_suspension_on_router(ip_address: str, router_obj=None, is_active: bool = True) -> bool:
    """Sync client active/suspension status to MikroTik '1CLIENTES' address list.
       is_active=True means client is active (can navigate), so address list rule is disabled=true.
       is_active=False means client is suspended, so address list rule is disabled=false.
    """
    if not router_obj:
        return False
    try:
        connection = routeros_api.RouterOsApiPool(
            router_obj.ip_address.strip(),
            username=router_obj.usuario.strip(),
            password=router_obj.password,
            plaintext_login=True,
        )
        api = connection.get_api()
        address_lists_resource = api.get_resource('/ip/firewall/address-list')
        
        # Search for existing entry in '1CLIENTES' list
        all_entries = address_lists_resource.get()
        existing_entry = next((e for e in all_entries if e.get('list') == '1CLIENTES' and e.get('address') == ip_address), None)
        
        disabled_str = 'true' if is_active else 'false'
        
        if existing_entry:
            # Entry exists, update its disabled status if needed
            entry_id = existing_entry.get('id')
            current_disabled = existing_entry.get('disabled', 'false')
            if isinstance(current_disabled, str):
                current_disabled = current_disabled.lower() == 'true'
                
            if current_disabled != is_active:
                address_lists_resource.set(id=entry_id, disabled=disabled_str)
                logger.info(f"Updated '1CLIENTES' entry for IP {ip_address} to disabled={disabled_str}")
        else:
            # Entry doesn't exist, create it
            address_lists_resource.add(list='1CLIENTES', address=ip_address, disabled=disabled_str)
            logger.info(f"Created '1CLIENTES' entry for IP {ip_address} with disabled={disabled_str}")
            
        connection.disconnect()
        # Invalidate cache
        ADDRESS_LISTS_CACHE.pop(router_obj.id, None)
        return True
    except Exception as e:
        logger.error(f"Error syncing client suspension for IP {ip_address} on router {router_obj.ip_address}: {e}")
        return False


def sync_multiple_clients_suspension_on_router(ips_list: list, router_obj=None, is_active: bool = True) -> bool:
    """Sync multiple client active/suspension statuses to MikroTik '1CLIENTES' address list in a single connection."""
    if not router_obj or not ips_list:
        return False
    try:
        connection = routeros_api.RouterOsApiPool(
            router_obj.ip_address.strip(),
            username=router_obj.usuario.strip(),
            password=router_obj.password,
            plaintext_login=True,
        )
        api = connection.get_api()
        address_lists_resource = api.get_resource('/ip/firewall/address-list')
        
        all_entries = address_lists_resource.get()
        disabled_str = 'true' if is_active else 'false'
        
        for ip in ips_list:
            existing_entry = next((e for e in all_entries if e.get('list') == '1CLIENTES' and e.get('address') == ip), None)
            if existing_entry:
                entry_id = existing_entry.get('id')
                current_disabled = existing_entry.get('disabled', 'false')
                if isinstance(current_disabled, str):
                    current_disabled = current_disabled.lower() == 'true'
                if current_disabled != is_active:
                    address_lists_resource.set(id=entry_id, disabled=disabled_str)
            else:
                address_lists_resource.add(list='1CLIENTES', address=ip, disabled=disabled_str)
                
        connection.disconnect()
        ADDRESS_LISTS_CACHE.pop(router_obj.id, None)
        return True
    except Exception as e:
        logger.error(f"Error bulk syncing client suspensions on router {router_obj.ip_address}: {e}")
        return False


def remove_client_suspension_from_router(ip_address: str, router_obj=None) -> bool:
    """Remove client IP from MikroTik '1CLIENTES' address list."""
    if not router_obj:
        return False
    try:
        connection = routeros_api.RouterOsApiPool(
            router_obj.ip_address.strip(),
            username=router_obj.usuario.strip(),
            password=router_obj.password,
            plaintext_login=True,
        )
        api = connection.get_api()
        address_lists_resource = api.get_resource('/ip/firewall/address-list')
        
        all_entries = address_lists_resource.get()
        existing_entry = next((e for e in all_entries if e.get('list') == '1CLIENTES' and e.get('address') == ip_address), None)
        
        if existing_entry:
            address_lists_resource.remove(id=existing_entry.get('id'))
            logger.info(f"Removed IP {ip_address} from '1CLIENTES' list")
            
        connection.disconnect()
        ADDRESS_LISTS_CACHE.pop(router_obj.id, None)
        return True
    except Exception as e:
        logger.error(f"Error removing IP {ip_address} from router {router_obj.ip_address}: {e}")
        return False


def is_client_connected_to_router(ip_address: str, router_obj=None) -> bool:
    """Check if a client IP has an active queue in MikroTik"""
    if not router_obj:
        return False
    queues = get_router_queues(router_obj)
    return any(ip_address in q.get('target', '') for q in queues)

# HTMX endpoint to add a new client, with validation and error handling, returning a modal with success or error message
@router.post("/clients", response_class=HTMLResponse)
async def add_client(
    request: Request,
    nombre: str = Form(...),
    ip_address: str = Form(...),
    router_id: int = Form(None),
    activo: str = Form(None),
):
    """Add new host to monitor"""
    is_active = True if activo == "on" else False
    
    db = SessionLocal()
    from ..models import Router
    
    try:
        # Check if IP already exists
        ip_exists = db.query(Host).filter(Host.ip_address == ip_address).first()
        if ip_exists:
            routers = db.query(Router).all()
            db.close()
            # Return modal with error message
            return templates.TemplateResponse(request, "modals/add_client.html", {
                "error": f"La dirección IP {ip_address} ya está siendo monitoreada por {ip_exists.nombre}",
                "nombre": nombre,
                "ip_address": ip_address,
                "router_id": router_id,
                "activo": activo,
                "routers": routers
            })
        
        new_host = Host(nombre=nombre, ip_address=ip_address, activo=is_active, router_id=router_id)
        db.add(new_host)
        db.commit()
        
        # Sync suspension list on MikroTik
        if router_id:
            router_obj = db.query(Router).filter(Router.id == router_id).first()
            if router_obj:
                sync_client_suspension_on_router(ip_address, router_obj, is_active)
    except SQLAlchemyError as e:
        db.rollback()
        print(f"Error al guardar: {e}")
    finally:
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

# HTMX endpoint to delete a client and return empty response to remove the row from the table with hx-swap="outerHTML"
@router.delete("/clients/{client_id}", response_class=HTMLResponse)
async def delete_client(request: Request, client_id: int, sort_by: str = "ip", order: str = "asc", period: str = "daily"):
    """Delete host from monitoring"""
    db = SessionLocal()
    try:
        client = db.query(Host).filter(Host.id == client_id).first()
        if client:
            ip_address = client.ip_address
            router_obj = client.router
            
            db.delete(client)
            db.commit()
            logger.info(f"Cliente {client.nombre} (ID: {client_id}) eliminado")
            
            if router_obj:
                remove_client_suspension_from_router(ip_address, router_obj)
        db.close()
        # Return empty string to remove the row from DOM with HTMX outerHTML swap
        return ""
    except Exception as e:
        db.close()
        logger.error(f"Error deleting client {client_id}: {str(e)}")
        return f"<!-- Error eliminating client: {str(e)} -->"


# HTMX fragment to get real-time connection status for a client, to be used in the clients table and updated every 30 seconds
@router.get("/views/client_status/{client_id}", response_class=HTMLResponse)
async def get_client_status(request: Request, client_id: int):
    """Get real-time connection status for a client"""
    db = SessionLocal()
    client = db.query(Host).filter(Host.id == client_id).first()
    
    if not client:
        db.close()
        return ""
    
    # Check suspension and connection status against MikroTik
    is_suspended = is_client_suspended(client.ip_address, client.router)
    is_connected = is_client_connected_to_router(client.ip_address, client.router)
    db.close()
    
    if is_suspended:
        return f"""
        <td id="status-{client_id}" class="px-3 py-3 sm:px-6 sm:py-4 whitespace-nowrap" 
            hx-get="/api/views/client_status/{client_id}" 
            hx-trigger="every 30s" 
            hx-swap="outerHTML">
            <span class="inline-flex items-center gap-1.5">
                <span class="px-2 py-2 inline-flex rounded-full bg-amber-100">
                    <span class="relative flex h-2.5 w-2.5">
                        <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75"></span>
                        <span class="relative inline-flex rounded-full h-2.5 w-2.5 bg-amber-500"></span>
                    </span>
                </span>
                <span class="text-amber-700 font-medium text-xs">Suspendido</span>
            </span>
        </td>
        """
    elif is_connected:
        return f"""
        <td id="status-{client_id}" class="px-3 py-3 sm:px-6 sm:py-4 whitespace-nowrap" 
            hx-get="/api/views/client_status/{client_id}" 
            hx-trigger="every 30s" 
            hx-swap="outerHTML">
            <span class="inline-flex items-center gap-1.5">
                <span class="px-2 py-2 inline-flex rounded-full bg-green-100">
                    <span class="relative flex h-2.5 w-2.5">
                        <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                        <span class="relative inline-flex rounded-full h-2.5 w-2.5 bg-green-500"></span>
                    </span>
                </span>
                <span class="text-green-700 font-medium text-xs">Conectado</span>
            </span>
        </td>
        """
    else:
        return f"""
        <td id="status-{client_id}" class="px-3 py-3 sm:px-6 sm:py-4 whitespace-nowrap" 
            hx-get="/api/views/client_status/{client_id}" 
            hx-trigger="every 30s" 
            hx-swap="outerHTML">
            <span class="inline-flex items-center gap-1.5">
                <span class="px-2 py-2 inline-flex rounded-full bg-red-100">
                    <span class="relative flex h-2.5 w-2.5">
                        <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
                        <span class="relative inline-flex rounded-full h-2.5 w-2.5 bg-red-500"></span>
                    </span>
                </span>
                <span class="text-red-700 font-medium text-xs">Desconectado</span>
            </span>
        </td>
        """


@router.get("/views/edit_client/{client_id}", response_class=HTMLResponse)
async def view_edit_client(request: Request, client_id: int):
    """HTMX fragment: edit host modal form"""
    from ..models import Router
    db = SessionLocal()
    client = db.query(Host).filter(Host.id == client_id).first()
    routers = db.query(Router).all()
    db.close()
    
    if not client:
        return templates.TemplateResponse(request, "modals/edit_client.html", {
            "error": "Cliente no encontrado",
            "client_id": client_id,
            "routers": routers
        })
    
    # Determine real-time active state from MikroTik:
    # A client is "activo" (allowed to navigate) only if it's NOT suspended in 1CLIENTES
    try:
        is_susp = is_client_suspended(client.ip_address, client.router)
        # activo=True means allowed (not suspended), activo=False means suspended
        activo_real = not is_susp
    except Exception:
        # If MikroTik is unreachable, fall back to the database value
        activo_real = client.activo if client.activo is not None else True
    
    return templates.TemplateResponse(request, "modals/edit_client.html", {
        "client_id": client_id,
        "nombre": client.nombre,
        "ip_address": client.ip_address,
        "activo": activo_real,
        "router_id": client.router_id,
        "routers": routers,
        "error": None
    })


@router.post("/clients/{client_id}/update", response_class=HTMLResponse)
async def update_client(
    request: Request,
    client_id: int,
    nombre: str = Form(...),
    ip_address: str = Form(...),
    router_id: int = Form(None),
    activo: str = Form(None),
):
    """Update host information"""
    from sqlalchemy import func, desc, asc
    from ..models import Router
    
    is_active = True if activo == "on" else False
    
    db = SessionLocal()
    routers = db.query(Router).all()
    
    try:
        client = db.query(Host).filter(Host.id == client_id).first()
        if not client:
            db.close()
            return templates.TemplateResponse(request, "modals/edit_client.html", {
                "error": "Cliente no encontrado",
                "client_id": client_id,
                "routers": routers
            })
        
        # Check if new IP is being used by another client
        if ip_address != client.ip_address:
            ip_exists = db.query(Host).filter(
                Host.ip_address == ip_address,
                Host.id != client_id
            ).first()
            if ip_exists:
                db.close()
                return templates.TemplateResponse(request, "modals/edit_client.html", {
                    "error": f"La dirección IP {ip_address} ya está siendo monitoreada por {ip_exists.nombre}",
                    "client_id": client_id,
                    "nombre": nombre,
                    "ip_address": ip_address,
                    "router_id": router_id,
                    "activo": activo,
                    "routers": routers
                })
        
        # Keep old values for MikroTik sync
        old_ip = client.ip_address
        old_router = client.router
        
        # Update client
        client.nombre = nombre
        client.ip_address = ip_address
        client.router_id = router_id
        client.activo = is_active
        db.commit()
        
        # Sync suspension list on MikroTik
        new_router = db.query(Router).filter(Router.id == router_id).first()
        
        # If router changed, or IP changed, remove from old router/IP list
        if old_router and (old_router.id != router_id or old_ip != ip_address):
            remove_client_suspension_from_router(old_ip, old_router)
        elif old_ip != ip_address and old_router:
            remove_client_suspension_from_router(old_ip, old_router)
            
        # Add or update on new router/IP list
        if new_router:
            sync_client_suspension_on_router(ip_address, new_router, is_active)
        
        # Return updated clients view (default period=daily and sort_by=ip)
        sort_by = "ip"
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
            
            # Check connection and suspension status
            suspended = is_client_suspended(c.ip_address, c.router)
            connected = is_client_connected_to_router(c.ip_address, c.router)
            
            if suspended:
                estado_real = "suspendido"
            elif connected:
                estado_real = "conectado"
            else:
                estado_real = "desconectado"
            
            clients_with_consumption.append({
                'id': c.id,
                'nombre': c.nombre,
                'ip_address': c.ip_address,
                'activo': c.activo,
                'estado_real': estado_real,
                'descarga': total_download,
                'subida': total_upload,
                'total': total_download + total_upload,
                'router_nombre': c.router.nombre if c.router else 'N/A'
            })
        
        # Apply sorting
        import ipaddress
        def ip_sort_key(x):
            ip_str = x['ip_address']
            try:
                return (0, ipaddress.ip_address(ip_str))
            except Exception:
                return (1, ip_str)
        clients_with_consumption.sort(key=ip_sort_key, reverse=False)
        
        # Get general metrics
        total_hosts = len(clients_with_consumption)
        hosts_activos = sum(1 for c in clients_with_consumption if c['estado_real'] == 'conectado')
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
        return templates.TemplateResponse(request, "modals/edit_client.html", {
            "error": f"Error al actualizar cliente: {str(e)}",
            "client_id": client_id,
            "nombre": nombre,
            "ip_address": ip_address,
            "router_id": router_id,
            "activo": activo,
            "routers": routers
        })
async def add_bulk_clients_from_list(
    address_list_name: str = Form(...),
    router_id: int = Form(None),
    activo: str = Form(None),
):
    """Add all IPs from an address list as clients"""
    is_active = True if activo == "on" else False
    
    db = SessionLocal()
    from ..models import Router
    added_count = 0
    skipped_count = 0
    errors = []
    
    try:
        # Get router info
        router_obj = None
        if router_id:
            router_obj = db.query(Router).filter(Router.id == router_id).first()
        if not router_obj:
            router_obj = db.query(Router).first()
            
        if not router_obj:
            db.close()
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "message": "No hay ningún router configurado.",
                    "added": 0,
                    "skipped": 0
                }
            )
            
        # Get IPs from the address list
        connection = routeros_api.RouterOsApiPool(
            router_obj.ip_address,
            username=router_obj.usuario,
            password=router_obj.password,
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
        successfully_added_ips = []
        for ip_address in ips_to_add:
            try:
                # Check if IP already exists
                ip_exists = db.query(Host).filter(Host.ip_address == ip_address).first()
                if ip_exists:
                    skipped_count += 1
                    continue
                
                # Create client with name based on list name and IP
                client_name = f"{address_list_name} - {ip_address}"
                new_host = Host(nombre=client_name, ip_address=ip_address, activo=is_active, router_id=router_obj.id)
                db.add(new_host)
                successfully_added_ips.append(ip_address)
                added_count += 1
                
            except Exception as e:
                logger.error(f"Error adding IP {ip_address}: {str(e)}")
                errors.append(f"{ip_address}: {str(e)}")
                skipped_count += 1
        
        db.commit()
        logger.info(f"Agregados {added_count} clientes de la lista '{address_list_name}'")
        
        # Sync to '1CLIENTES' address list in bulk
        if successfully_added_ips and router_obj:
            sync_multiple_clients_suspension_on_router(successfully_added_ips, router_obj, is_active)
        
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
async def add_bulk_clients(ips: str = Form(...), router_id: int = Form(None)):
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
        successfully_added_ips = []
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
                new_host = Host(nombre=nombre, ip_address=ip_address, activo=True, router_id=router_id)
                db.add(new_host)
                successfully_added_ips.append(ip_address)
                added_count += 1
                
            except Exception as e:
                logger.error(f"Error adding IP {ip_address if isinstance(item, dict) else item}: {str(e)}")
                errors.append(f"{ip_address if isinstance(item, dict) else item}: {str(e)}")
                skipped_count += 1
        
        db.commit()
        logger.info(f"Agregados {added_count} clientes en bulk")
        
        # Sync to '1CLIENTES' address list in bulk (they are added as active, so is_active=True)
        if successfully_added_ips and router_id:
            from ..models import Router
            router_obj = db.query(Router).filter(Router.id == router_id).first()
            if router_obj:
                sync_multiple_clients_suspension_on_router(successfully_added_ips, router_obj, is_active=True)
        
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
