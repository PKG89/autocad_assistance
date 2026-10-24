"""Focused contract tests for DXF generation API."""

from __future__ import annotations

import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

import httpx

from autocad_assistance.api import create_app


class DxfEndpointTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def _app(self):
        return create_app(
            upload_root=self._tmp.name,
            max_upload_bytes=1024 * 1024,
            max_preview_rows=10,
        )

    async def upload(self, *, filename: str, content: bytes) -> str:
        transport = httpx.ASGITransport(app=self._app())
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.post(
                "/api/v1/uploads",
                files={"file": (filename, content, "application/octet-stream")},
            )
        self.assertEqual(response.status_code, 201)
        return response.json()["uploadId"]

    async def generate_dxf(self, upload_id: str, payload: dict):
        transport = httpx.ASGITransport(app=self._app())
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.post(f"/api/v1/uploads/{upload_id}/dxf", json=payload)

    def default_payload(self) -> dict:
        return {
            "mapping": {"Point": 0, "X": 1, "Y": 2, "Z": 3, "Code": 4},
            "scaleFactor": 1.0,
            "tinSettings": {"codes": [], "refine": False, "scale_value": None},
        }

    async def test_dxf_success_returns_attachment_bytes(self):
        upload_id = await self.upload(
            filename="survey.csv",
            content=b"A,1,2,3,C1\n",
        )
        with patch(
            "autocad_assistance.api.uploads.render_dxf_bytes",
            return_value=b"DXF-DATA",
        ) as render:
            response = await self.generate_dxf(upload_id, self.default_payload())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "application/dxf")
        self.assertIn('attachment; filename="drawing.dxf"', response.headers["content-disposition"])
        self.assertEqual(response.content, b"DXF-DATA")
        render.assert_called_once()

    async def test_dxf_unknown_upload_returns_not_found(self):
        response = await self.generate_dxf(str(uuid4()), self.default_payload())
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "UPLOAD_NOT_FOUND")

    async def test_dxf_rejects_kml_upload(self):
        upload_id = await self.upload(filename="survey.kml", content=b"<kml></kml>")
        response = await self.generate_dxf(upload_id, self.default_payload())
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "UNSUPPORTED_DXF_FORMAT")

    async def test_dxf_preserves_mapping_coordinate_errors(self):
        upload_id = await self.upload(
            filename="survey.csv",
            content=b"A,1,2,3,C1\nB,nan,5,6,C2\n",
        )
        response = await self.generate_dxf(upload_id, self.default_payload())
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "INVALID_COORDINATE")

    async def test_dxf_wraps_generation_failure(self):
        upload_id = await self.upload(
            filename="survey.csv",
            content=b"A,1,2,3,C1\n",
        )
        with patch(
            "autocad_assistance.api.uploads.render_dxf_bytes",
            side_effect=RuntimeError("failed"),
        ):
            response = await self.generate_dxf(upload_id, self.default_payload())

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["error"]["code"], "DXF_GENERATION_FAILED")
        self.assertNotIn("path", response.text)

    async def test_dxf_passes_tin_scale_value_option(self):
        upload_id = await self.upload(
            filename="survey.csv",
            content=b"A,1,2,3,C1\n",
        )
        payload = self.default_payload()
        payload["tinSettings"]["scale_value"] = 2.5
        with patch(
            "autocad_assistance.api.uploads.render_dxf_bytes",
            return_value=b"DXF-DATA",
        ) as render:
            response = await self.generate_dxf(upload_id, payload)

        self.assertEqual(response.status_code, 200)
        _, kwargs = render.call_args
        self.assertEqual(
            kwargs["tin_settings"],
            {"codes": [], "refine": False, "scale_value": 2.5},
        )

    async def test_dxf_valueerror_from_generator_returns_generic_500(self):
        upload_id = await self.upload(
            filename="survey.csv",
            content=b"A,1,2,3,C1\n",
        )
        with patch(
            "autocad_assistance.api.uploads.render_dxf_bytes",
            side_effect=ValueError("internal /tmp/secret/path leak"),
        ):
            response = await self.generate_dxf(upload_id, self.default_payload())

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["error"]["code"], "DXF_GENERATION_FAILED")
        self.assertNotIn("/tmp/secret/path", response.text)


if __name__ == "__main__":
    unittest.main()
