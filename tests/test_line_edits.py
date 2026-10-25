"""Explicit line topology edits preserve source rows and reproduce in DXF."""

from __future__ import annotations

import asyncio
from contextlib import closing
from decimal import Decimal
from io import BytesIO
import json
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from uuid import uuid4

import ezdxf
import httpx
import pandas as pd

from autocad_assistance.api import create_app
from autocad_assistance.services.auth_store import AuthStore
from autocad_assistance.services.project_store import ProjectStore
from autocad_assistance.services.survey_contract import SurveyContext
from autocad_assistance.services.uploads import store_upload
from autocad_assistance.dxf_generator.polylines import extract_structural_breaklines


SOURCE = (b"Point,X,Y,Z,Code,Comments\n"
          b"P1,0,0,1,k1,\nP2,100,0,2,k1,\nP3,1,0,3,k1,\nP4,2,0,4,k1,\n"
          b"Q1,0,10,5,k2,\nQ2,10,10,6,k2,\n")
MAPPING = {"Point": 0, "X": 1, "Y": 2, "Z": 3, "Code": 4, "Comments": 5}
ORIGIN = "https://testserver"
PASSWORD = "Synthetic-only-owner-passphrase-123"


class LineEditTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.owner = AuthStore(self.root / "auth").create_owner("owner", PASSWORD).user_id
        self.store = ProjectStore(self.root / "projects")
        upload = store_upload(BytesIO(SOURCE), "source.csv", self.root / "uploads", 10 * 1024 * 1024)
        self.store.register_upload_owner(self.owner, upload)
        project = self.store.create_owned_project(self.owner, "Synthetic edits")
        self.project_id = project.project_id
        revision = self.store.add_revision_for(self.owner, project.project_id, self.root / "uploads",
            upload.upload_id, context=SurveyContext(scale_factor=Decimal("500")),
            settings={"mapping": MAPPING}, algorithm_version="geoai-dxf-v1")
        self.revision_id = revision.revision_id
        self.app = create_app(auth_root=self.root / "auth", project_root=self.root / "projects",
            upload_root=self.root / "uploads", jobs_root=self.root / "jobs", auth_origin=ORIGIN)
        self.addCleanup(self.app.state.job_manager.close)
        self.path = f"/api/v1/projects/{self.project_id}/revisions/{self.revision_id}/line-edits"

    async def login(self, client):
        response = await client.post("/api/v1/auth/login", json={"username": "owner", "password": PASSWORD},
                                     headers={"Origin": ORIGIN})
        self.assertEqual(response.status_code, 200, response.text)
        return {"Origin": ORIGIN, "X-CSRF-Token": response.json()["csrfToken"]}

    async def edit(self, client, headers, version, operation, *, key=None, status=200):
        payload = {"requestId": key or str(uuid4()), "expectedVersion": version,
                   "operation": operation}
        response = await client.post(self.path, json=payload, headers=headers)
        self.assertEqual(response.status_code, status, response.text)
        return response.json(), payload

    async def submit_lines(self, client, headers):
        response = await client.post("/api/v1/jobs", json={"revisionId": self.revision_id},
            headers={**headers, "Idempotency-Key": str(uuid4())})
        self.assertEqual(response.status_code, 201, response.text)
        job_id = response.json()["jobId"]
        for _ in range(200):
            state = (await client.get(f"/api/v1/jobs/{job_id}")).json()
            if state["status"] in {"succeeded", "failed"}:
                self.assertEqual(state["status"], "succeeded", state)
                break
            await asyncio.sleep(0.05)
        else:
            self.fail("DXF job timeout")
        raw = (await client.get(f"/api/v1/jobs/{job_id}/result")).content
        path = self.root / f"{job_id}.dxf"
        path.write_bytes(raw)
        drawing = ezdxf.readfile(path)
        lines = [[(point[0], point[1]) for point in line.get_points("xy")]
                 for line in drawing.modelspace().query("LWPOLYLINE")]
        request = json.loads((self.root / "jobs" / job_id / "request.json").read_text())
        return job_id, lines, request, raw

    async def test_reorder_split_move_join_undo_and_job_snapshot(self):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url=ORIGIN) as client:
            self.assertEqual((await client.get(self.path + "/current")).status_code, 401)
            headers = await self.login(client)
            initial = (await client.get(self.path + "/current")).json()
            self.assertEqual(initial["version"], 0)
            self.assertFalse(initial["staleDecisions"])
            self.assertEqual(initial["model"]["sourceRowIndexes"], [1, 2, 3, 4, 5, 6])
            self.assertEqual(initial["model"]["lines"][0]["rowIndexes"], [1, 3, 4, 2])

            first, request = await self.edit(client, headers, 0,
                {"type": "reorder", "lineId": "k1:0", "rowIndexes": [1, 2, 3, 4]})
            self.assertEqual(first["version"], 1)
            replay = await client.post(self.path, json=request, headers=headers)
            self.assertEqual(replay.json()["eventId"], first["eventId"])
            await self.edit(client, headers, 0, {"type": "reset"}, status=409)
            await self.edit(client, headers, 1,
                {"type": "reorder", "lineId": "k1:0", "rowIndexes": [1, 1, 3, 4]}, status=422)
            before_id, before_lines, before_request, before_raw = await self.submit_lines(client, headers)
            self.assertEqual(before_lines[0], [(0, 0), (100, 0), (1, 0), (2, 0)])
            self.assertEqual(before_request["line_model"]["segments"][0]["rowIndexes"], [1, 2, 3, 4])

            new_line_id = str(uuid4())
            split, _ = await self.edit(client, headers, 1,
                {"type": "split", "lineId": "k1:0", "at": 2, "newLineId": new_line_id})
            self.assertEqual([line["rowIndexes"] for line in split["model"]["lines"]],
                             [[1, 2], [3, 4], [5, 6]])
            moved, _ = await self.edit(client, headers, 2,
                {"type": "move", "fromLineId": new_line_id, "toLineId": "k2:0",
                 "rowIndex": 4, "position": 1})
            self.assertEqual([line["rowIndexes"] for line in moved["model"]["lines"]],
                             [[1, 2], [3], [5, 4, 6]])
            joined, _ = await self.edit(client, headers, 3,
                {"type": "join", "firstLineId": "k1:0", "secondLineId": new_line_id,
                 "groupCode": "k2"})
            self.assertEqual([line["rowIndexes"] for line in joined["model"]["lines"]],
                             [[1, 2, 3], [5, 4, 6]])
            _, joined_lines, joined_request, _ = await self.submit_lines(client, headers)
            self.assertEqual(joined_lines, [[(0, 0), (100, 0), (1, 0)],
                                            [(0, 10), (2, 0), (10, 10)]])
            self.assertEqual(joined_request["line_model"]["sourceRowIndexes"], [1, 2, 3, 4, 5, 6])
            self.assertEqual(json.loads((self.root / "jobs" / before_id / "request.json").read_text()), before_request)
            self.assertEqual((await client.get(f"/api/v1/jobs/{before_id}/result")).content, before_raw)

            undone, _ = await self.edit(client, headers, 4, {"type": "undo", "targetVersion": 1})
            self.assertEqual(undone["version"], 5)
            self.assertEqual(undone["model"], first["model"])
            history = (await client.get(self.path + "/history?pageSize=2")).json()
            self.assertEqual([item["version"] for item in history["events"]], [5, 4])
            self.assertTrue(history["pagination"]["hasMore"])
            old = (await client.get(self.path + "/versions/2")).json()
            self.assertEqual(old["model"], split["model"])
            self.assertEqual(self.store.read_source_for(self.owner, self.project_id, self.revision_id), SOURCE)

            foreign = SimpleNamespace(user=SimpleNamespace(user_id=str(uuid4())),
                                      csrf_token=headers["X-CSRF-Token"])
            with patch.object(AuthStore, "authenticate", return_value=foreign):
                self.assertEqual((await client.get(self.path + "/current")).status_code, 404)
                await self.edit(client, headers, 5, {"type": "reset"}, status=404)

    async def test_decision_change_requires_explicit_reset_and_invalid_model_is_rejected(self):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url=ORIGIN) as client:
            headers = await self.login(client)
            await self.edit(client, headers, 0, {"type": "reset"})
            comparison = (await client.get(
                f"/api/v1/projects/{self.project_id}/revisions/{self.revision_id}/line-candidates")).json()
            decision = {"requestId": str(uuid4()), "expectedVersion": 0, "action": "A",
                        "sourceSha256": comparison["sourceSha256"],
                        "settingsSha256": comparison["settingsSha256"],
                        "candidateVersion": comparison["candidateVersion"]}
            response = await client.post(
                f"/api/v1/projects/{self.project_id}/revisions/{self.revision_id}/line-decisions/k1",
                json=decision, headers=headers)
            self.assertEqual(response.status_code, 200, response.text)
            current = (await client.get(self.path + "/current")).json()
            self.assertTrue(current["staleDecisions"])
            await self.edit(client, headers, 1, {"type": "reorder", "lineId": "k1:0",
                                                 "rowIndexes": [1, 2, 3, 4]}, status=409)
            job = await client.post("/api/v1/jobs", json={"revisionId": self.revision_id},
                                    headers={**headers, "Idempotency-Key": str(uuid4())})
            self.assertEqual(job.status_code, 409, job.text)
            reset, _ = await self.edit(client, headers, 1, {"type": "reset"})
            self.assertEqual(reset["model"]["lines"][0]["rowIndexes"], [1, 2, 3, 4])
            self.assertFalse((await client.get(self.path + "/current")).json()["staleDecisions"])
            await self.edit(client, headers, 2,
                {"type": "join", "firstLineId": "k1:0", "secondLineId": "k2:0",
                 "groupCode": "unknown"}, status=422)
            await self.edit(client, headers, 2,
                {"type": "move", "fromLineId": "k1:0", "toLineId": "k2:0",
                 "rowIndex": 999, "position": 0}, status=422)
            with patch("autocad_assistance.services.project_store.MAX_LINE_EDIT_BYTES", 1):
                await self.edit(client, headers, 2, {"type": "reset"}, status=413)
            self.assertEqual((await client.get(self.path + "/current")).json()["version"], 2)

            with closing(sqlite3.connect(self.store.db_path)) as db:
                db.execute("UPDATE line_edit_events SET model_json='{}' WHERE event_id=?",
                           (reset["eventId"],))
                db.commit()
            corrupt = await client.post("/api/v1/jobs", json={"revisionId": self.revision_id},
                                        headers={**headers, "Idempotency-Key": str(uuid4())})
            self.assertEqual(corrupt.status_code, 422, corrupt.text)


class LineEditMigrationTests(unittest.TestCase):
    def test_existing_v6_project_database_migrates(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = ProjectStore(root)
            owner = str(uuid4())
            project = store.create_owned_project(owner, "Existing")
            with closing(sqlite3.connect(store.db_path)) as db:
                db.execute("DROP TABLE line_edit_events")
                db.execute("PRAGMA user_version=6")
                db.commit()
            reopened = ProjectStore(root)
            self.assertEqual(reopened.assert_project_owner(owner, project.project_id), project)
            with closing(sqlite3.connect(reopened.db_path)) as db:
                self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 7)
                self.assertIsNotNone(db.execute(
                    "SELECT name FROM sqlite_master WHERE name='line_edit_events'").fetchone())


class LineEditGeometryTests(unittest.TestCase):
    def test_split_breaklines_and_missing_row_rejection(self):
        frame = pd.DataFrame([
            {"Point": "P1", "X": 0, "Y": 0, "Z": 1, "Code": "k1"},
            {"Point": "P2", "X": 100, "Y": 0, "Z": 2, "Code": "k1"},
            {"Point": "P3", "X": 1, "Y": 0, "Z": 3, "Code": "k1"},
            {"Point": "P4", "X": 2, "Y": 0, "Z": 4, "Code": "k1"},
            {"Point": "Q1", "X": 0, "Y": 10, "Z": 5, "Code": "k2"},
            {"Point": "Q2", "X": 10, "Y": 10, "Z": 6, "Code": "k2"},
        ])
        model = {"editableGroupCodes": ["k1", "k2"],
                 "sourceRowIndexes": [1, 2, 3, 4, 5, 6],
                 "segments": [
                     {"groupCode": "k1", "rowIndexes": [1, 2]},
                     {"groupCode": "k1", "rowIndexes": [3, 4]},
                     {"groupCode": "k2", "rowIndexes": [5, 6]},
                 ]}
        breaklines = extract_structural_breaklines(frame, line_model=model)
        self.assertEqual([[point[0] for point in line] for line in breaklines],
                         [[0, 100], [1, 2], [0, 10]])
        broken = {**model, "segments": [
            {"groupCode": "k1", "rowIndexes": [1, 2]},
            {"groupCode": "k1", "rowIndexes": [3, 3]},
            {"groupCode": "k2", "rowIndexes": [5, 6]},
        ]}
        with self.assertRaisesRegex(ValueError, "duplicates or drops"):
            extract_structural_breaklines(frame, line_model=broken)


if __name__ == "__main__":
    unittest.main()
