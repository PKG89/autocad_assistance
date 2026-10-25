"""Separate, versioned GEO AI project storage; no public access layer."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import stat
from typing import Iterator, Mapping
import unicodedata
from uuid import UUID, uuid4

from autocad_assistance.services.survey_contract import SurveyContext
from autocad_assistance.services.uploads import read_stored_upload, validate_upload_bytes


MAX_SOURCE_BYTES = 10 * 1024 * 1024
MAX_RESULT_BYTES = 25 * 1024 * 1024
MAX_SETTINGS_BYTES = 64 * 1024
JOB_STATUSES = frozenset({"queued", "running", "cancelling", "cancelled", "failed", "succeeded"})


class ProjectStoreError(ValueError):
    """Invalid project operation or metadata."""


class ProjectNotFoundError(LookupError):
    """Requested project, revision or job does not exist."""


class ProjectIntegrityError(IOError):
    """Stored bytes or path no longer match accepted metadata."""


@dataclass(frozen=True)
class ProjectRecord:
    project_id: str
    name: str
    created_at: str


@dataclass(frozen=True)
class RevisionRecord:
    revision_id: str
    project_id: str
    sequence: int
    parent_revision_id: str | None
    source_format: str
    source_sha256: str
    source_size: int
    settings_json: str
    settings_sha256: str
    algorithm_version: str
    created_at: str


@dataclass(frozen=True)
class ProjectJobRecord:
    job_id: str
    revision_id: str
    request_json: str
    request_sha256: str
    status: str
    result_sha256: str | None
    result_size: int | None
    algorithm_version: str
    created_at: str


def _uuid(value: str) -> str:
    try:
        normalized = str(UUID(value))
    except (ValueError, TypeError) as exc:
        raise ProjectNotFoundError(value) from exc
    if normalized != value:
        raise ProjectNotFoundError(value)
    return value


def _label(value: str, *, name: str, limit: int) -> str:
    if not isinstance(value, str):
        raise ProjectStoreError(f"{name} must be text")
    normalized = value.strip()
    if not normalized or len(normalized) > limit or any(
        unicodedata.category(char) in {"Cc", "Cf"} for char in normalized
    ):
        raise ProjectStoreError(f"{name} is invalid")
    return normalized


def _canonical_json(value: object) -> str:
    try:
        rendered = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ProjectStoreError("Settings must be finite JSON values") from exc
    if len(rendered.encode("utf-8")) > MAX_SETTINGS_BYTES:
        raise ProjectStoreError("Settings exceed the 64 KiB metadata limit")
    return rendered


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


class ProjectStore:
    """Immutable project revisions and verified source/result snapshots.

    The caller must supply identity/ownership policy before exposing these
    operations over HTTP. No Telegram database is opened or migrated.
    """

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.files_root = self.root / "projects"
        self.files_root.mkdir(exist_ok=True, mode=0o700)
        self.db_path = self.root / "projects.sqlite3"
        with self._db() as db:
            current = db.execute("PRAGMA user_version").fetchone()[0]
            if current not in (0, 1):
                raise ProjectStoreError(f"Unsupported project schema version: {current}")
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS projects (
                    project_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS revisions (
                    revision_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL REFERENCES projects(project_id),
                    sequence INTEGER NOT NULL,
                    parent_revision_id TEXT REFERENCES revisions(revision_id),
                    source_format TEXT NOT NULL,
                    source_sha256 TEXT NOT NULL,
                    source_size INTEGER NOT NULL,
                    settings_json TEXT NOT NULL,
                    settings_sha256 TEXT NOT NULL,
                    algorithm_version TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(project_id, sequence)
                );
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    revision_id TEXT NOT NULL REFERENCES revisions(revision_id),
                    request_json TEXT NOT NULL,
                    request_sha256 TEXT NOT NULL,
                    status TEXT NOT NULL,
                    result_sha256 TEXT,
                    result_size INTEGER,
                    algorithm_version TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                PRAGMA user_version = 1;
                """
            )

    @contextmanager
    def _db(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.db_path, timeout=15, isolation_level=None)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA foreign_keys = ON")
            db.execute("PRAGMA journal_mode = WAL")
            db.execute("PRAGMA synchronous = FULL")
            yield db
        finally:
            db.close()

    def _open_directory(self, *parts: str, create: bool = False) -> int:
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        descriptor = os.open(self.files_root, flags)
        try:
            for part in parts:
                if part in {"", ".", ".."} or "/" in part or "\\" in part:
                    raise ProjectStoreError("Unsafe project path component")
                if create:
                    try:
                        os.mkdir(part, mode=0o700, dir_fd=descriptor)
                    except FileExistsError:
                        pass
                child = os.open(part, flags, dir_fd=descriptor)
                os.close(descriptor)
                descriptor = child
            return descriptor
        except Exception:
            os.close(descriptor)
            raise

    @staticmethod
    def _write_file(directory_fd: int, filename: str, raw: bytes) -> None:
        descriptor = os.open(
            filename,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
            dir_fd=directory_fd,
        )
        try:
            with os.fdopen(descriptor, "wb", closefd=False) as target:
                target.write(raw)
                target.flush()
                os.fsync(target.fileno())
            os.fsync(directory_fd)
        finally:
            os.close(descriptor)

    def _read_file(
        self, parts: tuple[str, ...], filename: str, size_limit: int, sha256: str, expected_size: int
    ) -> bytes:
        try:
            directory_fd = self._open_directory(*parts)
            try:
                descriptor = os.open(filename, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory_fd)
                try:
                    if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                        raise ProjectIntegrityError("Project file is not regular")
                    with os.fdopen(descriptor, "rb", closefd=False) as source:
                        raw = source.read(size_limit + 1)
                finally:
                    os.close(descriptor)
            finally:
                os.close(directory_fd)
        except OSError as exc:
            raise ProjectIntegrityError("Project file is missing or unsafe") from exc
        if not 0 < len(raw) <= size_limit or len(raw) != expected_size or _digest(raw) != sha256:
            raise ProjectIntegrityError("Project file checksum or size is invalid")
        return raw

    def create_project(self, name: str) -> ProjectRecord:
        name = _label(name, name="Project name", limit=200)
        project_id = str(uuid4())
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                descriptor = self._open_directory(project_id, create=True)
                os.close(descriptor)
                db.execute("INSERT INTO projects(project_id, name) VALUES (?, ?)", (project_id, name))
                db.execute("COMMIT")
            except Exception:
                db.execute("ROLLBACK")
                try:
                    root_fd = self._open_directory()
                    try:
                        os.rmdir(project_id, dir_fd=root_fd)
                    finally:
                        os.close(root_fd)
                except OSError:
                    pass
                raise
        return self.get_project(project_id)

    def get_project(self, project_id: str) -> ProjectRecord:
        with self._db() as db:
            row = db.execute("SELECT * FROM projects WHERE project_id = ?", (_uuid(project_id),)).fetchone()
        if row is None:
            raise ProjectNotFoundError(project_id)
        return ProjectRecord(**dict(row))

    def list_projects(self) -> tuple[ProjectRecord, ...]:
        with self._db() as db:
            rows = db.execute("SELECT * FROM projects ORDER BY created_at, project_id").fetchall()
        return tuple(ProjectRecord(**dict(row)) for row in rows)

    def add_revision(
        self,
        project_id: str,
        upload_root: str | Path,
        upload_id: str,
        *,
        context: SurveyContext,
        settings: Mapping[str, object] | None,
        algorithm_version: str,
    ) -> RevisionRecord:
        project_id = _uuid(project_id)
        algorithm_version = _label(algorithm_version, name="Algorithm version", limit=128)
        if not isinstance(context, SurveyContext):
            raise ProjectStoreError("Explicit survey context is required")
        raw, source_format = read_stored_upload(upload_root, upload_id, MAX_SOURCE_BYTES)
        validate_upload_bytes(raw, source_format)
        stored_settings = {
            "coordinateSystem": context.coordinate_system,
            "horizontalUnit": context.horizontal_unit,
            "verticalUnit": context.vertical_unit,
            "scaleFactor": str(context.scale_factor),
            "renderSettings": dict(settings or {}),
        }
        settings_json = _canonical_json(stored_settings)
        revision_id = str(uuid4())
        source_name = f"source.{source_format}"
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                project = db.execute("SELECT 1 FROM projects WHERE project_id = ?", (project_id,)).fetchone()
                if project is None:
                    raise ProjectNotFoundError(project_id)
                previous = db.execute(
                    "SELECT revision_id, sequence FROM revisions WHERE project_id = ? ORDER BY sequence DESC LIMIT 1",
                    (project_id,),
                ).fetchone()
                sequence = previous["sequence"] + 1 if previous else 1
                parent = previous["revision_id"] if previous else None
                descriptor = self._open_directory(project_id, "revisions", revision_id, create=True)
                try:
                    self._write_file(descriptor, source_name, raw)
                finally:
                    os.close(descriptor)
                db.execute(
                    """INSERT INTO revisions(
                        revision_id, project_id, sequence, parent_revision_id,
                        source_format, source_sha256, source_size, settings_json,
                        settings_sha256, algorithm_version
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        revision_id, project_id, sequence, parent, source_format,
                        _digest(raw), len(raw), settings_json,
                        _digest(settings_json.encode("utf-8")), algorithm_version,
                    ),
                )
                db.execute("COMMIT")
            except Exception:
                db.execute("ROLLBACK")
                try:
                    parent_fd = self._open_directory(project_id, "revisions")
                    try:
                        revision_fd = os.open(
                            revision_id, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd
                        )
                        try:
                            try:
                                os.unlink(source_name, dir_fd=revision_fd)
                            except FileNotFoundError:
                                pass
                        finally:
                            os.close(revision_fd)
                        os.rmdir(revision_id, dir_fd=parent_fd)
                    finally:
                        os.close(parent_fd)
                except OSError:
                    pass
                raise
        return self.get_revision(revision_id)

    def get_revision(self, revision_id: str) -> RevisionRecord:
        with self._db() as db:
            row = db.execute("SELECT * FROM revisions WHERE revision_id = ?", (_uuid(revision_id),)).fetchone()
        if row is None:
            raise ProjectNotFoundError(revision_id)
        record = RevisionRecord(**dict(row))
        if record.source_format not in {"txt", "csv", "kml"}:
            raise ProjectIntegrityError("Revision source format is invalid")
        try:
            _uuid(record.project_id)
            if record.parent_revision_id is not None:
                _uuid(record.parent_revision_id)
        except ProjectNotFoundError as exc:
            raise ProjectIntegrityError("Revision identifier is invalid") from exc
        if not 0 < record.source_size <= MAX_SOURCE_BYTES:
            raise ProjectIntegrityError("Revision source size is invalid")
        if _digest(record.settings_json.encode("utf-8")) != record.settings_sha256:
            raise ProjectIntegrityError("Revision settings checksum is invalid")
        return record

    def list_revisions(self, project_id: str) -> tuple[RevisionRecord, ...]:
        self.get_project(project_id)
        with self._db() as db:
            rows = db.execute(
                "SELECT revision_id FROM revisions WHERE project_id = ? ORDER BY sequence",
                (project_id,),
            ).fetchall()
        return tuple(self.get_revision(row["revision_id"]) for row in rows)

    def read_source(self, revision_id: str) -> bytes:
        revision = self.get_revision(revision_id)
        return self._read_file(
            (revision.project_id, "revisions", revision.revision_id),
            f"source.{revision.source_format}",
            MAX_SOURCE_BYTES,
            revision.source_sha256,
            revision.source_size,
        )

    def register_job(
        self,
        revision_id: str,
        job_id: str,
        *,
        request_settings: Mapping[str, object],
        status: str = "queued",
    ) -> ProjectJobRecord:
        revision = self.get_revision(revision_id)
        job_id = _uuid(job_id)
        if status not in JOB_STATUSES:
            raise ProjectStoreError("Job status is invalid")
        request_json = _canonical_json(dict(request_settings))
        request_sha256 = _digest(request_json.encode("utf-8"))
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                db.execute(
                    """INSERT INTO jobs(job_id, revision_id, request_json, request_sha256, status, algorithm_version)
                    VALUES (?, ?, ?, ?, ?, ?)""",
                    (job_id, revision_id, request_json, request_sha256, status, revision.algorithm_version),
                )
                db.execute("COMMIT")
            except Exception:
                db.execute("ROLLBACK")
                raise
        return self.get_job(job_id)

    def get_job(self, job_id: str) -> ProjectJobRecord:
        with self._db() as db:
            row = db.execute("SELECT * FROM jobs WHERE job_id = ?", (_uuid(job_id),)).fetchone()
        if row is None:
            raise ProjectNotFoundError(job_id)
        record = ProjectJobRecord(**dict(row))
        if _digest(record.request_json.encode("utf-8")) != record.request_sha256:
            raise ProjectIntegrityError("Job request checksum is invalid")
        if record.result_size is not None and not 0 < record.result_size <= MAX_RESULT_BYTES:
            raise ProjectIntegrityError("Job result size is invalid")
        return record

    def update_job_status(self, job_id: str, status: str) -> ProjectJobRecord:
        if status not in JOB_STATUSES:
            raise ProjectStoreError("Job status is invalid")
        current = self.get_job(job_id)
        if current.result_sha256 is not None and status != "succeeded":
            raise ProjectStoreError("Completed result status is immutable")
        with self._db() as db:
            db.execute("UPDATE jobs SET status = ? WHERE job_id = ?", (status, job_id))
        return self.get_job(job_id)

    def publish_result(self, job_id: str, result_bytes: bytes) -> ProjectJobRecord:
        if not isinstance(result_bytes, bytes) or not 0 < len(result_bytes) <= MAX_RESULT_BYTES:
            raise ProjectStoreError("Result must be 1 to 25 MiB of bytes")
        job = self.get_job(job_id)
        revision = self.get_revision(job.revision_id)
        if job.algorithm_version != revision.algorithm_version:
            raise ProjectIntegrityError("Job algorithm version differs from its source revision")
        result_name = f"{job_id}.dxf"
        write_started = False
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                state = db.execute("SELECT status, result_sha256 FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
                if state is None or state["status"] != "succeeded" or state["result_sha256"] is not None:
                    raise ProjectStoreError("Only a successful unpublished job can publish a result")
                descriptor = self._open_directory(
                    revision.project_id, "revisions", revision.revision_id, "results", create=True
                )
                try:
                    write_started = True
                    self._write_file(descriptor, result_name, result_bytes)
                finally:
                    os.close(descriptor)
                db.execute(
                    "UPDATE jobs SET result_sha256 = ?, result_size = ? WHERE job_id = ?",
                    (_digest(result_bytes), len(result_bytes), job_id),
                )
                db.execute("COMMIT")
            except Exception:
                db.execute("ROLLBACK")
                if write_started:
                    try:
                        result_fd = self._open_directory(
                            revision.project_id, "revisions", revision.revision_id, "results"
                        )
                        try:
                            os.unlink(result_name, dir_fd=result_fd)
                        finally:
                            os.close(result_fd)
                    except OSError:
                        pass
                raise
        return self.get_job(job_id)

    def read_result(self, job_id: str) -> bytes:
        job = self.get_job(job_id)
        if job.result_sha256 is None:
            raise ProjectStoreError("Job has no accepted result")
        revision = self.get_revision(job.revision_id)
        if job.algorithm_version != revision.algorithm_version:
            raise ProjectIntegrityError("Job algorithm version differs from its source revision")
        return self._read_file(
            (revision.project_id, "revisions", revision.revision_id, "results"),
            f"{job_id}.dxf",
            MAX_RESULT_BYTES,
            job.result_sha256,
            job.result_size,
        )
