"""Owner authorization, migration, and integrity regression tests."""

from contextlib import closing
from decimal import Decimal
from io import BytesIO
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

import httpx

from autocad_assistance.api import create_app
from autocad_assistance.services.auth_store import AuthStore
from autocad_assistance.services.project_store import ProjectIntegrityError, ProjectNotFoundError, ProjectStore
from autocad_assistance.services.survey_contract import SurveyContext
from autocad_assistance.services.uploads import store_upload


SOURCE = b"Point,X,Y,Z,Code\nP1,123.456,234.567,11.2,K\n"
PASSWORD = "Synthetic-only-owner-passphrase-123"


class OwnershipTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.auth = AuthStore(self.root / "auth")
        self.owner = self.auth.create_owner("owner", PASSWORD).user_id
        self.other = str(uuid4())
        self.store = ProjectStore(self.root / "projects")
        self.app = create_app(
            upload_root=self.root / "uploads", auth_root=self.root / "auth",
            auth_origin="https://testserver", project_root=self.root / "projects",
        )

    async def login(self, client):
        response = await client.post(
            "/api/v1/auth/login", json={"username": "owner", "password": PASSWORD},
            headers={"Origin": "https://testserver"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return {"Origin": "https://testserver", "X-CSRF-Token": response.json()["csrfToken"]}

    async def test_upload_guard_owner_integrity_and_rollback(self):
        transport = httpx.ASGITransport(app=self.app)
        async with httpx.AsyncClient(transport=transport, base_url="https://testserver") as client:
            anonymous = await client.post("/api/v1/uploads", content=b"invalid multipart")
            self.assertEqual(anonymous.status_code, 401)
            headers = await self.login(client)
            self.assertEqual((await client.post("/api/v1/uploads", content=b"invalid multipart")).status_code, 403)
            self.assertFalse((self.root / "uploads").exists())
            accepted = await client.post(
                "/api/v1/uploads", headers=headers,
                files={"file": ("survey.csv", SOURCE, "text/csv")},
            )
            self.assertEqual(accepted.status_code, 201, accepted.text)
            upload_id = accepted.json()["uploadId"]
            self.assertEqual(self.store.assert_upload_owner(self.owner, upload_id).sha256, accepted.json()["sha256"])
            self.assertEqual((await client.get(f"/api/v1/uploads/{upload_id}/preview")).status_code, 200)
            for candidate in (str(uuid4()), upload_id):
                if candidate == upload_id:
                    with closing(sqlite3.connect(self.store.db_path)) as db, db:
                        db.execute("UPDATE upload_owners SET owner_id=? WHERE upload_id=?", (self.other, upload_id))
                response = await client.get(f"/api/v1/uploads/{candidate}/preview")
                self.assertEqual(response.status_code, 404)
            with closing(sqlite3.connect(self.store.db_path)) as db, db:
                db.execute("UPDATE upload_owners SET owner_id=? WHERE upload_id=?", (self.owner, upload_id))
            target = self.root / "uploads" / upload_id / f"{upload_id}.csv"
            target.write_bytes(SOURCE + b"P2,1,2,3,K\n")
            self.assertEqual((await client.get(f"/api/v1/uploads/{upload_id}/preview")).status_code, 422)
            target.unlink()
            outside = self.root / "outside.csv"
            outside.write_bytes(SOURCE)
            target.symlink_to(outside)
            self.assertEqual((await client.get(f"/api/v1/uploads/{upload_id}/preview")).status_code, 404)
            self.assertEqual(outside.read_bytes(), SOURCE)
            with patch.object(ProjectStore, "register_upload_owner", side_effect=RuntimeError("DB fault")):
                failed = await client.post(
                    "/api/v1/uploads", headers=headers,
                    files={"file": ("survey.csv", SOURCE, "text/csv")},
                )
            self.assertEqual(failed.status_code, 500)
            self.assertEqual(len(list((self.root / "uploads").iterdir())), 1)

    async def test_project_job_source_result_idor_and_unowned(self):
        upload = store_upload(BytesIO(SOURCE), "survey.csv", self.root / "uploads", 10 * 1024 * 1024)
        self.store.register_upload_owner(self.owner, upload)
        mine = self.store.create_owned_project(self.owner, "Mine")
        foreign = self.store.create_owned_project(self.other, "Other")
        unowned = self.store.create_project("Legacy")
        revision = self.store.add_revision_for(
            self.owner, mine.project_id, self.root / "uploads", upload.upload_id,
            context=SurveyContext(scale_factor=Decimal("500")), settings={}, algorithm_version="v1",
        )
        job_id = str(uuid4())
        self.store.register_job_for(self.owner, revision.revision_id, job_id, request_settings={})
        self.store.update_job_status(job_id, "succeeded")
        self.store.publish_result_for(self.owner, job_id, b"DXF result")
        for candidate in (foreign.project_id, unowned.project_id, str(uuid4())):
            with self.assertRaises(ProjectNotFoundError):
                self.store.assert_project_owner(self.owner, candidate)
        with self.assertRaises(ProjectNotFoundError):
            self.store.read_source_for(self.other, mine.project_id, revision.revision_id)
        with self.assertRaises(ProjectNotFoundError):
            self.store.read_result_for(self.other, job_id)
        transport = httpx.ASGITransport(app=self.app)
        async with httpx.AsyncClient(transport=transport, base_url="https://testserver") as client:
            self.assertEqual((await client.get(f"/api/v1/jobs/{job_id}/result")).status_code, 401)
            await self.login(client)
            source_url = f"/api/v1/projects/{mine.project_id}/revisions/{revision.revision_id}/source"
            self.assertEqual((await client.get(source_url)).content, SOURCE)
            self.assertEqual((await client.get(f"/api/v1/jobs/{job_id}/result")).content, b"DXF result")
            for candidate in (foreign.project_id, unowned.project_id, str(uuid4())):
                response = await client.get(f"/api/v1/projects/{candidate}/revisions/{revision.revision_id}/source")
                self.assertEqual(response.status_code, 404)
            result_file = next((self.root / "projects" / "projects").glob("**/results/*.dxf"))
            result_file.write_bytes(b"tampered")
            self.assertEqual((await client.get(f"/api/v1/jobs/{job_id}/result")).status_code, 422)


class MigrationTests(unittest.TestCase):
    def test_v1_rows_remain_unowned_and_bytes_untouched(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "projects"
            root.mkdir()
            legacy_id = str(uuid4())
            database = root / "projects.sqlite3"
            with closing(sqlite3.connect(database)) as db, db:
                db.executescript("""
                    CREATE TABLE projects (
                        project_id TEXT PRIMARY KEY, name TEXT NOT NULL,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    );
                    CREATE TABLE revisions (
                        revision_id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(project_id),
                        sequence INTEGER NOT NULL, parent_revision_id TEXT REFERENCES revisions(revision_id),
                        source_format TEXT NOT NULL, source_sha256 TEXT NOT NULL,
                        source_size INTEGER NOT NULL, settings_json TEXT NOT NULL,
                        settings_sha256 TEXT NOT NULL, algorithm_version TEXT NOT NULL,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(project_id, sequence)
                    );
                    CREATE TABLE jobs (
                        job_id TEXT PRIMARY KEY, revision_id TEXT NOT NULL REFERENCES revisions(revision_id),
                        request_json TEXT NOT NULL, request_sha256 TEXT NOT NULL,
                        status TEXT NOT NULL, result_sha256 TEXT, result_size INTEGER,
                        algorithm_version TEXT NOT NULL,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    );
                    PRAGMA user_version=1;
                """)
                db.execute("INSERT INTO projects(project_id,name) VALUES (?,?)", (legacy_id, "Legacy"))
            store = ProjectStore(root)
            self.assertIsNone(store.get_project(legacy_id).owner_id)
            with self.assertRaises(ProjectNotFoundError):
                store.assert_project_owner(str(uuid4()), legacy_id)
            with closing(sqlite3.connect(database)) as db, db:
                self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 3)
                self.assertEqual(db.execute("SELECT name FROM projects WHERE project_id=?", (legacy_id,)).fetchone()[0], "Legacy")
            self.assertEqual(ProjectStore(root).get_project(legacy_id).name, "Legacy")


if __name__ == "__main__":
    unittest.main()
