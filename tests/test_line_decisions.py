"""Versioned line choices and their exact effect on new DXF jobs."""

from __future__ import annotations

import asyncio
from contextlib import closing
from decimal import Decimal
from io import BytesIO
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

import ezdxf
import httpx

from autocad_assistance.api import create_app
from autocad_assistance.services.auth_store import AuthStore
from autocad_assistance.services.project_store import ProjectStore
from autocad_assistance.services.survey_contract import SurveyContext
from autocad_assistance.services.uploads import store_upload


SOURCE = (b"Point,X,Y,Z,Code,Comments\n"
          b"P1,0,0,1,k1,first\nP2,100,0,2,k1,second\n"
          b"P3,1,0,3,k1,third\nP4,2,0,4,k1,fourth\n")
MAPPING = {"Point": 0, "X": 1, "Y": 2, "Z": 3, "Code": 4, "Comments": 5}
ORIGIN = "https://testserver"
PASSWORD = "Synthetic-only-owner-passphrase-123"


class LineDecisionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.owner = AuthStore(self.root / "auth").create_owner("owner", PASSWORD).user_id
        self.store = ProjectStore(self.root / "projects")
        stored = store_upload(BytesIO(SOURCE), "source.csv", self.root / "uploads", 10 * 1024 * 1024)
        self.store.register_upload_owner(self.owner, stored)
        project = self.store.create_owned_project(self.owner, "Synthetic zigzag")
        self.project_id = project.project_id
        revision = self.store.add_revision_for(
            self.owner, project.project_id, self.root / "uploads", stored.upload_id,
            context=SurveyContext(scale_factor=Decimal("500")),
            settings={"mapping": MAPPING}, algorithm_version="geoai-dxf-v1",
        )
        self.revision_id = revision.revision_id
        self.app = create_app(auth_root=self.root / "auth", project_root=self.root / "projects",
                              upload_root=self.root / "uploads", jobs_root=self.root / "jobs",
                              auth_origin=ORIGIN)
        self.addCleanup(self.app.state.job_manager.close)
        self.path = f"/api/v1/projects/{self.project_id}/revisions/{self.revision_id}"

    async def login(self, client):
        response = await client.post("/api/v1/auth/login", json={"username": "owner", "password": PASSWORD},
                                     headers={"Origin": ORIGIN})
        self.assertEqual(response.status_code, 200, response.text)
        return {"Origin": ORIGIN, "X-CSRF-Token": response.json()["csrfToken"]}

    async def comparison(self, client):
        response = await client.get(f"{self.path}/line-candidates")
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def payload(self, comparison, action, version, key=None):
        return {"requestId": key or str(uuid4()), "expectedVersion": version, "action": action,
                "sourceSha256": comparison["sourceSha256"],
                "settingsSha256": comparison["settingsSha256"],
                "candidateVersion": comparison["candidateVersion"]}

    async def wait_result(self, client, job_id):
        for _ in range(200):
            state = (await client.get(f"/api/v1/jobs/{job_id}")).json()
            if state["status"] in {"succeeded", "failed"}:
                self.assertEqual(state["status"], "succeeded", state)
                return
            await asyncio.sleep(0.05)
        self.fail("DXF job timed out")

    async def test_idempotent_history_stale_tab_and_owner_boundary(self):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url=ORIGIN) as client:
            self.assertEqual((await client.get(f"{self.path}/line-decisions")).status_code, 401)
            headers = await self.login(client)
            comparison = await self.comparison(client)
            first_body = self.payload(comparison, "A", 0)
            endpoint = f"{self.path}/line-decisions/k1"
            first = await client.post(endpoint, json=first_body, headers=headers)
            self.assertEqual(first.status_code, 200, first.text)
            self.assertEqual(first.json()["version"], 1)
            self.assertEqual(first.json()["snapshot"]["group"], comparison["groups"][0])
            again = await client.post(endpoint, json=first_body, headers=headers)
            self.assertEqual(again.json()["eventId"], first.json()["eventId"])
            self.assertEqual((await client.post(endpoint, json={**first_body, "action": "B"},
                                                headers=headers)).status_code, 409)
            stale = await client.post(endpoint, json=self.payload(comparison, "B", 0), headers=headers)
            self.assertEqual(stale.status_code, 409)
            wrong = self.payload(comparison, "B", 1)
            wrong["sourceSha256"] = "0" * 64
            self.assertEqual((await client.post(endpoint, json=wrong, headers=headers)).status_code, 422)
            manual = await client.post(endpoint, json=self.payload(comparison, "manual", 1), headers=headers)
            self.assertEqual(manual.status_code, 200, manual.text)
            self.assertEqual(manual.json()["version"], 2)
            history = await client.get(f"{self.path}/line-decisions")
            self.assertEqual([item["action"] for item in history.json()["events"]], ["A", "manual"])
            page = await client.get(f"{self.path}/line-decisions?page=1&pageSize=1")
            self.assertEqual(len(page.json()["events"]), 1)
            self.assertTrue(page.json()["pagination"]["hasMore"])
            self.assertEqual(page.json()["latest"][0]["action"], "manual")
            self.assertTrue(all(item["authorId"] == self.owner for item in history.json()["events"]))
            from types import SimpleNamespace
            foreign = SimpleNamespace(user=SimpleNamespace(user_id=str(uuid4())),
                                      csrf_token=headers["X-CSRF-Token"])
            with patch.object(AuthStore, "authenticate", return_value=foreign):
                self.assertEqual((await client.get(f"{self.path}/line-decisions")).status_code, 404)
                self.assertEqual((await client.post(endpoint, json=self.payload(comparison, "B", 2),
                                                    headers=headers)).status_code, 404)

    async def test_accepted_a_and_b_change_only_new_dxf_job_order(self):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url=ORIGIN) as client:
            headers = await self.login(client)
            comparison = await self.comparison(client)
            endpoint = f"{self.path}/line-decisions/k1"

            async def submit_and_points(expected):
                response = await client.post("/api/v1/jobs", json={"revisionId": self.revision_id},
                                             headers={**headers, "Idempotency-Key": str(uuid4())})
                self.assertEqual(response.status_code, 201, response.text)
                job_id = response.json()["jobId"]
                await self.wait_result(client, job_id)
                raw = (await client.get(f"/api/v1/jobs/{job_id}/result")).content
                path = self.root / f"{job_id}.dxf"
                path.write_bytes(raw)
                drawing = ezdxf.readfile(path)
                polylines = list(drawing.modelspace().query("LWPOLYLINE"))
                self.assertEqual(len(polylines), 1)
                xs = [point[0] for point in polylines[0].get_points("xy")]
                self.assertEqual(xs, expected)
                request = json.loads((self.root / "jobs" / job_id / "request.json").read_text())
                return job_id, request, raw

            first = await client.post(endpoint, json=self.payload(comparison, "A", 0), headers=headers)
            self.assertEqual(first.status_code, 200, first.text)
            a_id, a_request, a_raw = await submit_and_points([0.0, 100.0, 1.0, 2.0])
            self.assertEqual(a_request["line_orders"], {"k1": [1, 2, 3, 4]})
            second = await client.post(endpoint, json=self.payload(comparison, "B", 1), headers=headers)
            self.assertEqual(second.status_code, 200, second.text)
            b_id, b_request, _ = await submit_and_points([0.0, 1.0, 2.0, 100.0])
            self.assertEqual(b_request["line_orders"], {"k1": [1, 3, 4, 2]})
            self.assertNotEqual(a_id, b_id)
            self.assertEqual(json.loads((self.root / "jobs" / a_id / "request.json").read_text()), a_request)
            self.assertEqual((await client.get(f"/api/v1/jobs/{a_id}/result")).content, a_raw)
            self.assertEqual(self.store.read_source_for(self.owner, self.project_id, self.revision_id), SOURCE)

            manual = await client.post(endpoint, json=self.payload(comparison, "manual", 2), headers=headers)
            self.assertEqual(manual.status_code, 200, manual.text)
            _, manual_request, _ = await submit_and_points([0.0, 1.0, 2.0, 100.0])
            self.assertEqual(manual_request["line_orders"], {})

    async def test_abstaining_group_and_tampered_snapshot_fail_safely(self):
        duplicate = (b"Point,X,Y,Z,Code,Comments\n"
                     b"P1,0,0,1,k2,\nP1,1,0,2,k2,\n")
        upload = store_upload(BytesIO(duplicate), "duplicate.csv", self.root / "uploads", 10 * 1024 * 1024)
        self.store.register_upload_owner(self.owner, upload)
        revision = self.store.add_revision_for(
            self.owner, self.project_id, self.root / "uploads", upload.upload_id,
            context=SurveyContext(scale_factor=Decimal("500")),
            settings={"mapping": MAPPING}, algorithm_version="geoai-dxf-v1",
        )
        path = f"/api/v1/projects/{self.project_id}/revisions/{revision.revision_id}"
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url=ORIGIN) as client:
            headers = await self.login(client)
            comparison = (await client.get(f"{path}/line-candidates")).json()
            self.assertEqual(comparison["groups"][0]["status"], "needs_review")
            endpoint = f"{path}/line-decisions/k2"
            self.assertEqual((await client.post(endpoint, json=self.payload(comparison, "A", 0),
                                                headers=headers)).status_code, 422)
            manual = await client.post(endpoint, json=self.payload(comparison, "manual", 0), headers=headers)
            self.assertEqual(manual.status_code, 200, manual.text)
            self.assertEqual(manual.json()["action"], "manual")

            original = await self.comparison(client)
            accepted = await client.post(f"{self.path}/line-decisions/k1",
                                         json=self.payload(original, "A", 0), headers=headers)
            self.assertEqual(accepted.status_code, 200, accepted.text)
            with closing(sqlite3.connect(self.store.db_path)) as db:
                db.execute("UPDATE line_decision_events SET snapshot_json='{}' WHERE event_id=?",
                           (accepted.json()["eventId"],))
                db.commit()
            result = await client.post("/api/v1/jobs", json={"revisionId": self.revision_id},
                                       headers={**headers, "Idempotency-Key": str(uuid4())})
            self.assertEqual(result.status_code, 422, result.text)
            self.assertEqual(self.store.list_jobs_for(self.owner, self.project_id), ())


class LineDecisionMigrationTests(unittest.TestCase):
    def test_existing_v5_project_database_migrates_without_losing_projects(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = ProjectStore(root)
            owner = str(uuid4())
            project = store.create_owned_project(owner, "Earlier project")
            with closing(sqlite3.connect(store.db_path)) as db:
                db.execute("DROP TABLE line_edit_events")
                db.execute("DROP TABLE line_decision_events")
                db.execute("PRAGMA user_version=5")
                db.commit()
            reopened = ProjectStore(root)
            self.assertEqual(reopened.assert_project_owner(owner, project.project_id), project)
            with closing(sqlite3.connect(reopened.db_path)) as db:
                self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 7)
                self.assertIsNotNone(db.execute("SELECT name FROM sqlite_master WHERE name='line_decision_events'").fetchone())


if __name__ == "__main__":
    unittest.main()
