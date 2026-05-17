import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .database import engine, SessionLocal, run_lightweight_migrations
from .models import Base
from .routers import transactions, categories, budgets, cao, dashboard
from .routers.categories import seed_default_categories
from .routers.cao import seed_vgn_scales

Base.metadata.create_all(bind=engine)
run_lightweight_migrations()

app = FastAPI(title="Finance Dashboard", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# All API endpoints live under /api/* so the SPA can own the root.
app.include_router(transactions.router, prefix="/api")
app.include_router(categories.router, prefix="/api")
app.include_router(budgets.router, prefix="/api")
app.include_router(cao.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.on_event("startup")
def on_startup():
    db = SessionLocal()
    try:
        seed_default_categories(db)
        seed_vgn_scales(db)
    finally:
        db.close()


# ─── Serve the built React frontend ────────────────────────────────────────
STATIC_DIR = Path(os.getenv("STATIC_DIR", "/app/static"))

if STATIC_DIR.exists():
    # Mount /assets (Vite's hashed bundles)
    assets_dir = STATIC_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str):
        # Serve real files when they exist (favicon, etc.), otherwise index.html for client-side routing.
        target = STATIC_DIR / full_path
        if full_path and target.is_file():
            return FileResponse(target)
        return FileResponse(STATIC_DIR / "index.html")
