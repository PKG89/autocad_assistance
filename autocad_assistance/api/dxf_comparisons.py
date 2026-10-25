"""Authenticated, read-only comparison of an archived reference and a job DXF."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from autocad_assistance.services.dxf_compare import (
    DxfCompareInvalidError, DxfCompareLimitError, compare_dxf,
)
from autocad_assistance.services.project_store import (
    ProjectIntegrityError, ProjectNotFoundError, ProjectStore,
    ProjectStoreError,
)


def create_dxf_comparison_router(store: ProjectStore) -> APIRouter:
    router = APIRouter(prefix="/api/v1/reference-archives", tags=["dxf-comparisons"])

    @router.get("/{entry_id}/comparisons/{job_id}")
    async def compare(entry_id: UUID, job_id: UUID, request: Request):
        owner_id = request.scope["geoai.owner_id"]
        try:
            archive = await run_in_threadpool(store.get_reference_for, owner_id, str(entry_id))
            job = await run_in_threadpool(store.assert_job_owner, owner_id, str(job_id))
            if job.revision_id != archive.revision_id or job.result_sha256 is None:
                raise ProjectNotFoundError(str(job_id))
            reference_raw = await run_in_threadpool(store.read_reference_for, owner_id, str(entry_id))
            result_raw = await run_in_threadpool(store.read_result_for, owner_id, str(job_id))
        except ProjectNotFoundError:
            return JSONResponse(status_code=404, content={"error": {
                "code": "RESOURCE_NOT_FOUND", "message": "Resource not found",
            }}, headers={"Cache-Control": "no-store"})
        except (ProjectIntegrityError, ProjectStoreError):
            return JSONResponse(status_code=422, content={"error": {
                "code": "DXF_UNAVAILABLE", "message": "DXF input is unavailable",
            }}, headers={"Cache-Control": "no-store"})
        try:
            report = await run_in_threadpool(compare_dxf, reference_raw, result_raw)
        except DxfCompareLimitError:
            return JSONResponse(status_code=413, content={"error": {
                "code": "DXF_COMPARISON_LIMIT", "message": "DXF exceeds comparison limits",
            }}, headers={"Cache-Control": "no-store"})
        except DxfCompareInvalidError:
            return JSONResponse(status_code=422, content={"error": {
                "code": "DXF_COMPARISON_INVALID", "message": "DXF cannot be compared",
            }}, headers={"Cache-Control": "no-store"})
        report.update({
            "referenceEntryId": archive.entry_id, "jobId": job.job_id,
            "revisionId": archive.revision_id, "sourceSha256": archive.source_sha256,
            "referenceSha256": archive.reference_sha256,
            "resultSha256": job.result_sha256,
            "algorithmVersion": job.algorithm_version,
        })
        return JSONResponse(content=report, headers={"Cache-Control": "no-store"})

    return router
