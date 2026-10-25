"""Minimal FastAPI application factory.

This module intentionally does not import the Telegram entry point or any
geometry generators.  API adapters can be added here incrementally without
starting polling or performing product work during import.
"""

from pathlib import Path
import tempfile
from typing import Literal

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .middleware import RequestBodyLimitMiddleware
from .auth import create_auth_router, validate_auth_origin
from .owner_guard import OwnerGuardMiddleware
from .owned_files import create_owned_files_router
from .uploads import create_upload_router
from autocad_assistance.services.auth_store import AuthStore
from autocad_assistance.services.project_store import ProjectStore


DEFAULT_MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MULTIPART_OVERHEAD_BYTES = 64 * 1024


class HealthResponse(BaseModel):
    """Stable response contract for the service health endpoint."""

    status: Literal["ok"] = "ok"
    service: str = "autocad-assistance-geo-ai"


def create_app(
    *,
    upload_root: str | Path | None = None,
    max_upload_bytes: int = DEFAULT_MAX_UPLOAD_BYTES,
    max_preview_rows: int = 50,
    auth_root: str | Path | None = None,
    auth_origin: str | None = None,
    project_root: str | Path | None = None,
) -> FastAPI:
    """Create an isolated HTTP application without starting a server."""

    if max_upload_bytes <= 0:
        raise ValueError("max_upload_bytes must be positive")
    if max_preview_rows <= 0:
        raise ValueError("max_preview_rows must be positive")
    if auth_root is not None and auth_origin is None:
        raise ValueError("auth_origin is required when auth_root is configured")
    if auth_root is not None and project_root is None:
        raise ValueError("project_root is required when auth_root is configured")
    if auth_root is not None:
        auth_origin = validate_auth_origin(auth_origin)

    resolved_upload_root = Path(upload_root) if upload_root is not None else (
        Path(tempfile.gettempdir()) / "autocad-assistance-geo-ai" / "uploads"
    )

    app = FastAPI(
        title="AutoCAD Assistance GEO AI",
        version="0.1.0",
    )
    app.state.upload_root = resolved_upload_root
    app.state.max_upload_bytes = max_upload_bytes
    app.state.max_preview_rows = max_preview_rows
    app.state.max_upload_request_bytes = (
        max_upload_bytes + MULTIPART_OVERHEAD_BYTES
    )
    app.add_middleware(
        RequestBodyLimitMiddleware,
        path="/api/v1/uploads",
        max_body_bytes=app.state.max_upload_request_bytes,
    )
    project_store = ProjectStore(project_root) if auth_root is not None else None
    if auth_root is not None:
        identity_store = AuthStore(auth_root)
        app.state.auth_store = identity_store
        app.state.project_store = project_store
        app.add_middleware(
            RequestBodyLimitMiddleware,
            path="/api/v1/auth/login",
            max_body_bytes=4096,
            error_code="AUTH_BODY_TOO_LARGE",
            subject="Authentication request",
        )
        app.include_router(create_auth_router(identity_store, auth_origin))
        app.add_middleware(OwnerGuardMiddleware, store=identity_store, trusted_origin=auth_origin)
        app.include_router(create_owned_files_router(project_store))

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        del request, exc
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Invalid request",
                }
            },
        )

    @app.get("/health", response_model=HealthResponse, tags=["system"])
    async def health() -> HealthResponse:
        return HealthResponse()

    app.include_router(
        create_upload_router(
            upload_root=resolved_upload_root,
            max_upload_bytes=max_upload_bytes,
            max_preview_rows=max_preview_rows,
            project_store=project_store,
        )
    )

    return app
