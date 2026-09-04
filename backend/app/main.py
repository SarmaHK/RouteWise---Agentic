"""FastAPI application entrypoint (Workstream A, Phase A1 foundation).

Wires together: configuration, logging, CORS for local frontend dev, the health probe, the
``/api`` router (foundation ``POST /api/route/plan``), and structured error handling matching
the envelope in docs/API_CONTRACTS.md §5. No agent / tool / decision logic is built in A1.

Run locally from the ``backend/`` directory::

    uvicorn app.main:app --reload
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import __version__
from app.api.health import router as health_router
from app.api.router import api_router
from app.config import get_settings
from app.logging_config import configure_logging

logger = logging.getLogger("routewise.backend")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Configure logging on startup; log a NON-secret view only (never the API key)."""
    settings = get_settings()
    configure_logging(settings.log_level)
    logger.info("RouteWise backend starting (phase A1): %s", settings.public_view())
    yield
    logger.info("RouteWise backend shutting down.")


def create_app() -> FastAPI:
    """Application factory. Returns a fully-wired FastAPI app."""
    settings = get_settings()
    app = FastAPI(
        title="RouteWise Agentic API",
        version=__version__,
        description=(
            "Autonomous Multi-Modal Travel & Transit Coordinator for Tourism in Sri Lanka. "
            "Phase A1 foundation: health probe + a foundation POST /api/route/plan stub. "
            "Real planning arrives in A2-A9."
        ),
        lifespan=lifespan,
    )

    # CORS for local frontend development (origins configurable via env).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers: health at the root; application API under /api.
    app.include_router(health_router)
    app.include_router(api_router, prefix="/api")

    @app.get("/", tags=["health"], summary="Service index")
    def root() -> dict[str, str]:
        return {
            "service": "routewise-agentic-backend",
            "phase": "A1-foundation",
            "health": "/health",
            "docs": "/docs",
        }

    _register_error_handlers(app)
    return app


def _register_error_handlers(app: FastAPI) -> None:
    """Map errors to the structured envelope (docs/API_CONTRACTS.md §5)."""

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        return _error_response(
            status_code=exc.status_code,
            code=_code_for_status(exc.status_code),
            message=str(exc.detail),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return _error_response(
            status_code=422,
            code="validation_error",
            message="Request validation failed.",
            details={"errors": jsonable_encoder(exc.errors())},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        # Log server-side; never leak internals to the client.
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return _error_response(
            status_code=500, code="internal_error", message="Unexpected server error."
        )


def _code_for_status(status_code: int) -> str:
    return {
        400: "bad_request",
        404: "not_found",
        422: "unprocessable_entity",
        503: "service_unavailable",
    }.get(status_code, "http_error")


def _error_response(
    status_code: int, code: str, message: str, details: dict | None = None
) -> JSONResponse:
    body = {
        "status": "ERROR",
        "error": {
            "code": code,
            "message": message,
            "details": details,
            "retryable": status_code >= 500,
        },
    }
    return JSONResponse(status_code=status_code, content=body)


# Module-level app for `uvicorn app.main:app`.
app = create_app()
