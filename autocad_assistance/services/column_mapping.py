"""Framework-independent explicit survey column mapping."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import TypedDict


class MappingValidationError(ValueError):
    """Raised when explicit mapping or mapped data is invalid."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class MappedPointRecord(TypedDict):
    Point: str
    X: str
    Y: str
    Z: str
    Code: str
    Comments: str | None


@dataclass(frozen=True)
class MappingResult:
    rows: tuple[MappedPointRecord, ...]


_REQUIRED_KEYS = ("Point", "X", "Y", "Z", "Code")
_ALLOWED_KEYS = set(_REQUIRED_KEYS + ("Comments",))


def _mapping_error(message: str) -> MappingValidationError:
    return MappingValidationError("INVALID_COLUMN_MAPPING", message)


def _coordinate_error(message: str) -> MappingValidationError:
    return MappingValidationError("INVALID_COORDINATE", message)


def _validate_mapping_shape(mapping: dict[str, object]) -> dict[str, int]:
    missing = [key for key in _REQUIRED_KEYS if key not in mapping]
    if missing:
        raise _mapping_error(f"Missing required mapping keys: {', '.join(missing)}")

    unknown = [key for key in mapping if key not in _ALLOWED_KEYS]
    if unknown:
        raise _mapping_error(f"Unsupported mapping keys: {', '.join(unknown)}")

    seen: set[int] = set()
    normalized_mapping: dict[str, int] = {}
    for key, index in mapping.items():
        if isinstance(index, bool) or not isinstance(index, int) or index < 0:
            raise _mapping_error(f"Invalid column index for '{key}'")
        if index in seen:
            raise _mapping_error("Column indices must be distinct across mapping keys")
        seen.add(index)
        normalized_mapping[key] = index

    return normalized_mapping


def _validate_coordinate(value: str, *, row_number: int, field: str) -> None:
    stripped = value.strip()
    if stripped == "":
        raise _coordinate_error(f"Row {row_number} has empty coordinate '{field}'")
    try:
        numeric = float(stripped)
    except ValueError as exc:
        raise _coordinate_error(
            f"Row {row_number} has non-numeric coordinate '{field}'"
        ) from exc
    if not math.isfinite(numeric):
        raise _coordinate_error(
            f"Row {row_number} has non-finite coordinate '{field}'"
        )


def map_survey_rows(rows: list[list[str]], mapping: dict[str, object]) -> MappingResult:
    """Map parsed survey rows to explicit point records with strict validation."""

    normalized_mapping = _validate_mapping_shape(mapping)

    if not rows:
        return MappingResult(rows=())

    max_columns = max(len(row) for row in rows)
    for key, index in normalized_mapping.items():
        if index >= max_columns:
            raise _mapping_error(
                f"Column index {index} for '{key}' is out of range for survey rows"
            )

    mapped_rows: list[MappedPointRecord] = []
    for row_idx, source_row in enumerate(rows, start=1):
        point_index = normalized_mapping["Point"]
        x_index = normalized_mapping["X"]
        y_index = normalized_mapping["Y"]
        z_index = normalized_mapping["Z"]
        code_index = normalized_mapping["Code"]
        comments_index = normalized_mapping.get("Comments")

        required_indices = {
            "Point": point_index,
            "X": x_index,
            "Y": y_index,
            "Z": z_index,
        }
        for field, index in required_indices.items():
            if index >= len(source_row):
                raise _mapping_error(
                    f"Row {row_idx} is missing required field '{field}'"
                )

        if code_index >= len(source_row):
            code_value = ""
        else:
            code_value = source_row[code_index]

        comments_value: str | None = None
        if comments_index is not None and comments_index < len(source_row):
            comments_value = source_row[comments_index]

        point_value = source_row[point_index]
        x_value = source_row[x_index]
        y_value = source_row[y_index]
        z_value = source_row[z_index]

        _validate_coordinate(x_value, row_number=row_idx, field="X")
        _validate_coordinate(y_value, row_number=row_idx, field="Y")
        _validate_coordinate(z_value, row_number=row_idx, field="Z")

        mapped_rows.append(
            {
                "Point": point_value,
                "X": x_value,
                "Y": y_value,
                "Z": z_value,
                "Code": code_value,
                "Comments": comments_value,
            }
        )

    return MappingResult(rows=tuple(mapped_rows))
