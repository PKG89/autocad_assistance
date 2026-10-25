"""Focused tests for operational configuration; no product state or network."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pilot_ops"))
from geoai_pilot_ops.runtime import Config, PilotError, RELEASES, init_state


class PilotConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "install"
        self.root.mkdir(mode=0o700)
        (self.root / "states").mkdir(mode=0o700)
        self.config_path = Path(self.temp.name) / "config.json"
        sha = next(iter(RELEASES))
        state = self.root / "states" / "primary"
        self.raw = {
            "mode": "synthetic", "installation_root": str(self.root),
            "release_commit": sha,
            "archive_path": str(self.root / "archives" / f"{sha}.tar"),
            "release_root": str(self.root / "releases" / sha),
            "state_root": str(state),
            "auth_root": str(state / "auth"),
            "project_root": str(state / "projects"),
            "upload_root": str(state / "uploads"),
            "jobs_root": str(state / "jobs"),
            "backup_root": str(self.root / "backups"),
            "log_root": str(self.root / "logs"),
            "auth_origin": "https://127.0.0.1:18591",
            "bind_host": "127.0.0.1", "bind_port": 18591,
        }

    def load(self):
        self.config_path.write_text(json.dumps(self.raw), encoding="utf-8")
        self.config_path.chmod(0o600)
        return Config.load(self.config_path)

    def test_fresh_private_state_is_explicit(self):
        config = self.load()
        with self.assertRaises(PilotError):
            config.check_state()
        init_state(config)
        config.check_state()
        with self.assertRaises(PilotError):
            init_state(config)

    def test_rejects_unsafe_or_conflicting_settings(self):
        cases = (
            ("bind_host", "0.0.0.0"),
            ("auth_origin", "http://127.0.0.1:18591"),
            ("auth_origin", "https://127.0.0.1:18592"),
            ("auth_root", str(self.root / "other-auth")),
            ("release_commit", "a" * 40),
            ("state_root", str(self.root / "states" / "../bot")),
            ("state_root", str(self.root / "states" / "primary" / "nested")),
            ("bind_port", 80),
        )
        for name, value in cases:
            with self.subTest(name=name, value=value):
                original = self.raw[name]
                self.raw[name] = value
                with self.assertRaises(PilotError):
                    self.load()
                self.raw[name] = original

    def test_rejects_unknown_keys_and_linked_paths(self):
        self.raw["unexpected"] = "ignored?"
        with self.assertRaises(PilotError):
            self.load()
        del self.raw["unexpected"]
        link = Path(self.temp.name) / "linked"
        link.symlink_to(self.root, target_is_directory=True)
        self.raw["installation_root"] = str(link)
        with self.assertRaises(PilotError):
            self.load()

    def test_pilot_origin_and_root_are_fixed(self):
        self.raw["mode"] = "pilot"
        with self.assertRaises(PilotError):
            self.load()
        self.raw["installation_root"] = "/srv/geoai-pilot"
        with self.assertRaises(PilotError):
            self.load()  # the real installation root is not created by config parsing

    def test_rejects_writable_config(self):
        self.load()
        self.config_path.chmod(0o666)
        with self.assertRaises(PilotError):
            Config.load(self.config_path)


if __name__ == "__main__":
    unittest.main()
