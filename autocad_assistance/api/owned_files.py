"""Owner-scoped immutable project source and result downloads."""

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, Response

from autocad_assistance.services.project_store import (
    ProjectIntegrityError, ProjectNotFoundError, ProjectStore, ProjectStoreError,
)
from autocad_assistance.services.project_jobs import ProjectJobBridge


def _not_found() -> JSONResponse:
    return JSONResponse(status_code=404, content={"error": {"code": "RESOURCE_NOT_FOUND", "message": "Resource not found"}})


def create_owned_files_router(store: ProjectStore, bridge: ProjectJobBridge | None = None) -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["projects"])

    @router.get("/projects/{project_id}/revisions/{revision_id}/source")
    async def source(project_id: str, revision_id: str, request: Request):
        owner_id = request.scope["geoai.owner_id"]
        try:
            revision = await run_in_threadpool(store.assert_revision_owner, owner_id, revision_id)
            raw = await run_in_threadpool(store.read_source_for, owner_id, project_id, revision_id)
        except ProjectNotFoundError:
            return _not_found()
        except (ProjectIntegrityError, ProjectStoreError):
            return JSONResponse(status_code=422, content={"error": {"code": "SOURCE_UNAVAILABLE", "message": "Source unavailable"}})
        return Response(
            raw, media_type="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="source.{revision.source_format}"',
                     "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
        )

    @router.get("/jobs/{job_id}/result")
    async def result(job_id: str, request: Request):
        owner_id = request.scope["geoai.owner_id"]
        try:
            if bridge is not None:
                await run_in_threadpool(bridge.get, owner_id, job_id)
            raw = await run_in_threadpool(store.read_result_for, owner_id, job_id)
        except ProjectNotFoundError:
            return _not_found()
        except (ProjectIntegrityError, ProjectStoreError):
            return JSONResponse(status_code=422, content={"error": {"code": "RESULT_UNAVAILABLE", "message": "Result unavailable"}})
        return Response(
            raw, media_type="application/dxf",
            headers={"Content-Disposition": 'attachment; filename="drawing.dxf"',
                     "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
        )

    return router
