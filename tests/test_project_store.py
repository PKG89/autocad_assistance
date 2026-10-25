"""Versioned project persistence and integrity checks."""

from __future__ import annotations

from contextlib import closing
from decimal import Decimal
from io import BytesIO
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch
from uuid import uuid4

from autocad_assistance.services.project_store import (
    ProjectIntegrityError,
    ProjectNotFoundError,
    ProjectStore,
    ProjectStoreError,
)
from autocad_assistance.services.calculation_jobs import CalculationJobManager
from autocad_assistance.services.survey_contract import SurveyContext
from autocad_assistance.services.uploads import store_upload


SOURCE = b"Point,X,Y,Z,Code\nP1,123.456,234.567,11.2,K\n"


class ProjectStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.root = self.home / "project-data"
        self.upload_root = self.home / "uploads"
        self.store = ProjectStore(self.root)
        self.upload = store_upload(BytesIO(SOURCE), "source.csv", self.upload_root, 10 * 1024 * 1024)

    def add_revision(self, project_id: str, *, settings=None, context=None):
        return self.store.add_revision(
            project_id,
            self.upload_root,
            self.upload.upload_id,
            context=context or SurveyContext(scale_factor=Decimal("500")),
            settings=settings or {"codes": ["K"], "refine": False},
            algorithm_version="geoai-dxf-v1",
        )

    def test_project_revisions_preserve_source_context_and_parent_after_restart(self):
        project = self.store.create_project("Участок 1")
        first = self.add_revision(project.project_id)
        second = self.add_revision(
            project.project_id,
            settings={"codes": ["K"], "refine": True},
            context=SurveyContext(
                coordinate_system="local survey grid",
                horizontal_unit="m",
                vertical_unit=None,
                scale_factor=Decimal("1000"),
            ),
        )
        self.assertEqual((first.sequence, second.sequence), (1, 2))
        self.assertEqual(second.parent_revision_id, first.revision_id)
        self.assertNotEqual(first.settings_sha256, second.settings_sha256)
        self.assertEqual(first.source_sha256, second.source_sha256)
        self.assertIn('"coordinateSystem":null', first.settings_json)
        self.assertIn('"coordinateSystem":"local survey grid"', second.settings_json)
        reopened = ProjectStore(self.root)
        self.assertEqual(reopened.get_project(project.project_id).name, "Участок 1")
        self.assertEqual(reopened.list_projects(), (project,))
        self.assertEqual(reopened.list_revisions(project.project_id), (first, second))
        self.assertEqual(reopened.read_source(first.revision_id), SOURCE)
        self.assertEqual(reopened.read_source(second.revision_id), SOURCE)
        self.assertFalse((self.home / "telegram.sqlite3").exists())

    def test_job_result_has_source_request_and_algorithm_provenance(self):
        project = self.store.create_project("One")
        revision = self.add_revision(project.project_id)
        job_id = str(uuid4())
        job = self.store.register_job(
            revision.revision_id,
            job_id,
            request_settings={"mapping": {"X": 1, "Y": 2, "Z": 3}, "scale": 500},
        )
        self.assertEqual(job.revision_id, revision.revision_id)
        self.assertEqual(job.algorithm_version, revision.algorithm_version)
        self.assertIn('"scale":500', job.request_json)
        with self.assertRaises(ProjectStoreError):
            self.store.publish_result(job_id, b"DXF result")
        self.store.update_job_status(job_id, "succeeded")
        accepted = self.store.publish_result(job_id, b"DXF result")
        self.assertEqual(accepted.result_size, 10)
        self.assertEqual(len(accepted.result_sha256), 64)
        with self.assertRaises(ProjectStoreError):
            self.store.publish_result(job_id, b"different")
        reopened = ProjectStore(self.root)
        self.assertEqual(reopened.get_job(job_id), accepted)
        self.assertEqual(reopened.read_result(job_id), b"DXF result")
        self.assertEqual(reopened.get_revision(accepted.revision_id).source_sha256, revision.source_sha256)

    def test_unknown_ids_invalid_metadata_and_symlink_are_rejected(self):
        project = self.store.create_project("One")
        revision = self.add_revision(project.project_id)
        with self.assertRaises(ProjectNotFoundError):
            self.store.get_project(str(uuid4()))
        with self.assertRaises(ProjectNotFoundError):
            self.store.get_revision("../other")
        source_path = self.root / "projects" / project.project_id / "revisions" / revision.revision_id / "source.csv"
        outside = self.home / "private.txt"
        outside.write_bytes(b"private data")
        source_path.unlink()
        source_path.symlink_to(outside)
        with self.assertRaises(ProjectIntegrityError):
            self.store.read_source(revision.revision_id)
        source_path.unlink()
        source_path.write_bytes(SOURCE + b"modified")
        with self.assertRaises(ProjectIntegrityError):
            self.store.read_source(revision.revision_id)
        with closing(sqlite3.connect(self.store.db_path)) as db:
            with db:
                db.execute("UPDATE revisions SET settings_json = 'changed' WHERE revision_id = ?", (revision.revision_id,))
        with self.assertRaises(ProjectIntegrityError):
            self.store.get_revision(revision.revision_id)

    def test_tampered_job_request_and_source_format_are_rejected(self):
        project = self.store.create_project("One")
        revision = self.add_revision(project.project_id)
        job_id = str(uuid4())
        self.store.register_job(revision.revision_id, job_id, request_settings={"scale": 1})
        with closing(sqlite3.connect(self.store.db_path)) as db:
            with db:
                db.execute("UPDATE jobs SET request_json = '{}' WHERE job_id = ?", (job_id,))
        with self.assertRaises(ProjectIntegrityError):
            self.store.get_job(job_id)
        with closing(sqlite3.connect(self.store.db_path)) as db:
            with db:
                db.execute("UPDATE revisions SET source_format = '../private' WHERE revision_id = ?", (revision.revision_id,))
        with self.assertRaises(ProjectIntegrityError):
            self.store.read_source(revision.revision_id)

    def test_real_job_result_is_snapshotted_to_its_source_revision(self):
        project = self.store.create_project("One")
        revision = self.add_revision(project.project_id)
        manager = CalculationJobManager(self.home / "jobs")
        self.addCleanup(manager.close)
        job = manager.submit(
            [{"Point": "P1", "X": "123.456", "Y": "234.567", "Z": "11.2", "Code": "K"}],
            scale_factor=500,
        )
        self.store.register_job(
            revision.revision_id, job.job_id, request_settings={"scaleFactor": 500, "mapping": [0, 1, 2, 3, 4]}
        )
        deadline = time.monotonic() + 20
        while manager.get(job.job_id).status not in {"succeeded", "failed"} and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertEqual(manager.get(job.job_id).status, "succeeded")
        self.store.update_job_status(job.job_id, "succeeded")
        accepted = self.store.publish_result(job.job_id, manager.read_result(job.job_id))
        self.assertEqual(accepted.revision_id, revision.revision_id)
        self.assertEqual(self.store.read_result(job.job_id), manager.read_result(job.job_id))

    def test_settings_limit_and_kml_source_snapshot(self):
        project = self.store.create_project("One")
        with self.assertRaises(ProjectStoreError):
            self.add_revision(project.project_id, settings={"note": "x" * 65_536})
        self.assertEqual(self.store.list_revisions(project.project_id), ())
        kml = b"<kml><Placemark><Point><coordinates>1,2</coordinates></Point></Placemark></kml>"
        accepted_kml = store_upload(BytesIO(kml), "survey.kml", self.upload_root, 10 * 1024 * 1024)
        revision = self.store.add_revision(
            project.project_id,
            self.upload_root,
            accepted_kml.upload_id,
            context=SurveyContext(),
            settings={},
            algorithm_version="geoai-dxf-v1",
        )
        self.assertEqual(revision.source_format, "kml")
        self.assertEqual(self.store.read_source(revision.revision_id), kml)

    def test_failed_file_write_leaves_no_accepted_revision_or_result(self):
        project = self.store.create_project("One")
        original_write = ProjectStore._write_file

        def write_then_fail(descriptor, filename, raw):
            original_write(descriptor, filename, raw)
            raise OSError("synthetic failure after fsync")

        with patch.object(ProjectStore, "_write_file", side_effect=write_then_fail):
            with self.assertRaises(OSError):
                self.add_revision(project.project_id)
        self.assertEqual(self.store.list_revisions(project.project_id), ())
        self.assertEqual(list((self.root / "projects" / project.project_id / "revisions").iterdir()), [])
        revision = self.add_revision(project.project_id)
        job_id = str(uuid4())
        self.store.register_job(revision.revision_id, job_id, request_settings={})
        self.store.update_job_status(job_id, "succeeded")
        with patch.object(ProjectStore, "_write_file", side_effect=write_then_fail):
            with self.assertRaises(OSError):
                self.store.publish_result(job_id, b"DXF result")
        self.assertIsNone(self.store.get_job(job_id).result_sha256)
        self.assertFalse((self.root / "projects" / project.project_id / "revisions" / revision.revision_id / "results" / f"{job_id}.dxf").exists())

    def test_symlinked_project_directory_blocks_write_outside_root(self):
        project = self.store.create_project("One")
        project_dir = self.root / "projects" / project.project_id
        project_dir.rmdir()
        outside = self.home / "outside"
        outside.mkdir()
        project_dir.symlink_to(outside, target_is_directory=True)
        with self.assertRaises(OSError):
            self.add_revision(project.project_id)
        self.assertEqual(list(outside.iterdir()), [])
        self.assertEqual(self.store.list_revisions(project.project_id), ())

    def test_failed_write_cleanup_does_not_follow_a_swapped_parent(self):
        project = self.store.create_project("One")
        project_dir = self.root / "projects" / project.project_id
        outside = self.home / "outside"
        outside.mkdir()
        original_write = ProjectStore._write_file

        def write_then_swap(descriptor, filename, raw):
            original_write(descriptor, filename, raw)
            project_dir.rename(project_dir.with_name(project.project_id + ".old"))
            project_dir.symlink_to(outside, target_is_directory=True)
            raise OSError("synthetic parent swap")

        with patch.object(ProjectStore, "_write_file", side_effect=write_then_swap):
            with self.assertRaises(OSError):
                self.add_revision(project.project_id)
        self.assertEqual(list(outside.iterdir()), [])
        self.assertEqual(self.store.list_revisions(project.project_id), ())


if __name__ == "__main__":
    unittest.main()
