"""The isolated runners reject report paths inside the repository."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class BootstrapRootTests(unittest.TestCase):
    def test_report_root_cannot_target_repository(self):
        repo = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as external_root:
            for script in ("geoai_bootstrap.py", "geoai_api_bootstrap.py"):
                with self.subTest(script=script):
                    env = os.environ.copy()
                    env["GEOAI_TEST_REPORT_ROOT"] = external_root
                    result = subprocess.run(
                        [
                            sys.executable,
                            "-I",
                            "-B",
                            str(repo / "tests" / script),
                            "--output-dir",
                            str(repo / "tests" / "forbidden-report"),
                        ],
                        cwd=repo,
                        env=env,
                        capture_output=True,
                        text=True,
                        timeout=15,
                        check=False,
                    )
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("external GEOAI report root", result.stderr)
                    self.assertFalse((repo / "tests" / "forbidden-report").exists())
