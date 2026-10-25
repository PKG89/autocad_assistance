"""Bounded compute queue and real DXF worker checks."""

from __future__ import annotations

import asyncio
from dataclasses import asdict
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest

import httpx

from autocad_assistance.api import create_app
from autocad_assistance.services.calculation_jobs import (
    CalculationJobManager,
    JobCapacityError,
    JobStateError,
)


FAKE_WORKER = '''import json
from pathlib import Path
import sys
import time
job_dir = Path(sys.argv[1])
point = json.loads((job_dir / "request.json").read_text())["rows"][0]["Point"]
if point in {"SLOW", "TIMEOUT"}:
    (job_dir / "dxf-job-leftover").mkdir()
    time.sleep(2)
if point == "CRASH":
    sys.exit(7)
if point != "EMPTY":
    (job_dir / "result.candidate").write_bytes(b"DXF:" + point.encode())
'''


def rows(point="OK"):
    return [{"Point": point, "X": "1", "Y": "2", "Z": "3", "Code": ""}]


def wait_for(manager, job_id, wanted, seconds=8):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        current = manager.get(job_id)
        if current.status in wanted:
            return current
        time.sleep(0.01)
    raise AssertionError(f"Job {job_id} did not reach {wanted}; current={manager.get(job_id)}")


class CalculationJobTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "jobs"
        script = Path(self.temp.name) / "worker.py"
        script.write_text(FAKE_WORKER, encoding="utf-8")
        self.fake_command = (sys.executable, str(script))
        self.managers = []
        self.addCleanup(self._close_managers)

    def _close_managers(self):
        for manager in reversed(self.managers):
            manager.close()

    def manager(self, **kwargs):
        result = CalculationJobManager(self.root, worker_command=self.fake_command, **kwargs)
        self.managers.append(result)
        return result

    def test_fixed_queue_capacity_and_single_running_worker(self):
        manager = self.manager()
        active = manager.submit(rows("SLOW"))
        wait_for(manager, active.job_id, {"running"})
        waiting = [manager.submit(rows()) for _ in range(4)]
        with self.assertRaises(JobCapacityError):
            manager.submit(rows())
        self.assertEqual(sum(manager.get(item.job_id).status == "queued" for item in waiting), 4)
        manager.cancel(active.job_id)
        wait_for(manager, active.job_id, {"cancelled"})
        for item in waiting:
            self.assertEqual(wait_for(manager, item.job_id, {"succeeded"}).status, "succeeded")
            self.assertEqual(manager.result_path(item.job_id).read_bytes(), b"DXF:OK")
        self.assertEqual(len({item.job_id for item in waiting + [active]}), 5)

    def test_queued_and_running_cancellation_release_capacity(self):
        manager = self.manager(max_pending=1)
        active = manager.submit(rows("SLOW"))
        wait_for(manager, active.job_id, {"running"})
        waiting = manager.submit(rows())
        self.assertEqual(manager.cancel(waiting.job_id).status, "cancelled")
        next_job = manager.submit(rows())
        self.assertEqual(manager.cancel(active.job_id).status, "cancelling")
        wait_for(manager, active.job_id, {"cancelled"})
        self.assertFalse((self.root / active.job_id / "result.dxf").exists())
        self.assertFalse((self.root / active.job_id / "dxf-job-leftover").exists())
        wait_for(manager, next_job.job_id, {"succeeded"})

    def test_second_coordinator_cannot_start_on_same_root(self):
        self.manager()
        with self.assertRaises(JobStateError):
            CalculationJobManager(self.root, worker_command=self.fake_command)

    def test_missing_or_nonfinite_height_is_rejected_before_queueing(self):
        manager = self.manager()
        for invalid in ("", "NaN", "Infinity", "not-a-height", "1e9999", "1e-9999"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                manager.submit([{**rows()[0], "Z": invalid}])
        self.assertEqual(list(self.root.glob("*/state.json")), [])

    def test_timeout_crash_invalid_result_and_bounded_retry(self):
        manager = self.manager(timeout_seconds=0.1)
        timeout = manager.submit(rows("TIMEOUT"))
        self.assertEqual(wait_for(manager, timeout.job_id, {"failed"}).error_code, "TIMEOUT")
        crash = manager.submit(rows("CRASH"))
        self.assertEqual(wait_for(manager, crash.job_id, {"failed"}).error_code, "WORKER_FAILED")
        first_retry = manager.retry(crash.job_id)
        self.assertEqual((first_retry.attempt, first_retry.retry_of), (2, crash.job_id))
        wait_for(manager, first_retry.job_id, {"failed"})
        second_retry = manager.retry(first_retry.job_id)
        self.assertEqual(second_retry.attempt, 3)
        wait_for(manager, second_retry.job_id, {"failed"})
        with self.assertRaises(JobStateError):
            manager.retry(second_retry.job_id)
        empty = manager.submit(rows("EMPTY"))
        self.assertEqual(wait_for(manager, empty.job_id, {"failed"}).error_code, "INVALID_RESULT")
        self.assertFalse((self.root / empty.job_id / "result.dxf").exists())

    def test_restart_marks_interrupted_work_and_preserves_result(self):
        first = self.manager()
        complete = first.submit(rows())
        wait_for(first, complete.job_id, {"succeeded"})
        first.close()
        interrupted = first.get(complete.job_id)
        recovered_id = "b4bf9041-ff7d-4d0f-9031-c80bfe895acd"
        recovered_dir = self.root / recovered_id
        recovered_dir.mkdir()
        (recovered_dir / "request.json").write_text(
            json.dumps({"version": 1, "rows": rows(), "scale_factor": 1.0, "tin_settings": {}}),
            encoding="utf-8",
        )
        (recovered_dir / "state.json").write_text(
            json.dumps({**asdict(interrupted), "job_id": recovered_id, "status": "running"}),
            encoding="utf-8",
        )
        second = self.manager()
        self.assertEqual(second.result_path(complete.job_id).read_bytes(), b"DXF:OK")
        self.assertEqual(second.get(recovered_id).error_code, "INTERRUPTED")
        retry = second.retry(recovered_id)
        wait_for(second, retry.job_id, {"succeeded"})

    def test_real_worker_renders_small_dxf(self):
        manager = CalculationJobManager(self.root)
        self.managers.append(manager)
        job = manager.submit(rows("P1"))
        result = wait_for(manager, job.job_id, {"succeeded", "failed"}, seconds=20)
        self.assertEqual(result.status, "succeeded", (result, (self.root / job.job_id / "worker.log").read_text()))
        self.assertIn(b"SECTION", manager.read_result(job.job_id))

    def test_result_symlink_cannot_read_outside_jobs_root(self):
        manager = self.manager()
        job = manager.submit(rows())
        wait_for(manager, job.job_id, {"succeeded"})
        result = manager.result_path(job.job_id)
        outside = Path(self.temp.name) / "outside.dxf"
        outside.write_bytes(b"private data")
        result.unlink()
        result.symlink_to(outside)
        with self.assertRaises(JobStateError):
            manager.read_result(job.job_id)

    def test_submission_does_not_block_health_request(self):
        manager = self.manager()
        job = manager.submit(rows("SLOW"))
        wait_for(manager, job.job_id, {"running"})

        async def check_health():
            app = create_app(upload_root=Path(self.temp.name) / "uploads")
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                started = time.monotonic()
                response = await client.get("/health")
                return response.status_code, time.monotonic() - started

        status, elapsed = asyncio.run(check_health())
        self.assertEqual(status, 200)
        self.assertLess(elapsed, 0.5)
        manager.cancel(job.job_id)
        wait_for(manager, job.job_id, {"cancelled"})


if __name__ == "__main__":
    unittest.main()
