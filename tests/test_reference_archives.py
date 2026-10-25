"""Synthetic-only private reference archive contract and integrity checks."""

from __future__ import annotations

import json
from contextlib import closing
from decimal import Decimal
from io import BytesIO, StringIO
from pathlib import Path
import sqlite3
import tempfile
import unittest
from uuid import uuid4

import ezdxf
import httpx

from autocad_assistance.api import create_app
from autocad_assistance.services.auth_store import AuthStore
from autocad_assistance.services.project_store import ProjectStore, ResourceQuota
from autocad_assistance.services.reference_archive import create_reference
from autocad_assistance.services.survey_contract import SurveyContext
from autocad_assistance.services.uploads import store_upload


ORIGIN = "https://testserver"
PASSWORD = "Synthetic-only-owner-passphrase-123"
SOURCE = b"Point,X,Y,Z,Code,Comments\nP1,0,0,1,k1,\nP2,1,0,2,k1,\n"
MAPPING = {"Point": 0, "X": 1, "Y": 2, "Z": 3, "Code": 4, "Comments": 5}
META = {
    "fieldProvenance": "Synthetic field.csv created in test; no real field data",
    "referenceProvenance": "Independent synthetic DXF drawn in test",
    "rightsHolder": "Test fixture author",
    "permissionEvidence": "Synthetic fixture created for this test; author permits comparison only",
    "permittedUses": ["comparison"],
}


def synthetic_dxf() -> bytes:
    drawing = ezdxf.new("R2010")
    drawing.modelspace().add_line((0, 0), (1, 0))
    output = StringIO()
    drawing.write(output)
    return output.getvalue().encode("utf-8")


class ReferenceArchiveTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        auth = AuthStore(self.root / "auth")
        self.owner = auth.create_owner("owner", PASSWORD).user_id
        self.store = ProjectStore(self.root / "projects")
        upload = store_upload(BytesIO(SOURCE), "source.csv", self.root / "uploads", 10 * 1024 * 1024)
        self.store.register_upload_owner(self.owner, upload)
        project = self.store.create_owned_project(self.owner, "Synthetic reference archive")
        self.project_id = project.project_id
        revision = self.store.add_revision_for(
            self.owner, project.project_id, self.root / "uploads", upload.upload_id,
            context=SurveyContext(scale_factor=Decimal("500")),
            settings={"mapping": MAPPING}, algorithm_version="geoai-dxf-v1",
        )
        self.revision_id = revision.revision_id
        self.raw = synthetic_dxf()
        self.app = create_app(auth_root=self.root / "auth", project_root=self.root / "projects",
                              upload_root=self.root / "uploads", auth_origin=ORIGIN)

    async def login(self, client, user="owner"):
        response = await client.post("/api/v1/auth/login", json={"username": user, "password": PASSWORD},
                                     headers={"Origin": ORIGIN})
        self.assertEqual(response.status_code, 200, response.text)
        return {"Origin": ORIGIN, "X-CSRF-Token": response.json()["csrfToken"]}

    async def archive(self, client, headers, *, key=None, metadata=None, raw=None):
        return await client.post(
            "/api/v1/reference-archives",
            data={"revisionId": self.revision_id, "metadata": json.dumps(metadata if metadata is not None else META)},
            files={"referenceDxf": ("correct.dxf", self.raw if raw is None else raw, "application/dxf")},
            headers={**headers, "Idempotency-Key": key or str(uuid4())},
        )

    async def test_archive_round_trip_idempotency_and_owner(self):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url=ORIGIN) as client:
            self.assertEqual((await client.get(f"/api/v1/projects/{self.project_id}/reference-archives")).status_code, 401)
            headers = await self.login(client)
            key = str(uuid4())
            saved = await self.archive(client, headers, key=key)
            self.assertEqual(saved.status_code, 201, saved.text)
            entry = saved.json()
            self.assertEqual(entry["permissionStatus"], "user_asserted_unverified")
            self.assertEqual(entry["metadata"]["permittedUses"], ["comparison"])
            self.assertEqual(entry["corrections"], {"decisions": [], "lineEdit": None})
            repeated = await self.archive(client, headers, key=key)
            self.assertEqual(repeated.status_code, 200, repeated.text)
            self.assertEqual(repeated.json(), entry)
            changed = await self.archive(client, headers, key=key, raw=synthetic_dxf() + b"\n999\n")
            self.assertEqual(changed.status_code, 409, changed.text)
            listed = await client.get(f"/api/v1/projects/{self.project_id}/reference-archives")
            self.assertEqual(listed.json()["pagination"]["totalItems"], 1)
            path = f"/api/v1/reference-archives/{entry['entryId']}"
            self.assertEqual((await client.get(path)).json(), entry)
            download = await client.get(path + "/dxf")
            self.assertEqual(download.status_code, 200, download.text[:100])
            self.assertEqual(download.content, self.raw)
            self.assertEqual(download.headers["cache-control"], "no-store")
            self.assertEqual(self.store.read_source_for(self.owner, self.project_id, self.revision_id), SOURCE)
        other_auth = self.root / "other-auth"
        AuthStore(other_auth).create_owner("other", PASSWORD)
        foreign_app = create_app(auth_root=other_auth, project_root=self.root / "projects",
                                 upload_root=self.root / "uploads", auth_origin=ORIGIN)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=foreign_app), base_url=ORIGIN) as client:
            foreign_headers = await self.login(client, "other")
            self.assertEqual((await client.get(path)).status_code, 404)
            self.assertEqual((await client.get(path + "/dxf")).status_code, 404)
            self.assertEqual((await client.get(f"/api/v1/projects/{self.project_id}/reference-archives")).status_code, 404)
            self.assertEqual((await self.archive(client, foreign_headers)).status_code, 404)

        restarted = ProjectStore(self.root / "projects")
        self.assertEqual(restarted.read_reference_for(self.owner, entry["entryId"]), self.raw)
        self.assertEqual(restarted.get_reference_for(self.owner, entry["entryId"]).entry_sha256,
                         self.store.get_reference_for(self.owner, entry["entryId"]).entry_sha256)

    async def test_rejects_missing_rights_invalid_dxf_and_limits(self):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url=ORIGIN) as client:
            headers = await self.login(client)
            incomplete = dict(META)
            del incomplete["permissionEvidence"]
            self.assertEqual((await self.archive(client, headers, metadata=incomplete)).status_code, 422)
            self.assertEqual((await self.archive(client, headers, raw=b"not dxf")).status_code, 422)
            self.assertEqual((await self.archive(client, headers, raw=b"x" * (25 * 1024 * 1024 + 1))).status_code, 413)
            self.assertEqual((await client.post("/api/v1/reference-archives", data={
                "revisionId": self.revision_id, "metadata": json.dumps(META),
            }, files={"referenceDxf": ("x.dxf", self.raw, "application/dxf")},
                headers={"Origin": ORIGIN, "Idempotency-Key": str(uuid4())})).status_code, 403)
            self.assertEqual((await client.get(f"/api/v1/projects/{self.project_id}/reference-archives")).json()
                             ["pagination"]["totalItems"], 0)

    async def test_tamper_bytes_and_metadata_detected(self):
        entry = create_reference(self.store, self.owner, self.revision_id, str(uuid4()), self.raw, META)
        entry_id = entry["entryId"]
        path = self.root / "projects" / "projects" / self.project_id / "references" / f"{entry_id}.dxf"
        path.write_bytes(b"tampered")
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url=ORIGIN) as client:
            await self.login(client)
            self.assertEqual((await client.get(f"/api/v1/reference-archives/{entry_id}/dxf")).status_code, 422)
        with closing(sqlite3.connect(self.store.db_path)) as db:
            db.execute("UPDATE reference_entries SET metadata_json=? WHERE entry_id=?",
                       (json.dumps({"rightsHolder": "attacker"}), entry_id))
            db.commit()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url=ORIGIN) as client:
            await self.login(client)
            self.assertEqual((await client.get(f"/api/v1/reference-archives/{entry_id}")).status_code, 422)

    async def test_correction_event_snapshot_is_fixed(self):
        edit_path = (f"/api/v1/projects/{self.project_id}/revisions/"
                     f"{self.revision_id}/line-edits")
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url=ORIGIN) as client:
            headers = await self.login(client)
            first = await client.post(edit_path, headers=headers, json={
                "requestId": str(uuid4()), "expectedVersion": 0,
                "operation": {"type": "reset"},
            })
            self.assertEqual(first.status_code, 200, first.text)
            first_event = first.json()
            saved = await self.archive(client, headers)
            self.assertEqual(saved.status_code, 201, saved.text)
            archived = saved.json()
            self.assertEqual(archived["corrections"]["lineEdit"], {
                "eventId": first_event["eventId"], "version": 1,
                "modelSha256": first_event["modelSha256"],
            })
            second = await client.post(edit_path, headers=headers, json={
                "requestId": str(uuid4()), "expectedVersion": 1,
                "operation": {"type": "reset"},
            })
            self.assertEqual(second.status_code, 200, second.text)
            self.assertNotEqual(second.json()["eventId"], first_event["eventId"])
            again = await client.get(f"/api/v1/reference-archives/{archived['entryId']}")
            self.assertEqual(again.status_code, 200, again.text)
            self.assertEqual(again.json()["corrections"], archived["corrections"])

    async def test_quota_and_schema_migration(self):
        previous = self.root / "previous"
        previous_store = ProjectStore(previous)
        with closing(sqlite3.connect(previous_store.db_path)) as db:
            db.execute("DROP TABLE reference_entries")
            db.execute("PRAGMA user_version=7")
            db.commit()
        migrated = ProjectStore(previous)
        with closing(sqlite3.connect(migrated.db_path)) as db:
            self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 8)
        strict = ProjectStore(self.root / "projects", quota=ResourceQuota(max_references=1))
        create_reference(strict, self.owner, self.revision_id, str(uuid4()), self.raw, META)
        with self.assertRaisesRegex(ValueError, "quota"):
            create_reference(strict, self.owner, self.revision_id, str(uuid4()), self.raw, META)
        bytes_limited = ProjectStore(self.root / "projects",
            quota=ResourceQuota(max_reference_bytes=len(self.raw)))
        with self.assertRaisesRegex(ValueError, "reference byte quota"):
            create_reference(bytes_limited, self.owner, self.revision_id, str(uuid4()), self.raw, META)


if __name__ == "__main__":
    unittest.main()
