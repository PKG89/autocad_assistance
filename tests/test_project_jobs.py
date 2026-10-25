"""Authenticated durable job admission, result and restart checks."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from io import BytesIO
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from uuid import uuid4

import httpx

from autocad_assistance.api import create_app
from autocad_assistance.services.auth_store import AuthStore
from autocad_assistance.services.calculation_jobs import CalculationJobManager
from autocad_assistance.services.project_jobs import ProjectJobBridge
from autocad_assistance.services.project_store import ProjectNotFoundError, ProjectStore
from autocad_assistance.services.survey_contract import SurveyContext
from autocad_assistance.services.uploads import store_upload


SOURCE = b"Point,X,Y,Z,Code\nP1,123.456,234.567,11.2,K\nP2,124,235,12,K\nP3,125,236,13,K\n"
PASSWORD = "Synthetic-only-owner-passphrase-123"
ORIGIN = "https://testserver"


class ProjectJobsTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        auth = AuthStore(self.root / "auth")
        self.owner = auth.create_owner("owner", PASSWORD).user_id
        self.store = ProjectStore(self.root / "projects")
        stored = store_upload(BytesIO(SOURCE), "survey.csv", self.root / "uploads", 10 * 1024 * 1024)
        self.store.register_upload_owner(self.owner, stored)
        project = self.store.create_owned_project(self.owner, "Synthetic")
        self.project_id = project.project_id
        revision = self.store.add_revision_for(
            self.owner, project.project_id, self.root / "uploads", stored.upload_id,
            context=SurveyContext(scale_factor=Decimal("500")),
            settings={"mapping": {"Point": 0, "X": 1, "Y": 2, "Z": 3, "Code": 4}},
            algorithm_version="geoai-dxf-v1",
        )
        self.revision_id = revision.revision_id
        self.app = self.make_app()
        self.addCleanup(self.app.state.job_manager.close)

    def make_app(self):
        return create_app(
            upload_root=self.root / "uploads", auth_root=self.root / "auth",
            auth_origin=ORIGIN, project_root=self.root / "projects",
            jobs_root=self.root / "jobs",
        )

    async def login(self, client, username="owner"):
        response = await client.post(
            "/api/v1/auth/login", json={"username": username, "password": PASSWORD},
            headers={"Origin": ORIGIN},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return {"Origin": ORIGIN, "X-CSRF-Token": response.json()["csrfToken"]}

    async def wait_result(self, client, job_id):
        for _ in range(200):
            response = await client.get(f"/api/v1/jobs/{job_id}")
            self.assertEqual(response.status_code, 200, response.text)
            payload = response.json()
            if payload["status"] in {"succeeded", "failed", "cancelled"}:
                return payload
            await asyncio.sleep(0.05)
        self.fail("Job did not finish within 10 seconds")

    async def test_submit_result_idempotency_restart_and_owner_boundary(self):
        transport = httpx.ASGITransport(app=self.app)
        async with httpx.AsyncClient(transport=transport, base_url=ORIGIN) as client:
            payload = {"revisionId": self.revision_id, "tinSettings": {}}
            key = str(uuid4())
            anonymous = await client.post("/api/v1/jobs", json=payload)
            self.assertEqual(anonymous.status_code, 401)
            headers = await self.login(client)
            self.assertEqual((await client.post("/api/v1/jobs", json=payload,
                headers={"Idempotency-Key": key})).status_code, 403)
            first = await client.post("/api/v1/jobs", json=payload,
                headers={**headers, "Idempotency-Key": key})
            self.assertEqual(first.status_code, 201, first.text)
            job_id = first.json()["jobId"]
            replay = await client.post("/api/v1/jobs", json=payload,
                headers={**headers, "Idempotency-Key": key})
            self.assertEqual(replay.json()["jobId"], job_id)
            conflict = await client.post("/api/v1/jobs", json={**payload, "tinSettings": {"refine": True}},
                headers={**headers, "Idempotency-Key": key})
            self.assertEqual(conflict.status_code, 409, conflict.text)
            finished = await self.wait_result(client, job_id)
            self.assertEqual(finished["status"], "succeeded", finished)
            self.assertTrue(finished["resultReady"])
            result = await client.get(f"/api/v1/jobs/{job_id}/result")
            self.assertEqual(result.status_code, 200, result.text[:100])
            self.assertIn(b"SECTION", result.content)
            listing = await client.get(f"/api/v1/projects/{self.project_id}/jobs")
            self.assertEqual([item["jobId"] for item in listing.json()["data"]], [job_id])
            self.assertEqual((await client.get(f"/api/v1/jobs/{uuid4()}")).status_code, 404)

        self.app.state.job_manager.close()
        restarted = self.make_app()
        self.addCleanup(restarted.state.job_manager.close)
        transport = httpx.ASGITransport(app=restarted)
        async with httpx.AsyncClient(transport=transport, base_url=ORIGIN) as client:
            headers = await self.login(client)
            replay = await client.post("/api/v1/jobs", json=payload,
                headers={**headers, "Idempotency-Key": key})
            self.assertEqual(replay.status_code, 201, replay.text)
            self.assertEqual(replay.json()["jobId"], job_id)
            self.assertEqual((await client.get(f"/api/v1/jobs/{job_id}/result")).content, result.content)
        with self.assertRaises(ProjectNotFoundError):
            self.store.assert_job_owner(str(uuid4()), job_id)

    async def test_admission_failure_leaves_no_job_or_claim(self):
        transport = httpx.ASGITransport(app=self.app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url=ORIGIN) as client:
            headers = await self.login(client)
            with patch.object(ProjectStore, "register_job_submission_for", side_effect=RuntimeError("DB fault")):
                response = await client.post("/api/v1/jobs", json={"revisionId": self.revision_id},
                    headers={**headers, "Idempotency-Key": str(uuid4())})
            self.assertEqual(response.status_code, 500)
            self.assertEqual(self.store.list_jobs_for(self.owner, self.project_id), ())
            self.assertEqual(list((self.root / "jobs").glob("*/state.json")), [])

    async def test_concurrent_claim_cancel_retry_and_tampered_result(self):
        worker = self.root / "fake_worker.py"
        worker.write_text(
            "import sys,time\nfrom pathlib import Path\n"
            "time.sleep(0.25)\n"
            "(Path(sys.argv[1])/'result.candidate').write_bytes(b'DXF synthetic')\n",
            encoding="utf-8",
        )
        manager = CalculationJobManager(
            self.root / "jobs2", worker_command=(sys.executable, str(worker)),
        )
        self.addCleanup(manager.close)
        bridge = ProjectJobBridge(self.store, manager)
        key = str(uuid4())
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(bridge.submit, self.owner, self.revision_id, key,
                tin_settings={}) for _ in range(2)]
            jobs = [future.result() for future in futures]
        self.assertEqual(jobs[0].job_id, jobs[1].job_id)
        self.assertEqual(len(self.store.list_jobs_for(self.owner, self.project_id)), 1)
        original = bridge.cancel(self.owner, jobs[0].job_id)
        for _ in range(100):
            original = bridge.get(self.owner, original.job_id)
            if original.status == "cancelled":
                break
            time.sleep(0.02)
        self.assertEqual(original.status, "cancelled")
        retry_key = str(uuid4())
        retried = bridge.retry(self.owner, original.job_id, retry_key)
        self.assertEqual(bridge.retry(self.owner, original.job_id, retry_key).job_id, retried.job_id)
        self.assertEqual(retried.retry_of, original.job_id)
        for _ in range(100):
            if manager.get(retried.job_id).status == "succeeded":
                break
            time.sleep(0.02)
        self.assertEqual(manager.get(retried.job_id).status, "succeeded")
        (manager.root / retried.job_id / "result.dxf").write_bytes(b"tampered bytes")
        inspected = bridge.get(self.owner, retried.job_id)
        self.assertFalse(inspected.result_ready)
        self.assertEqual(inspected.error_code, "RESULT_UNAVAILABLE")
        self.assertIsNone(self.store.get_job(retried.job_id).result_sha256)
        next_job = bridge.submit(self.owner, self.revision_id, str(uuid4()), tin_settings={})
        for _ in range(100):
            if manager.get(next_job.job_id).status == "succeeded":
                break
            time.sleep(0.02)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(bridge.get, self.owner, next_job.job_id) for _ in range(2)]
            views = [future.result() for future in futures]
        self.assertTrue(all(view.result_ready for view in views))
        self.assertEqual(self.store.read_result_for(self.owner, next_job.job_id), b"DXF synthetic")


if __name__ == "__main__":
    unittest.main()
