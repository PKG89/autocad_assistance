"""Shared, lossless survey contract for HTTP and Telegram adapters.

This module records what was measured and how it was interpreted. It does not
transform coordinates, convert units, or apply drawing scale to measurements.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import math
import re
from typing import Mapping, Sequence

from autocad_assistance.services.column_mapping import MappedPointRecord, map_survey_rows
from autocad_assistance.services.survey_parser import parse_survey_bytes


class SurveyContractError(ValueError):
    """An input cannot be represented without losing survey meaning."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class SurveyContext:
    coordinate_system: str | None = None
    horizontal_unit: str | None = None
    vertical_unit: str | None = None
    scale_factor: Decimal = Decimal("1")

    def __post_init__(self) -> None:
        for name in ("coordinate_system", "horizontal_unit", "vertical_unit"):
            value = getattr(self, name)
            if value is not None:
                if not isinstance(value, str) or not value.strip():
                    raise SurveyContractError("INVALID_SURVEY_CONTEXT", f"{name} must be a nonempty label")
                object.__setattr__(self, name, value.strip())
        try:
            scale = Decimal(str(self.scale_factor))
            scale_float = float(scale)
        except (InvalidOperation, ValueError, OverflowError) as exc:
            raise SurveyContractError("INVALID_SURVEY_CONTEXT", "scale_factor must be finite and positive") from exc
        if not scale.is_finite() or scale <= 0 or not math.isfinite(scale_float) or scale_float == 0:
            raise SurveyContractError("INVALID_SURVEY_CONTEXT", "scale_factor must be finite and positive")
        object.__setattr__(self, "scale_factor", scale)


PLAN_BASE_DENOMINATOR = 1000


def drawing_factor_for_plan_denominator(value: object) -> float:
    """Match the established Telegram 1:N DXF sizing, preserving measured XYZ."""
    try:
        denominator = Decimal(str(value))
        numeric = float(denominator)
    except (InvalidOperation, ValueError, OverflowError) as exc:
        raise SurveyContractError("INVALID_SURVEY_CONTEXT", "Plan denominator must be finite and positive") from exc
    if not denominator.is_finite() or denominator <= 0 or not math.isfinite(numeric):
        raise SurveyContractError("INVALID_SURVEY_CONTEXT", "Plan denominator must be finite and positive")
    return max(numeric / PLAN_BASE_DENOMINATOR, 0.05)


@dataclass(frozen=True)
class SurveyWarning:
    code: str
    message: str
    row_index: int | None = None


@dataclass(frozen=True)
class SurveyRecord:
    point_id: str
    x_text: str
    y_text: str
    z_text: str
    x: Decimal
    y: Decimal
    z: Decimal
    code: str
    comments: str | None
    source_row_index: int
    source_line_number: int | None
    source_cells: tuple[str, ...]


@dataclass(frozen=True)
class SurveyDataset:
    records: tuple[SurveyRecord, ...]
    source_sha256: str
    context: SurveyContext
    warnings: tuple[SurveyWarning, ...] = field(default_factory=tuple)
    encoding: str | None = None
    delimiter: str | None = None

    @property
    def mapped_rows(self) -> tuple[MappedPointRecord, ...]:
        """Return the established generator/API shape without rounding XYZ."""
        return tuple(
            {
                "Point": record.point_id,
                "X": record.x_text,
                "Y": record.y_text,
                "Z": record.z_text,
                "Code": record.code,
                "Comments": record.comments,
            }
            for record in self.records
        )


def _coordinate(value: object, row_index: int, axis: str) -> tuple[str, Decimal]:
    if not isinstance(value, str) or not value.strip():
        raise SurveyContractError("INVALID_COORDINATE", f"Row {row_index} has empty coordinate '{axis}'")
    try:
        numeric = Decimal(value.strip())
        as_float = float(numeric)
    except (InvalidOperation, ValueError, OverflowError) as exc:
        raise SurveyContractError("INVALID_COORDINATE", f"Row {row_index} has invalid coordinate '{axis}'") from exc
    if not numeric.is_finite() or not math.isfinite(as_float):
        raise SurveyContractError("INVALID_COORDINATE", f"Row {row_index} has non-finite coordinate '{axis}'")
    if numeric != 0 and as_float == 0:
        raise SurveyContractError("INVALID_COORDINATE", f"Row {row_index} coordinate '{axis}' underflows DXF precision")
    return value, numeric


def make_survey_dataset(
    mapped_rows: Sequence[Mapping[str, object]],
    *,
    source_rows: Sequence[Sequence[str]],
    source_sha256: str,
    source_line_numbers: Sequence[int] = (),
    context: SurveyContext | None = None,
    encoding: str | None = None,
    delimiter: str | None = None,
) -> SurveyDataset:
    """Freeze mapped records and their unchanged source-row provenance."""
    if not re.fullmatch(r"[0-9a-f]{64}", source_sha256):
        raise SurveyContractError("INVALID_PROVENANCE", "source_sha256 must be a lowercase SHA-256 digest")
    if len(mapped_rows) != len(source_rows) or (
        source_line_numbers and len(source_line_numbers) != len(source_rows)
    ):
        raise SurveyContractError("INVALID_PROVENANCE", "Mapped and source rows must align")

    records: list[SurveyRecord] = []
    warnings: list[SurveyWarning] = []
    seen_ids: dict[str, int] = {}
    for row_index, (mapped, original) in enumerate(zip(mapped_rows, source_rows), start=1):
        x_text, x = _coordinate(mapped.get("X"), row_index, "X")
        y_text, y = _coordinate(mapped.get("Y"), row_index, "Y")
        z_text, z = _coordinate(mapped.get("Z"), row_index, "Z")
        point_value = mapped.get("Point")
        point_id = point_value if isinstance(point_value, str) else ""
        code_value = mapped.get("Code")
        code = code_value if isinstance(code_value, str) else ""
        comments_value = mapped.get("Comments")
        comments = comments_value if isinstance(comments_value, str) else None
        if not point_id.strip():
            warnings.append(SurveyWarning("EMPTY_POINT_ID", "Point ID is empty", row_index))
        elif point_id in seen_ids:
            warnings.append(
                SurveyWarning(
                    "DUPLICATE_POINT_ID",
                    f"Point ID duplicates row {seen_ids[point_id]}",
                    row_index,
                )
            )
        else:
            seen_ids[point_id] = row_index
        line_number = source_line_numbers[row_index - 1] if source_line_numbers else None
        if line_number is not None and line_number < 1:
            raise SurveyContractError("INVALID_PROVENANCE", "Source line number must be positive")
        records.append(
            SurveyRecord(
                point_id=point_id,
                x_text=x_text,
                y_text=y_text,
                z_text=z_text,
                x=x,
                y=y,
                z=z,
                code=code,
                comments=comments,
                source_row_index=row_index,
                source_line_number=line_number,
                source_cells=tuple(original),
            )
        )

    survey_context = context if context is not None else SurveyContext()
    if survey_context.coordinate_system is None:
        warnings.append(SurveyWarning("UNKNOWN_COORDINATE_SYSTEM", "Coordinate system was not specified"))
    if survey_context.horizontal_unit is None:
        warnings.append(SurveyWarning("UNKNOWN_HORIZONTAL_UNIT", "Horizontal unit was not specified"))
    if survey_context.vertical_unit is None:
        warnings.append(SurveyWarning("UNKNOWN_VERTICAL_UNIT", "Vertical unit was not specified"))
    return SurveyDataset(
        records=tuple(records),
        source_sha256=source_sha256,
        context=survey_context,
        warnings=tuple(warnings),
        encoding=encoding,
        delimiter=delimiter,
    )


def build_survey_dataset(
    raw_data: bytes,
    mapping: dict[str, object],
    *,
    context: SurveyContext | None = None,
) -> SurveyDataset:
    """Use the accepted parser and mapper to build the shared contract."""
    parsed = parse_survey_bytes(raw_data)
    mapped = map_survey_rows(parsed.rows, mapping)
    return make_survey_dataset(
        mapped.rows,
        source_rows=parsed.rows,
        source_sha256=sha256(raw_data).hexdigest(),
        source_line_numbers=parsed.source_line_numbers,
        context=context,
        encoding=parsed.encoding,
        delimiter=parsed.delimiter,
    )
