"""Framework-independent TXT/CSV survey parsing."""

from __future__ import annotations

from dataclasses import dataclass
import csv
from io import BytesIO, TextIOWrapper

import chardet


class SurveyParseError(ValueError):
    """Raised when survey bytes are empty or yield no usable data rows."""


@dataclass(frozen=True)
class SurveyParseResult:
    rows: list[list[str]]
    encoding: str
    delimiter: str
    header: list[str] | None


def _detect_encoding(raw_data: bytes) -> str:
    # Prefer UTF-8 (including BOM) and only fall back to chardet if decoding fails.
    try:
        raw_data.decode("utf-8-sig")
        return "utf-8-sig"
    except UnicodeDecodeError:
        result_encoding = chardet.detect(raw_data) or {}
        encoding = result_encoding.get("encoding") or "utf-8"
        if isinstance(encoding, str) and encoding.lower() == "ascii":
            return "cp1251"
        return encoding


def _detect_delimiter(line: str) -> str:
    for candidate in ("\t", ";", ",", "|"):
        if candidate in line:
            return candidate
    return " "


def _is_coordinate_header(cleaned: list[str]) -> bool:
    return [cell.lower() for cell in cleaned[1:4]] in (["x", "y", "z"], ["y", "x", "z"])


def parse_survey_bytes(raw_data: bytes) -> SurveyParseResult:
    """Decode, detect delimiter, and parse survey point rows from raw file bytes."""

    encoding = _detect_encoding(raw_data)

    try:
        delimiter = " "
        with TextIOWrapper(BytesIO(raw_data), encoding=encoding) as source:
            for line in source:
                stripped = line.strip()
                if stripped:
                    delimiter = _detect_delimiter(stripped)
                    break

        rows: list[list[str]] = []
        header: list[str] | None = None
        with TextIOWrapper(BytesIO(raw_data), encoding=encoding) as source:
            reader = csv.reader(source, delimiter=delimiter, skipinitialspace=True)
            for row in reader:
                cleaned = [cell.strip() for cell in row]
                if delimiter == " ":
                    cleaned = [cell for cell in cleaned if cell]
                # A header is not a survey point; preserve empty data columns.
                if not rows and _is_coordinate_header(cleaned):
                    if header is None:
                        header = cleaned
                    continue
                if len(cleaned) >= 4:
                    rows.append(cleaned)
    except (LookupError, UnicodeDecodeError) as exc:
        raise SurveyParseError("Survey file could not be decoded") from exc

    if not rows:
        raise SurveyParseError("Survey file contains no usable data rows")

    return SurveyParseResult(
        rows=rows,
        encoding=encoding,
        delimiter=delimiter,
        header=header,
    )
