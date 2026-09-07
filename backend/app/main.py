from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.auth import router as auth_router
from app.api.scans import router as scans_router
from app.api.sessions import router as sessions_router
from app.core.config import settings

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "LabelBox — Compliance checking system for packaged commodities "
        "under the Legal Metrology (Packaged Commodities) Rules, 2011"
    ),
)

# CORS — allow the frontend origin (same-origin in production, but useful for dev)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routers
app.include_router(auth_router)
app.include_router(sessions_router)
app.include_router(scans_router)

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok", "app": settings.app_name, "version": settings.app_version}


# Static files — CSS, JS, manifest, service worker
if FRONTEND_DIR.is_dir():
    # Service worker must be served from root for scope
    @app.get("/sw.js")
    async def service_worker():
        return FileResponse(FRONTEND_DIR / "sw.js", media_type="application/javascript")

    @app.get("/manifest.json")
    async def manifest():
        return FileResponse(FRONTEND_DIR / "manifest.json", media_type="application/json")

    app.mount("/css", StaticFiles(directory=str(FRONTEND_DIR / "css")), name="css")
    app.mount("/js", StaticFiles(directory=str(FRONTEND_DIR / "js")), name="js")
    app.mount("/icons", StaticFiles(directory=str(FRONTEND_DIR / "icons")), name="icons")

    # Catch-all: serve index.html for SPA routing
    @app.get("/{full_path:path}")
    async def serve_frontend(request: Request, full_path: str):
        # Don't intercept API doc routes
        if full_path in ("docs", "redoc", "openapi.json"):
            return None
        file_path = FRONTEND_DIR / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(FRONTEND_DIR / "index.html")
