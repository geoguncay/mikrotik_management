"""View routes for rendering templates and HTML fragments"""

from datetime import datetime, timedelta
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from sqlalchemy import func
import routeros_api
import logging

from ..database import SessionLocal
from ..models import Host, RegistroTrafico
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
        total_hosts = db.query(Host).count()
        hosts_activos = db.query(Host).filter(Host.activo.is_(True)).count()
        hosts_inactivos = total_hosts - hosts_activos

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
        total_hosts = db.query(Host).count()
        hosts_activos = db.query(Host).filter(Host.activo.is_(True)).count()
        hosts_inactivos = total_hosts - hosts_activos

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
async def view_clients(request: Request, sort_by: str = "nombre", order: str = "asc", period: str = "daily"):
    """HTMX fragment: clients table with sorting and time period filtering"""
    from sqlalchemy import func, desc, asc
    
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
        
        clients_with_consumption.append({
            'id': client.id,
            'nombre': client.nombre,
            'ip_address': client.ip_address,
            'activo': client.activo,
            'descarga': total_download,
            'subida': total_upload,
            'total': total_download + total_upload
        })
    
    # Apply sorting
    reverse = order == "desc"
    
    if sort_by == "nombre":
        clients_with_consumption.sort(key=lambda x: x['nombre'].lower(), reverse=reverse)
    elif sort_by == "ip":
        clients_with_consumption.sort(key=lambda x: x['ip_address'], reverse=reverse)
    elif sort_by == "descarga":
        clients_with_consumption.sort(key=lambda x: x['descarga'], reverse=reverse)
    elif sort_by == "subida":
        clients_with_consumption.sort(key=lambda x: x['subida'], reverse=reverse)
    elif sort_by == "total":
        clients_with_consumption.sort(key=lambda x: x['total'], reverse=reverse)
    
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
            "period_label": period_labels.get(period, "Últimos 30 días"),
            "total_hosts": total_hosts,
            "hosts_activos": hosts_activos,
            "hosts_inactivos": hosts_inactivos,
            "total_period_descarga": total_period_download,
            "total_period_subida": total_period_upload,
        }
    )


@router.get("/modal_add_config", response_class=HTMLResponse)
async def view_modal_add(request: Request):
    """HTMX fragment: add host modal form"""
    return templates.TemplateResponse(request, "modals/modal_add_client.html")


@router.get("/modal_add_client", response_class=HTMLResponse)
async def view_modal_add_client(request: Request):
    """HTMX fragment: add client modal form (manual)"""
    return templates.TemplateResponse(request, "modals/modal_add_client.html")


@router.get("/modal_add_client_from_list", response_class=HTMLResponse)
async def view_modal_add_client_from_list(request: Request):
    """HTMX fragment: add client from list modal"""
    return templates.TemplateResponse(request, "modals/modal_add_client_from_list.html")


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


@router.get("/configuration", response_class=HTMLResponse)
async def view_configuration(request: Request):
    """HTMX fragment: configuration form"""
    from ..config import CONFIG
    
    return templates.TemplateResponse(
        request,
        "config.html",
        {
            "mk_ip": CONFIG["MK_IP"],
            "mk_user": CONFIG["MK_USER"],
            "intervalo_minutos": CONFIG["INTERVALO_MINUTOS"],
            "message": None,
        },
    )


@router.get("/demo", response_class=HTMLResponse)
async def view_demo(request: Request):
    """HTMX fragment: demo data management page"""
    db = SessionLocal()
    
    # Count total clients and demo clients
    total_clients = db.query(Host).count()
    demo_clients_list = db.query(Host).filter(Host.nombre.like("DEMO_%")).all()
    demo_count = len(demo_clients_list)
    records_count = db.query(RegistroTrafico).count()
    
    # Calculate consumption for each demo client
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


@router.get("/address-lists", response_class=HTMLResponse)
async def view_address_lists(request: Request):
    """HTMX fragment: Address Lists from MikroTik"""
    try:
        logger.info("Fetching Address Lists from MikroTik...")
        
        connection = routeros_api.RouterOsApiPool(
            CONFIG["MK_IP"],
            username=CONFIG["MK_USER"],
            password=CONFIG["MK_PASS"],
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
            comment = addr.get('comment', '')
            
            if list_name not in lists_dict:
                lists_dict[list_name] = {
                    'name': list_name,
                    'addresses': []
                }
            
            lists_dict[list_name]['addresses'].append({
                'address': address,
                'disabled': disabled,
                'comment': comment
            })
        
        # Convert to list and sort by name
        lists_display = sorted(lists_dict.values(), key=lambda x: x['name'])
        
        return templates.TemplateResponse(
            request,
            "address_lists.html",
            {
                "address_lists": lists_display,
                "total_lists": len(lists_dict),
                "total_addresses": len(address_lists)
            }
        )
        
    except Exception as e:
        logger.error(f"Error fetching address lists: {type(e).__name__}: {str(e)}")
        return templates.TemplateResponse(
            request,
            "address_lists.html",
            {
                "address_lists": [],
                "total_lists": 0,
                "total_addresses": 0,
                "error": f"Error al conectar con MikroTik: {str(e)}"
            }
        )


@router.get("/address-lists-summary")
async def get_address_lists_summary():
    """API endpoint: Get all address lists with address count and comments for selection"""
    from fastapi.responses import JSONResponse
    try:
        logger.info("Fetching Address Lists summary...")
        
        connection = routeros_api.RouterOsApiPool(
            CONFIG["MK_IP"],
            username=CONFIG["MK_USER"],
            password=CONFIG["MK_PASS"],
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
        logger.error(f"Error fetching address lists: {type(e).__name__}: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": f"Error al obtener listas: {str(e)}",
                "lists": [],
                "total": 0
            }
        )
