"""Authenticated, read-only metadata readiness report."""

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from autocad_assistance.services.dataset_readiness import (
    DatasetReadinessError, audit_owner,
)
from autocad_assistance.services.project_store import (
    ProjectIntegrityError, ProjectStore, ProjectStoreError,
)


def create_dataset_readiness_router(store: ProjectStore) -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["dataset-readiness"])

    @router.get("/dataset-readiness")
    async def readiness(request: Request):
        try:
            result = await run_in_threadpool(audit_owner, store, request.scope["geoai.owner_id"])
        except (DatasetReadinessError, ProjectIntegrityError, ProjectStoreError):
            return JSONResponse(status_code=422, content={"error": {
                "code": "READINESS_AUDIT_UNAVAILABLE",
                "message": "Archive metadata cannot be audited safely",
            }}, headers={"Cache-Control": "no-store"})
        return JSONResponse(content=result, headers={"Cache-Control": "no-store"})

    return router
