"""Authenticated, owner-scoped local DXF job API."""

from __future__ import annotations

from math import ceil
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Query, Request, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, StringConstraints

from autocad_assistance.services.calculation_jobs import JobCapacityError, JobNotFoundError, JobStateError
from autocad_assistance.services.column_mapping import MappingValidationError
from autocad_assistance.services.project_jobs import ProjectJobBridge
from autocad_assistance.services.project_store import (
    ProjectIntegrityError, ProjectNotFoundError, ProjectStoreError,
    ResourceQuotaExceededError, SubmissionConflictError,
)
from autocad_assistance.services.survey_contract import SurveyContractError
from autocad_assistance.services.survey_parser import SurveyParseError


class TinSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    codes: list[Annotated[str, StringConstraints(min_length=1, max_length=64)]] = Field(
        default_factory=list, max_length=100,
    )
    refine: bool = False
    scale_value: FiniteFloat | None = Field(default=None, gt=0, le=1_000_000_000)


class SubmitJobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revisionId: UUID
    tinSettings: TinSettings = Field(default_factory=TinSettings)


def _error(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"error": {"code": code, "message": message}})


def _view(job) -> dict:
    return {
        "jobId": job.job_id, "revisionId": job.revision_id,
        "status": job.status, "attempt": job.attempt, "retryOf": job.retry_of,
        "errorCode": job.error_code, "resultReady": job.result_ready,
        "createdAt": job.created_at, "updatedAt": job.updated_at,
    }


def _failure(exc: Exception) -> JSONResponse:
    if isinstance(exc, ProjectNotFoundError):
        return _error(404, "RESOURCE_NOT_FOUND", "Resource not found")
    if isinstance(exc, SubmissionConflictError):
        return _error(409, "IDEMPOTENCY_CONFLICT", "Idempotency key belongs to a different request")
    if isinstance(exc, JobCapacityError):
        return _error(429, "JOB_CAPACITY", "Job queue is full")
    if isinstance(exc, ResourceQuotaExceededError):
        return _error(429, "QUOTA_EXCEEDED", "Owner resource quota exceeded")
    if isinstance(exc, JobStateError):
        return _error(409, "JOB_STATE", str(exc))
    if isinstance(exc, SurveyContractError):
        return _error(422, exc.code, exc.message)
    if isinstance(exc, MappingValidationError):
        return _error(422, exc.code, exc.message)
    if isinstance(exc, (ProjectIntegrityError, FileNotFoundError)):
        return _error(422, "SOURCE_UNAVAILABLE", "Source is unavailable")
    if isinstance(exc, (SurveyParseError, ProjectStoreError, ValueError, TypeError)):
        return _error(422, "INVALID_JOB", "Job request is invalid")
    if isinstance(exc, JobNotFoundError):
        return _error(422, "JOB_UNAVAILABLE", "Job coordinator record is unavailable")
    raise exc


def create_job_router(bridge: ProjectJobBridge) -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["jobs"])

    @router.post("/jobs", status_code=status.HTTP_201_CREATED,
                 description="Submit once with a stable client UUID Idempotency-Key; no automatic retry.")
    async def submit(
        request: Request, payload: SubmitJobRequest,
        key: Annotated[UUID, Header(alias="Idempotency-Key")],
    ):
        try:
            job = await run_in_threadpool(
                bridge.submit, request.scope["geoai.owner_id"], str(payload.revisionId),
                str(key), tin_settings=payload.tinSettings.model_dump(),
            )
        except Exception as exc:
            return _failure(exc)
        return _view(job)

    @router.get("/jobs/{job_id}")
    async def get(job_id: UUID, request: Request):
        try:
            job = await run_in_threadpool(bridge.get, request.scope["geoai.owner_id"], str(job_id))
        except Exception as exc:
            return _failure(exc)
        return _view(job)

    @router.post("/jobs/{job_id}/cancel")
    async def cancel(job_id: UUID, request: Request):
        try:
            job = await run_in_threadpool(bridge.cancel, request.scope["geoai.owner_id"], str(job_id))
        except Exception as exc:
            return _failure(exc)
        return _view(job)

    @router.post("/jobs/{job_id}/retry", status_code=status.HTTP_201_CREATED,
                 description="Explicit retry with a new stable UUID Idempotency-Key.")
    async def retry(
        job_id: UUID, request: Request,
        key: Annotated[UUID, Header(alias="Idempotency-Key")],
    ):
        try:
            job = await run_in_threadpool(
                bridge.retry, request.scope["geoai.owner_id"], str(job_id), str(key),
            )
        except Exception as exc:
            return _failure(exc)
        return _view(job)

    @router.get("/projects/{project_id}/jobs")
    async def list_jobs(
        project_id: UUID, request: Request,
        page: Annotated[int, Query(ge=1)] = 1,
        pageSize: Annotated[int, Query(ge=1, le=50)] = 20,
    ):
        owner_id = request.scope["geoai.owner_id"]
        try:
            records = await run_in_threadpool(bridge.store.list_jobs_for, owner_id, str(project_id))
            start = (page - 1) * pageSize
            jobs = []
            for record in records[start:start + pageSize]:
                jobs.append(_view(await run_in_threadpool(bridge.get, owner_id, record.job_id)))
        except Exception as exc:
            return _failure(exc)
        return {
            "data": jobs,
            "pagination": {
                "page": page, "pageSize": pageSize, "totalItems": len(records),
                "totalPages": ceil(len(records) / pageSize),
            },
        }

    return router
