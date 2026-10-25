"""Owner-scoped, immutable user-supplied DXF reference archive."""

from __future__ import annotations

import json
from hashlib import sha256
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Form, Header, Query, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, Response

from autocad_assistance.services.project_store import (
    MAX_REFERENCE_DXF_BYTES, ProjectIntegrityError, ProjectNotFoundError,
    ProjectStore, ProjectStoreError, ReferenceConflictError,
    ResourceQuotaExceededError,
)
from autocad_assistance.services.reference_archive import (
    ReferenceInvalidError, ReferenceLimitError, create_reference,
    list_references, reference_view, validate_metadata,
)


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}},
                        headers={"Cache-Control": "no-store"})


def create_reference_archive_router(store: ProjectStore) -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["reference-archives"])

    @router.post("/reference-archives", status_code=201)
    async def archive_reference(
        request: Request,
        revisionId: Annotated[UUID, Form()],
        metadata: Annotated[str, Form(max_length=16 * 1024)],
        referenceDxf: Annotated[UploadFile, File()],
        idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
    ):
        if len(metadata.encode("utf-8")) > 16 * 1024:
            return _error(413, "REFERENCE_METADATA_TOO_LARGE", "Reference metadata is too large")
        try:
            details = json.loads(metadata)
        except (TypeError, ValueError):
            return _error(422, "REFERENCE_METADATA_INVALID", "Reference metadata is invalid")
        if referenceDxf.content_type not in {"application/dxf", "application/octet-stream"}:
            return _error(422, "REFERENCE_DXF_INVALID", "Reference DXF content type is invalid")
        raw = await referenceDxf.read(MAX_REFERENCE_DXF_BYTES + 1)
        if len(raw) > MAX_REFERENCE_DXF_BYTES:
            return _error(413, "REFERENCE_TOO_LARGE", "Reference DXF exceeds 25 MiB")
        owner_id = request.scope["geoai.owner_id"]
        try:
            existing = await run_in_threadpool(
                store.lookup_reference_for, owner_id, str(revisionId), str(idempotency_key),
                reference_sha256=sha256(raw).hexdigest(),
                metadata=validate_metadata(details),
            )
            if existing is not None:
                return JSONResponse(content=reference_view(existing),
                                    headers={"Cache-Control": "no-store"})
            value = await run_in_threadpool(
                create_reference, store, owner_id, str(revisionId),
                str(idempotency_key), raw, details,
            )
        except ProjectNotFoundError:
            return _error(404, "RESOURCE_NOT_FOUND", "Resource not found")
        except ReferenceConflictError:
            return _error(409, "REFERENCE_CONFLICT", "Idempotency key belongs to another reference")
        except ReferenceLimitError:
            return _error(413, "REFERENCE_TOO_LARGE", "Reference DXF exceeds archive limits")
        except ResourceQuotaExceededError:
            return _error(429, "REFERENCE_LIMIT", "Reference archive limit exceeded")
        except ReferenceInvalidError:
            return _error(422, "REFERENCE_INVALID", "Reference DXF or metadata is invalid")
        except (ProjectIntegrityError, ProjectStoreError):
            return _error(422, "REFERENCE_UNAVAILABLE", "Reference could not be archived")
        return JSONResponse(status_code=201, content=value,
                            headers={"Cache-Control": "no-store"})

    @router.get("/projects/{project_id}/reference-archives")
    async def archive_list(
        project_id: UUID, request: Request,
        page: Annotated[int, Query(ge=1)] = 1,
        pageSize: Annotated[int, Query(ge=1, le=50)] = 20,
    ):
        try:
            value = await run_in_threadpool(
                list_references, store, request.scope["geoai.owner_id"],
                str(project_id), page=page, page_size=pageSize,
            )
        except ProjectNotFoundError:
            return _error(404, "RESOURCE_NOT_FOUND", "Resource not found")
        except (ProjectIntegrityError, ProjectStoreError):
            return _error(422, "REFERENCE_UNAVAILABLE", "Reference archive is unavailable")
        return JSONResponse(content=value, headers={"Cache-Control": "no-store"})

    @router.get("/reference-archives/{entry_id}")
    async def archive_metadata(entry_id: UUID, request: Request):
        try:
            record = await run_in_threadpool(store.get_reference_for,
                                             request.scope["geoai.owner_id"], str(entry_id))
        except ProjectNotFoundError:
            return _error(404, "RESOURCE_NOT_FOUND", "Resource not found")
        except (ProjectIntegrityError, ProjectStoreError):
            return _error(422, "REFERENCE_UNAVAILABLE", "Reference archive is unavailable")
        return JSONResponse(content=reference_view(record), headers={"Cache-Control": "no-store"})

    @router.get("/reference-archives/{entry_id}/dxf")
    async def archive_download(entry_id: UUID, request: Request):
        try:
            raw = await run_in_threadpool(store.read_reference_for,
                                          request.scope["geoai.owner_id"], str(entry_id))
        except ProjectNotFoundError:
            return _error(404, "RESOURCE_NOT_FOUND", "Resource not found")
        except (ProjectIntegrityError, ProjectStoreError):
            return _error(422, "REFERENCE_UNAVAILABLE", "Reference archive is unavailable")
        return Response(raw, media_type="application/dxf", headers={
            "Content-Disposition": 'attachment; filename="reference.dxf"',
            "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
        })

    return router
