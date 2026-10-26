"""Transactional owner quotas and explicit retention cleanup."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing, redirect_stdout
from decimal import Decimal
from io import BytesIO, StringIO
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from uuid import uuid4

import httpx

from autocad_assistance.api import create_app
from autocad_assistance.services.auth_store import AuthStore
from autocad_assistance.services.project_store import (
    ProjectNotFoundError, ProjectStore, ResourceQuota, ResourceQuotaExceededError,
)
from autocad_assistance.services.resource_cleanup import main as cleanup_main
from autocad_assistance.services.survey_contract import SurveyContext
from autocad_assistance.services.uploads import store_upload


SOURCE = b"Point,X,Y,Z,Code\nP1,123.456,234.567,11.2,K\n"
PASSWORD = "Synthetic-only-owner-passphrase-123"


class ResourceLimitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.owner = str(uuid4())
        self.quota = ResourceQuota(
            max_projects=1, max_uploads=2, max_revisions=1,
            max_jobs=1, max_total_bytes=len(SOURCE) * 3 + 10,
        )
        self.store = ProjectStore(
            self.root / "projects", quota=self.quota, upload_retention_days=1,
        )
        self.upload_root = self.root / "uploads"

    def upload(self):
        return store_upload(BytesIO(SOURCE), "source.csv", self.upload_root, 10 * 1024 * 1024)

    def revision(self, project_id, upload_id):
        return self.store.add_revision_for(
            self.owner, project_id, self.upload_root, upload_id,
            context=SurveyContext(scale_factor=Decimal("500")),
            settings={}, algorithm_version="v1",
        )

    def test_count_and_byte_limits_preserve_accepted_records(self):
        project = self.store.create_owned_project(self.owner, "One")
        with self.assertRaises(ResourceQuotaExceededError):
            self.store.create_owned_project(self.owner, "Two")
        one = self.upload()
        two = self.upload()
        self.store.register_upload_owner(self.owner, one)
        self.store.register_upload_owner(self.owner, two)
        with self.assertRaises(ResourceQuotaExceededError):
            self.store.register_upload_owner(self.owner, self.upload())
        revision = self.revision(project.project_id, one.upload_id)
        with self.assertRaises(ResourceQuotaExceededError):
            self.revision(project.project_id, two.upload_id)
        first_job = str(uuid4())
        self.store.register_job_for(self.owner, revision.revision_id, first_job, request_settings={})
        with self.assertRaises(ResourceQuotaExceededError):
            self.store.register_job_for(self.owner, revision.revision_id, str(uuid4()), request_settings={})
        self.store.update_job_status(first_job, "succeeded")
        with self.assertRaises(ResourceQuotaExceededError):
            self.store.publish_result_for(self.owner, first_job, b"X" * 11)
        self.assertIsNone(self.store.get_job(first_job).result_sha256)
        self.store.publish_result_for(self.owner, first_job, b"X" * 10)
        self.assertEqual(self.store.read_result_for(self.owner, first_job), b"X" * 10)
        reopened = ProjectStore(self.root / "projects", quota=self.quota, upload_retention_days=1)
        self.assertEqual(reopened.read_source_for(self.owner, project.project_id, revision.revision_id), SOURCE)
        with self.assertRaises(ResourceQuotaExceededError):
            reopened.create_owned_project(self.owner, "After restart")

    def test_concurrent_project_writers_cannot_exceed_limit(self):
        def create(index):
            store = ProjectStore(self.root / "projects", quota=self.quota)
            try:
                return store.create_owned_project(self.owner, f"Project {index}").project_id
            except ResourceQuotaExceededError:
                return None
        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(create, (1, 2)))
        self.assertEqual(sum(value is not None for value in outcomes), 1)
        self.assertEqual(len(self.store.list_projects_for(self.owner)), 1)

    def test_retention_dry_run_apply_symlink_retry_and_revision_survival(self):
        project = self.store.create_owned_project(self.owner, "One")
        one = self.upload()
        two = self.upload()
        first = self.store.register_upload_owner(self.owner, one)
        second = self.store.register_upload_owner(self.owner, two)
        revision = self.revision(project.project_id, one.upload_id)
        cutoff = max(first.expires_at, second.expires_at)
        self.assertEqual(self.store.expired_uploads(now=cutoff - 1), ())
        dry = self.store.cleanup_expired_uploads(self.upload_root, now=cutoff, apply=False)
        self.assertEqual(len(dry.candidates), 2)
        self.assertEqual(dry.removed, ())
        self.assertEqual(self.store.cleanup_journal(), ())
        self.assertTrue(one.path.exists())
        two.path.unlink()
        outside = self.root / "outside.csv"
        outside.write_bytes(SOURCE)
        two.path.symlink_to(outside)
        applied = self.store.cleanup_expired_uploads(self.upload_root, now=cutoff, apply=True)
        self.assertIn(one.upload_id, applied.removed)
        self.assertIn(two.upload_id, applied.failed)
        self.assertEqual({item.outcome for item in self.store.cleanup_journal()}, {"removed", "failed"})
        self.assertEqual(outside.read_bytes(), SOURCE)
        self.assertEqual(self.store.read_source_for(self.owner, project.project_id, revision.revision_id), SOURCE)
        self.assertFalse(one.path.exists())
        with self.assertRaises(ProjectNotFoundError):
            self.store.assert_upload_owner(self.owner, two.upload_id)
        two.path.unlink()
        two.path.write_bytes(SOURCE)
        retry = self.store.cleanup_expired_uploads(self.upload_root, now=cutoff, apply=True)
        self.assertEqual(retry.removed, (two.upload_id,))
        self.assertEqual(retry.failed, ())
        self.assertFalse(two.path.exists())
        self.assertEqual(self.store.cleanup_journal()[0].outcome, "removed")
        reopened = ProjectStore(self.store.root, quota=self.quota, upload_retention_days=1)
        outcomes = [item.outcome for item in reopened.cleanup_journal()]
        self.assertEqual(outcomes[0], "removed")
        self.assertEqual(outcomes.count("removed"), 2)
        self.assertEqual(outcomes.count("failed"), 1)

    def test_retention_absent_and_version2_migration_are_non_destructive(self):
        root = self.root / "legacy"
        root.mkdir()
        owner = str(uuid4())
        upload_id = str(uuid4())
        with closing(sqlite3.connect(root / "projects.sqlite3")) as db, db:
            db.executescript("""
                CREATE TABLE projects(project_id TEXT PRIMARY KEY,name TEXT NOT NULL,created_at TEXT NOT NULL,owner_id TEXT);
                CREATE TABLE upload_owners(upload_id TEXT PRIMARY KEY,owner_id TEXT NOT NULL,
                    sha256 TEXT NOT NULL,stored_format TEXT NOT NULL,size_bytes INTEGER NOT NULL);
                PRAGMA user_version=2;
            """)
            db.execute("INSERT INTO upload_owners VALUES(?,?,?,?,?)", (upload_id, owner, "a" * 64, "csv", 5))
        legacy = ProjectStore(root, upload_retention_days=1)
        row = legacy.assert_upload_owner(owner, upload_id)
        self.assertIsNone(row.created_at)
        self.assertIsNone(row.expires_at)
        self.assertEqual(legacy.expired_uploads(now=2**40), ())
        no_retention = ProjectStore(self.root / "without-retention")
        stored = self.upload()
        new_row = no_retention.register_upload_owner(self.owner, stored)
        self.assertIsNone(new_row.expires_at)
        self.assertEqual(no_retention.expired_uploads(now=2**40), ())

    def test_cli_dry_run_changes_no_upload_and_requires_explicit_apply(self):
        item = self.upload()
        record = self.store.register_upload_owner(self.owner, item)
        with closing(sqlite3.connect(self.store.db_path)) as db, db:
            db.execute("UPDATE upload_owners SET expires_at=1 WHERE upload_id=?", (item.upload_id,))
        output = StringIO()
        args = ["--project-root", str(self.store.root), "--upload-root", str(self.upload_root)]
        with redirect_stdout(output):
            self.assertEqual(cleanup_main(args), 0)
        self.assertEqual(json.loads(output.getvalue())["mode"], "dry-run")
        self.assertEqual(json.loads(output.getvalue())["journal"], [])
        self.assertTrue(item.path.exists())
        output = StringIO()
        with redirect_stdout(output):
            self.assertEqual(cleanup_main(args + ["--apply"]), 0)
        self.assertEqual(json.loads(output.getvalue())["removed"], [item.upload_id])
        self.assertEqual(json.loads(output.getvalue())["journal"][0]["outcome"], "removed")
        self.assertFalse(item.path.exists())


class UploadQuotaApiTests(unittest.IsolatedAsyncioTestCase):
    async def test_quota_rejection_removes_second_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            AuthStore(root / "auth").create_owner("owner", PASSWORD)
            app = create_app(
                upload_root=root / "uploads", auth_root=root / "auth",
                project_root=root / "projects", auth_origin="https://testserver",
                resource_quota=ResourceQuota(max_uploads=1),
            )
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="https://testserver") as client:
                login = await client.post(
                    "/api/v1/auth/login", json={"username": "owner", "password": PASSWORD},
                    headers={"Origin": "https://testserver"},
                )
                headers = {"Origin": "https://testserver", "X-CSRF-Token": login.json()["csrfToken"]}
                first = await client.post(
                    "/api/v1/uploads", headers=headers, files={"file": ("survey.csv", SOURCE, "text/csv")},
                )
                second = await client.post(
                    "/api/v1/uploads", headers=headers, files={"file": ("survey.csv", SOURCE, "text/csv")},
                )
                self.assertEqual(first.status_code, 201, first.text)
                self.assertEqual(second.status_code, 429, second.text)
                self.assertEqual(second.json()["error"]["code"], "QUOTA_EXCEEDED")
                self.assertEqual(len(list((root / "uploads").iterdir())), 1)


if __name__ == "__main__":
    unittest.main()
