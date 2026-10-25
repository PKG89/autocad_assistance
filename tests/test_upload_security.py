"""Bounded-upload and no-follow file-access checks."""

from __future__ import annotations

from io import BytesIO
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import httpx

from autocad_assistance.api import create_app
from autocad_assistance.services.uploads import (
    InvalidUploadContentError,
    InvalidUploadNameError,
    UploadLimitError,
    read_stored_upload,
    store_upload,
)


class StoredUploadSecurityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "uploads"

    def store(self, data: bytes, name: str = "survey.csv"):
        return store_upload(BytesIO(data), name, self.root, 10 * 1024 * 1024)

    def assert_no_partial_upload(self):
        self.assertEqual(list(self.root.rglob("*")), [])

    def test_rejects_binary_spoof_and_malformed_kml_without_partial_data(self):
        cases = (
            ("survey.csv", b"PK\x03\x04fake archive"),
            ("survey.csv", b"A,1,2,3\x1b\n"),
            ("survey.csv", b"<?xml version='1.0'?><kml/>"),
            ("survey.kml", b"A,1,2,3\n"),
            ("survey.kml", b"<!DOCTYPE kml><kml/>"),
            ("survey.kml", "<!DOCTYPE kml><kml/>".encode("utf-16")),
        )
        for name, raw in cases:
            with self.subTest(name=name, raw=raw), self.assertRaises(InvalidUploadContentError):
                self.store(raw, name)
            self.assert_no_partial_upload()

    def test_point_row_column_and_field_limits_clean_up(self):
        cases = (
            b"A,1,2,3\n" * 100_001,
            b"\n" * 150_001,
            b"\r" * 150_001,
            b",".join([b"x"] * 65) + b"\n",
            b",".join([b"Point", b"X", b"Y", b"Z"] + [b"x"] * 61) + b"\nA,1,2,3\n",
            b"A,1,2,3," + b"x" * 4097 + b"\n",
        )
        for raw in cases:
            with self.subTest(size=len(raw)), self.assertRaises(UploadLimitError):
                self.store(raw)
            self.assert_no_partial_upload()

    def test_kml_coordinate_limit_and_normal_kml(self):
        normal = self.store(b"<kml><Placemark><Point><coordinates>1,2</coordinates></Point></Placemark></kml>", "x.kml")
        self.assertEqual(read_stored_upload(self.root, normal.upload_id, 10 * 1024 * 1024)[1], "kml")
        (self.root / normal.upload_id / f"{normal.upload_id}.kml").unlink()
        (self.root / normal.upload_id).rmdir()
        oversized = b"<kml><coordinates>" + b"1,2 " * 100_001 + b"</coordinates></kml>"
        with self.assertRaises(UploadLimitError):
            self.store(oversized, "x.kml")
        self.assert_no_partial_upload()

    def test_original_name_is_metadata_and_ids_do_not_repeat(self):
        first = self.store(b"A,1,2,3\n", "съёмка.csv")
        second = self.store(b"A,1,2,3\n", r"..\..\survey.csv")
        self.assertEqual(first.original_filename, "съёмка.csv")
        self.assertEqual(second.original_filename, "survey.csv")
        self.assertNotEqual(first.upload_id, second.upload_id)
        self.assertEqual(first.path.name, f"{first.upload_id}.csv")
        with self.assertRaises(InvalidUploadNameError):
            self.store(b"A,1,2,3\n", "bad\u202e.csv")

    def test_symlinked_directory_or_file_cannot_be_read(self):
        stored = self.store(b"A,1,2,3\n")
        outside = Path(self.temp.name) / "outside.csv"
        outside.write_bytes(b"synthetic outside data")
        self.assertEqual(read_stored_upload(self.root, stored.upload_id, 1024)[0], b"A,1,2,3\n")
        stored.path.unlink()
        stored.path.symlink_to(outside)
        with self.assertRaises(FileNotFoundError):
            read_stored_upload(self.root, stored.upload_id, 1024)
        stored.path.unlink()
        (self.root / stored.upload_id).rmdir()
        (self.root / stored.upload_id).symlink_to(outside.parent, target_is_directory=True)
        with self.assertRaises(FileNotFoundError):
            read_stored_upload(self.root, stored.upload_id, 1024)

    def test_path_swap_after_open_reads_original_descriptor(self):
        stored = self.store(b"A,1,2,3\n")
        outside = Path(self.temp.name) / "outside.csv"
        outside.write_bytes(b"synthetic outside data")
        original_open = os.open
        swapped = False

        def open_then_swap(path, flags, *args, **kwargs):
            nonlocal swapped
            descriptor = original_open(path, flags, *args, **kwargs)
            if path == stored.path.name and not swapped:
                swapped = True
                stored.path.rename(stored.path.with_suffix(".old"))
                stored.path.symlink_to(outside)
            return descriptor

        with patch("autocad_assistance.services.uploads.os.open", side_effect=open_then_swap):
            raw, stored_format = read_stored_upload(self.root, stored.upload_id, 1024)
        self.assertTrue(swapped)
        self.assertEqual((raw, stored_format), (b"A,1,2,3\n", "csv"))


class UploadBoundaryApiTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "uploads"

    async def upload(self, name: str, raw: bytes):
        app = create_app(upload_root=self.root)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.post(
                "/api/v1/uploads",
                files={"file": (name, raw, "application/octet-stream")},
            )

    async def test_invalid_content_and_point_limit_have_stable_errors(self):
        for name, raw, status, code in (
            ("survey.csv", b"PK\x03\x04fake archive", 422, "INVALID_UPLOAD_CONTENT"),
            ("survey.csv", b"Point,X,Y,Z\n", 422, "INVALID_UPLOAD_CONTENT"),
            ("survey.csv", b"A,1,2,3\n" * 100_001, 413, "UPLOAD_LIMIT_EXCEEDED"),
        ):
            with self.subTest(name=name, status=status, size=len(raw)):
                response = await self.upload(name, raw)
                self.assertEqual(response.status_code, status)
                self.assertEqual(response.json()["error"]["code"], code)
                self.assertEqual(list(self.root.rglob("*")), [])
