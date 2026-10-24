"""HTTP adapter for accepting field-survey source files."""

import csv
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Query, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from autocad_assistance.services.column_mapping import (
    MappingValidationError,
    map_survey_rows,
)
from autocad_assistance.services.dxf_jobs import (
    DxfCoordinateValidationError,
    render_dxf_bytes,
)
from autocad_assistance.services.survey_parser import SurveyParseError, parse_survey_bytes
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


class PreviewWarning(BaseModel):
    code: str
    message: str


class PreviewResponse(BaseModel):
    uploadId: str
    format: str
    encoding: str
    delimiter: str
    columns: list[str]
    rows: list[list[str]]
    rowCount: int
    returnedRows: int
    warnings: list[PreviewWarning]


class MappingRequest(BaseModel):
    mapping: dict[str, object]


class TinSettingsRequest(BaseModel):
    codes: list[str] = []
    refine: bool = False
    scale_value: float | None = None


class DxfRequest(BaseModel):
    mapping: dict[str, object]
    scaleFactor: float = 1.0
    tinSettings: TinSettingsRequest = Field(default_factory=TinSettingsRequest)


class MappingRow(BaseModel):
    Point: str
    X: str
    Y: str
    Z: str
    Code: str
    Comments: str | None


class MappingResponse(BaseModel):
    uploadId: str
    mapping: dict[str, int]
    rows: list[MappingRow]
    rowCount: int
    returnedRows: int


def _error(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message}},
    )


def _resolve_upload_file(upload_root: Path, upload_id: str) -> tuple[Path, str]:
    root = upload_root.resolve()
    upload_dir = root / upload_id
    if upload_dir.is_symlink() or not upload_dir.is_dir():
        raise FileNotFoundError

    try:
        resolved_dir = upload_dir.resolve(strict=True)
    except OSError as exc:
        raise FileNotFoundError from exc
    if not resolved_dir.is_relative_to(root):
        raise FileNotFoundError

    expected_files = [resolved_dir / f"{upload_id}.txt", resolved_dir / f"{upload_id}.csv", resolved_dir / f"{upload_id}.kml"]
    matches: list[Path] = []
    for candidate in expected_files:
        if not candidate.exists():
            continue
        if candidate.is_symlink() or not candidate.is_file():
            raise FileNotFoundError
        try:
            resolved_candidate = candidate.resolve(strict=True)
        except OSError as exc:
            raise FileNotFoundError from exc
        if not resolved_candidate.is_relative_to(root):
            raise FileNotFoundError
        matches.append(resolved_candidate)

    if len(matches) != 1:
        raise FileNotFoundError

    stored_file = matches[0]
    return stored_file, stored_file.suffix.lower().removeprefix(".")


def _build_preview_columns(header: list[str] | None, rows: list[list[str]]) -> list[str]:
    if header is not None:
        return header
    widest = max(len(row) for row in rows)
    return [f"Column {index}" for index in range(1, widest + 1)]


def create_upload_router(
    *,
    upload_root: str | Path,
    max_upload_bytes: int,
    max_preview_rows: int,
) -> APIRouter:
    if max_preview_rows <= 0:
        raise ValueError("max_preview_rows must be positive")

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

    @router.get(
        "/uploads/{upload_id}/preview",
        response_model=PreviewResponse,
        responses={
            404: {"model": ErrorResponse, "description": "Upload not found"},
            422: {"model": ErrorResponse, "description": "Preview unavailable"},
        },
    )
    async def upload_preview(
        upload_id: UUID,
        limit: Annotated[int | None, Query(gt=0)] = None,
    ):
        preview_limit = limit if limit is not None else min(10, max_preview_rows)
        if preview_limit > max_preview_rows:
            return _error(
                422,
                "PREVIEW_LIMIT_EXCEEDED",
                f"Preview limit cannot exceed {max_preview_rows}",
            )

        try:
            stored_file, stored_format = await run_in_threadpool(
                _resolve_upload_file,
                Path(upload_root),
                str(upload_id),
            )
        except FileNotFoundError:
            return _error(404, "UPLOAD_NOT_FOUND", "Upload not found")

        if stored_format == "kml":
            return _error(
                422,
                "UNSUPPORTED_PREVIEW_FORMAT",
                "Preview supports only TXT and CSV uploads",
            )

        if stored_format not in {"txt", "csv"}:
            return _error(404, "UPLOAD_NOT_FOUND", "Upload not found")

        try:
            raw_data = await run_in_threadpool(stored_file.read_bytes)
            parsed = await run_in_threadpool(parse_survey_bytes, raw_data)
        except (OSError, SurveyParseError, csv.Error):
            return _error(422, "INVALID_SURVEY", "Survey data cannot be previewed")

        warnings: list[PreviewWarning] = []
        if parsed.header is None:
            warnings.append(
                PreviewWarning(
                    code="HEADER_NOT_DETECTED",
                    message="Survey header was not detected",
                )
            )
        row_widths = {len(row) for row in parsed.rows}
        if len(row_widths) > 1:
            warnings.append(
                PreviewWarning(
                    code="INCONSISTENT_COLUMNS",
                    message="Survey rows have inconsistent column counts",
                )
            )

        limited_rows = parsed.rows[:preview_limit]
        return PreviewResponse(
            uploadId=str(upload_id),
            format=stored_format,
            encoding=parsed.encoding,
            delimiter=parsed.delimiter,
            columns=_build_preview_columns(parsed.header, parsed.rows),
            rows=limited_rows,
            rowCount=len(parsed.rows),
            returnedRows=len(limited_rows),
            warnings=warnings,
        )

    @router.post(
        "/uploads/{upload_id}/mapping",
        response_model=MappingResponse,
        responses={
            404: {"model": ErrorResponse, "description": "Upload not found"},
            422: {"model": ErrorResponse, "description": "Mapping unavailable"},
        },
    )
    async def upload_mapping(
        upload_id: UUID,
        payload: MappingRequest,
        limit: Annotated[int | None, Query(gt=0)] = None,
    ):
        preview_limit = limit if limit is not None else min(10, max_preview_rows)
        if preview_limit > max_preview_rows:
            return _error(
                422,
                "PREVIEW_LIMIT_EXCEEDED",
                f"Preview limit cannot exceed {max_preview_rows}",
            )

        try:
            stored_file, stored_format = await run_in_threadpool(
                _resolve_upload_file,
                Path(upload_root),
                str(upload_id),
            )
        except FileNotFoundError:
            return _error(404, "UPLOAD_NOT_FOUND", "Upload not found")

        if stored_format == "kml":
            return _error(
                422,
                "UNSUPPORTED_MAPPING_FORMAT",
                "Column mapping supports only TXT and CSV uploads",
            )

        if stored_format not in {"txt", "csv"}:
            return _error(404, "UPLOAD_NOT_FOUND", "Upload not found")

        try:
            raw_data = await run_in_threadpool(stored_file.read_bytes)
            parsed = await run_in_threadpool(parse_survey_bytes, raw_data)
            mapped = await run_in_threadpool(
                map_survey_rows,
                parsed.rows,
                payload.mapping,
            )
        except (OSError, SurveyParseError, csv.Error):
            return _error(422, "INVALID_SURVEY", "Survey data cannot be mapped")
        except MappingValidationError as exc:
            return _error(422, exc.code, exc.message)

        limited_rows = [MappingRow(**mapped_row) for mapped_row in mapped.rows[:preview_limit]]
        response_mapping = {key: int(value) for key, value in payload.mapping.items()}
        return MappingResponse(
            uploadId=str(upload_id),
            mapping=response_mapping,
            rows=limited_rows,
            rowCount=len(mapped.rows),
            returnedRows=len(limited_rows),
        )

    @router.post(
        "/uploads/{upload_id}/dxf",
        responses={
            200: {"description": "DXF generated"},
            404: {"model": ErrorResponse, "description": "Upload not found"},
            422: {"model": ErrorResponse, "description": "Generation unavailable"},
            500: {"model": ErrorResponse, "description": "Generation failure"},
        },
    )
    async def upload_dxf(
        upload_id: UUID,
        payload: DxfRequest,
    ):
        try:
            stored_file, stored_format = await run_in_threadpool(
                _resolve_upload_file,
                Path(upload_root),
                str(upload_id),
            )
        except FileNotFoundError:
            return _error(404, "UPLOAD_NOT_FOUND", "Upload not found")

        if stored_format == "kml":
            return _error(
                422,
                "UNSUPPORTED_DXF_FORMAT",
                "DXF generation supports only TXT and CSV uploads",
            )

        if stored_format not in {"txt", "csv"}:
            return _error(404, "UPLOAD_NOT_FOUND", "Upload not found")

        try:
            raw_data = await run_in_threadpool(stored_file.read_bytes)
            parsed = await run_in_threadpool(parse_survey_bytes, raw_data)
            mapped = await run_in_threadpool(
                map_survey_rows,
                parsed.rows,
                payload.mapping,
            )
            dxf_bytes = await run_in_threadpool(
                render_dxf_bytes,
                mapped.rows,
                scale_factor=payload.scaleFactor,
                tin_settings={
                    "codes": payload.tinSettings.codes,
                    "refine": payload.tinSettings.refine,
                    "scale_value": payload.tinSettings.scale_value,
                },
            )
        except (OSError, SurveyParseError, csv.Error):
            return _error(422, "INVALID_SURVEY", "Survey data cannot be mapped")
        except MappingValidationError as exc:
            return _error(422, exc.code, exc.message)
        except DxfCoordinateValidationError as exc:
            return _error(422, "INVALID_COORDINATE", str(exc))
        except Exception:
            return _error(500, "DXF_GENERATION_FAILED", "Unable to generate DXF")

        return Response(
            content=dxf_bytes,
            media_type="application/dxf",
            headers={"Content-Disposition": 'attachment; filename="drawing.dxf"'},
        )

    return router
