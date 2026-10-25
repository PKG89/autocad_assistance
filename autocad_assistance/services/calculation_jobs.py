"""One-process, bounded, restart-aware coordinator for local DXF calculations."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
from threading import Condition, Thread
import time
from typing import Callable, Mapping, Sequence
from uuid import UUID, uuid4


class JobCapacityError(ValueError):
    """The fixed waiting queue is full."""


class JobNotFoundError(LookupError):
    """The job ID is unknown to this coordinator."""


class JobStateError(ValueError):
    """An operation is invalid for the current job state."""


@dataclass(frozen=True)
class JobSnapshot:
    job_id: str
    status: str
    attempt: int
    retry_of: str | None
    error_code: str | None
    created_at: float
    updated_at: float
    result_sha256: str | None = None


class CalculationJobManager:
    """Serialize jobs through one disposable child process at a time.

    The caller owns this manager and must call ``close`` during shutdown.
    Requests and state are durable, while in-flight jobs require explicit
    retry after a restart. The child is the only process that imports the
    geometry engine for calculation.
    """

    def __init__(
        self,
        jobs_root: str | Path,
        *,
        max_pending: int = 4,
        timeout_seconds: float = 120.0,
        max_output_bytes: int = 25 * 1024 * 1024,
        max_retries: int = 2,
        worker_command: Sequence[str] | None = None,
    ) -> None:
        if max_pending <= 0 or timeout_seconds <= 0 or max_output_bytes <= 0 or max_retries < 0:
            raise ValueError("Job limits must be positive and retries nonnegative")
        self.root = Path(jobs_root).resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            import fcntl
        except ImportError as exc:
            raise RuntimeError("A POSIX file lock is required for the single-worker coordinator") from exc
        self._lock_fd = os.open(self.root / ".coordinator.lock", os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(self._lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            os.close(self._lock_fd)
            raise JobStateError("A coordinator already owns this jobs root") from exc
        self.max_pending = max_pending
        self.timeout_seconds = timeout_seconds
        self.max_output_bytes = max_output_bytes
        self.max_retries = max_retries
        self._worker_command = tuple(worker_command) if worker_command is not None else (
            sys.executable, "-m", "autocad_assistance.services.calculation_worker"
        )
        self._condition = Condition()
        self._records: dict[str, JobSnapshot] = {}
        self._active_process: subprocess.Popen[bytes] | None = None
        self._closed = False
        self._recover()
        self._thread = Thread(target=self._worker_loop, name="geoai-dxf-jobs", daemon=True)
        self._thread.start()

    def _directory(self, job_id: str) -> Path:
        if str(UUID(job_id)) != job_id:
            raise JobNotFoundError(job_id)
        return self.root / job_id

    @staticmethod
    def _write_json(path: Path, payload: object) -> None:
        temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
        try:
            with temporary.open("x", encoding="utf-8") as target:
                os.chmod(temporary, 0o600)
                json.dump(payload, target, ensure_ascii=False, allow_nan=False)
                target.flush()
                os.fsync(target.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)

    def _save(self, snapshot: JobSnapshot) -> None:
        self._write_json(self._directory(snapshot.job_id) / "state.json", asdict(snapshot))
        self._records[snapshot.job_id] = snapshot

    def _set_state(
        self, job_id: str, status: str, error_code: str | None = None,
        result_sha256: str | None = None,
    ) -> JobSnapshot:
        current = self._records[job_id]
        updated = replace(
            current, status=status, error_code=error_code,
            result_sha256=result_sha256, updated_at=time.time(),
        )
        self._save(updated)
        self._condition.notify_all()
        return updated

    def _recover(self) -> None:
        for job_dir in self.root.iterdir():
            if job_dir.is_symlink() or not job_dir.is_dir():
                continue
            try:
                if str(UUID(job_dir.name)) != job_dir.name:
                    continue
                payload = json.loads((job_dir / "state.json").read_text(encoding="utf-8"))
                snapshot = JobSnapshot(**payload)
                if snapshot.job_id != job_dir.name:
                    continue
                result = job_dir / "result.dxf"
                if snapshot.status in {"queued", "running", "cancelling"}:
                    snapshot = replace(snapshot, status="failed", error_code="INTERRUPTED", updated_at=time.time())
                    self._save(snapshot)
                elif snapshot.status == "succeeded" and (
                    result.is_symlink() or not result.is_file() or result.stat().st_size > self.max_output_bytes
                ):
                    snapshot = replace(snapshot, status="failed", error_code="MISSING_RESULT", updated_at=time.time())
                    self._save(snapshot)
                self._records[snapshot.job_id] = snapshot
            except (OSError, ValueError, TypeError, KeyError):
                continue

    def _submit_request(
        self, request: dict, *, attempt: int, retry_of: str | None,
        on_admit: Callable[[str], None] | None = None,
    ) -> JobSnapshot:
        with self._condition:
            if self._closed:
                raise JobStateError("Coordinator is closed")
            waiting = sum(item.status == "queued" for item in self._records.values())
            if waiting >= self.max_pending:
                raise JobCapacityError("Job queue is full")
            job_id = str(uuid4())
            job_dir = self._directory(job_id)
            job_dir.mkdir(mode=0o700)
            now = time.time()
            snapshot = JobSnapshot(job_id, "queued", attempt, retry_of, None, now, now)
            try:
                self._write_json(job_dir / "request.json", request)
                self._save(snapshot)
                if on_admit is not None:
                    on_admit(job_id)
            except Exception:
                self._records.pop(job_id, None)
                for child in job_dir.iterdir():
                    child.unlink()
                job_dir.rmdir()
                raise
            self._condition.notify_all()
            return snapshot

    def submit(
        self,
        mapped_rows: Sequence[Mapping[str, object]],
        *,
        scale_factor: float = 1.0,
        tin_settings: Mapping[str, object] | None = None,
        on_admit: Callable[[str], None] | None = None,
    ) -> JobSnapshot:
        if not 0 < len(mapped_rows) <= 100_000:
            raise ValueError("Job requires 1 to 100000 mapped rows")
        if not math.isfinite(scale_factor) or scale_factor <= 0:
            raise ValueError("Job scale factor must be finite and positive")
        required = {"Point", "X", "Y", "Z", "Code"}
        if any(not required.issubset(row) for row in mapped_rows):
            raise ValueError("Job rows must contain Point, X, Y, Z and Code")
        for index, row in enumerate(mapped_rows, start=1):
            for axis in ("X", "Y", "Z"):
                value = str(row[axis]).strip() if row[axis] is not None else ""
                if not value:
                    raise ValueError(f"Row {index} has an empty {axis} coordinate")
                try:
                    numeric = Decimal(value)
                    as_float = float(numeric)
                except (InvalidOperation, OverflowError, ValueError) as exc:
                    raise ValueError(f"Row {index} has an invalid {axis} coordinate") from exc
                if not numeric.is_finite() or not math.isfinite(as_float):
                    raise ValueError(f"Row {index} has a nonfinite {axis} coordinate")
                if numeric != 0 and as_float == 0:
                    raise ValueError(f"Row {index} has an underflowing {axis} coordinate")
        request = {
            "version": 1,
            "rows": [dict(row) for row in mapped_rows],
            "scale_factor": scale_factor,
            "tin_settings": dict(tin_settings or {}),
        }
        # Encode before queue admission so malformed request objects never
        # consume a slot or leave a half-created job directory.
        encoded = json.dumps(request, ensure_ascii=False, allow_nan=False).encode("utf-8")
        if len(encoded) > 32 * 1024 * 1024:
            raise ValueError("Job request exceeds the 32 MiB limit")
        return self._submit_request(request, attempt=1, retry_of=None, on_admit=on_admit)

    def get(self, job_id: str) -> JobSnapshot:
        with self._condition:
            try:
                return self._records[job_id]
            except KeyError as exc:
                raise JobNotFoundError(job_id) from exc

    def cancel(self, job_id: str) -> JobSnapshot:
        with self._condition:
            try:
                current = self._records[job_id]
            except KeyError as exc:
                raise JobNotFoundError(job_id) from exc
            if current.status == "queued":
                return self._set_state(job_id, "cancelled", "CANCELLED")
            if current.status == "running":
                return self._set_state(job_id, "cancelling", None)
            if current.status == "cancelling":
                return current
            raise JobStateError("Only queued or running jobs can be cancelled")

    def retry(self, job_id: str, *, on_admit: Callable[[str], None] | None = None) -> JobSnapshot:
        with self._condition:
            try:
                current = self._records[job_id]
            except KeyError as exc:
                raise JobNotFoundError(job_id) from exc
            if current.status not in {"failed", "cancelled"}:
                raise JobStateError("Only failed or cancelled jobs can be retried")
            if current.attempt > self.max_retries:
                raise JobStateError("Job retry limit reached")
            request = json.loads((self._directory(job_id) / "request.json").read_text(encoding="utf-8"))
        return self._submit_request(request, attempt=current.attempt + 1, retry_of=job_id, on_admit=on_admit)

    def result_path(self, job_id: str) -> Path:
        snapshot = self.get(job_id)
        if snapshot.status != "succeeded":
            raise JobStateError("Job has no successful result")
        result = self._directory(job_id) / "result.dxf"
        if result.is_symlink() or not result.is_file():
            raise JobStateError("Job result is missing")
        return result

    def read_result(self, job_id: str) -> bytes:
        """Read one bounded regular result without following a file symlink."""
        self.result_path(job_id)
        job_dir = self._directory(job_id)
        directory_fd = os.open(job_dir, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            result_fd = os.open("result.dxf", os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory_fd)
            try:
                if not stat.S_ISREG(os.fstat(result_fd).st_mode):
                    raise JobStateError("Job result is not a regular file")
                with os.fdopen(result_fd, "rb", closefd=False) as source:
                    data = source.read(self.max_output_bytes + 1)
                if not 0 < len(data) <= self.max_output_bytes:
                    raise JobStateError("Job result exceeds the output limit")
                expected = self.get(job_id).result_sha256
                if expected is None or hashlib.sha256(data).hexdigest() != expected:
                    raise JobStateError("Job result checksum is invalid")
                return data
            finally:
                os.close(result_fd)
        finally:
            os.close(directory_fd)

    def _worker_loop(self) -> None:
        while True:
            with self._condition:
                self._condition.wait_for(
                    lambda: self._closed or any(item.status == "queued" for item in self._records.values())
                )
                if self._closed:
                    return
                selected = min(
                    (item for item in self._records.values() if item.status == "queued"),
                    key=lambda item: item.created_at,
                )
                self._set_state(selected.job_id, "running")
            self._run_one(selected.job_id)

    @staticmethod
    def _stop_process(process: subprocess.Popen[bytes]) -> None:
        if process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()

    @staticmethod
    def _remove_transient_dirs(job_dir: Path) -> None:
        for transient in job_dir.glob("dxf-job-*"):
            if transient.is_symlink() or transient.is_file():
                transient.unlink()
            elif transient.is_dir():
                shutil.rmtree(transient)

    def _run_one(self, job_id: str) -> None:
        job_dir = self._directory(job_id)
        candidate = job_dir / "result.candidate"
        candidate.unlink(missing_ok=True)
        try:
            with (job_dir / "worker.log").open("wb") as log:
                process = subprocess.Popen(
                    [*self._worker_command, str(job_dir), str(self.max_output_bytes), str(os.getpid())],
                    stdin=subprocess.DEVNULL,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    cwd=Path(__file__).resolve().parents[2],
                )
                with self._condition:
                    self._active_process = process
                started = time.monotonic()
                terminal_error = None
                while process.poll() is None:
                    with self._condition:
                        cancelling = self._closed or self._records[job_id].status == "cancelling"
                    if cancelling:
                        terminal_error = "CANCELLED" if not self._closed else "INTERRUPTED"
                    elif time.monotonic() - started >= self.timeout_seconds:
                        terminal_error = "TIMEOUT"
                    if terminal_error is not None:
                        self._stop_process(process)
                        break
                    try:
                        process.wait(timeout=0.05)
                    except subprocess.TimeoutExpired:
                        pass
                self._remove_transient_dirs(job_dir)
                with self._condition:
                    self._active_process = None
                    if terminal_error == "CANCELLED" or self._records[job_id].status == "cancelling":
                        candidate.unlink(missing_ok=True)
                        self._set_state(job_id, "cancelled", "CANCELLED")
                    elif terminal_error is not None:
                        candidate.unlink(missing_ok=True)
                        self._set_state(job_id, "failed", terminal_error)
                    elif process.returncode != 0:
                        candidate.unlink(missing_ok=True)
                        self._set_state(job_id, "failed", "WORKER_FAILED")
                    elif candidate.is_symlink() or not candidate.is_file() or not 0 < candidate.stat().st_size <= self.max_output_bytes:
                        candidate.unlink(missing_ok=True)
                        self._set_state(job_id, "failed", "INVALID_RESULT")
                    else:
                        candidate_fd = os.open(candidate, os.O_RDONLY | os.O_NOFOLLOW)
                        try:
                            if not stat.S_ISREG(os.fstat(candidate_fd).st_mode):
                                raise JobStateError("Job candidate is not regular")
                            with os.fdopen(candidate_fd, "rb", closefd=False) as source:
                                data = source.read(self.max_output_bytes + 1)
                            if not 0 < len(data) <= self.max_output_bytes:
                                raise JobStateError("Job candidate exceeds the output limit")
                            result_sha256 = hashlib.sha256(data).hexdigest()
                        finally:
                            os.close(candidate_fd)
                        os.replace(candidate, job_dir / "result.dxf")
                        self._set_state(job_id, "succeeded", result_sha256=result_sha256)
        except (OSError, ValueError):
            candidate.unlink(missing_ok=True)
            self._remove_transient_dirs(job_dir)
            with self._condition:
                self._active_process = None
                self._set_state(job_id, "failed", "WORKER_FAILED")
        finally:
            candidate.unlink(missing_ok=True)

    def close(self) -> None:
        with self._condition:
            if self._closed and self._lock_fd is None:
                return
            self._closed = True
            self._condition.notify_all()
        self._thread.join(timeout=5)
        if self._thread.is_alive():
            raise RuntimeError("Compute worker did not stop; coordinator lock remains held")
        with self._condition:
            for item in list(self._records.values()):
                if item.status in {"queued", "running", "cancelling"}:
                    self._set_state(item.job_id, "failed", "INTERRUPTED")
        if self._lock_fd is not None:
            os.close(self._lock_fd)
            self._lock_fd = None
