"""Disposable staging invariants, using synthetic Git and state only."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest


MODULE = Path(__file__).resolve().parents[1] / "scripts" / "geoai_staging.py"
spec = importlib.util.spec_from_file_location("geoai_staging", MODULE)
stage = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(stage)


class StagingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.source = self.base / "source"
        self.source.mkdir()
        self.lock = self.base / "requirements.lock"
        frozen = subprocess.check_output(
            [sys.executable, "-m", "pip", "freeze"], text=True
        )
        self.lock.write_text(frozen, encoding="utf-8")
        subprocess.run(["git", "init", "-q", str(self.source)], check=True)
        subprocess.run(["git", "-C", str(self.source), "config", "user.name", "Synthetic"], check=True)
        subprocess.run(["git", "-C", str(self.source), "config", "user.email", "test@example.invalid"], check=True)
        (self.source / "sample.txt").write_text("first\n", encoding="utf-8")
        self.commit()
        self.root = self.base / "stage"
        stage.init(str(self.root), str(self.lock), "https://localhost:18765")

    def commit(self):
        subprocess.run(["git", "-C", str(self.source), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(self.source), "commit", "-qm", "synthetic"], check=True)
        return subprocess.check_output(
            ["git", "-C", str(self.source), "rev-parse", "HEAD"], text=True
        ).strip()

    def build(self, ref="HEAD"):
        return stage.build(str(self.root), str(self.source), sys.executable, ref)

    def test_release_is_reproducible_and_tampering_is_rejected(self):
        first = self.build()
        same = self.build()
        self.assertEqual(first["archiveSha256"], same["archiveSha256"])
        stage.activate(str(self.root), first["commit"])
        self.assertEqual(stage.verify(str(self.root))["commit"], first["commit"])
        (self.source / "sample.txt").write_text("dirty\n", encoding="utf-8")
        with self.assertRaises(stage.StageError):
            self.build()
        (self.source / "sample.txt").write_text("first\n", encoding="utf-8")
        release_file = self.root / "releases" / first["commit"] / "sample.txt"
        release_file.write_text("corrupted\n", encoding="utf-8")
        with self.assertRaises(stage.StageError):
            stage.verify(str(self.root))

    def test_offline_backup_restore_and_corruption(self):
        first = self.build()
        stage.activate(str(self.root), first["commit"])
        database = self.root / "state" / "auth" / "auth.sqlite3"
        with sqlite3.connect(database) as connection:
            connection.execute("CREATE TABLE owners (name TEXT PRIMARY KEY)")
            connection.execute("INSERT INTO owners VALUES ('synthetic-owner')")
        result = self.root / "state" / "jobs" / "synthetic-result.dxf"
        result.write_bytes(b"synthetic DXF bytes")
        with stage._lock(self.root):
            with self.assertRaises(stage.StageError):
                stage.backup(str(self.root), str(self.base / "while-active"))
        backup = self.base / "backup"
        stage.backup(str(self.root), str(backup))
        restored = self.base / "restored"
        stage.restore(str(backup), str(restored))
        self.assertEqual(result.read_bytes(), (restored / "state/jobs/synthetic-result.dxf").read_bytes())
        with sqlite3.connect(restored / "state/auth/auth.sqlite3") as connection:
            self.assertEqual(connection.execute("SELECT name FROM owners").fetchone()[0], "synthetic-owner")
        with self.assertRaises(stage.StageError):
            stage.restore(str(backup), str(restored))
        (backup / "state/jobs/synthetic-result.dxf").write_bytes(b"tampered")
        with self.assertRaises(stage.StageError):
            stage.restore(str(backup), str(self.base / "corrupt-restore"))
        self.assertFalse((self.base / "corrupt-restore").exists())

    def test_second_release_activation_and_root_validation(self):
        first = self.build()
        (self.source / "sample.txt").write_text("second\n", encoding="utf-8")
        second_commit = self.commit()
        second = self.build()
        self.assertEqual(second["commit"], second_commit)
        stage.activate(str(self.root), second["commit"])
        stage.activate(str(self.root), first["commit"])
        self.assertEqual(stage.verify(str(self.root))["commit"], first["commit"])
        with self.assertRaises(stage.StageError):
            stage.init(str(self.base / "invalid"), str(self.lock), "http://localhost:18765")
        link = self.base / "symlink-stage"
        link.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(stage.StageError):
            stage.verify(str(link))


if __name__ == "__main__":
    unittest.main()
