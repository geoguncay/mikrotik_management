"""View routes for rendering templates and HTML fragments"""

from datetime import datetime, timedelta
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from sqlalchemy import func
import routeros_api
import logging

from ..database import SessionLocal
from ..models import Router, Host, RegistroTrafico
from ..config import CONFIG

# Setup logging
logger = logging.getLogger(__name__)


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

# Register custom filters
templates.env.filters['format_bytes'] = format_bytes

router = APIRouter(prefix="/views", tags=["Views"])


@router.get("/dashboard", response_class=HTMLResponse)
async def view_dashboard(request: Request):
    """HTMX fragment: dashboard with metrics"""
    db = SessionLocal()
    try:
        from .clients import is_client_connected_to_router, is_client_suspended
        all_hosts = db.query(Host).all()
        total_hosts = len(all_hosts)
        hosts_activos = 0
        for host in all_hosts:
            is_susp = is_client_suspended(host.ip_address, host.router)
            is_conn = is_client_connected_to_router(host.ip_address, host.router)
            if is_conn and not is_susp:
                hosts_activos += 1
        hosts_inactivos = total_hosts - hosts_activos

        total_routers = db.query(Router).count()
        routers_activos = db.query(Router).filter(Router.activo.is_(True)).count()
        routers_inactivos = total_routers - routers_activos

        ago_24h = datetime.utcnow() - timedelta(hours=24)
        ago_7d = datetime.utcnow() - timedelta(days=7)

        total_24h_download = db.query(func.coalesce(func.sum(RegistroTrafico.bytes_descarga), 0)).filter(
            RegistroTrafico.timestamp >= ago_24h
        ).scalar() or 0
        total_24h_upload = db.query(func.coalesce(func.sum(RegistroTrafico.bytes_subida), 0)).filter(
            RegistroTrafico.timestamp >= ago_24h
        ).scalar() or 0

        total_7d_download = db.query(func.coalesce(func.sum(RegistroTrafico.bytes_descarga), 0)).filter(
            RegistroTrafico.timestamp >= ago_7d
        ).scalar() or 0
        total_7d_upload = db.query(func.coalesce(func.sum(RegistroTrafico.bytes_subida), 0)).filter(
            RegistroTrafico.timestamp >= ago_7d
        ).scalar() or 0
        
        # Overall totals (all time)
        total_all_download = db.query(func.coalesce(func.sum(RegistroTrafico.bytes_descarga), 0)).scalar() or 0
        total_all_upload = db.query(func.coalesce(func.sum(RegistroTrafico.bytes_subida), 0)).scalar() or 0

        total_traffic_expr = (func.sum(RegistroTrafico.bytes_descarga) + func.sum(RegistroTrafico.bytes_subida)).label("total")
        top_hosts_query = (
            db.query(
                Host.nombre,
                func.coalesce(func.sum(RegistroTrafico.bytes_descarga), 0).label("descarga"),
                func.coalesce(func.sum(RegistroTrafico.bytes_subida), 0).label("subida"),
                total_traffic_expr,
            )
            .join(RegistroTrafico, RegistroTrafico.host_id == Host.id)
            .filter(RegistroTrafico.timestamp >= ago_7d)
            .group_by(Host.id)
            .order_by(total_traffic_expr.desc())
            .limit(5)
            .all()
        )

        top_hosts = [
            {
                "nombre": row.nombre,
                "descarga": int(row.descarga or 0),
                "subida": int(row.subida or 0),
                "total": int(row.total or 0),
            }
            for row in top_hosts_query
        ]
    finally:
        db.close()

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "total_hosts": total_hosts,
            "hosts_activos": hosts_activos,
            "hosts_inactivos": hosts_inactivos,
            "total_routers": total_routers,
            "routers_activos": routers_activos,
            "routers_inactivos": routers_inactivos,
            "total_24h_descarga": total_24h_download,
            "total_24h_subida": total_24h_upload,
            "total_7d_descarga": total_7d_download,
            "total_7d_subida": total_7d_upload,
            "total_all_descarga": total_all_download,
            "total_all_subida": total_all_upload,
            "top_hosts": top_hosts,
            "message": None,
        },
    )


@router.get("/dashboard-data")
async def get_dashboard_data():
    """JSON endpoint: return all dashboard data for dynamic updates"""
    db = SessionLocal()
    try:
        from .clients import is_client_connected_to_router, is_client_suspended
        all_hosts = db.query(Host).all()
        total_hosts = len(all_hosts)
        hosts_activos = 0
        for host in all_hosts:
            is_susp = is_client_suspended(host.ip_address, host.router)
            is_conn = is_client_connected_to_router(host.ip_address, host.router)
            if is_conn and not is_susp:
                hosts_activos += 1
        hosts_inactivos = total_hosts - hosts_activos

        total_routers = db.query(Router).count()
        routers_activos = db.query(Router).filter(Router.activo.is_(True)).count()
        routers_inactivos = total_routers - routers_activos

        ago_24h = datetime.utcnow() - timedelta(hours=24)
        ago_7d = datetime.utcnow() - timedelta(days=7)

        total_24h_download = db.query(func.coalesce(func.sum(RegistroTrafico.bytes_descarga), 0)).filter(
            RegistroTrafico.timestamp >= ago_24h
        ).scalar() or 0
        total_24h_upload = db.query(func.coalesce(func.sum(RegistroTrafico.bytes_subida), 0)).filter(
            RegistroTrafico.timestamp >= ago_24h
        ).scalar() or 0

        total_7d_download = db.query(func.coalesce(func.sum(RegistroTrafico.bytes_descarga), 0)).filter(
            RegistroTrafico.timestamp >= ago_7d
        ).scalar() or 0
        total_7d_upload = db.query(func.coalesce(func.sum(RegistroTrafico.bytes_subida), 0)).filter(
            RegistroTrafico.timestamp >= ago_7d
        ).scalar() or 0
        
        # Overall totals (all time)
        total_all_download = db.query(func.coalesce(func.sum(RegistroTrafico.bytes_descarga), 0)).scalar() or 0
        total_all_upload = db.query(func.coalesce(func.sum(RegistroTrafico.bytes_subida), 0)).scalar() or 0

        total_traffic_expr = (func.sum(RegistroTrafico.bytes_descarga) + func.sum(RegistroTrafico.bytes_subida)).label("total")
        top_hosts_query = (
            db.query(
                Host.nombre,
                func.coalesce(func.sum(RegistroTrafico.bytes_descarga), 0).label("descarga"),
                func.coalesce(func.sum(RegistroTrafico.bytes_subida), 0).label("subida"),
                total_traffic_expr,
            )
            .join(RegistroTrafico, RegistroTrafico.host_id == Host.id)
            .filter(RegistroTrafico.timestamp >= ago_7d)
            .group_by(Host.id)
            .order_by(total_traffic_expr.desc())
            .limit(5)
            .all()
        )

        top_hosts = [
            {
                "nombre": row.nombre,
                "descarga": int(row.descarga or 0),
                "subida": int(row.subida or 0),
                "total": int(row.total or 0),
            }
            for row in top_hosts_query
        ]

        return JSONResponse({
            "total_hosts": total_hosts,
            "hosts_activos": hosts_activos,
            "hosts_inactivos": hosts_inactivos,
            "total_routers": total_routers,
            "routers_activos": routers_activos,
            "routers_inactivos": routers_inactivos,
            "total_24h_descarga": total_24h_download,
            "total_24h_subida": total_24h_upload,
            "total_7d_descarga": total_7d_download,
            "total_7d_subida": total_7d_upload,
            "total_all_descarga": total_all_download,
            "total_all_subida": total_all_upload,
            "top_hosts": top_hosts,
        })
    finally:
        db.close()


@router.get("/clients", response_class=HTMLResponse)
async def view_clients(request: Request, sort_by: str = "ip", order: str = "asc", period: str = "daily"):
    """HTMX fragment: clients table with sorting and time period filtering"""
    from sqlalchemy import func, desc, asc
    from .clients import is_client_connected_to_router, is_client_suspended
    
    db = SessionLocal()
    clients_db = db.query(Host).all()
    
    # Determine start date according to period
    now = datetime.utcnow()
    if period == "1h":
        start_date = now - timedelta(hours=1)
    elif period == "12h":
        start_date = now - timedelta(hours=12)
    elif period == "daily":
        start_date = now - timedelta(days=1)
    elif period == "weekly":
        start_date = now - timedelta(days=7)
    elif period == "monthly":
        start_date = now - timedelta(days=30)
    elif period == "yearly":
        start_date = now - timedelta(days=365)
    else:
        start_date = now - timedelta(days=1)  # default daily
    
    # Calculate consumption per client in the period
    clients_with_consumption = []
    for client in clients_db:
        consumption = db.query(
            func.sum(RegistroTrafico.bytes_descarga).label('total_descarga'),
            func.sum(RegistroTrafico.bytes_subida).label('total_subida')
        ).filter(
            RegistroTrafico.host_id == client.id,
            RegistroTrafico.timestamp >= start_date
        ).first()
        
        total_download = consumption.total_descarga or 0
        total_upload = consumption.total_subida or 0
        
        # Check connection and suspension status
        suspended = is_client_suspended(client.ip_address, client.router)
        connected = is_client_connected_to_router(client.ip_address, client.router)
        
        if suspended:
            estado_real = "suspendido"
        elif connected:
            estado_real = "conectado"
        else:
            estado_real = "desconectado"
        
        clients_with_consumption.append({
            'id': client.id,
            'nombre': client.nombre,
            'ip_address': client.ip_address,
            'activo': client.activo,
            'estado_real': estado_real,
            'descarga': total_download,
            'subida': total_upload,
            'total': total_download + total_upload,
            'router_nombre': client.router.nombre if client.router else 'N/A'
        })
    
    # Apply sorting
    reverse = order == "desc"
    
    if sort_by == "nombre":
        clients_with_consumption.sort(key=lambda x: x['nombre'].lower(), reverse=reverse)
    elif sort_by == "ip":
        import ipaddress
        def ip_sort_key(x):
            ip_str = x['ip_address']
            try:
                return (0, ipaddress.ip_address(ip_str))
            except Exception:
                return (1, ip_str)
        clients_with_consumption.sort(key=ip_sort_key, reverse=reverse)
    elif sort_by == "estado":
        status_order = {"conectado": 2, "desconectado": 1, "suspendido": 0}
        clients_with_consumption.sort(key=lambda x: status_order.get(x['estado_real'], 0), reverse=reverse)
    elif sort_by == "router":
        clients_with_consumption.sort(key=lambda x: x['router_nombre'].lower(), reverse=reverse)
    elif sort_by == "descarga":
        clients_with_consumption.sort(key=lambda x: x['descarga'], reverse=reverse)
    elif sort_by == "subida":
        clients_with_consumption.sort(key=lambda x: x['subida'], reverse=reverse)
    elif sort_by == "total":
        clients_with_consumption.sort(key=lambda x: x['total'], reverse=reverse)
    
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
            "period_label": period_labels.get(period, "Últimos 30 días"),
            "total_hosts": total_hosts,
            "hosts_activos": hosts_activos,
            "hosts_inactivos": hosts_inactivos,
            "total_period_descarga": total_period_download,
            "total_period_subida": total_period_upload,
        }
    )


@router.get("/add_config", response_class=HTMLResponse)
async def view_add_config(request: Request):
    """HTMX fragment: add host modal form"""
    from ..models import Router
    db = SessionLocal()
    try:
        routers = db.query(Router).all()
        return templates.TemplateResponse(request, "modals/add_client.html", {"routers": routers})
    finally:
        db.close()


@router.get("/add_client", response_class=HTMLResponse)
async def view_add_client(request: Request):
    """HTMX fragment: add client modal form (manual)"""
    from ..models import Router
    db = SessionLocal()
    try:
        routers = db.query(Router).all()
        return templates.TemplateResponse(request, "modals/add_client.html", {"routers": routers})
    finally:
        db.close()


@router.get("/add_clients", response_class=HTMLResponse)
async def view_add_clients(request: Request):
    """HTMX fragment: add client from list or queue modal"""
    from ..models import Router
    db = SessionLocal()
    try:
        routers = db.query(Router).all()
        return templates.TemplateResponse(
            request,
            "modals/add_clients.html",
            {"routers": routers}
        )
    finally:
        db.close()


@router.get("/add_router", response_class=HTMLResponse)
async def view_add_router(request: Request):
    """HTMX fragment: add router modal form"""
    return templates.TemplateResponse(request, "modals/add_router.html")


@router.get("/edit_router/{router_id}", response_class=HTMLResponse)
async def view_edit_router(request: Request, router_id: int):
    """HTMX fragment: edit router modal form"""
    from ..models import Router
    db = SessionLocal()
    try:
        router_obj = db.query(Router).filter(Router.id == router_id).first()
        return templates.TemplateResponse(request, "modals/edit_router.html", {"router": router_obj})
    finally:
        db.close()


@router.get("/existing-ips")
async def get_existing_ips():
    """API: Get all existing IPs in the system"""
    try:
        db = SessionLocal()
        hosts = db.query(Host).all()
        ips = [host.ip_address for host in hosts]
        db.close()
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "ips": ips
            }
        )
    except Exception as e:
        logger.error(f"Error al obtener IPs existentes: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(e)
            }
        )


def get_routers_with_stats(db):
    """Query routers and calculate host counts and traffic statistics for each"""
    from sqlalchemy import func
    from ..models import Router, Host, RegistroTrafico
    
    routers = db.query(Router).all()
    for router in routers:
        router.total_clientes = len(router.hosts)
        router.activos = sum(1 for h in router.hosts if h.activo)
        router.inactivos = router.total_clientes - router.activos
        
        # Calculate sums for upload and download for all hosts belonging to this router
        host_ids = [h.id for h in router.hosts]
        if host_ids:
            stats = db.query(
                func.coalesce(func.sum(RegistroTrafico.bytes_descarga), 0).label('descarga'),
                func.coalesce(func.sum(RegistroTrafico.bytes_subida), 0).label('subida')
            ).filter(RegistroTrafico.host_id.in_(host_ids)).first()
            router.total_descarga = stats.descarga or 0
            router.total_subida = stats.subida or 0
        else:
            router.total_descarga = 0
            router.total_subida = 0
            
    return routers


@router.get("/router", response_class=HTMLResponse)
async def view_router(request: Request):
    """HTMX fragment: configuration form"""
    db = SessionLocal()
    try:
        routers = get_routers_with_stats(db)
        return templates.TemplateResponse(
            request,
            "router.html",
            {
                "routers": routers,
                "message": None,
            },
        )
    finally:
        db.close()


@router.get("/address-lists", response_class=HTMLResponse)
async def view_address_lists(request: Request, router_id: int = None):
    """HTMX fragment: Address Lists from MikroTik"""
    from ..models import Router
    db = SessionLocal()
    try:
        routers = db.query(Router).all()
        if not routers:
            return templates.TemplateResponse(
                request,
                "address_lists.html",
                {
                    "address_lists": [],
                    "total_lists": 0,
                    "total_addresses": 0,
                    "routers": [],
                    "selected_router_id": None,
                    "error": "No hay routers configurados. Ve a la sección de Routers para registrar uno."
                }
            )
            
        selected_router = None
        if router_id:
            selected_router = db.query(Router).filter(Router.id == router_id).first()
        if not selected_router:
            selected_router = routers[0]
            
        logger.info(f"Fetching Address Lists from MikroTik {selected_router.nombre} ({selected_router.ip_address})...")
        
        connection = routeros_api.RouterOsApiPool(
            selected_router.ip_address,
            username=selected_router.usuario,
            password=selected_router.password,
            plaintext_login=True,
        )
        api = connection.get_api()
        
        # Get all address lists
        address_lists_resource = api.get_resource('/ip/firewall/address-list')
        address_lists = address_lists_resource.get()
        
        connection.disconnect()
        
        logger.info(f"Retrieved {len(address_lists)} address lists")
        
        # Group addresses by list
        lists_dict = {}
        for addr in address_lists:
            list_name = addr.get('list', 'unknown')
            address = addr.get('address', 'N/A')
            disabled = addr.get('disabled', False)
            if isinstance(disabled, str):
                disabled = disabled.lower() == 'true'
            comment = addr.get('comment', '')
            
            if list_name not in lists_dict:
                lists_dict[list_name] = {
                    'name': list_name,
                    'addresses': []
                }
            
            lists_dict[list_name]['addresses'].append({
                'id': addr.get('id'),
                'address': address,
                'disabled': disabled,
                'comment': comment
            })
        
        # Sort addresses within each list numerically by IP address
        import ipaddress
        
        def get_ip_sort_key(addr_dict):
            addr_str = addr_dict.get('address', '')
            try:
                return (0, ipaddress.ip_network(addr_str, strict=False))
            except Exception:
                return (1, addr_str)
                
        for list_data in lists_dict.values():
            list_data['addresses'] = sorted(list_data['addresses'], key=get_ip_sort_key)
            
        # Convert to list and sort by name
        lists_display = sorted(lists_dict.values(), key=lambda x: x['name'])
        
        return templates.TemplateResponse(
            request,
            "address_lists.html",
            {
                "address_lists": lists_display,
                "total_lists": len(lists_dict),
                "total_addresses": len(address_lists),
                "routers": routers,
                "selected_router_id": selected_router.id,
                "connected": True,
                "error": None
            }
        )
        
    except Exception as e:
        logger.error(f"Error fetching address lists: {type(e).__name__}: {str(e)}")
        # Fallback for displaying error but preserving dropdown context
        fallback_router_id = selected_router.id if 'selected_router' in locals() and selected_router else None
        return templates.TemplateResponse(
            request,
            "address_lists.html",
            {
                "address_lists": [],
                "total_lists": 0,
                "total_addresses": 0,
                "routers": routers if 'routers' in locals() else [],
                "selected_router_id": fallback_router_id,
                "connected": False,
                "error": f"Error al conectar con el router: {str(e)}"
            }
        )
    finally:
        db.close()


@router.get("/address-lists-summary")
async def get_address_lists_summary(router_id: int = None):
    """API endpoint: Get all address lists with address count and comments for selection"""
    from fastapi.responses import JSONResponse
    from ..models import Router
    db = SessionLocal()
    try:
        router_obj = None
        if router_id:
            router_obj = db.query(Router).filter(Router.id == router_id).first()
        if not router_obj:
            router_obj = db.query(Router).first()
            
        if not router_obj:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": "No hay ningún router configurado.",
                    "lists": [],
                    "total": 0
                }
            )
            
        logger.info(f"Fetching Address Lists summary from {router_obj.nombre} ({router_obj.ip_address})...")
        
        connection = routeros_api.RouterOsApiPool(
            router_obj.ip_address,
            username=router_obj.usuario,
            password=router_obj.password,
            plaintext_login=True,
        )
        api = connection.get_api()
        
        # Get all address lists
        address_lists_resource = api.get_resource('/ip/firewall/address-list')
        address_lists = address_lists_resource.get()
        
        connection.disconnect()
        
        # Group addresses by list and count
        lists_dict = {}
        for addr in address_lists:
            list_name = addr.get('list', 'unknown')
            address = addr.get('address', 'N/A')
            comment = addr.get('comment', '')  # Get comment if available
            
            if list_name not in lists_dict:
                lists_dict[list_name] = {
                    'name': list_name,
                    'addresses': []
                }
            
            # Store address with its comment
            lists_dict[list_name]['addresses'].append({
                'ip': address,
                'comment': comment
            })
        
        # Convert to list with count
        lists_display = [
            {
                'name': list_item['name'],
                'count': len(list_item['addresses']),
                'addresses': list_item['addresses']
            }
            for list_item in lists_dict.values()
        ]
        
        # Sort by name
        lists_display.sort(key=lambda x: x['name'])
        
        logger.info(f"Retrieved {len(lists_display)} address lists")
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "lists": lists_display,
                "total": len(lists_display)
            }
        )
        
    except Exception as e:
        logger.error(f"Error fetching address lists summary: {type(e).__name__}: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": f"Error al obtener listas: {str(e)}",
                "lists": [],
                "total": 0
            }
        )
    finally:
        db.close()


@router.get("/queues-summary")
async def get_queues_summary(router_id: int = None):
    """API endpoint: Get all simple queues as a list of IPs and names grouped hierarchically for selection"""
    from fastapi.responses import JSONResponse
    from ..models import Router
    import routeros_api
    db = SessionLocal()
    try:
        router_obj = None
        if router_id:
            router_obj = db.query(Router).filter(Router.id == router_id).first()
        if not router_obj:
            router_obj = db.query(Router).first()
            
        if not router_obj:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": "No hay ningún router configurado.",
                    "lists": [],
                    "total": 0
                }
            )
            
        logger.info(f"Fetching Simple Queues from {router_obj.nombre} ({router_obj.ip_address})...")
        
        connection = routeros_api.RouterOsApiPool(
            router_obj.ip_address,
            username=router_obj.usuario,
            password=router_obj.password,
            plaintext_login=True,
        )
        api = connection.get_api()
        list_queues = api.get_resource('/queue/simple')
        queues = list_queues.get()
        connection.disconnect()
        
        # Identify parent queues
        parent_names = set(q.get('parent') for q in queues if q.get('parent') and q.get('parent') != 'none')
        
        parents_dict = {}
        independent_queues = []
        
        for q in queues:
            target = q.get('target', '')
            if not target:
                continue
            
            targets = [t.strip() for t in target.split(',')]
            for t in targets:
                ip = t.split('/')[0] if '/' in t else t
                if ip and any(char.isdigit() for char in ip):
                    name = q.get('name', '')
                    comment = q.get('comment', '')
                    display_comment = f"{name} - {comment}" if comment else name
                    item = {
                        'ip': ip,
                        'comment': display_comment
                    }
                    
                    parent_name = q.get('parent')
                    if parent_name and parent_name != 'none':
                        if parent_name not in parents_dict:
                            parents_dict[parent_name] = []
                        parents_dict[parent_name].append(item)
                    else:
                        if name in parent_names:
                            if name not in parents_dict:
                                parents_dict[name] = []
                            parents_dict[name].append(item)
                        else:
                            independent_queues.append(item)
                            
        # Build lists_display format (similar to address lists)
        lists_display = []
        
        # Sort parents and add to display list
        for parent_key in sorted(parents_dict.keys()):
            children = parents_dict[parent_key]
            # Remove duplicates if any (same IP under same parent)
            seen_ips = set()
            unique_children = []
            for child in children:
                if child['ip'] not in seen_ips:
                    seen_ips.add(child['ip'])
                    unique_children.append(child)
            
            if unique_children:
                lists_display.append({
                    'name': f"Cola Padre: {parent_key}",
                    'count': len(unique_children),
                    'addresses': unique_children
                })
                
        # Add independent queues if any
        if independent_queues:
            seen_ips = set()
            unique_ind = []
            for item in independent_queues:
                if item['ip'] not in seen_ips:
                    seen_ips.add(item['ip'])
                    unique_ind.append(item)
            
            if unique_ind:
                lists_display.append({
                    'name': "Colas Independientes",
                    'count': len(unique_ind),
                    'addresses': unique_ind
                })
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "lists": lists_display,
                "total": len(lists_display)
            }
        )
    except Exception as e:
        logger.error(f"Error fetching queues summary: {type(e).__name__}: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": f"Error al conectar con el router: {str(e)}",
                "lists": [],
                "total": 0
            }
        )
    finally:
        db.close()


@router.get("/edit_address_list_entry", response_class=HTMLResponse)
async def view_edit_address_list_entry(
    request: Request,
    router_id: int,
    entry_id: str,
    list_name: str,
    address: str,
    disabled: str = "false",
    comment: str = ""
):
    """HTMX fragment: edit address list entry modal form"""
    is_disabled = disabled.lower() == "true"
    return templates.TemplateResponse(
        request,
        "modals/edit_address_list_entry.html",
        {
            "router_id": router_id,
            "entry_id": entry_id,
            "list_name": list_name,
            "address": address,
            "comment": comment,
            "disabled": is_disabled,
            "error": None
        }
    )


@router.put("/address-list-entry", response_class=HTMLResponse)
async def update_address_list_entry(
    request: Request,
    router_id: int = Form(...),
    entry_id: str = Form(...),
    list_name: str = Form(...),
    address: str = Form(...),
    comment: str = Form(""),
    active: str = Form(None),
):
    """Update address list entry in MikroTik firewall"""
    from ..models import Router
    db = SessionLocal()
    try:
        router_obj = db.query(Router).filter(Router.id == router_id).first()
        if not router_obj:
            raise ValueError("Router no encontrado")
            
        connection = routeros_api.RouterOsApiPool(
            router_obj.ip_address.strip(),
            username=router_obj.usuario.strip(),
            password=router_obj.password,
            plaintext_login=True,
        )
        api = connection.get_api()
        address_lists_resource = api.get_resource('/ip/firewall/address-list')
        
        # Checkbox "active" is "on" if checked, meaning disabled=False
        disabled_val = 'false' if active == 'on' else 'true'
        
        # Update address list entry by id
        address_lists_resource.set(
            id=entry_id,
            address=address.strip(),
            comment=comment.strip(),
            disabled=disabled_val
        )
        
        connection.disconnect()
        
        # After successful update, reload the address lists view for this router
        return await view_address_lists(request, router_id=router_id)
        
    except Exception as e:
        logger.error(f"Error updating address list entry: {str(e)}")
        # If there's an error, we return the modal template but with an error message
        # We also need to set HTMX headers to retarget to modal-container
        headers = {
            "HX-Retarget": "#modal-container",
            "HX-Reswap": "innerHTML"
        }
        is_disabled = active != 'on'
        return templates.TemplateResponse(
            request,
            "modals/edit_address_list_entry.html",
            {
                "router_id": router_id,
                "entry_id": entry_id,
                "list_name": list_name,
                "address": address,
                "comment": comment,
                "disabled": is_disabled,
                "error": f"Error al actualizar: {str(e)}"
            },
            headers=headers
        )
    finally:
        db.close()


@router.post("/toggle-address-list-entry", response_class=HTMLResponse)
async def toggle_address_list_entry(
    request: Request,
    router_id: int = Form(...),
    entry_id: str = Form(...),
    disabled: bool = Form(...),
):
    """Toggle the disabled state of an address list entry on MikroTik"""
    from ..models import Router
    db = SessionLocal()
    try:
        router_obj = db.query(Router).filter(Router.id == router_id).first()
        if not router_obj:
            raise ValueError("Router no encontrado")
            
        connection = routeros_api.RouterOsApiPool(
            router_obj.ip_address.strip(),
            username=router_obj.usuario.strip(),
            password=router_obj.password,
            plaintext_login=True,
        )
        api = connection.get_api()
        address_lists_resource = api.get_resource('/ip/firewall/address-list')
        
        # Update the disabled attribute in MikroTik
        disabled_str = 'true' if disabled else 'false'
        address_lists_resource.set(
            id=entry_id,
            disabled=disabled_str
        )
        
        connection.disconnect()
        
        # Return the updated status cell HTML for inline swap
        safe_id = entry_id.replace('*', '_')
        next_disabled_val = 'false' if disabled else 'true'
        
        if disabled:
            # Entry is now disabled
            return f"""
            <td class="px-4 sm:px-6 py-3 text-center" id="status-cell-{safe_id}">
                <button hx-post="/api/views/toggle-address-list-entry"
                    hx-vals='{{"router_id": "{router_id}", "entry_id": "{entry_id}", "disabled": {next_disabled_val}}}'
                    hx-target="#status-cell-{safe_id}"
                    hx-swap="outerHTML"
                    class="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-semibold rounded-full bg-red-50 text-red-700 border border-red-200 hover:bg-red-100 transition-all duration-200 shadow-sm"
                    title="Habilitar dirección">
                    <i class="fa-solid fa-circle-xmark text-red-500"></i>
                    <span>Deshabilitada</span>
                </button>
            </td>
            """
        else:
            # Entry is now active
            return f"""
            <td class="px-4 sm:px-6 py-3 text-center" id="status-cell-{safe_id}">
                <button hx-post="/api/views/toggle-address-list-entry"
                    hx-vals='{{"router_id": "{router_id}", "entry_id": "{entry_id}", "disabled": {next_disabled_val}}}'
                    hx-target="#status-cell-{safe_id}"
                    hx-swap="outerHTML"
                    class="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-semibold rounded-full bg-green-50 text-green-700 border border-green-200 hover:bg-green-100 transition-all duration-200 shadow-sm"
                    title="Deshabilitar dirección">
                    <i class="fa-solid fa-circle-check text-green-500"></i>
                    <span>Activa</span>
                </button>
            </td>
            """
            
    except Exception as e:
        logger.error(f"Error toggling address list entry: {str(e)}")
        safe_id = entry_id.replace('*', '_')
        current_disabled_val = 'true' if disabled else 'false'
        badge_class = "bg-red-50 text-red-700 border-red-300" if disabled else "bg-green-50 text-green-700 border-green-300"
        badge_text = "Deshabilitada" if disabled else "Activa"
        badge_icon = "fa-circle-xmark text-red-500" if disabled else "fa-circle-check text-green-500"
        
        return f"""
        <td class="px-4 sm:px-6 py-3 text-center" id="status-cell-{safe_id}">
            <button hx-post="/api/views/toggle-address-list-entry"
                hx-vals='{{"router_id": "{router_id}", "entry_id": "{entry_id}", "disabled": {current_disabled_val}}}'
                hx-target="#status-cell-{safe_id}"
                hx-swap="outerHTML"
                class="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-semibold rounded-full {badge_class} border hover:opacity-90 transition-all duration-200 shadow-sm"
                title="Error: {str(e)}. Clic para reintentar.">
                <i class="fa-solid {badge_icon}"></i>
                <span>{badge_text}</span>
            </button>
        </td>
        """
    finally:
        db.close()


@router.get("/filter_address_lists", response_class=HTMLResponse)
async def view_filter_address_lists(request: Request, router_id: int):
    """HTMX fragment: filter address lists visibility modal checklist"""
    from ..models import Router
    db = SessionLocal()
    try:
        router_obj = db.query(Router).filter(Router.id == router_id).first()
        if not router_obj:
            raise ValueError("Router no encontrado")
            
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
        
        # Group addresses by list to get list names and address count
        lists_dict = {}
        total_addresses = len(address_lists)
        for addr in address_lists:
            list_name = addr.get('list', 'unknown')
            if list_name not in lists_dict:
                lists_dict[list_name] = 0
            lists_dict[list_name] += 1
            
        # Convert to sorted list
        lists_display = sorted([
            {"name": name, "count": count}
            for name, count in lists_dict.items()
        ], key=lambda x: x['name'])
        
        return templates.TemplateResponse(
            request,
            "modals/filter_address_lists.html",
            {
                "lists": lists_display,
                "total_lists": len(lists_display),
                "total_addresses": total_addresses,
                "router_id": router_id
            }
        )
    except Exception as e:
        logger.error(f"Error loading filter lists modal: {str(e)}")
        return HTMLResponse(
            status_code=500,
            content=f"<div class='p-4 text-red-500'>Error al conectar con el router: {str(e)}</div>"
        )
    finally:
        db.close()
