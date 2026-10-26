"""Separate, versioned GEO AI project storage; no public access layer."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import stat
import time
from typing import Iterator, Mapping
import unicodedata
from uuid import UUID, uuid4

from autocad_assistance.services.survey_contract import SurveyContext
from autocad_assistance.services.uploads import (
    StoredUpload, read_stored_upload, remove_stored_upload, validate_upload_bytes,
)


MAX_SOURCE_BYTES = 10 * 1024 * 1024
MAX_RESULT_BYTES = 96 * 1024 * 1024
MAX_SETTINGS_BYTES = 64 * 1024
MAX_DECISION_BYTES = 1024 * 1024
MAX_DECISION_EVENTS_PER_REVISION = 2_000
MAX_LINE_EDIT_BYTES = 1024 * 1024
MAX_LINE_EDIT_EVENTS_PER_REVISION = 2_000
MAX_REFERENCE_DXF_BYTES = 25 * 1024 * 1024
JOB_STATUSES = frozenset({"queued", "running", "cancelling", "cancelled", "failed", "succeeded"})


class ProjectStoreError(ValueError):
    """Invalid project operation or metadata."""


class ProjectNotFoundError(LookupError):
    """Requested project, revision or job does not exist."""


class ProjectIntegrityError(IOError):
    """Stored bytes or path no longer match accepted metadata."""


class ResourceQuotaExceededError(ProjectStoreError):
    """A configured owner resource limit would be exceeded."""


class SubmissionConflictError(ProjectStoreError):
    """One idempotency key was reused for a different request."""


class DuplicateSubmissionError(ProjectStoreError):
    """A matching idempotent job has already been admitted."""

    def __init__(self, job_id: str) -> None:
        super().__init__("Submission already accepted")
        self.job_id = job_id


class LineDecisionConflictError(ProjectStoreError):
    """A stale version or reused request key conflicts with saved history."""


class LineEditConflictError(ProjectStoreError):
    """A stale line model or reused edit request key conflicts."""


class ReferenceConflictError(ProjectStoreError):
    """An archive request key was reused for different content."""


@dataclass(frozen=True)
class ResourceQuota:
    max_projects: int = 20
    max_uploads: int = 100
    max_revisions: int = 500
    max_jobs: int = 500
    max_total_bytes: int = 512 * 1024 * 1024
    max_references: int = 100
    max_reference_bytes: int = 256 * 1024 * 1024

    def __post_init__(self) -> None:
        if any(value <= 0 for value in (
            self.max_projects, self.max_uploads, self.max_revisions,
            self.max_jobs, self.max_total_bytes, self.max_references,
            self.max_reference_bytes,
        )):
            raise ValueError("Resource quota limits must be positive")


@dataclass(frozen=True)
class ProjectRecord:
    project_id: str
    name: str
    created_at: str
    owner_id: str | None


@dataclass(frozen=True)
class UploadOwnerRecord:
    upload_id: str
    owner_id: str
    sha256: str
    stored_format: str
    size_bytes: int
    created_at: int | None
    expires_at: int | None
    state: str


@dataclass(frozen=True)
class UploadCleanupReport:
    candidates: tuple[str, ...]
    removed: tuple[str, ...]
    failed: tuple[str, ...]


@dataclass(frozen=True)
class CleanupEventRecord:
    event_id: int
    upload_id: str
    owner_id: str
    outcome: str
    recorded_at: int


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
    retry_of: str | None


@dataclass(frozen=True)
class LineDecisionRecord:
    event_id: str
    revision_id: str
    group_code: str
    version: int
    request_id: str
    action: str
    snapshot_json: str
    author_id: str
    created_at: str


@dataclass(frozen=True)
class LineEditRecord:
    event_id: str
    revision_id: str
    version: int
    request_id: str
    request_sha256: str
    operation_json: str
    model_json: str
    model_sha256: str
    author_id: str
    created_at: str


@dataclass(frozen=True)
class ReferenceRecord:
    entry_id: str
    revision_id: str
    project_id: str
    request_id: str
    request_sha256: str
    source_sha256: str
    reference_sha256: str
    reference_size: int
    metadata_json: str
    corrections_json: str
    validation_json: str
    entry_sha256: str
    author_id: str
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

    def __init__(
        self, root: str | Path, *, quota: ResourceQuota | None = None,
        upload_retention_days: int | None = None,
    ) -> None:
        if upload_retention_days is not None and upload_retention_days <= 0:
            raise ValueError("upload_retention_days must be positive")
        self.quota = quota or ResourceQuota()
        self.upload_retention_days = upload_retention_days
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.files_root = self.root / "projects"
        self.files_root.mkdir(exist_ok=True, mode=0o700)
        self.db_path = self.root / "projects.sqlite3"
        with self._db() as db:
            current = db.execute("PRAGMA user_version").fetchone()[0]
            if current not in (0, 1, 2, 3, 4, 5, 6, 7, 8):
                raise ProjectStoreError(f"Unsupported project schema version: {current}")
            if current == 0:
                db.executescript(
                """
                CREATE TABLE IF NOT EXISTS projects (
                    project_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    owner_id TEXT
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
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    retry_of TEXT
                );
                CREATE TABLE IF NOT EXISTS upload_owners (
                    upload_id TEXT PRIMARY KEY,
                    owner_id TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    stored_format TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    created_at INTEGER,
                    expires_at INTEGER,
                    state TEXT NOT NULL DEFAULT 'active'
                );
                CREATE TABLE IF NOT EXISTS cleanup_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    upload_id TEXT NOT NULL,
                    owner_id TEXT NOT NULL,
                    outcome TEXT NOT NULL CHECK(outcome IN ('removed','failed')),
                    recorded_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS job_submissions (
                    request_id TEXT PRIMARY KEY,
                    owner_id TEXT NOT NULL,
                    revision_id TEXT NOT NULL REFERENCES revisions(revision_id),
                    request_sha256 TEXT NOT NULL,
                    job_id TEXT NOT NULL UNIQUE REFERENCES jobs(job_id),
                    created_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS line_decision_events (
                    event_id TEXT PRIMARY KEY,
                    revision_id TEXT NOT NULL REFERENCES revisions(revision_id),
                    group_code TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    request_id TEXT NOT NULL UNIQUE,
                    request_sha256 TEXT NOT NULL,
                    action TEXT NOT NULL CHECK(action IN ('A','B','skip','manual')),
                    snapshot_json TEXT NOT NULL,
                    author_id TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(revision_id, group_code, version)
                );
                CREATE INDEX IF NOT EXISTS line_decision_revision_group
                    ON line_decision_events(revision_id, group_code, version);
                CREATE TABLE IF NOT EXISTS line_edit_events (
                    event_id TEXT PRIMARY KEY,
                    revision_id TEXT NOT NULL REFERENCES revisions(revision_id),
                    version INTEGER NOT NULL,
                    request_id TEXT NOT NULL UNIQUE,
                    request_sha256 TEXT NOT NULL,
                    operation_json TEXT NOT NULL,
                    model_json TEXT NOT NULL,
                    model_sha256 TEXT NOT NULL,
                    author_id TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(revision_id, version)
                );
                CREATE INDEX IF NOT EXISTS line_edit_revision_version
                    ON line_edit_events(revision_id, version);
                CREATE TABLE IF NOT EXISTS reference_entries (
                    entry_id TEXT PRIMARY KEY,
                    revision_id TEXT NOT NULL REFERENCES revisions(revision_id),
                    project_id TEXT NOT NULL REFERENCES projects(project_id),
                    request_id TEXT NOT NULL UNIQUE,
                    request_sha256 TEXT NOT NULL,
                    source_sha256 TEXT NOT NULL,
                    reference_sha256 TEXT NOT NULL,
                    reference_size INTEGER NOT NULL,
                    metadata_json TEXT NOT NULL,
                    corrections_json TEXT NOT NULL,
                    validation_json TEXT NOT NULL,
                    entry_sha256 TEXT NOT NULL,
                    author_id TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS reference_project_created
                    ON reference_entries(project_id, created_at);
                PRAGMA user_version = 8;
                """
                )
            elif current == 1:
                db.execute("BEGIN IMMEDIATE")
                try:
                    db.execute("ALTER TABLE projects ADD COLUMN owner_id TEXT")
                    db.execute(
                        """CREATE TABLE upload_owners (
                            upload_id TEXT PRIMARY KEY,
                            owner_id TEXT NOT NULL,
                            sha256 TEXT NOT NULL,
                            stored_format TEXT NOT NULL,
                            size_bytes INTEGER NOT NULL
                        )"""
                    )
                    db.execute("PRAGMA user_version = 2")
                    db.execute("COMMIT")
                    current = 2
                except Exception:
                    db.execute("ROLLBACK")
                    raise
            if current == 2:
                db.execute("BEGIN IMMEDIATE")
                try:
                    db.execute("ALTER TABLE upload_owners ADD COLUMN created_at INTEGER")
                    db.execute("ALTER TABLE upload_owners ADD COLUMN expires_at INTEGER")
                    db.execute("ALTER TABLE upload_owners ADD COLUMN state TEXT NOT NULL DEFAULT 'active'")
                    db.execute("PRAGMA user_version = 3")
                    db.execute("COMMIT")
                    current = 3
                except Exception:
                    db.execute("ROLLBACK")
                    raise
            if current == 3:
                db.execute("BEGIN IMMEDIATE")
                try:
                    db.execute("""CREATE TABLE cleanup_events (
                        event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        upload_id TEXT NOT NULL,
                        owner_id TEXT NOT NULL,
                        outcome TEXT NOT NULL CHECK(outcome IN ('removed','failed')),
                        recorded_at INTEGER NOT NULL
                    )""")
                    db.execute("PRAGMA user_version = 4")
                    db.execute("COMMIT")
                    current = 4
                except Exception:
                    db.execute("ROLLBACK")
                    raise
            if current == 4:
                db.execute("BEGIN IMMEDIATE")
                try:
                    tables = {row[0] for row in db.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )}
                    if "jobs" in tables:
                        db.execute("ALTER TABLE jobs ADD COLUMN retry_of TEXT")
                    if {"jobs", "revisions"}.issubset(tables):
                        db.execute("""CREATE TABLE job_submissions (
                            request_id TEXT PRIMARY KEY,
                            owner_id TEXT NOT NULL,
                            revision_id TEXT NOT NULL REFERENCES revisions(revision_id),
                            request_sha256 TEXT NOT NULL,
                            job_id TEXT NOT NULL UNIQUE REFERENCES jobs(job_id),
                            created_at INTEGER NOT NULL
                        )""")
                    db.execute("PRAGMA user_version = 5")
                    db.execute("COMMIT")
                    current = 5
                except Exception:
                    db.execute("ROLLBACK")
                    raise
            if current == 5:
                db.execute("BEGIN IMMEDIATE")
                try:
                    db.execute("""CREATE TABLE line_decision_events (
                        event_id TEXT PRIMARY KEY,
                        revision_id TEXT NOT NULL REFERENCES revisions(revision_id),
                        group_code TEXT NOT NULL,
                        version INTEGER NOT NULL,
                        request_id TEXT NOT NULL UNIQUE,
                        request_sha256 TEXT NOT NULL,
                        action TEXT NOT NULL CHECK(action IN ('A','B','skip','manual')),
                        snapshot_json TEXT NOT NULL,
                        author_id TEXT NOT NULL,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(revision_id, group_code, version)
                    )""")
                    db.execute("""CREATE INDEX line_decision_revision_group
                        ON line_decision_events(revision_id, group_code, version)""")
                    db.execute("PRAGMA user_version = 6")
                    db.execute("COMMIT")
                    current = 6
                except Exception:
                    db.execute("ROLLBACK")
                    raise
            if current == 6:
                db.execute("BEGIN IMMEDIATE")
                try:
                    db.execute("""CREATE TABLE line_edit_events (
                        event_id TEXT PRIMARY KEY,
                        revision_id TEXT NOT NULL REFERENCES revisions(revision_id),
                        version INTEGER NOT NULL,
                        request_id TEXT NOT NULL UNIQUE,
                        request_sha256 TEXT NOT NULL,
                        operation_json TEXT NOT NULL,
                        model_json TEXT NOT NULL,
                        model_sha256 TEXT NOT NULL,
                        author_id TEXT NOT NULL,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(revision_id, version)
                    )""")
                    db.execute("""CREATE INDEX line_edit_revision_version
                        ON line_edit_events(revision_id, version)""")
                    db.execute("PRAGMA user_version = 7")
                    db.execute("COMMIT")
                    current = 7
                except Exception:
                    db.execute("ROLLBACK")
                    raise
            if current == 7:
                db.execute("BEGIN IMMEDIATE")
                try:
                    db.execute("""CREATE TABLE reference_entries (
                        entry_id TEXT PRIMARY KEY,
                        revision_id TEXT NOT NULL REFERENCES revisions(revision_id),
                        project_id TEXT NOT NULL REFERENCES projects(project_id),
                        request_id TEXT NOT NULL UNIQUE,
                        request_sha256 TEXT NOT NULL,
                        source_sha256 TEXT NOT NULL,
                        reference_sha256 TEXT NOT NULL,
                        reference_size INTEGER NOT NULL,
                        metadata_json TEXT NOT NULL,
                        corrections_json TEXT NOT NULL,
                        validation_json TEXT NOT NULL,
                        entry_sha256 TEXT NOT NULL,
                        author_id TEXT NOT NULL,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )""")
                    db.execute("""CREATE INDEX reference_project_created
                        ON reference_entries(project_id, created_at)""")
                    db.execute("PRAGMA user_version = 8")
                    db.execute("COMMIT")
                except Exception:
                    db.execute("ROLLBACK")
                    raise

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

    def _require_quota(
        self, db: sqlite3.Connection, owner_id: str | None,
        *, projects: int = 0, uploads: int = 0, revisions: int = 0,
        jobs: int = 0, references: int = 0, bytes_added: int = 0,
    ) -> None:
        if owner_id is None:
            return  # Historical local-only projects have no authenticated owner.
        counts = (
            db.execute("SELECT count(*) FROM projects WHERE owner_id=?", (owner_id,)).fetchone()[0],
            db.execute("SELECT count(*) FROM upload_owners WHERE owner_id=?", (owner_id,)).fetchone()[0],
            db.execute("""SELECT count(*) FROM revisions r JOIN projects p
                ON p.project_id=r.project_id WHERE p.owner_id=?""", (owner_id,)).fetchone()[0],
            db.execute("""SELECT count(*) FROM jobs j JOIN revisions r ON r.revision_id=j.revision_id
                JOIN projects p ON p.project_id=r.project_id WHERE p.owner_id=?""", (owner_id,)).fetchone()[0],
            db.execute("""SELECT count(*) FROM reference_entries e JOIN projects p
                ON p.project_id=e.project_id WHERE p.owner_id=?""", (owner_id,)).fetchone()[0],
        )
        limits = (
            self.quota.max_projects, self.quota.max_uploads,
            self.quota.max_revisions, self.quota.max_jobs, self.quota.max_references,
        )
        if any(count + change > limit for count, change, limit in zip(
            counts, (projects, uploads, revisions, jobs, references), limits
        )):
            raise ResourceQuotaExceededError("Owner resource count quota exceeded")
        upload_bytes = db.execute(
            "SELECT COALESCE(sum(size_bytes),0) FROM upload_owners WHERE owner_id=?", (owner_id,)
        ).fetchone()[0]
        revision_bytes = db.execute("""SELECT COALESCE(sum(r.source_size),0) FROM revisions r
            JOIN projects p ON p.project_id=r.project_id WHERE p.owner_id=?""", (owner_id,)).fetchone()[0]
        result_bytes = db.execute("""SELECT COALESCE(sum(j.result_size),0) FROM jobs j
            JOIN revisions r ON r.revision_id=j.revision_id
            JOIN projects p ON p.project_id=r.project_id WHERE p.owner_id=?""", (owner_id,)).fetchone()[0]
        reference_bytes = db.execute("""SELECT COALESCE(sum(e.reference_size),0) FROM reference_entries e
            JOIN projects p ON p.project_id=e.project_id WHERE p.owner_id=?""", (owner_id,)).fetchone()[0]
        if reference_bytes + (bytes_added if references else 0) > self.quota.max_reference_bytes:
            raise ResourceQuotaExceededError("Owner reference byte quota exceeded")
        if upload_bytes + revision_bytes + result_bytes + reference_bytes + bytes_added > self.quota.max_total_bytes:
            raise ResourceQuotaExceededError("Owner byte quota exceeded")

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

    def create_project(self, name: str, *, owner_id: str | None = None) -> ProjectRecord:
        name = _label(name, name="Project name", limit=200)
        if owner_id is not None:
            owner_id = _uuid(owner_id)
        project_id = str(uuid4())
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                self._require_quota(db, owner_id, projects=1)
                descriptor = self._open_directory(project_id, create=True)
                os.close(descriptor)
                db.execute(
                    "INSERT INTO projects(project_id, name, owner_id) VALUES (?, ?, ?)",
                    (project_id, name, owner_id),
                )
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

    def create_owned_project(self, owner_id: str, name: str) -> ProjectRecord:
        return self.create_project(name, owner_id=_uuid(owner_id))

    def register_upload_owner(self, owner_id: str, stored: StoredUpload) -> UploadOwnerRecord:
        owner_id = _uuid(owner_id)
        upload_id = _uuid(stored.upload_id)
        if stored.format not in {"txt", "csv", "kml"} or not 0 < stored.size_bytes <= MAX_SOURCE_BYTES:
            raise ProjectStoreError("Stored upload metadata is invalid")
        created_at = int(time.time())
        expires_at = (
            created_at + self.upload_retention_days * 86400
            if self.upload_retention_days is not None else None
        )
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                self._require_quota(db, owner_id, uploads=1, bytes_added=stored.size_bytes)
                db.execute(
                    """INSERT INTO upload_owners(
                        upload_id,owner_id,sha256,stored_format,size_bytes,created_at,expires_at,state
                    ) VALUES (?,?,?,?,?,?,?,'active')""",
                    (upload_id, owner_id, stored.sha256, stored.format, stored.size_bytes,
                     created_at, expires_at),
                )
                db.execute("COMMIT")
            except sqlite3.IntegrityError as exc:
                db.execute("ROLLBACK")
                raise ProjectStoreError("Upload already has an owner") from exc
            except Exception:
                db.execute("ROLLBACK")
                raise
        return self.assert_upload_owner(owner_id, upload_id)

    def assert_upload_owner(self, owner_id: str, upload_id: str) -> UploadOwnerRecord:
        with self._db() as db:
            row = db.execute(
                """SELECT * FROM upload_owners WHERE upload_id=? AND owner_id=?
                AND state='active' AND (expires_at IS NULL OR expires_at > ?)""",
                (_uuid(upload_id), _uuid(owner_id), int(time.time())),
            ).fetchone()
        if row is None:
            raise ProjectNotFoundError(upload_id)
        return UploadOwnerRecord(**dict(row))

    def read_upload_for(
        self, owner_id: str, upload_root: str | Path, upload_id: str,
    ) -> tuple[bytes, str]:
        owned = self.assert_upload_owner(owner_id, upload_id)
        raw, stored_format = read_stored_upload(upload_root, upload_id, MAX_SOURCE_BYTES)
        if (
            stored_format != owned.stored_format or len(raw) != owned.size_bytes
            or _digest(raw) != owned.sha256
        ):
            raise ProjectIntegrityError("Upload checksum or size is invalid")
        return raw, stored_format

    def expired_uploads(self, *, now: int | None = None, limit: int = 100) -> tuple[UploadOwnerRecord, ...]:
        if not 1 <= limit <= 100:
            raise ValueError("cleanup limit must be between 1 and 100")
        cutoff = int(time.time()) if now is None else int(now)
        with self._db() as db:
            rows = db.execute(
                """SELECT * FROM upload_owners WHERE expires_at IS NOT NULL
                AND expires_at <= ? AND state IN ('active','deleting')
                ORDER BY expires_at,upload_id LIMIT ?""", (cutoff, limit),
            ).fetchall()
        return tuple(UploadOwnerRecord(**dict(row)) for row in rows)

    def cleanup_expired_uploads(
        self, upload_root: str | Path, *, now: int | None = None,
        limit: int = 100, apply: bool = False,
    ) -> UploadCleanupReport:
        cutoff = int(time.time()) if now is None else int(now)
        candidates = self.expired_uploads(now=cutoff, limit=limit)
        if not apply:
            return UploadCleanupReport(tuple(item.upload_id for item in candidates), (), ())
        removed: list[str] = []
        failed: list[str] = []
        for item in candidates:
            with self._db() as db:
                db.execute("BEGIN IMMEDIATE")
                row = db.execute(
                    """SELECT state,expires_at FROM upload_owners WHERE upload_id=?""",
                    (item.upload_id,),
                ).fetchone()
                if row is None or row["expires_at"] is None or row["expires_at"] > cutoff:
                    db.execute("ROLLBACK")
                    continue
                db.execute(
                    "UPDATE upload_owners SET state='deleting' WHERE upload_id=?",
                    (item.upload_id,),
                )
                db.execute("COMMIT")
            try:
                remove_stored_upload(upload_root, item.upload_id, item.stored_format)
            except (OSError, ValueError):
                with self._db() as db:
                    db.execute(
                        """INSERT INTO cleanup_events(upload_id,owner_id,outcome,recorded_at)
                        VALUES (?,?,?,?)""",
                        (item.upload_id, item.owner_id, "failed", int(time.time())),
                    )
                failed.append(item.upload_id)
                continue
            with self._db() as db:
                db.execute("BEGIN IMMEDIATE")
                db.execute("DELETE FROM upload_owners WHERE upload_id=? AND state='deleting'", (item.upload_id,))
                db.execute(
                    """INSERT INTO cleanup_events(upload_id,owner_id,outcome,recorded_at)
                    VALUES (?,?,?,?)""",
                    (item.upload_id, item.owner_id, "removed", int(time.time())),
                )
                db.execute("COMMIT")
            removed.append(item.upload_id)
        return UploadCleanupReport(tuple(item.upload_id for item in candidates), tuple(removed), tuple(failed))

    def cleanup_journal(self, *, limit: int = 100) -> tuple[CleanupEventRecord, ...]:
        if not 1 <= limit <= 100:
            raise ValueError("journal limit must be between 1 and 100")
        with self._db() as db:
            rows = db.execute(
                "SELECT * FROM cleanup_events ORDER BY event_id DESC LIMIT ?", (limit,)
            ).fetchall()
        return tuple(CleanupEventRecord(**dict(row)) for row in rows)

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

    def list_projects_for(self, owner_id: str) -> tuple[ProjectRecord, ...]:
        with self._db() as db:
            rows = db.execute(
                "SELECT * FROM projects WHERE owner_id = ? ORDER BY created_at, project_id",
                (_uuid(owner_id),),
            ).fetchall()
        return tuple(ProjectRecord(**dict(row)) for row in rows)

    def assert_project_owner(self, owner_id: str, project_id: str) -> ProjectRecord:
        with self._db() as db:
            row = db.execute(
                "SELECT * FROM projects WHERE project_id = ? AND owner_id = ?",
                (_uuid(project_id), _uuid(owner_id)),
            ).fetchone()
        if row is None:
            raise ProjectNotFoundError(project_id)
        return ProjectRecord(**dict(row))

    def add_revision(
        self,
        project_id: str,
        upload_root: str | Path,
        upload_id: str,
        *,
        context: SurveyContext,
        settings: Mapping[str, object] | None,
        algorithm_version: str,
        expected_source_sha256: str | None = None,
        expected_source_format: str | None = None,
    ) -> RevisionRecord:
        project_id = _uuid(project_id)
        algorithm_version = _label(algorithm_version, name="Algorithm version", limit=128)
        if not isinstance(context, SurveyContext):
            raise ProjectStoreError("Explicit survey context is required")
        raw, source_format = read_stored_upload(upload_root, upload_id, MAX_SOURCE_BYTES)
        if expected_source_sha256 is not None and (
            _digest(raw) != expected_source_sha256 or source_format != expected_source_format
        ):
            raise ProjectIntegrityError("Upload changed before source snapshot")
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
                project = db.execute("SELECT owner_id FROM projects WHERE project_id = ?", (project_id,)).fetchone()
                if project is None:
                    raise ProjectNotFoundError(project_id)
                self._require_quota(db, project["owner_id"], revisions=1, bytes_added=len(raw))
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

    def add_revision_for(
        self, owner_id: str, project_id: str, upload_root: str | Path, upload_id: str,
        *, context: SurveyContext, settings: Mapping[str, object] | None, algorithm_version: str,
    ) -> RevisionRecord:
        self.assert_project_owner(owner_id, project_id)
        owned = self.assert_upload_owner(owner_id, upload_id)
        raw, stored_format = read_stored_upload(upload_root, upload_id, MAX_SOURCE_BYTES)
        if (
            stored_format != owned.stored_format or len(raw) != owned.size_bytes
            or _digest(raw) != owned.sha256
        ):
            raise ProjectIntegrityError("Upload checksum or size is invalid")
        return self.add_revision(
            project_id, upload_root, upload_id, context=context,
            settings=settings, algorithm_version=algorithm_version,
            expected_source_sha256=owned.sha256,
            expected_source_format=owned.stored_format,
        )

    def list_revisions(self, project_id: str) -> tuple[RevisionRecord, ...]:
        self.get_project(project_id)
        with self._db() as db:
            rows = db.execute(
                "SELECT revision_id FROM revisions WHERE project_id = ? ORDER BY sequence",
                (project_id,),
            ).fetchall()
        return tuple(self.get_revision(row["revision_id"]) for row in rows)

    def list_revisions_for(self, owner_id: str, project_id: str) -> tuple[RevisionRecord, ...]:
        self.assert_project_owner(owner_id, project_id)
        return self.list_revisions(project_id)

    def read_source(self, revision_id: str) -> bytes:
        revision = self.get_revision(revision_id)
        return self._read_file(
            (revision.project_id, "revisions", revision.revision_id),
            f"source.{revision.source_format}",
            MAX_SOURCE_BYTES,
            revision.source_sha256,
            revision.source_size,
        )

    def assert_revision_owner(self, owner_id: str, revision_id: str) -> RevisionRecord:
        with self._db() as db:
            row = db.execute(
                """SELECT r.revision_id FROM revisions r JOIN projects p ON p.project_id = r.project_id
                WHERE r.revision_id = ? AND p.owner_id = ?""",
                (_uuid(revision_id), _uuid(owner_id)),
            ).fetchone()
        if row is None:
            raise ProjectNotFoundError(revision_id)
        return self.get_revision(row["revision_id"])

    def read_source_for(self, owner_id: str, project_id: str, revision_id: str) -> bytes:
        self.assert_project_owner(owner_id, project_id)
        revision = self.assert_revision_owner(owner_id, revision_id)
        if revision.project_id != project_id:
            raise ProjectNotFoundError(revision_id)
        return self.read_source(revision_id)

    @staticmethod
    def _reference_record(row: sqlite3.Row) -> ReferenceRecord:
        if ProjectStore._reference_seal(row) != row["entry_sha256"]:
            raise ProjectIntegrityError("Reference metadata checksum is invalid")
        return ReferenceRecord(**{field: row[field] for field in ReferenceRecord.__dataclass_fields__})

    @staticmethod
    def _reference_seal(values: Mapping[str, object]) -> str:
        fields = ("entry_id", "revision_id", "project_id", "request_id", "request_sha256",
                  "source_sha256", "reference_sha256", "reference_size", "metadata_json",
                  "corrections_json", "validation_json", "author_id", "created_at")
        rendered = json.dumps({field: values[field] for field in fields},
                              ensure_ascii=False, sort_keys=True,
                              separators=(",", ":"), allow_nan=False)
        return _digest(rendered.encode("utf-8"))

    @staticmethod
    def _reference_request_hash(revision_id: str, reference_sha256: str,
                                metadata_json: str) -> str:
        request_json = _canonical_json({"revisionId": revision_id,
                                        "referenceSha256": reference_sha256,
                                        "metadata": json.loads(metadata_json)})
        return _digest(request_json.encode("utf-8"))

    def lookup_reference_for(
        self, owner_id: str, revision_id: str, request_id: str,
        *, reference_sha256: str, metadata: Mapping[str, object],
    ) -> ReferenceRecord | None:
        owner_id, revision_id, request_id = _uuid(owner_id), _uuid(revision_id), _uuid(request_id)
        self.assert_revision_owner(owner_id, revision_id)
        metadata_json = _canonical_json(dict(metadata))
        request_hash = self._reference_request_hash(revision_id, reference_sha256, metadata_json)
        with self._db() as db:
            row = db.execute("SELECT * FROM reference_entries WHERE request_id=?", (request_id,)).fetchone()
        if row is None:
            return None
        if (row["revision_id"], row["author_id"], row["request_sha256"]) != (
            revision_id, owner_id, request_hash,
        ):
            raise ReferenceConflictError("Reference request key was reused")
        return self._reference_record(row)

    def create_reference_for(
        self, owner_id: str, revision_id: str, request_id: str, raw: bytes,
        *, metadata: Mapping[str, object], corrections: Mapping[str, object],
        validation: Mapping[str, object],
    ) -> ReferenceRecord:
        owner_id, revision_id, request_id = _uuid(owner_id), _uuid(revision_id), _uuid(request_id)
        if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_REFERENCE_DXF_BYTES:
            raise ProjectStoreError("Reference DXF size is invalid")
        metadata_json = _canonical_json(dict(metadata))
        corrections_json = _canonical_json(dict(corrections))
        validation_json = _canonical_json(dict(validation))
        reference_hash = _digest(raw)
        request_hash = self._reference_request_hash(revision_id, reference_hash, metadata_json)
        entry_id = str(uuid4())
        directory_fd: int | None = None
        filename = f"{entry_id}.dxf"
        wrote_file = False
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                revision = db.execute("""SELECT r.project_id,r.source_sha256 FROM revisions r
                    JOIN projects p ON p.project_id=r.project_id
                    WHERE r.revision_id=? AND p.owner_id=?""", (revision_id, owner_id)).fetchone()
                if revision is None:
                    raise ProjectNotFoundError(revision_id)
                existing = db.execute("SELECT * FROM reference_entries WHERE request_id=?",
                                      (request_id,)).fetchone()
                if existing is not None:
                    if (existing["revision_id"], existing["author_id"], existing["request_sha256"]) != (
                        revision_id, owner_id, request_hash,
                    ):
                        raise ReferenceConflictError("Reference request key was reused")
                    db.execute("COMMIT")
                    return self._reference_record(existing)
                self._require_quota(db, owner_id, references=1, bytes_added=len(raw))
                directory_fd = self._open_directory(revision["project_id"], "references", create=True)
                wrote_file = True
                self._write_file(directory_fd, filename, raw)
                created_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                values = {
                    "entry_id": entry_id, "revision_id": revision_id,
                    "project_id": revision["project_id"], "request_id": request_id,
                    "request_sha256": request_hash, "source_sha256": revision["source_sha256"],
                    "reference_sha256": reference_hash, "reference_size": len(raw),
                    "metadata_json": metadata_json, "corrections_json": corrections_json,
                    "validation_json": validation_json, "author_id": owner_id,
                    "created_at": created_at,
                }
                seal = self._reference_seal(values)
                db.execute("""INSERT INTO reference_entries
                    (entry_id,revision_id,project_id,request_id,request_sha256,source_sha256,
                     reference_sha256,reference_size,metadata_json,corrections_json,
                     validation_json,entry_sha256,author_id,created_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (entry_id, revision_id, revision["project_id"], request_id, request_hash,
                     revision["source_sha256"], reference_hash, len(raw), metadata_json,
                     corrections_json, validation_json, seal, owner_id, created_at))
                row = db.execute("SELECT * FROM reference_entries WHERE entry_id=?",
                                 (entry_id,)).fetchone()
                db.execute("COMMIT")
                return self._reference_record(row)
            except Exception:
                db.execute("ROLLBACK")
                if wrote_file and directory_fd is not None:
                    try:
                        os.unlink(filename, dir_fd=directory_fd)
                        os.fsync(directory_fd)
                    except OSError:
                        pass
                raise
            finally:
                if directory_fd is not None:
                    os.close(directory_fd)

    def get_reference_for(self, owner_id: str, entry_id: str) -> ReferenceRecord:
        owner_id, entry_id = _uuid(owner_id), _uuid(entry_id)
        with self._db() as db:
            row = db.execute("""SELECT e.* FROM reference_entries e JOIN projects p
                ON p.project_id=e.project_id WHERE e.entry_id=? AND p.owner_id=?""",
                (entry_id, owner_id)).fetchone()
        if row is None:
            raise ProjectNotFoundError(entry_id)
        return self._reference_record(row)

    def list_references_for(
        self, owner_id: str, project_id: str, *, page: int = 1, page_size: int = 20,
    ) -> tuple[tuple[ReferenceRecord, ...], int]:
        owner_id, project_id = _uuid(owner_id), _uuid(project_id)
        self.assert_project_owner(owner_id, project_id)
        if page < 1 or not 1 <= page_size <= 50:
            raise ProjectStoreError("Reference page is invalid")
        with self._db() as db:
            total = db.execute("SELECT COUNT(*) FROM reference_entries WHERE project_id=?",
                               (project_id,)).fetchone()[0]
            rows = db.execute("""SELECT * FROM reference_entries WHERE project_id=?
                ORDER BY created_at DESC,entry_id DESC LIMIT ? OFFSET ?""",
                (project_id, page_size, (page - 1) * page_size))
            return tuple(self._reference_record(row) for row in rows), total

    def read_reference_for(self, owner_id: str, entry_id: str) -> bytes:
        record = self.get_reference_for(owner_id, entry_id)
        revision = self.assert_revision_owner(owner_id, record.revision_id)
        if revision.project_id != record.project_id or revision.source_sha256 != record.source_sha256:
            raise ProjectIntegrityError("Reference source provenance changed")
        self.read_source_for(owner_id, record.project_id, record.revision_id)
        return self._read_file((record.project_id, "references"), f"{record.entry_id}.dxf",
                               MAX_REFERENCE_DXF_BYTES, record.reference_sha256,
                               record.reference_size)

    @staticmethod
    def _line_decision(row: sqlite3.Row) -> LineDecisionRecord:
        return LineDecisionRecord(**{field: row[field] for field in LineDecisionRecord.__dataclass_fields__})

    def list_line_decisions_for(
        self, owner_id: str, revision_id: str, group_code: str | None = None,
        *, offset: int = 0, limit: int | None = None,
    ) -> tuple[LineDecisionRecord, ...]:
        owner_id, revision_id = _uuid(owner_id), _uuid(revision_id)
        self.assert_revision_owner(owner_id, revision_id)
        query = """SELECT event_id,revision_id,group_code,version,request_id,action,
            snapshot_json,author_id,created_at FROM line_decision_events
            WHERE revision_id=?"""
        params: tuple[object, ...] = (revision_id,)
        if group_code is not None:
            query += " AND group_code=?"
            params += (group_code,)
        query += " ORDER BY group_code,version"
        if limit is not None:
            if not 1 <= limit <= 50 or offset < 0:
                raise ProjectStoreError("Decision page is invalid")
            query += " LIMIT ? OFFSET ?"
            params += (limit, offset)
        with self._db() as db:
            return tuple(self._line_decision(row) for row in db.execute(query, params))

    def latest_line_decisions_for(
        self, owner_id: str, revision_id: str,
    ) -> tuple[LineDecisionRecord, ...]:
        owner_id, revision_id = _uuid(owner_id), _uuid(revision_id)
        self.assert_revision_owner(owner_id, revision_id)
        with self._db() as db:
            rows = db.execute("""SELECT e.event_id,e.revision_id,e.group_code,e.version,
                e.request_id,e.action,e.snapshot_json,e.author_id,e.created_at
                FROM line_decision_events e WHERE e.revision_id=? AND e.version=(
                    SELECT MAX(i.version) FROM line_decision_events i
                    WHERE i.revision_id=e.revision_id AND i.group_code=e.group_code)
                ORDER BY e.group_code""", (revision_id,))
            return tuple(self._line_decision(row) for row in rows)

    def count_line_decisions_for(self, owner_id: str, revision_id: str) -> int:
        owner_id, revision_id = _uuid(owner_id), _uuid(revision_id)
        self.assert_revision_owner(owner_id, revision_id)
        with self._db() as db:
            return db.execute("SELECT COUNT(*) FROM line_decision_events WHERE revision_id=?",
                              (revision_id,)).fetchone()[0]

    def record_line_decision_for(
        self, owner_id: str, revision_id: str, group_code: str,
        *, expected_version: int, request_id: str, action: str,
        snapshot: Mapping[str, object],
    ) -> LineDecisionRecord:
        owner_id, revision_id, request_id = _uuid(owner_id), _uuid(revision_id), _uuid(request_id)
        if not isinstance(group_code, str) or not 1 <= len(group_code) <= 64 or "/" in group_code:
            raise ProjectStoreError("Line group code is invalid")
        if action not in {"A", "B", "skip", "manual"} or type(expected_version) is not int or expected_version < 0:
            raise ProjectStoreError("Line decision request is invalid")
        try:
            snapshot_json = json.dumps(snapshot, sort_keys=True, separators=(",", ":"),
                                       ensure_ascii=False, allow_nan=False)
            request_json = json.dumps({"revisionId": revision_id, "groupCode": group_code,
                                       "expectedVersion": expected_version, "action": action,
                                       "snapshot": snapshot}, sort_keys=True,
                                      separators=(",", ":"), ensure_ascii=False, allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise ProjectStoreError("Line decision snapshot is invalid") from exc
        if len(snapshot_json.encode("utf-8")) > MAX_DECISION_BYTES:
            raise ProjectStoreError("Line decision snapshot is too large")
        request_hash = _digest(request_json.encode("utf-8"))
        fields = "event_id,revision_id,group_code,version,request_id,action,snapshot_json,author_id,created_at"
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                owned = db.execute("""SELECT 1 FROM revisions r JOIN projects p
                    ON p.project_id=r.project_id WHERE r.revision_id=? AND p.owner_id=?""",
                    (revision_id, owner_id)).fetchone()
                if owned is None:
                    raise ProjectNotFoundError(revision_id)
                existing = db.execute(f"SELECT {fields},request_sha256 FROM line_decision_events WHERE request_id=?",
                                      (request_id,)).fetchone()
                if existing is not None:
                    if (existing["revision_id"], existing["author_id"], existing["request_sha256"]) != (
                        revision_id, owner_id, request_hash,
                    ):
                        raise LineDecisionConflictError("Decision request key was reused")
                    db.execute("COMMIT")
                    return self._line_decision(existing)
                current = db.execute(f"""SELECT {fields} FROM line_decision_events
                    WHERE revision_id=? AND group_code=? ORDER BY version DESC LIMIT 1""",
                    (revision_id, group_code)).fetchone()
                version = current["version"] if current is not None else 0
                if version != expected_version:
                    raise LineDecisionConflictError("Decision version changed; reload candidates")
                count = db.execute("SELECT COUNT(*) FROM line_decision_events WHERE revision_id=?",
                                   (revision_id,)).fetchone()[0]
                if count >= MAX_DECISION_EVENTS_PER_REVISION:
                    raise ResourceQuotaExceededError("Revision decision history limit exceeded")
                event_id = str(uuid4())
                db.execute("""INSERT INTO line_decision_events
                    (event_id,revision_id,group_code,version,request_id,request_sha256,action,snapshot_json,author_id)
                    VALUES (?,?,?,?,?,?,?,?,?)""", (event_id, revision_id, group_code, version + 1,
                    request_id, request_hash, action, snapshot_json, owner_id))
                row = db.execute(f"SELECT {fields} FROM line_decision_events WHERE event_id=?",
                                 (event_id,)).fetchone()
                db.execute("COMMIT")
                return self._line_decision(row)
            except Exception:
                db.execute("ROLLBACK")
                raise

    @staticmethod
    def _line_edit(row: sqlite3.Row) -> LineEditRecord:
        if _digest(row["model_json"].encode("utf-8")) != row["model_sha256"]:
            raise ProjectIntegrityError("Saved line model checksum is invalid")
        return LineEditRecord(**{field: row[field] for field in LineEditRecord.__dataclass_fields__})

    @staticmethod
    def _line_edit_request(
        revision_id: str, expected_version: int, operation: Mapping[str, object],
    ) -> tuple[str, str]:
        if type(expected_version) is not int or expected_version < 0:
            raise ProjectStoreError("Line edit version is invalid")
        try:
            rendered = json.dumps({"revisionId": revision_id, "expectedVersion": expected_version,
                                   "operation": operation}, ensure_ascii=False, sort_keys=True,
                                  separators=(",", ":"), allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise ProjectStoreError("Line edit operation is invalid") from exc
        if len(rendered.encode("utf-8")) > MAX_SETTINGS_BYTES:
            raise ProjectStoreError("Line edit operation is too large")
        return rendered, _digest(rendered.encode("utf-8"))

    def find_line_edit_request_for(
        self, owner_id: str, revision_id: str, request_id: str,
        *, expected_version: int, operation: Mapping[str, object],
    ) -> LineEditRecord | None:
        owner_id, revision_id, request_id = _uuid(owner_id), _uuid(revision_id), _uuid(request_id)
        self.assert_revision_owner(owner_id, revision_id)
        _, request_hash = self._line_edit_request(revision_id, expected_version, operation)
        with self._db() as db:
            row = db.execute("SELECT * FROM line_edit_events WHERE request_id=?", (request_id,)).fetchone()
        if row is None:
            return None
        if (row["revision_id"], row["author_id"], row["request_sha256"]) != (
            revision_id, owner_id, request_hash,
        ):
            raise LineEditConflictError("Edit request key was reused")
        return self._line_edit(row)

    def latest_line_edit_for(self, owner_id: str, revision_id: str) -> LineEditRecord | None:
        owner_id, revision_id = _uuid(owner_id), _uuid(revision_id)
        self.assert_revision_owner(owner_id, revision_id)
        with self._db() as db:
            row = db.execute("""SELECT * FROM line_edit_events WHERE revision_id=?
                ORDER BY version DESC LIMIT 1""", (revision_id,)).fetchone()
        return self._line_edit(row) if row is not None else None

    def line_edit_version_for(self, owner_id: str, revision_id: str, version: int) -> LineEditRecord:
        owner_id, revision_id = _uuid(owner_id), _uuid(revision_id)
        self.assert_revision_owner(owner_id, revision_id)
        with self._db() as db:
            row = db.execute("SELECT * FROM line_edit_events WHERE revision_id=? AND version=?",
                             (revision_id, version)).fetchone()
        if row is None:
            raise ProjectNotFoundError(str(version))
        return self._line_edit(row)

    def list_line_edit_events_for(
        self, owner_id: str, revision_id: str, *, page: int = 1, page_size: int = 50,
    ) -> tuple[tuple[LineEditRecord, ...], int]:
        owner_id, revision_id = _uuid(owner_id), _uuid(revision_id)
        self.assert_revision_owner(owner_id, revision_id)
        if page < 1 or not 1 <= page_size <= 50:
            raise ProjectStoreError("Line edit page is invalid")
        with self._db() as db:
            total = db.execute("SELECT COUNT(*) FROM line_edit_events WHERE revision_id=?",
                               (revision_id,)).fetchone()[0]
            rows = db.execute("""SELECT * FROM line_edit_events WHERE revision_id=?
                ORDER BY version DESC LIMIT ? OFFSET ?""",
                (revision_id, page_size, (page - 1) * page_size))
            return tuple(self._line_edit(row) for row in rows), total

    def record_line_edit_for(
        self, owner_id: str, revision_id: str, request_id: str,
        *, expected_version: int, operation: Mapping[str, object],
        model: Mapping[str, object],
    ) -> LineEditRecord:
        owner_id, revision_id, request_id = _uuid(owner_id), _uuid(revision_id), _uuid(request_id)
        operation_json, request_hash = self._line_edit_request(revision_id, expected_version, operation)
        try:
            model_json = json.dumps(model, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":"), allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise ProjectStoreError("Line edit model is invalid") from exc
        if len(model_json.encode("utf-8")) > MAX_LINE_EDIT_BYTES:
            raise ResourceQuotaExceededError("Line edit model is too large")
        model_hash = _digest(model_json.encode("utf-8"))
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                owned = db.execute("""SELECT 1 FROM revisions r JOIN projects p
                    ON p.project_id=r.project_id WHERE r.revision_id=? AND p.owner_id=?""",
                    (revision_id, owner_id)).fetchone()
                if owned is None:
                    raise ProjectNotFoundError(revision_id)
                existing = db.execute("SELECT * FROM line_edit_events WHERE request_id=?",
                                      (request_id,)).fetchone()
                if existing is not None:
                    if (existing["revision_id"], existing["author_id"], existing["request_sha256"]) != (
                        revision_id, owner_id, request_hash,
                    ):
                        raise LineEditConflictError("Edit request key was reused")
                    db.execute("COMMIT")
                    return self._line_edit(existing)
                current = db.execute("SELECT MAX(version) FROM line_edit_events WHERE revision_id=?",
                                     (revision_id,)).fetchone()[0] or 0
                if current != expected_version:
                    raise LineEditConflictError("Line model changed; reload edits")
                count = db.execute("SELECT COUNT(*) FROM line_edit_events WHERE revision_id=?",
                                   (revision_id,)).fetchone()[0]
                if count >= MAX_LINE_EDIT_EVENTS_PER_REVISION:
                    raise ResourceQuotaExceededError("Line edit history limit exceeded")
                event_id = str(uuid4())
                db.execute("""INSERT INTO line_edit_events
                    (event_id,revision_id,version,request_id,request_sha256,operation_json,model_json,model_sha256,author_id)
                    VALUES (?,?,?,?,?,?,?,?,?)""", (event_id, revision_id, current + 1,
                    request_id, request_hash, operation_json, model_json, model_hash, owner_id))
                row = db.execute("SELECT * FROM line_edit_events WHERE event_id=?", (event_id,)).fetchone()
                db.execute("COMMIT")
                return self._line_edit(row)
            except Exception:
                db.execute("ROLLBACK")
                raise

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
                owner = db.execute("""SELECT p.owner_id FROM revisions r JOIN projects p
                    ON p.project_id=r.project_id WHERE r.revision_id=?""", (revision_id,)).fetchone()
                if owner is None:
                    raise ProjectNotFoundError(revision_id)
                self._require_quota(db, owner["owner_id"], jobs=1)
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

    def register_job_for(
        self, owner_id: str, revision_id: str, job_id: str,
        *, request_settings: Mapping[str, object], status: str = "queued"
    ) -> ProjectJobRecord:
        self.assert_revision_owner(owner_id, revision_id)
        return self.register_job(revision_id, job_id, request_settings=request_settings, status=status)

    def register_job_submission_for(
        self, owner_id: str, revision_id: str, job_id: str,
        request_id: str, *, request_settings: Mapping[str, object],
        retry_of: str | None = None,
    ) -> ProjectJobRecord:
        owner_id, revision_id, job_id, request_id = (
            _uuid(owner_id), _uuid(revision_id), _uuid(job_id), _uuid(request_id)
        )
        if retry_of is not None:
            retry_of = _uuid(retry_of)
        request_json = _canonical_json(dict(request_settings))
        request_hash = _digest(request_json.encode("utf-8"))
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                revision = db.execute("""SELECT r.algorithm_version FROM revisions r
                    JOIN projects p ON p.project_id=r.project_id
                    WHERE r.revision_id=? AND p.owner_id=?""",
                    (revision_id, owner_id),
                ).fetchone()
                if revision is None:
                    raise ProjectNotFoundError(revision_id)
                existing = db.execute(
                    "SELECT owner_id,revision_id,request_sha256,job_id FROM job_submissions WHERE request_id=?",
                    (request_id,),
                ).fetchone()
                if existing is not None:
                    if (
                        existing["owner_id"] == owner_id
                        and existing["revision_id"] == revision_id
                        and existing["request_sha256"] == request_hash
                    ):
                        raise DuplicateSubmissionError(existing["job_id"])
                    raise SubmissionConflictError("Idempotency key belongs to a different request")
                self._require_quota(db, owner_id, jobs=1)
                db.execute("""INSERT INTO jobs(
                    job_id,revision_id,request_json,request_sha256,status,algorithm_version,retry_of
                ) VALUES (?,?,?,?,?,?,?)""", (
                    job_id, revision_id, request_json, request_hash, "queued",
                    revision["algorithm_version"], retry_of,
                ))
                db.execute("""INSERT INTO job_submissions(
                    request_id,owner_id,revision_id,request_sha256,job_id,created_at
                ) VALUES (?,?,?,?,?,?)""", (
                    request_id, owner_id, revision_id, request_hash, job_id, int(time.time()),
                ))
                db.execute("COMMIT")
            except Exception:
                db.execute("ROLLBACK")
                raise
        return self.get_job(job_id)

    def lookup_job_submission_for(
        self, owner_id: str, revision_id: str, request_id: str,
        *, request_settings: Mapping[str, object],
    ) -> str | None:
        owner_id, revision_id, request_id = _uuid(owner_id), _uuid(revision_id), _uuid(request_id)
        request_json = _canonical_json(dict(request_settings))
        request_hash = _digest(request_json.encode("utf-8"))
        with self._db() as db:
            row = db.execute(
                "SELECT owner_id,revision_id,request_sha256,job_id FROM job_submissions WHERE request_id=?",
                (request_id,),
            ).fetchone()
        if row is None:
            return None
        if (row["owner_id"], row["revision_id"], row["request_sha256"]) != (
            owner_id, revision_id, request_hash,
        ):
            raise SubmissionConflictError("Idempotency key belongs to a different request")
        return row["job_id"]

    def list_jobs_for(self, owner_id: str, project_id: str) -> tuple[ProjectJobRecord, ...]:
        self.assert_project_owner(owner_id, project_id)
        with self._db() as db:
            rows = db.execute("""SELECT j.job_id FROM jobs j
                JOIN revisions r ON r.revision_id=j.revision_id
                WHERE r.project_id=? ORDER BY j.rowid DESC""", (project_id,)).fetchall()
        return tuple(self.get_job(row["job_id"]) for row in rows)

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

    def assert_job_owner(self, owner_id: str, job_id: str) -> ProjectJobRecord:
        with self._db() as db:
            row = db.execute(
                """SELECT j.job_id FROM jobs j
                JOIN revisions r ON r.revision_id = j.revision_id
                JOIN projects p ON p.project_id = r.project_id
                WHERE j.job_id = ? AND p.owner_id = ?""",
                (_uuid(job_id), _uuid(owner_id)),
            ).fetchone()
        if row is None:
            raise ProjectNotFoundError(job_id)
        return self.get_job(row["job_id"])

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
            raise ProjectStoreError("Result must be 1 to 96 MiB of bytes")
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
                owner = db.execute("SELECT owner_id FROM projects WHERE project_id=?", (revision.project_id,)).fetchone()
                self._require_quota(db, owner["owner_id"], bytes_added=len(result_bytes))
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

    def publish_result_for(self, owner_id: str, job_id: str, result_bytes: bytes) -> ProjectJobRecord:
        self.assert_job_owner(owner_id, job_id)
        return self.publish_result(job_id, result_bytes)

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

    def read_result_for(self, owner_id: str, job_id: str) -> bytes:
        self.assert_job_owner(owner_id, job_id)
        return self.read_result(job_id)
