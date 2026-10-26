"""Metadata-only dataset audit never treats assertions as verified rights."""

from __future__ import annotations

from contextlib import closing
from decimal import Decimal
from io import BytesIO, StringIO
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
from autocad_assistance.services.dataset_readiness import audit_owner
from autocad_assistance.services.project_store import ProjectStore
from autocad_assistance.services.reference_archive import create_reference
from autocad_assistance.services.survey_contract import SurveyContext
from autocad_assistance.services.uploads import store_upload


ORIGIN = "https://testserver"
PASSWORD = "Synthetic-only-owner-passphrase-123"
SOURCE = b"Point,X,Y,Z,Code,Comments\nP1,0,0,1,k1,\nP2,1,0,2,k1,\n"
MAPPING = {"Point": 0, "X": 1, "Y": 2, "Z": 3, "Code": 4, "Comments": 5}
PRIVATE_EVIDENCE = "PRIVATE_PERMISSION_EVIDENCE_DO_NOT_RETURN"


def reference_dxf() -> bytes:
    drawing = ezdxf.new("R2010")
    drawing.modelspace().add_line((0, 0), (1, 0))
    output = StringIO()
    drawing.write(output)
    return output.getvalue().encode("utf-8")


class DatasetReadinessTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.owner = AuthStore(self.root / "auth").create_owner("owner", PASSWORD).user_id
        self.store = ProjectStore(self.root / "projects")
        self.project = self.store.create_owned_project(self.owner, "Synthetic readiness")
        self.app = create_app(auth_root=self.root / "auth", project_root=self.root / "projects",
                              upload_root=self.root / "uploads", auth_origin=ORIGIN)

    def archive(self, uses):
        upload = store_upload(BytesIO(SOURCE), "field.csv", self.root / "uploads", 10 * 1024 * 1024)
        self.store.register_upload_owner(self.owner, upload)
        revision = self.store.add_revision_for(
            self.owner, self.project.project_id, self.root / "uploads", upload.upload_id,
            context=SurveyContext(scale_factor=Decimal("500")),
            settings={"mapping": MAPPING}, algorithm_version="geoai-dxf-v1",
        )
        return create_reference(self.store, self.owner, revision.revision_id, str(uuid4()),
            reference_dxf(), {
                "fieldProvenance": "Synthetic source made in test",
                "referenceProvenance": "Synthetic independent DXF made in test",
                "rightsHolder": "Private synthetic author",
                "permissionEvidence": PRIVATE_EVIDENCE,
                "permittedUses": uses,
            })

    async def login(self, client, username="owner"):
        response = await client.post("/api/v1/auth/login", json={
            "username": username, "password": PASSWORD,
        }, headers={"Origin": ORIGIN})
        self.assertEqual(response.status_code, 200, response.text)

    async def test_empty_owner_has_concrete_blockers_and_authentication(self):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url=ORIGIN) as client:
            self.assertEqual((await client.get("/api/v1/dataset-readiness")).status_code, 401)
            await self.login(client)
            response = await client.get("/api/v1/dataset-readiness")
            self.assertEqual(response.status_code, 200, response.text)
            report = response.json()
            self.assertTrue(report["complete"])
            self.assertFalse(report["readyForTraining"])
            self.assertFalse(report["readyForEvaluation"])
            self.assertEqual(report["archiveCount"], 0)
            codes = {item["code"] for item in report["blockers"]}
            self.assertIn("NO_REFERENCES", codes)
            self.assertIn("RIGHTS_UNVERIFIED", codes)
            self.assertIn("OBJECT_FAMILY_ID_MISSING", codes)
            self.assertEqual(response.headers["cache-control"], "no-store")

    async def test_training_assertion_does_not_clear_evidence_or_leak_secrets(self):
        entry = self.archive(["training", "evaluation"])
        with patch.object(self.store, "read_reference_for", side_effect=AssertionError("raw read")):
            report = audit_owner(self.store, self.owner)
        self.assertEqual(report["archiveCount"], 1)
        self.assertEqual(report["trainingUseAssertions"], 1)
        self.assertEqual(report["evaluationUseAssertions"], 1)
        self.assertFalse(report["readyForTraining"])
        self.assertFalse(report["readyForEvaluation"])
        rendered = json.dumps(report)
        self.assertNotIn(PRIVATE_EVIDENCE, rendered)
        self.assertNotIn(self.owner, rendered)
        self.assertNotIn(entry["referenceSha256"], rendered)
        codes = {item["code"] for item in report["blockers"]}
        self.assertNotIn("TRAINING_USE_NOT_ASSERTED", codes)
        self.assertIn("RIGHTS_UNVERIFIED", codes)
        self.assertIn("INDEPENDENT_SPLIT_MISSING", codes)
        self.assertIn("REFERENCE_REVIEW_MISSING", codes)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url=ORIGIN) as client:
            await self.login(client)
            response = await client.get("/api/v1/dataset-readiness")
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json(), report)

        other_auth = self.root / "other-auth"
        AuthStore(other_auth).create_owner("other", PASSWORD)
        foreign_app = create_app(auth_root=other_auth, project_root=self.root / "projects",
                                 upload_root=self.root / "uploads", auth_origin=ORIGIN)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=foreign_app), base_url=ORIGIN) as client:
            await self.login(client, "other")
            foreign = await client.get("/api/v1/dataset-readiness")
            self.assertEqual(foreign.status_code, 200, foreign.text)
            self.assertEqual(foreign.json()["archiveCount"], 0)

    async def test_tamper_and_limits_fail_closed(self):
        entry = self.archive(["comparison"])
        with patch("autocad_assistance.services.dataset_readiness.MAX_AUDIT_PROJECTS", 0):
            limited = audit_owner(self.store, self.owner)
        self.assertFalse(limited["complete"])
        self.assertEqual(limited["blockers"][0]["code"], "AUDIT_PROJECT_LIMIT")
        with patch("autocad_assistance.services.dataset_readiness.MAX_AUDIT_ARCHIVES", 0):
            limited = audit_owner(self.store, self.owner)
        self.assertFalse(limited["complete"])
        self.assertEqual(limited["blockers"][0]["code"], "AUDIT_ARCHIVE_LIMIT")
        with closing(sqlite3.connect(self.store.db_path)) as db:
            db.execute("UPDATE reference_entries SET metadata_json=? WHERE entry_id=?",
                       ('{"permittedUses":["training"]}', entry["entryId"]))
            db.commit()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url=ORIGIN) as client:
            await self.login(client)
            response = await client.get("/api/v1/dataset-readiness")
            self.assertEqual(response.status_code, 422)
            self.assertEqual(response.json()["error"]["code"], "READINESS_AUDIT_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
