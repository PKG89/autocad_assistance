#!/usr/bin/env python3
"""Synthetic checks for the VM110 dump freshness and integrity gate."""

import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).with_name("geoai-pilot-backup-check.py")
T0 = "2026-10-25T02:00:00+00:00"


class BackupCheckTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "backups"
        self.state = self.root / "synthetic-1" / "state"
        self.state.mkdir(parents=True)
        for relative, version in (("auth/auth.sqlite3", 1),
                                  ("projects/projects.sqlite3", 8)):
            path = self.state / relative
            path.parent.mkdir()
            with sqlite3.connect(path) as db:
                db.execute(f"PRAGMA user_version={version}")
                db.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY)")
                db.execute("INSERT INTO sample VALUES (1)")
        sample = self.state / "jobs" / "result.dxf"
        sample.parent.mkdir()
        sample.write_text("synthetic DXF", encoding="utf-8")
        files = {p.relative_to(self.state).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in self.state.rglob("*") if p.is_file()}
        manifest = {"format": 1, "stateName": "synthetic", "files": files,
                    "sqlite": {"auth/auth.sqlite3": 1,
                               "projects/projects.sqlite3": 8}}
        (self.state.parent / "manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8")
        self.status = Path(self.temp.name) / "status" / "latest.json"

    def run_check(self, action, *arguments):
        run = subprocess.run([sys.executable, str(SCRIPT), action,
                              "--root", str(self.root), "--status", str(self.status),
                              *arguments], capture_output=True, text=True)
        return run.returncode, json.loads(run.stdout)

    def mark(self, result):
        extras = ["--attempt", "synthetic-attempt", "--result", result, "--at", T0]
        if result == "success":
            extras += ["--backup", "synthetic-1"]
        return self.run_check("mark", *extras)

    def test_success_and_boundary(self):
        self.assertEqual(self.mark("running")[0], 0)
        self.assertEqual(self.run_check("check", "--at", T0)[0], 2)
        self.assertEqual(self.mark("success")[0], 0)
        code, result = self.run_check("check", "--at", "2026-10-25T02:45:00+00:00")
        self.assertEqual(code, 0)
        self.assertEqual(result["ageSeconds"], 2700)
        self.assertEqual(result["backupName"], "synthetic-1")

    def test_missed_and_failed_dump(self):
        self.assertEqual(self.run_check("check", "--at", T0)[0], 2)
        self.assertEqual(self.mark("failed")[0], 0)
        code, result = self.run_check("check", "--at", T0)
        self.assertEqual(code, 2)
        self.assertIn("not successful", result["error"])

    def test_stale_and_changed_dump(self):
        self.assertEqual(self.mark("success")[0], 0)
        self.assertEqual(self.run_check("check", "--at", "2026-10-25T02:45:01+00:00")[0], 2)
        (self.state / "jobs" / "result.dxf").write_text("changed", encoding="utf-8")
        code, result = self.run_check("check", "--at", T0)
        self.assertEqual(code, 2)
        self.assertIn("checksum", result["error"])


if __name__ == "__main__":
    unittest.main()
