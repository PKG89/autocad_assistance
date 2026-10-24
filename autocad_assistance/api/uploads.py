"""HTTP adapter for accepting field-survey source files."""

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from autocad_assistance.services.uploads import (
    EmptyUploadError,
    InvalidUploadNameError,
    UnsupportedUploadFormatError,
    UploadTooLargeError,
    store_upload,
)


class UploadResponse(BaseModel):
    uploadId: str
    originalFilename: str
    format: str
    sizeBytes: int
    sha256: str


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


def _error(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message}},
    )


def create_upload_router(
    *,
    upload_root: str | Path,
    max_upload_bytes: int,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["uploads"])

    @router.post(
        "/uploads",
        status_code=status.HTTP_201_CREATED,
        response_model=UploadResponse,
        responses={
            413: {"model": ErrorResponse, "description": "Upload exceeds size limit"},
            422: {"model": ErrorResponse, "description": "Invalid upload"},
            500: {"model": ErrorResponse, "description": "Storage failure"},
        },
        description=(
            "Stores one TXT, CSV, or KML source file. Each successful retry "
            "creates a new uploadId; this endpoint is not idempotent."
        ),
    )
    async def upload_survey(
        file: Annotated[UploadFile, File(description="TXT, CSV, or KML source file")],
    ):
        try:
            stored = await run_in_threadpool(
                store_upload,
                file.file,
                file.filename or "",
                upload_root,
                max_upload_bytes,
            )
        except InvalidUploadNameError as exc:
            return _error(422, "INVALID_UPLOAD_NAME", str(exc))
        except UnsupportedUploadFormatError as exc:
            return _error(422, "UNSUPPORTED_FILE_FORMAT", str(exc))
        except EmptyUploadError as exc:
            return _error(422, "EMPTY_FILE", str(exc))
        except UploadTooLargeError as exc:
            return _error(413, "UPLOAD_TOO_LARGE", str(exc))
        except OSError:
            return _error(500, "STORAGE_ERROR", "Unable to store uploaded file")
        finally:
            await file.close()

        return UploadResponse(
            uploadId=stored.upload_id,
            originalFilename=stored.original_filename,
            format=stored.format,
            sizeBytes=stored.size_bytes,
            sha256=stored.sha256,
        )

    return router
