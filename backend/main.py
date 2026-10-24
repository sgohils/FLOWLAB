"""FLOWLAB API application.

Run locally with::

    uvicorn backend.main:app --reload --port 8000
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException as StarletteHTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from .api.routes_analysis import router as analysis_router
from .api.routes_cloud_upload import router as cloud_upload_router
from .api.routes_simulation import router as simulation_router
from .api.routes_upload import router as upload_router
from .api.state import jobs, reconcile_orphans, register_demo
from .config import PROJECT_DIR, settings
from .storage import StorageError
from .vision.detector import DetectorError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
)
logger = logging.getLogger("flowlab")

#: Built frontend (optional - the API works without it).
FRONTEND_DIST = PROJECT_DIR / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    register_demo()
    # Jobs live in memory: anything still marked "processing" in the database
    # describes work that was interrupted by a previous shutdown.
    repaired = reconcile_orphans()
    if repaired:
        logger.warning(
            "%s analysis record(s) were interrupted by a restart and are marked failed.",
            repaired,
        )
    logger.info(
        "FLOWLAB API ready - model=%s classes=%s data=%s",
        settings.model_name,
        ",".join(settings.classes),
        settings.data_dir,
    )
    yield
    jobs.shutdown()


app = FastAPI(
    title="FLOWLAB",
    version="1.0.0",
    description=(
        "Privacy-preserving school traffic digital twin: anonymous vehicle "
        "trajectories, queue measurements, bottleneck maps and scenario simulation."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    # The API has no authentication of any kind, so the browser origin list is
    # the only access boundary there is.  It stays on 127.0.0.1 by design: see
    # ``FLOWLAB_CORS_ORIGINS`` in backend/config.py before changing it.
    allow_origins=list(settings.cors_origins),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload_router)
app.include_router(cloud_upload_router)
app.include_router(analysis_router)
app.include_router(simulation_router)


# --------------------------------------------------------------------------------------
# Error handling: the UI only ever receives a message and a hint, never a traceback.
# --------------------------------------------------------------------------------------


def _error(status_code: int, message: str, hint: str | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"message": message, "hint": hint},
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Every error the client sees uses the same {message, hint} shape."""
    message = exc.detail if isinstance(exc.detail, str) else "The request could not be completed."
    return _error(exc.status_code, message, getattr(exc, "hint", None))


@app.exception_handler(RequestValidationError)
async def request_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Body/query validation: report the offending field, never a traceback."""
    first = exc.errors()[0] if exc.errors() else {}
    field = ".".join(str(part) for part in first.get("loc", ())[1:]) or "request"
    return _error(
        422, f"{field}: {first.get('msg', 'invalid value')}", "Check the value and try again."
    )


@app.exception_handler(ValidationError)
async def validation_error(request: Request, exc: ValidationError) -> JSONResponse:
    first: dict[str, Any] = dict(exc.errors()[0]) if exc.errors() else {}
    field = ".".join(str(part) for part in first.get("loc", ())[1:]) or "request"
    return _error(
        422,
        f"{field}: {first.get('msg', 'invalid value')}",
        "Check the highlighted values and try again.",
    )


@app.exception_handler(StorageError)
async def storage_error(request: Request, exc: StorageError) -> JSONResponse:
    return _error(400, str(exc))


@app.exception_handler(DetectorError)
async def detector_error(request: Request, exc: DetectorError) -> JSONResponse:
    return _error(
        503,
        str(exc),
        "The API is still running; processing will resume once the model loads.",
    )


@app.exception_handler(ValueError)
async def value_error(request: Request, exc: ValueError) -> JSONResponse:
    return _error(400, str(exc) or "The request could not be processed.")


@app.exception_handler(Exception)
async def unhandled_error(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s", request.url.path)
    return _error(
        500,
        "Something went wrong while processing this request.",
        "Check the backend log for the full traceback.",
    )


# --------------------------------------------------------------------------------------
# Optional: serve the built single page app from the same origin.
# --------------------------------------------------------------------------------------

def spa_file(full_path: str) -> Path:
    """Resolve a request path to a file inside :data:`FRONTEND_DIST`.

    The path segment comes straight from the URL, so it is *resolved* and then
    checked for containment before anything is served.  A request for
    ``../../../../etc/passwd`` is not a file the SPA is allowed to hand out:
    it falls back to ``index.html`` exactly like any unknown client-side route.
    Symlinks are resolved too, so an ``assets/`` link pointing outside the build
    directory is refused rather than followed.
    """
    index = FRONTEND_DIST / "index.html"
    if not full_path:
        return index
    try:
        root = FRONTEND_DIST.resolve()
        candidate = (FRONTEND_DIST / full_path).resolve()
    except OSError:  # unreadable path, e.g. a name that is too long on Windows
        return index
    if root not in candidate.parents or not candidate.is_file():
        return index
    return candidate


if FRONTEND_DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str) -> FileResponse:
        return FileResponse(spa_file(full_path))
