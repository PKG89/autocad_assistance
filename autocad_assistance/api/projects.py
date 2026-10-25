"""Owner-scoped projects and immutable mapped survey revisions."""

from __future__ import annotations

import csv
from math import ceil
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Request, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from autocad_assistance.services.column_mapping import MappingValidationError
from autocad_assistance.services.project_store import (
    ProjectIntegrityError, ProjectNotFoundError, ProjectStore,
    ProjectStoreError, ResourceQuotaExceededError,
)
from autocad_assistance.services.survey_contract import (
    SurveyContext, SurveyContractError, build_survey_dataset,
)
from autocad_assistance.services.survey_parser import SurveyParseError
from autocad_assistance.services.uploads import UploadTooLargeError
from autocad_assistance.services.line_candidates import (
    LineCandidateInvalidError, LineCandidateLimitError, build_line_candidates,
)


ALGORITHM_VERSION = "geoai-dxf-v1"


class CreateProjectRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class ProjectResponse(BaseModel):
    projectId: str
    name: str
    createdAt: str


class RevisionResponse(BaseModel):
    revisionId: str
    projectId: str
    sequence: int
    parentRevisionId: str | None
    sourceFormat: str
    sourceSha256: str
    sourceSize: int
    algorithmVersion: str
    createdAt: str


class Pagination(BaseModel):
    page: int
    pageSize: int
    totalItems: int
    totalPages: int


class ProjectPage(BaseModel):
    data: list[ProjectResponse]
    pagination: Pagination


class RevisionPage(BaseModel):
    data: list[RevisionResponse]
    pagination: Pagination


class ImportSurveyRequest(BaseModel):
    uploadId: UUID
    mapping: dict[str, object]
    coordinateSystem: str | None = Field(default=None, max_length=128)
    horizontalUnit: str | None = Field(default=None, max_length=64)
    verticalUnit: str | None = Field(default=None, max_length=64)
    scaleFactor: str = Field(min_length=1, max_length=64)


class ImportWarning(BaseModel):
    code: str
    message: str
    rowIndex: int | None


class ImportResponse(BaseModel):
    revision: RevisionResponse
    rowCount: int
    warnings: list[ImportWarning]


def _error(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"error": {"code": code, "message": message}})


def _project(record) -> ProjectResponse:
    return ProjectResponse(projectId=record.project_id, name=record.name, createdAt=record.created_at)


def _revision(record) -> RevisionResponse:
    return RevisionResponse(
        revisionId=record.revision_id, projectId=record.project_id,
        sequence=record.sequence, parentRevisionId=record.parent_revision_id,
        sourceFormat=record.source_format, sourceSha256=record.source_sha256,
        sourceSize=record.source_size, algorithmVersion=record.algorithm_version,
        createdAt=record.created_at,
    )


def _page(records, page: int, page_size: int, serializer) -> dict:
    total = len(records)
    start = (page - 1) * page_size
    return {
        "data": [serializer(record).model_dump() for record in records[start:start + page_size]],
        "pagination": {
            "page": page, "pageSize": page_size, "totalItems": total,
            "totalPages": ceil(total / page_size),
        },
    }


def create_project_router(store: ProjectStore, upload_root: str | Path) -> APIRouter:
    router = APIRouter(prefix="/api/v1/projects", tags=["projects"])

    @router.get("", response_model=ProjectPage)
    async def list_projects(
        request: Request, page: Annotated[int, Query(ge=1)] = 1,
        pageSize: Annotated[int, Query(ge=1, le=50)] = 20,
    ):
        records = await run_in_threadpool(store.list_projects_for, request.scope["geoai.owner_id"])
        return _page(records, page, pageSize, _project)

    @router.post("", status_code=status.HTTP_201_CREATED, response_model=ProjectResponse,
                 description="Creates a new project; do not retry a successful request.")
    async def create_project(request: Request, payload: CreateProjectRequest):
        try:
            record = await run_in_threadpool(
                store.create_owned_project, request.scope["geoai.owner_id"], payload.name,
            )
        except ResourceQuotaExceededError:
            return _error(429, "QUOTA_EXCEEDED", "Owner resource quota exceeded")
        except ProjectStoreError:
            return _error(422, "INVALID_PROJECT", "Project name is invalid")
        return _project(record)

    @router.get("/{project_id}/revisions", response_model=RevisionPage)
    async def list_revisions(
        project_id: UUID, request: Request,
        page: Annotated[int, Query(ge=1)] = 1,
        pageSize: Annotated[int, Query(ge=1, le=50)] = 20,
    ):
        try:
            records = await run_in_threadpool(
                store.list_revisions_for, request.scope["geoai.owner_id"], str(project_id),
            )
        except ProjectNotFoundError:
            return _error(404, "RESOURCE_NOT_FOUND", "Resource not found")
        return _page(tuple(reversed(records)), page, pageSize, _revision)

    @router.post("/{project_id}/revisions", status_code=status.HTTP_201_CREATED,
                 response_model=ImportResponse,
                 description="Imports a mapped survey as a new immutable revision; no automatic retry.")
    async def import_survey(project_id: UUID, request: Request, payload: ImportSurveyRequest):
        owner_id = request.scope["geoai.owner_id"]
        try:
            await run_in_threadpool(store.assert_project_owner, owner_id, str(project_id))
            raw, source_format = await run_in_threadpool(
                store.read_upload_for, owner_id, upload_root, str(payload.uploadId),
            )
        except ProjectNotFoundError:
            return _error(404, "RESOURCE_NOT_FOUND", "Resource not found")
        except FileNotFoundError:
            return _error(404, "RESOURCE_NOT_FOUND", "Resource not found")
        except (ProjectIntegrityError, UploadTooLargeError):
            return _error(422, "SOURCE_UNAVAILABLE", "Source is unavailable")
        if source_format not in {"txt", "csv"}:
            return _error(422, "UNSUPPORTED_IMPORT_FORMAT", "Mapped survey import supports TXT and CSV")
        try:
            context = SurveyContext(
                coordinate_system=payload.coordinateSystem,
                horizontal_unit=payload.horizontalUnit,
                vertical_unit=payload.verticalUnit,
                scale_factor=payload.scaleFactor,
            )
            dataset = await run_in_threadpool(
                build_survey_dataset, raw, payload.mapping, context=context,
            )
            revision = await run_in_threadpool(
                store.add_revision_for, owner_id, str(project_id), upload_root,
                str(payload.uploadId), context=context,
                settings={"mapping": payload.mapping}, algorithm_version=ALGORITHM_VERSION,
            )
        except MappingValidationError as exc:
            return _error(422, exc.code, exc.message)
        except SurveyContractError as exc:
            return _error(422, exc.code, exc.message)
        except (SurveyParseError, csv.Error):
            return _error(422, "INVALID_SURVEY", "Survey data cannot be imported")
        except ResourceQuotaExceededError:
            return _error(429, "QUOTA_EXCEEDED", "Owner resource quota exceeded")
        except ProjectNotFoundError:
            return _error(404, "RESOURCE_NOT_FOUND", "Resource not found")
        except (ProjectIntegrityError, UploadTooLargeError, FileNotFoundError):
            return _error(422, "SOURCE_UNAVAILABLE", "Source is unavailable")
        except ProjectStoreError:
            return _error(422, "INVALID_IMPORT", "Survey import metadata is invalid")
        return ImportResponse(
            revision=_revision(revision), rowCount=len(dataset.records),
            warnings=[ImportWarning(
                code=warning.code, message=warning.message, rowIndex=warning.row_index,
            ) for warning in dataset.warnings],
        )

    @router.get("/{project_id}/revisions/{revision_id}/line-candidates")
    async def line_candidates(project_id: UUID, revision_id: UUID, request: Request):
        try:
            comparison = await run_in_threadpool(
                build_line_candidates, store, request.scope["geoai.owner_id"],
                str(project_id), str(revision_id),
            )
        except ProjectNotFoundError:
            return _error(404, "RESOURCE_NOT_FOUND", "Resource not found")
        except LineCandidateLimitError:
            return _error(413, "CANDIDATES_TOO_LARGE", "Line comparison exceeds viewer limits")
        except (LineCandidateInvalidError, ProjectIntegrityError, ProjectStoreError):
            return _error(422, "CANDIDATES_UNAVAILABLE", "Line comparison cannot be displayed")
        return JSONResponse(content=comparison, headers={"Cache-Control": "no-store"})

    return router
