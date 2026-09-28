"""HTTP routes for FLOWLAB."""

from .routes_analysis import router as analysis_router
from .routes_simulation import router as simulation_router
from .routes_upload import router as upload_router

__all__ = ["analysis_router", "simulation_router", "upload_router"]
