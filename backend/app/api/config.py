"""Routes for configuration management"""

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
import routeros_api
import logging

from ..config import CONFIG, update_config
from .views import format_bytes, get_routers_with_stats

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

# Register custom filters
templates.env.filters['format_bytes'] = format_bytes

router = APIRouter(prefix="", tags=["Configuration"])


@router.post("/router", response_class=HTMLResponse)
async def add_router(
    request: Request,
    nombre: str = Form(...),
    mk_ip: str = Form(...),
    mk_user: str = Form(...),
    mk_pass: str = Form(""),
    intervalo_minutos: int = Form(5),
):
    """Create a new Router connection"""
    from ..models import Router
    from ..database import SessionLocal
    
    db = SessionLocal()
    try:
        new_router = Router(
            nombre=nombre.strip(),
            ip_address=mk_ip.strip(),
            usuario=mk_user.strip(),
            password=mk_pass,
            intervalo_minutos=max(1, min(intervalo_minutos, 1440)),
            activo=True
        )
        db.add(new_router)
        db.commit()
        
        routers = get_routers_with_stats(db)
        return templates.TemplateResponse(
            request,
            "router.html",
            {
                "routers": routers,
                "message": f"Router '{nombre}' agregado exitosamente.",
            },
        )
    except Exception as e:
        db.rollback()
        routers = get_routers_with_stats(db)
        return templates.TemplateResponse(
            request,
            "router.html",
            {
                "routers": routers,
                "error": f"Error al agregar router: {str(e)}",
            },
        )
    finally:
        db.close()


@router.delete("/router/{router_id}", response_class=HTMLResponse)
async def delete_router(request: Request, router_id: int):
    """Delete a Router connection"""
    from ..models import Router
    from ..database import SessionLocal
    
    db = SessionLocal()
    try:
        router_obj = db.query(Router).filter(Router.id == router_id).first()
        if router_obj:
            db.delete(router_obj)
            db.commit()
            
        routers = get_routers_with_stats(db)
        return templates.TemplateResponse(
            request,
            "router.html",
            {
                "routers": routers,
                "message": "Router eliminado exitosamente.",
            },
        )
    except Exception as e:
        db.rollback()
        routers = get_routers_with_stats(db)
        return templates.TemplateResponse(
            request,
            "router.html",
            {
                "routers": routers,
                "error": f"Error al eliminar router: {str(e)}",
            },
        )
    finally:
        db.close()


@router.get("/router/{router_id}/test-connection", response_class=HTMLResponse)
async def test_saved_router_connection(router_id: int):
    """Test connection to an existing router by ID and return HTML status badge for HTMX"""
    from ..models import Router
    from ..database import SessionLocal
    import routeros_api
    
    db = SessionLocal()
    router_obj = db.query(Router).filter(Router.id == router_id).first()
    db.close()
    
    if not router_obj:
        return HTMLResponse(
            content=f"""
            <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-red-50 text-red-700 border border-red-200" title="Router no encontrado">
                <span class="w-1.5 h-1.5 rounded-full bg-red-500"></span>
                Error
            </span>
            """
        )
        
    connection = None
    try:
        connection = routeros_api.RouterOsApiPool(
            router_obj.ip_address.strip(),
            username=router_obj.usuario.strip(),
            password=router_obj.password,
            plaintext_login=True,
        )
        api = connection.get_api()
        identity = api.get_resource('/system/identity')
        result = identity.get()
        connection.disconnect()
        
        device_name = result[0].get('name', 'RouterOS') if result else 'RouterOS'
        tooltip = f"✓ Conectado a {device_name}"
        
        return HTMLResponse(
            content=f"""
            <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-green-50 text-green-700 border border-green-200 cursor-pointer hover:bg-green-100 transition-colors" 
                  hx-get="/api/router/{router_id}/test-connection" hx-target="#status-container-{router_id}" hx-swap="innerHTML"
                  title="{tooltip}">
                <span class="relative flex h-2 w-2">
                    <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                    <span class="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
                </span>
                Online
            </span>
            """
        )
    except Exception as e:
        if connection:
            try:
                connection.disconnect()
            except:
                pass
        error_msg = str(e)
        tooltip = f"✗ Error: {error_msg}"
        return HTMLResponse(
            content=f"""
            <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-red-50 text-red-700 border border-red-200 cursor-pointer hover:bg-red-100 transition-colors" 
                  hx-get="/api/router/{router_id}/test-connection" hx-target="#status-container-{router_id}" hx-swap="innerHTML"
                  title="{tooltip}">
                <span class="relative flex h-2 w-2">
                    <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
                    <span class="relative inline-flex rounded-full h-2 w-2 bg-red-500"></span>
                </span>
                Offline
            </span>
            """
        )


@router.post("/router/{router_id}", response_class=HTMLResponse)
async def update_router(
    request: Request,
    router_id: int,
    nombre: str = Form(...),
    mk_ip: str = Form(...),
    mk_user: str = Form(...),
    mk_pass: str = Form(""),
    intervalo_minutos: int = Form(5),
):
    """Update an existing Router configuration"""
    from ..models import Router
    from ..database import SessionLocal
    
    db = SessionLocal()
    try:
        router_obj = db.query(Router).filter(Router.id == router_id).first()
        if not router_obj:
            routers = get_routers_with_stats(db)
            return templates.TemplateResponse(
                request,
                "router.html",
                {
                    "routers": routers,
                    "error": "Router no encontrado.",
                },
            )
            
        router_obj.nombre = nombre.strip()
        router_obj.ip_address = mk_ip.strip()
        router_obj.usuario = mk_user.strip()
        if mk_pass.strip():
            router_obj.password = mk_pass
        router_obj.intervalo_minutos = max(1, min(intervalo_minutos, 1440))
        db.commit()
        
        routers = get_routers_with_stats(db)
        return templates.TemplateResponse(
            request,
            "router.html",
            {
                "routers": routers,
                "message": f"Router '{nombre}' actualizado exitosamente.",
            },
        )
    except Exception as e:
        db.rollback()
        routers = get_routers_with_stats(db)
        return templates.TemplateResponse(
            request,
            "router.html",
            {
                "routers": routers,
                "error": f"Error al actualizar router: {str(e)}",
            },
        )
    finally:
        db.close()


@router.post("/test-connection")
async def test_connection(
    mk_ip: str = Form(...),
    mk_user: str = Form(...),
    mk_pass: str = Form(""),
):
    """Test connection to MikroTik with provided credentials (used by the modals)"""
    connection = None
    try:
        password = mk_pass
        
        logger.info(f"Attempting to connect to MikroTik at {mk_ip} with user {mk_user}")
        
        connection = routeros_api.RouterOsApiPool(
            mk_ip.strip(),
            username=mk_user.strip(),
            password=password,
            plaintext_login=True,
        )
        api = connection.get_api()
        
        logger.info("API connection established, testing accessibility...")
        
        identity = api.get_resource('/system/identity')
        result = identity.get()
        
        logger.info(f"Successfully retrieved system identity: {result}")
        
        device_name = result[0].get('name', 'RouterOS') if result else 'RouterOS'
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": f"✓ Conexión exitosa a MikroTik: {device_name}"
            }
        )
        
    except routeros_api.exceptions.RouterOsApiConnectionError as e:
        logger.error(f"Connection error: {str(e)}")
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "message": f"✗ Error de conexión: No se pudo conectar a {mk_ip}. Verifica la IP y que MikroTik tenga API habilitada."
            }
        )
    except routeros_api.exceptions.RouterOsApiCommunicationError as e:
        logger.error(f"Communication error: {str(e)}")
        error_msg = str(e).lower()
        
        if "auth" in error_msg or "password" in error_msg or "login" in error_msg:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "message": f"✗ Error de autenticación: Usuario o contraseña incorrectos."
                }
            )
        else:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "message": f"✗ Error de comunicación: {error_msg}. Verifica la configuración."
                }
            )
    except Exception as e:
        logger.error(f"Unexpected error: {type(e).__name__}: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"✗ Error inesperado: {type(e).__name__}: {str(e)}"
            }
        )
    finally:
        if connection:
            try:
                connection.disconnect()
                logger.info("Connection closed")
            except Exception as e:
                logger.error(f"Error closing connection: {str(e)}")


@router.get("/connection-status")
async def connection_status():
    """Get current connection status and combined active devices count"""
    from ..models import Router
    from ..database import SessionLocal
    import routeros_api
    
    db = SessionLocal()
    try:
        active_routers = db.query(Router).filter(Router.activo == True).all()
    finally:
        db.close()
        
    if not active_routers:
        return JSONResponse(
            status_code=200,
            content={
                "connected": False,
                "device_name": "Sin routers",
                "ip": "N/A"
            }
        )
        
    online_count = 0
    total_count = len(active_routers)
    device_names = []
    
    for router in active_routers:
        connection = None
        try:
            connection = routeros_api.RouterOsApiPool(
                router.ip_address.strip(),
                username=router.usuario.strip(),
                password=router.password,
                plaintext_login=True,
            )
            api = connection.get_api()
            identity = api.get_resource('/system/identity')
            result = identity.get()
            device_name = result[0].get('name', 'RouterOS') if result else 'RouterOS'
            device_names.append(device_name)
            online_count += 1
        except Exception as e:
            logger.warning(f"Connection check failed for {router.nombre} during global status check: {str(e)}")
        finally:
            if connection:
                try:
                    connection.disconnect()
                except:
                    pass
                    
    connected = online_count > 0
    if connected:
        names_str = ", ".join(device_names[:2])
        if len(device_names) > 2:
            names_str += "..."
        summary_name = f"{online_count}/{total_count} Online ({names_str})"
    else:
        summary_name = f"0/{total_count} Online"
        
    return JSONResponse(
        status_code=200,
        content={
            "connected": connected,
            "device_name": summary_name,
            "ip": active_routers[0].ip_address if active_routers else "N/A"
        }
    )
