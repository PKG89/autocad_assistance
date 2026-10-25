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
import time
from typing import Iterator, Mapping
import unicodedata
from uuid import UUID, uuid4

from autocad_assistance.services.survey_contract import SurveyContext
from autocad_assistance.services.uploads import (
    StoredUpload, read_stored_upload, remove_stored_upload, validate_upload_bytes,
)


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


class ResourceQuotaExceededError(ProjectStoreError):
    """A configured owner resource limit would be exceeded."""


@dataclass(frozen=True)
class ResourceQuota:
    max_projects: int = 20
    max_uploads: int = 100
    max_revisions: int = 500
    max_jobs: int = 500
    max_total_bytes: int = 512 * 1024 * 1024

    def __post_init__(self) -> None:
        if any(value <= 0 for value in (
            self.max_projects, self.max_uploads, self.max_revisions,
            self.max_jobs, self.max_total_bytes,
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
            if current not in (0, 1, 2, 3, 4):
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
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
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
                PRAGMA user_version = 4;
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
        jobs: int = 0, bytes_added: int = 0,
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
        )
        limits = (
            self.quota.max_projects, self.quota.max_uploads,
            self.quota.max_revisions, self.quota.max_jobs,
        )
        if any(count + change > limit for count, change, limit in zip(
            counts, (projects, uploads, revisions, jobs), limits
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
        if upload_bytes + revision_bytes + result_bytes + bytes_added > self.quota.max_total_bytes:
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
