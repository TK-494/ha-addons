"""Financials — FastAPI application.

One container: this app serves both the JSON API under `/api` and the built
React SPA at the root. There is deliberately **no CORS middleware** — the SPA
and the API are same-origin under both HA Ingress and standalone Docker, so
any CORS configuration would only widen the attack surface.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import config
from .database import Base, SessionLocal, apply_migrations, engine
from .parsers import ParseError
from .routers import accounts, categories, imports, settings, transactions
from .security import contained_path, mask_iban, security_headers_middleware
from .services.categorize import seed_defaults


class RedactingFormatter(logging.Formatter):
    """Add-on logs are visible in the HA UI and get attached to diagnostics,
    so account numbers must never reach them."""

    def format(self, record: logging.LogRecord) -> str:
        return mask_iban(super().format(record))


def _configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(RedactingFormatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)


_configure_logging()
log = logging.getLogger("financials")

Base.metadata.create_all(bind=engine)
apply_migrations()
config.ensure_dirs()

@asynccontextmanager
async def lifespan(_app: FastAPI):
    db = SessionLocal()
    try:
        seed_defaults(db)
    finally:
        db.close()
    log.info("%s %s gestart", config.APP_NAME, config.APP_VERSION)
    yield


app = FastAPI(
    title=config.APP_NAME,
    version=config.APP_VERSION,
    docs_url=None,      # no interactive docs in a household app
    redoc_url=None,
    openapi_url=None,
    lifespan=lifespan,
)

app.middleware("http")(security_headers_middleware)

app.include_router(imports.router, prefix="/api")
app.include_router(accounts.router, prefix="/api")
app.include_router(transactions.router, prefix="/api")
app.include_router(categories.router, prefix="/api")
app.include_router(settings.router, prefix="/api")


@app.exception_handler(ParseError)
async def parse_error_handler(_request, exc: ParseError):
    """A format mismatch is a 422 with the reason spelled out, never a silent
    fallback to a parser that produces zeroes."""
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.get("/api/health")
def health():
    return {"status": "ok", "version": config.APP_VERSION}


# ─── static SPA ─────────────────────────────────────────────────────────────

if config.STATIC_DIR.exists():
    assets = config.STATIC_DIR / "assets"
    if assets.exists():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    _INDEX = config.STATIC_DIR / "index.html"

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str):
        """Serve a real file when one exists, otherwise the SPA shell.

        Every candidate goes through `contained_path`: without it, a request
        for `..%2F..%2Fdata%2Ffinancials.db` escapes the static root and the
        server hands over the database.
        """
        if full_path:
            candidate = contained_path(config.STATIC_DIR, full_path)
            if candidate is not None and candidate.is_file():
                return FileResponse(candidate)
        return FileResponse(_INDEX)
