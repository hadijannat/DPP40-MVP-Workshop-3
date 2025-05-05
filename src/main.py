"""
DPP4.0 MVP - Main Application Entry Point.

This module initializes the FastAPI application and sets up routes,
middleware, and dependency injection.
"""
from fastapi import FastAPI, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
import basyx.aas
from basyx.aas.model import DictObjectStore
import os
import pathlib
import logging

from src.api import router as api_router
from src.api.visualization import router as visualization_router
from src.utils.logging import setup_logging, RequestContextMiddleware
from src.core.config import settings
from src.persistence.database import init_db, check_db_connection
from src.web.routes import router as web_router

# Configure logging first
log_level = os.environ.get("LOG_LEVEL", "INFO")
setup_logging(log_level)

logger = logging.getLogger(__name__)
logger.info("Starting DPP40 MVP application")

# Create FastAPI app with the proper configuration for API docs
app = FastAPI(
    title="Digital Product Passport 4.0 MVP",
    description="A demonstration of Digital Product Passports using Asset Administration Shell",
    version="1.0.0",
    # Configure docs URLs - critical for fixing the API docs issues
    docs_url="/api/v1/docs",            # Versioned docs
    redoc_url="/api/v1/redoc",          # Versioned redoc
    openapi_url="/api/v1/openapi.json", # Versioned schema
    # Critical setting to prevent redirects
    redirect_slashes=False,
)

# Add request context middleware for logging
app.middleware("http")(RequestContextMiddleware())

# Create in-memory storage for AAS objects
aas_store = DictObjectStore()
submodel_store = DictObjectStore()

# Get project root directory and static folder path
BASE_DIR = pathlib.Path(__file__).parent.parent.absolute()
STATIC_DIR = BASE_DIR / "static"

# Ensure static directory exists
if not STATIC_DIR.exists():
    STATIC_DIR.mkdir(exist_ok=True)
    # Create placeholder file
    (STATIC_DIR / "placeholder.txt").touch()

logger.info(f"Static directory: {STATIC_DIR}")

# Add docs redirect before including routers
@app.get("/docs", include_in_schema=False)
async def docs_redirect():
    """Redirect /docs to /api/v1/docs for compatibility"""
    logger.info("Redirecting /docs to /api/v1/docs")
    return RedirectResponse(url="/api/v1/docs")

# Health check endpoint - MUST be defined before static mounts
@app.get("/health", tags=["Health"])
async def health_check():
    """Basic health check endpoint - returns system status"""
    db_status = "connected" if check_db_connection() else "disconnected"
    return {
        "status": "ok", 
        "version": app.version,
        "database": db_status
    }

# Include API routes with prefix - MUST BE BEFORE STATIC FILES
app.include_router(
    api_router, 
    prefix="/api/v1/aas",
)
app.include_router(
    visualization_router,
    prefix="/api/v1/aas", # Assuming visualization is part of the AAS API
)

# Include web routes
app.include_router(web_router)

# Mount static files for /static path
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# For direct HTML file access, mount HTML files at root path
# Important: Mount at root with html=True to serve HTML files directly
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="root")

# Handle both with and without trailing slash for consistency
@app.get("/", include_in_schema=False)
@app.get("/index", include_in_schema=False)
async def root():
    """Root endpoint - serve the home page"""
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    else:
        logger.warning("index.html not found, serving default response")
        return {"message": "Welcome to DPP40 MVP API"}

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    """Initialize components on application startup"""
    try:
        # Set environment variable to use SQLite
        os.environ["USE_SQLITE"] = "True"
        init_db()
        logger.info("Database initialized")

        # Log routes
        route_count = len(app.routes)
        logger.info(f"Application initialized with {route_count} routes")
        for route in app.routes:
            if hasattr(route, 'path'):
                methods = getattr(route, 'methods', ['UNKNOWN'])
                logger.debug(f"Route: {route.path} [{','.join(methods)}]")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        logger.warning("Continuing without database initialization. Some features may not work correctly.")
        # Don't raise here to allow app to start even if DB isn't ready

# Run server with uvicorn when called directly
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True) 