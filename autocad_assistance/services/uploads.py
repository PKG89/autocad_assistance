"""Framework-independent storage for validated survey uploads."""

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4


ALLOWED_UPLOAD_SUFFIXES = frozenset({".txt", ".csv", ".kml"})
UPLOAD_CHUNK_BYTES = 64 * 1024


class InvalidUploadNameError(ValueError):
    pass


class UnsupportedUploadFormatError(ValueError):
    pass


class EmptyUploadError(ValueError):
    pass


class UploadTooLargeError(ValueError):
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
        or any(ord(character) < 32 for character in safe_name)
    ):
        raise InvalidUploadNameError("Upload filename is invalid")
    return safe_name


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
