"""FLOWLAB API application.

Run locally with::

    uvicorn backend.main:app --reload --port 8000
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import HTTPException as StarletteHTTPException
from pydantic import ValidationError

from .api.routes_analysis import router as analysis_router
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
async def lifespan(app: FastAPI):
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
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload_router)
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
    return _error(422, f"{field}: {first.get('msg', 'invalid value')}", "Check the value and try again.")


@app.exception_handler(ValidationError)
async def validation_error(request: Request, exc: ValidationError) -> JSONResponse:
    first = exc.errors()[0] if exc.errors() else {}
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
    return _error(503, str(exc), "The API is still running; processing will resume once the model loads.")


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

if FRONTEND_DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str) -> FileResponse:
        candidate = FRONTEND_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")

