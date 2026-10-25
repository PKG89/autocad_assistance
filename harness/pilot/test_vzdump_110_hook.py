#!/usr/bin/env python3
"""Synthetic pairing tests; no VM or Proxmox configuration is touched."""

import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location(
    "geoai_vzdump_hook", Path(__file__).with_name("geoai-vzdump-110-hook.py"))
HOOK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HOOK)


class VzdumpPairTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name) / "dump"
        self.directory.mkdir()
        self.archive = self.directory / "vzdump-qemu-110-2026_10_25-02_30_00.vma.zst"
        source = Path(self.temp.name) / "source"
        source.write_bytes(b"synthetic VMA payload\n")
        subprocess.run(["zstd", "-q", "-o", str(self.archive), str(source)], check=True)
        self.good = {"ok": True, "attemptId": "dump-1", "backupName": "synthetic-1",
                     "manifestSha256": "a" * 64,
                     "completedAt": "2026-10-25T02:00:00+00:00", "ageSeconds": 1800}

    def pair(self, started, checked):
        return HOOK.pair_record("backup-fast-nfs", self.archive, started, checked,
                                self.directory)

    def test_successful_pair_has_archive_and_dump_identity(self):
        record = self.pair(HOOK.start_record("backup-fast-nfs", self.good), self.good)
        self.assertEqual(record["appDumpStatus"], "paired")
        self.assertEqual(record["appDump"]["backupName"], "synthetic-1")
        self.assertEqual(record["vmBackupIntegrity"], "zstd-ok")
        self.assertEqual(len(record["vmBackupSha256"]), 64)

    def test_missing_and_failed_dump_are_vm_only(self):
        for reason in ("dump status missing", "latest dump attempt not successful"):
            with self.subTest(reason=reason):
                failed = {"ok": False, "error": reason}
                record = self.pair(HOOK.start_record("backup-fast-nfs", failed), failed)
                self.assertEqual(record["appDumpStatus"], "vm-only")
                self.assertEqual(record["appDumpReason"], reason)
                self.assertNotIn("appDump", record)

    def test_dump_change_and_missing_start_are_vm_only(self):
        changed = self.good | {"attemptId": "dump-2"}
        self.assertEqual(self.pair(HOOK.start_record("backup-fast-nfs", self.good), changed)
                         ["appDumpStatus"], "vm-only")
        self.assertEqual(self.pair(None, self.good)["appDumpReason"],
                         "backup-start status missing")

    def test_corrupt_archive_cannot_be_paired(self):
        self.archive.write_bytes(b"not zstd")
        with self.assertRaisesRegex(ValueError, "zstd integrity"):
            self.pair(HOOK.start_record("backup-fast-nfs", self.good), self.good)

    def test_guest_checker_failure_is_explicit(self):
        wrapped = '{"exited":1,"exitcode":2,"out-data":"{\\"ok\\":false}"}'
        with patch.object(HOOK.subprocess, "run") as run:
            run.return_value.returncode = 0
            run.return_value.stdout = wrapped
            run.return_value.stderr = ""
            result = HOOK.guest_check()
        self.assertFalse(result["ok"])
        self.assertIn("failed", result["error"])


if __name__ == "__main__":
    unittest.main()
