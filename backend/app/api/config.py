"""Routes for configuration management"""

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
import routeros_api
import logging

from ..config import CONFIG, update_config
from .views import format_bytes

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


@router.post("/configuration", response_class=HTMLResponse)
async def update_configuration(
    request: Request,
    mk_ip: str = Form(...),
    mk_user: str = Form(...),
    mk_pass: str = Form(""),
    intervalo_minutos: int = Form(...),
):
    """Update MikroTik connection configuration"""
    update_config(
        mk_ip=mk_ip,
        mk_user=mk_user,
        mk_pass=mk_pass,
        intervalo_minutos=intervalo_minutos
    )

    return templates.TemplateResponse(
        request,
        "config.html",
        {
            "mk_ip": CONFIG["MK_IP"],
            "mk_user": CONFIG["MK_USER"],
            "intervalo_minutos": CONFIG["INTERVALO_MINUTOS"],
            "message": "Configuración actualizada en memoria. Para persistirla, usa variables de entorno o un archivo de configuración.",
        },
    )


@router.post("/test-connection")
async def test_connection(
    mk_ip: str = Form(...),
    mk_user: str = Form(...),
    mk_pass: str = Form(""),
):
    """Test connection to MikroTik with provided credentials"""
    connection = None
    try:
        # Use provided password or fall back to current config
        password = mk_pass if mk_pass.strip() else CONFIG["MK_PASS"]
        
        logger.info(f"Attempting to connect to MikroTik at {mk_ip} with user {mk_user}")
        
        connection = routeros_api.RouterOsApiPool(
            mk_ip.strip(),
            username=mk_user.strip(),
            password=password,
            plaintext_login=True,
        )
        api = connection.get_api()
        
        logger.info("API connection established, testing accessibility...")
        
        # Try to get a simple resource to verify connection
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
        
        # Detectar si es error de autenticación
        if "auth" in error_msg or "password" in error_msg or "login" in error_msg:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "message": f"✗ Error de autenticación: Usuario o contraseña incorrectos."
                }
            )
        else:
            # Otro error de comunicación
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
    """Get current MikroTik connection status and device name"""
    connection = None
    try:
        logger.info("Checking MikroTik connection status...")
        
        connection = routeros_api.RouterOsApiPool(
            CONFIG["MK_IP"],
            username=CONFIG["MK_USER"],
            password=CONFIG["MK_PASS"],
            plaintext_login=True,
        )
        api = connection.get_api()
        
        # Get system identity
        identity = api.get_resource('/system/identity')
        result = identity.get()
        
        device_name = result[0].get('name', 'RouterOS') if result else 'RouterOS'
        
        logger.info(f"Connection successful: {device_name}")
        
        return JSONResponse(
            status_code=200,
            content={
                "connected": True,
                "device_name": device_name,
                "ip": CONFIG["MK_IP"]
            }
        )
        
    except Exception as e:
        logger.warning(f"Connection status check failed: {type(e).__name__}")
        return JSONResponse(
            status_code=200,
            content={
                "connected": False,
                "device_name": None,
                "ip": CONFIG["MK_IP"],
                "error": str(e)
            }
        )
    finally:
        if connection:
            try:
                connection.disconnect()
            except Exception as e:
                logger.error(f"Error closing connection: {str(e)}")
