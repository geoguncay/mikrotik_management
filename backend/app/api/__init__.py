"""API routers for MikroTik Traffic Counter"""

from fastapi import APIRouter
from .views import router as views_router
from .clients import router as clients_router
from .config import router as config_router
from .demo import router as demo_router
from .traffic import router as traffic_router

# Create main API router
api_router = APIRouter(prefix="/api")

# Include all routers
api_router.include_router(views_router)
api_router.include_router(clients_router)
api_router.include_router(config_router)
api_router.include_router(demo_router)
api_router.include_router(traffic_router)

__all__ = ["api_router"]
