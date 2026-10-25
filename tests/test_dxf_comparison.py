"""Exact synthetic DXF diagnostics and owner-scoped comparison API."""

from __future__ import annotations

from decimal import Decimal
from io import BytesIO, StringIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

import ezdxf
import httpx

from autocad_assistance.api import create_app
from autocad_assistance.services.auth_store import AuthStore
from autocad_assistance.services.dxf_compare import (
    DxfCompareInvalidError, DxfCompareLimitError, compare_dxf, inventory,
)
from autocad_assistance.services.project_store import ProjectStore
from autocad_assistance.services.reference_archive import create_reference
from autocad_assistance.services.survey_contract import SurveyContext
from autocad_assistance.services.uploads import store_upload


ORIGIN = "https://testserver"
PASSWORD = "Synthetic-only-owner-passphrase-123"
SOURCE = b"Point,X,Y,Z,Code,Comments\nP1,0,0,1,k1,\nP2,1,0,2,k1,\n"
MAPPING = {"Point": 0, "X": 1, "Y": 2, "Z": 3, "Code": 4, "Comments": 5}
META = {
    "fieldProvenance": "Synthetic field.csv created in test",
    "referenceProvenance": "Independent synthetic reference DXF created in test",
    "rightsHolder": "Synthetic fixture author",
    "permissionEvidence": "Author permits comparison of created synthetic files",
    "permittedUses": ["comparison"],
}


def drawing_bytes(*, changed=False, circle=False, block=False) -> bytes:
    drawing = ezdxf.new("R2010")
    msp = drawing.modelspace()
    msp.add_point((20, 20) if changed else (10, 10), dxfattribs={"layer": "POINTS"})
    msp.add_line((0, 0), (2, 1) if changed else (2, 0),
                 dxfattribs={"layer": "WRONG" if changed else "LINES"})
    msp.add_lwpolyline([(0, 1), (2, 1)], dxfattribs={"layer": "LINES"})
    msp.add_mtext("wrong label" if changed else "correct label",
                  dxfattribs={"layer": "LABELS", "insert": (5, 5, 0)})
    if block:
        drawing.blocks.new("POLE")
        drawing.blocks.new("TREE")
        msp.add_blockref("TREE" if changed else "POLE", (3, 3, 0),
                         dxfattribs={"layer": "SYMBOLS", "rotation": 45 if changed else 0})
    if circle:
        msp.add_circle((0, 0), 1, dxfattribs={"layer": "UNSUPPORTED"})
    output = StringIO()
    drawing.write(output)
    return output.getvalue().encode("utf-8")


class DxfCompareTests(unittest.TestCase):
    def test_mtext_rotation_is_compared(self):
        def make(rotation):
            drawing = ezdxf.new("R2010")
            drawing.modelspace().add_mtext("label", dxfattribs={
                "layer": "LABELS", "insert": (1, 2, 0), "rotation": rotation,
            })
            output = StringIO()
            drawing.write(output)
            return output.getvalue().encode("utf-8")

        report = compare_dxf(make(0), make(45))
        self.assertTrue(report["complete"])
        self.assertEqual(report["metrics"]["wrongRotations"], 1)

    def test_long_line_example_is_bounded(self):
        def make(last_y):
            drawing = ezdxf.new("R2010")
            drawing.modelspace().add_lwpolyline(
                [(i, last_y if i == 19 else 0) for i in range(20)])
            output = StringIO()
            drawing.write(output)
            return output.getvalue().encode("utf-8")

        report = compare_dxf(make(0), make(1))
        self.assertEqual(report["metrics"]["wrongLines"], 1)
        example = report["examples"]["wrongLines"][0]["expected"]
        self.assertEqual(example["pointCount"], 20)
        self.assertEqual(len(example["points"]), 16)
        self.assertTrue(example["pointsTruncated"])

    def test_exact_and_introduced_errors(self):
        correct = drawing_bytes()
        same = compare_dxf(correct, correct)
        self.assertTrue(same["complete"])
        self.assertEqual(same["metrics"]["exactMatches"], 4)
        self.assertEqual(sum(value for key, value in same["metrics"].items()
                             if key != "exactMatches"), 0)
        result = compare_dxf(drawing_bytes(block=True), drawing_bytes(changed=True, circle=True, block=True))
        self.assertFalse(result["complete"])
        self.assertEqual(result["result"]["unsupported"]["CIRCLE"], 1)
        self.assertEqual(result["reference"]["unsupported"]["BLOCK_CONTENTS_NOT_COMPARED"], 1)
        self.assertEqual(result["metrics"]["wrongBlockNames"], 1)
        self.assertEqual(result["metrics"]["wrongRotations"], 1)
        self.assertEqual(result["metrics"]["wrongLayers"], 1)
        self.assertEqual(result["metrics"]["wrongLabels"], 1)
        self.assertEqual(result["metrics"]["wrongLines"], 1)
        self.assertEqual(result["metrics"]["missing"], 1)
        self.assertEqual(result["metrics"]["extra"], 1)

    def test_invalid_bounds_and_unsupported_bulge(self):
        with self.assertRaises(DxfCompareInvalidError):
            inventory(b"not a DXF")
        with self.assertRaises(DxfCompareLimitError):
            inventory(b"x" * (25 * 1024 * 1024 + 1))
        with patch("autocad_assistance.services.dxf_compare.MAX_ENTITIES", 2):
            with self.assertRaises(DxfCompareLimitError):
                inventory(drawing_bytes())
        drawing = ezdxf.new("R2010")
        drawing.modelspace().add_lwpolyline([(0, 0, 0, 0, 0.5), (1, 0)], format="xyseb")
        output = StringIO()
        drawing.write(output)
        parsed = inventory(output.getvalue().encode("utf-8"))
        self.assertEqual(parsed["unsupported"], {"LWPOLYLINE_BULGE": 1})
        self.assertEqual(parsed["supportedEntities"], 0)


class DxfComparisonApiTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.owner = AuthStore(self.root / "auth").create_owner("owner", PASSWORD).user_id
        self.store = ProjectStore(self.root / "projects")
        upload = store_upload(BytesIO(SOURCE), "field.csv", self.root / "uploads", 10 * 1024 * 1024)
        self.store.register_upload_owner(self.owner, upload)
        self.upload_id = upload.upload_id
        project = self.store.create_owned_project(self.owner, "Synthetic comparison")
        self.project_id = project.project_id
        revision = self.store.add_revision_for(
            self.owner, project.project_id, self.root / "uploads", upload.upload_id,
            context=SurveyContext(scale_factor=Decimal("500")),
            settings={"mapping": MAPPING}, algorithm_version="geoai-dxf-v1",
        )
        self.revision_id = revision.revision_id
        self.reference_raw = drawing_bytes()
        archive = create_reference(self.store, self.owner, self.revision_id,
                                   str(uuid4()), self.reference_raw, META)
        self.entry_id = archive["entryId"]
        job = self.store.register_job_for(self.owner, self.revision_id, str(uuid4()),
                                          request_settings={"fixture": "synthetic"})
        self.store.update_job_status(job.job_id, "succeeded")
        self.store.publish_result(job.job_id, drawing_bytes(changed=True))
        self.job_id = job.job_id
        self.app = create_app(auth_root=self.root / "auth", project_root=self.root / "projects",
                              upload_root=self.root / "uploads", auth_origin=ORIGIN)

    async def login(self, client, username="owner"):
        response = await client.post("/api/v1/auth/login", json={"username": username, "password": PASSWORD},
                                     headers={"Origin": ORIGIN})
        self.assertEqual(response.status_code, 200, response.text)

    async def test_owner_revision_and_verified_inputs(self):
        path = f"/api/v1/reference-archives/{self.entry_id}/comparisons/{self.job_id}"
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url=ORIGIN) as client:
            self.assertEqual((await client.get(path)).status_code, 401)
            await self.login(client)
            response = await client.get(path)
            self.assertEqual(response.status_code, 200, response.text)
            report = response.json()
            self.assertEqual(report["referenceEntryId"], self.entry_id)
            self.assertEqual(report["metrics"]["wrongLines"], 1)
            self.assertEqual(report["metrics"]["wrongLabels"], 1)
            self.assertEqual(response.headers["cache-control"], "no-store")
            another = self.store.add_revision_for(self.owner, self.project_id,
                self.root / "uploads", self.upload_id,
                context=SurveyContext(scale_factor=Decimal("500")),
                settings={"mapping": MAPPING}, algorithm_version="geoai-dxf-v1")
            other_job = self.store.register_job_for(self.owner, another.revision_id,
                str(uuid4()), request_settings={"fixture": "other"})
            self.assertEqual((await client.get(
                f"/api/v1/reference-archives/{self.entry_id}/comparisons/{other_job.job_id}"
            )).status_code, 404)
            result_path = self.root / "projects" / "projects" / self.project_id / "revisions" / self.revision_id / "results" / f"{self.job_id}.dxf"
            result_path.write_bytes(b"tampered")
            self.assertEqual((await client.get(path)).status_code, 422)
        other_auth = self.root / "other-auth"
        AuthStore(other_auth).create_owner("other", PASSWORD)
        foreign_app = create_app(auth_root=other_auth, project_root=self.root / "projects",
                                 upload_root=self.root / "uploads", auth_origin=ORIGIN)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=foreign_app), base_url=ORIGIN) as client:
            await self.login(client, "other")
            self.assertEqual((await client.get(path)).status_code, 404)


if __name__ == "__main__":
    unittest.main()
