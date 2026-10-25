"""Framework-independent storage for validated survey uploads."""

from dataclasses import dataclass
import csv
import errno
import hashlib
from io import BytesIO
import os
from pathlib import Path
import stat
from typing import BinaryIO
import unicodedata
from uuid import UUID, uuid4
import xml.etree.ElementTree as ET

from autocad_assistance.services.survey_parser import SurveyParseError, parse_survey_bytes


ALLOWED_UPLOAD_SUFFIXES = frozenset({".txt", ".csv", ".kml"})
UPLOAD_CHUNK_BYTES = 64 * 1024
MAX_SURVEY_ROWS = 100_000
MAX_PHYSICAL_LINES = 150_000
MAX_SURVEY_COLUMNS = 64
MAX_FIELD_CHARACTERS = 4_096
MAX_KML_COORDINATES = 100_000
MAX_KML_ELEMENTS = 200_000


class InvalidUploadNameError(ValueError):
    pass


class UnsupportedUploadFormatError(ValueError):
    pass


class EmptyUploadError(ValueError):
    pass


class UploadTooLargeError(ValueError):
    pass


class UploadLimitError(ValueError):
    pass


class InvalidUploadContentError(ValueError):
    pass


@dataclass(frozen=True)
class StoredUpload:
    upload_id: str
    original_filename: str
    format: str
    size_bytes: int
    sha256: str
    path: Path


def _safe_original_filename(filename: str) -> str:
    safe_name = filename.replace("\\", "/").rsplit("/", 1)[-1].strip()
    if (
        not safe_name
        or safe_name in {".", ".."}
        or len(safe_name) > 255
        or any(unicodedata.category(character) in {"Cc", "Cf"} for character in safe_name)
    ):
        raise InvalidUploadNameError("Upload filename is invalid")
    return safe_name


def _validate_survey_content(raw_data: bytes) -> None:
    if any(byte < 32 and byte not in (9, 10, 13) or byte == 127 for byte in raw_data):
        raise InvalidUploadContentError("Survey upload is not a supported text file")
    if raw_data.startswith((b"PK\x03\x04", b"\x1f\x8b", b"%PDF-")):
        raise InvalidUploadContentError("Survey upload is not a supported text file")
    if raw_data.lstrip().lower().startswith((b"<?xml", b"<kml", b"<!doctype")):
        raise InvalidUploadContentError("Survey upload is not a TXT/CSV survey")
    if len(raw_data.splitlines()) > MAX_PHYSICAL_LINES:
        raise UploadLimitError("Survey file exceeds the physical-line limit")
    try:
        parsed = parse_survey_bytes(raw_data)
    except (SurveyParseError, csv.Error) as exc:
        raise InvalidUploadContentError("Survey upload could not be parsed") from exc
    if len(parsed.rows) > MAX_SURVEY_ROWS:
        raise UploadLimitError("Survey file exceeds the point-row limit")
    if any(len(row) > MAX_SURVEY_COLUMNS for row in parsed.rows):
        raise UploadLimitError("Survey row exceeds the column limit")
    if parsed.header is not None and len(parsed.header) > MAX_SURVEY_COLUMNS:
        raise UploadLimitError("Survey header exceeds the column limit")
    if any(len(cell) > MAX_FIELD_CHARACTERS for row in parsed.rows for cell in row):
        raise UploadLimitError("Survey field exceeds the character limit")
    if parsed.header is not None and any(len(cell) > MAX_FIELD_CHARACTERS for cell in parsed.header):
        raise UploadLimitError("Survey header field exceeds the character limit")


def _validate_kml_content(raw_data: bytes) -> None:
    if b"\x00" in raw_data:
        raise InvalidUploadContentError("KML binary encoding is unsupported")
    if b"<!DOCTYPE" in raw_data.upper() or b"<!ENTITY" in raw_data.upper():
        raise InvalidUploadContentError("KML declarations and entities are unsupported")
    elements = 0
    coordinates = 0
    root_seen = False
    try:
        for event, element in ET.iterparse(BytesIO(raw_data), events=("start", "end")):
            if event == "start":
                elements += 1
                if elements > MAX_KML_ELEMENTS:
                    raise UploadLimitError("KML exceeds the element limit")
                if not root_seen:
                    root_seen = True
                    if element.tag.rsplit("}", 1)[-1].lower() != "kml":
                        raise InvalidUploadContentError("KML root element is invalid")
            else:
                tag = element.tag.rsplit("}", 1)[-1].lower()
                if tag == "coordinates" and element.text:
                    coordinates += len(element.text.split())
                elif tag == "coord":
                    coordinates += 1
                if coordinates > MAX_KML_COORDINATES:
                    raise UploadLimitError("KML exceeds the coordinate limit")
                element.clear()
    except ET.ParseError as exc:
        raise InvalidUploadContentError("KML upload is malformed") from exc
    if not root_seen:
        raise InvalidUploadContentError("KML upload is empty")


def _validate_upload_content(destination: Path, suffix: str) -> None:
    raw_data = destination.read_bytes()
    validate_upload_bytes(raw_data, suffix.removeprefix("."))


def validate_upload_bytes(raw_data: bytes, stored_format: str) -> None:
    """Recheck accepted bytes before preserving a project source snapshot."""
    if stored_format == "kml":
        _validate_kml_content(raw_data)
    elif stored_format in {"txt", "csv"}:
        _validate_survey_content(raw_data)
    else:
        raise UnsupportedUploadFormatError("Unsupported stored upload format")


def store_upload(
    source: BinaryIO,
    original_filename: str,
    upload_root: str | Path,
    max_upload_bytes: int,
) -> StoredUpload:
    """Validate and store one upload using only server-generated path parts."""

    if max_upload_bytes <= 0:
        raise ValueError("max_upload_bytes must be positive")

    safe_name = _safe_original_filename(original_filename)
    suffix = Path(safe_name).suffix.lower()
    if suffix not in ALLOWED_UPLOAD_SUFFIXES:
        formats = ", ".join(sorted(ALLOWED_UPLOAD_SUFFIXES))
        raise UnsupportedUploadFormatError(f"Allowed file formats: {formats}")

    root = Path(upload_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    upload_id = str(uuid4())
    upload_dir = root / upload_id
    upload_dir.mkdir(exist_ok=False)
    destination = upload_dir / f"{upload_id}{suffix}"

    size_bytes = 0
    digest = hashlib.sha256()
    try:
        with destination.open("xb") as target:
            while True:
                chunk = source.read(UPLOAD_CHUNK_BYTES)
                if not chunk:
                    break
                size_bytes += len(chunk)
                if size_bytes > max_upload_bytes:
                    raise UploadTooLargeError(
                        f"Upload exceeds the {max_upload_bytes}-byte limit"
                    )
                digest.update(chunk)
                target.write(chunk)
        if size_bytes == 0:
            raise EmptyUploadError("Uploaded file is empty")
        _validate_upload_content(destination, suffix)
    except Exception:
        destination.unlink(missing_ok=True)
        try:
            upload_dir.rmdir()
        except OSError:
            pass
        raise

    return StoredUpload(
        upload_id=upload_id,
        original_filename=safe_name,
        format=suffix.removeprefix("."),
        size_bytes=size_bytes,
        sha256=digest.hexdigest(),
        path=destination,
    )


def read_stored_upload(
    upload_root: str | Path,
    upload_id: str,
    max_upload_bytes: int,
) -> tuple[bytes, str]:
    """Read exactly one UUID-named regular file via no-follow directory FDs."""
    try:
        canonical_id = str(UUID(upload_id))
    except ValueError as exc:
        raise FileNotFoundError from exc
    if canonical_id != upload_id:
        raise FileNotFoundError

    nofollow = getattr(os, "O_NOFOLLOW", 0)
    directory = getattr(os, "O_DIRECTORY", 0)
    if not nofollow or not directory:
        raise RuntimeError("Secure upload reads require O_NOFOLLOW and O_DIRECTORY")
    root = Path(upload_root).resolve()
    root_fd = None
    upload_fd = None
    matches: list[tuple[bytes, str]] = []
    try:
        root_fd = os.open(root, os.O_RDONLY | directory | nofollow)
        upload_fd = os.open(canonical_id, os.O_RDONLY | directory | nofollow, dir_fd=root_fd)
        for suffix in sorted(ALLOWED_UPLOAD_SUFFIXES):
            filename = f"{canonical_id}{suffix}"
            try:
                fd = os.open(filename, os.O_RDONLY | os.O_NONBLOCK | nofollow, dir_fd=upload_fd)
            except OSError as exc:
                if exc.errno in (errno.ENOENT, errno.ELOOP):
                    continue
                raise FileNotFoundError from exc
            try:
                if not stat.S_ISREG(os.fstat(fd).st_mode):
                    raise FileNotFoundError
                with os.fdopen(fd, "rb", closefd=False) as source:
                    raw_data = source.read(max_upload_bytes + 1)
                if len(raw_data) > max_upload_bytes:
                    raise UploadTooLargeError("Stored upload exceeds the byte limit")
                matches.append((raw_data, suffix.removeprefix(".")))
            finally:
                os.close(fd)
    except OSError as exc:
        raise FileNotFoundError from exc
    finally:
        if upload_fd is not None:
            os.close(upload_fd)
        if root_fd is not None:
            os.close(root_fd)
    if len(matches) != 1:
        raise FileNotFoundError
    return matches[0]


def remove_stored_upload(upload_root: str | Path, upload_id: str, stored_format: str) -> None:
    """Remove a just-created UUID upload after owner registration fails."""
    canonical_id = str(UUID(upload_id))
    if canonical_id != upload_id or stored_format not in {"txt", "csv", "kml"}:
        raise ValueError("Invalid stored upload identity")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    root_fd = os.open(Path(upload_root).resolve(), flags)
    try:
        upload_fd = os.open(canonical_id, flags, dir_fd=root_fd)
        try:
            os.unlink(f"{canonical_id}.{stored_format}", dir_fd=upload_fd)
        finally:
            os.close(upload_fd)
        os.rmdir(canonical_id, dir_fd=root_fd)
    finally:
        os.close(root_fd)
