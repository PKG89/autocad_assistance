"""Owner credentials, revocable sessions and link confirmation."""

from __future__ import annotations

from contextlib import closing
import stat
import sqlite3
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from autocad_assistance.services.auth_store import (
    ABSOLUTE_SECONDS,
    ATTEMPT_WINDOW_SECONDS,
    AuthBusyError,
    AuthError,
    AuthSetupError,
    AuthStore,
    IDLE_SECONDS,
    LINK_SECONDS,
)


PASSWORD = "Synthetic-only-owner-passphrase-123"


class AuthStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "identity"
        self.now = 1_800_000_000
        self.store = AuthStore(self.root, clock=lambda: self.now)
        self.owner = self.store.create_owner("Owner", PASSWORD)

    def test_one_time_owner_hashes_and_session_verifier_survive_restart(self):
        with self.assertRaises(AuthSetupError):
            self.store.create_owner("other", PASSWORD)
        grant = self.store.login("OWNER", PASSWORD)
        self.assertNotEqual(grant.token, grant.csrf_token)
        with closing(sqlite3.connect(self.store.db_path)) as db:
            user = db.execute("SELECT password_salt, password_digest FROM users").fetchone()
            stored_session = db.execute("SELECT token_hash FROM sessions").fetchone()[0]
        self.assertEqual(len(user[0]), 32)
        self.assertEqual(len(user[1]), 32)
        self.assertNotIn(PASSWORD.encode(), self.store.db_path.read_bytes())
        self.assertNotIn(grant.token.encode(), self.store.db_path.read_bytes())
        self.assertNotEqual(stored_session, grant.token)
        self.assertEqual(stat.S_IMODE(self.root.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(self.store.db_path.stat().st_mode), 0o600)
        reopened = AuthStore(self.root, clock=lambda: self.now)
        self.assertEqual(reopened.authenticate(grant.token).user, self.owner)

    def test_login_rotates_prior_cookie_and_logout_revokes_server_side(self):
        old = self.store.login("owner", PASSWORD)
        new = self.store.login("owner", PASSWORD, previous_token=old.token)
        self.assertNotEqual(old.token, new.token)
        with self.assertRaises(AuthError):
            self.store.authenticate(old.token)
        self.store.check_csrf(new, new.csrf_token)
        with self.assertRaises(AuthError):
            self.store.check_csrf(new, "wrong")
        self.store.logout(new.token)
        with self.assertRaises(AuthError):
            self.store.authenticate(new.token)

    def test_idle_absolute_and_revoke_all(self):
        idle = self.store.login("owner", PASSWORD)
        self.now += IDLE_SECONDS
        with self.assertRaises(AuthError):
            self.store.authenticate(idle.token)
        first = self.store.login("owner", PASSWORD)
        for _ in range(16):
            self.now += IDLE_SECONDS - 1
            self.store.authenticate(first.token)
        self.now = first.absolute_expires_at
        with self.assertRaises(AuthError):
            self.store.authenticate(first.token)
        another = self.store.login("owner", PASSWORD)
        second = self.store.login("owner", PASSWORD)
        self.assertEqual(self.store.revoke_all(self.owner.user_id), 2)
        for token in (another.token, second.token):
            with self.assertRaises(AuthError):
                self.store.authenticate(token)

    def test_failed_login_is_generic_and_rate_limited(self):
        for _ in range(5):
            with self.assertRaisesRegex(AuthError, "Invalid credentials"):
                self.store.login("owner", "wrong")
        with self.assertRaisesRegex(AuthError, "Invalid credentials"):
            self.store.login("owner", PASSWORD)
        self.now += ATTEMPT_WINDOW_SECONDS
        grant = self.store.login("owner", PASSWORD)
        self.assertEqual(grant.user.user_id, self.owner.user_id)

    def test_random_username_spray_hits_global_limit(self):
        with patch("autocad_assistance.services.auth_store._password_hash", return_value=b"x" * 32):
            for index in range(20):
                with self.assertRaises(AuthError):
                    self.store.login(f"unknown{index}", "wrong")
        with self.assertRaises(AuthError):
            self.store.login("owner", PASSWORD)
        self.now += ATTEMPT_WINDOW_SECONDS
        self.assertEqual(self.store.login("owner", PASSWORD).user.user_id, self.owner.user_id)

    def test_password_checks_are_serialized_across_store_instances(self):
        second = AuthStore(self.root, clock=lambda: self.now)
        with self.store._kdf_slot():
            with self.assertRaises(AuthBusyError):
                second.login("owner", PASSWORD)

    def test_link_needs_admin_actor_is_one_time_and_expires(self):
        active = self.store.login("owner", PASSWORD)
        code = self.store.create_link_challenge(self.owner.user_id)
        with self.assertRaises(AuthError):
            self.store.confirm_link(code, 42, frozenset({99}))
        self.assertIsNone(self.store.get_user(self.owner.user_id).telegram_user_id)
        linked = self.store.confirm_link(code, 42, frozenset({42}))
        self.assertEqual(linked.telegram_user_id, 42)
        with self.assertRaises(AuthError):
            self.store.confirm_link(code, 42, frozenset({42}))
        with self.assertRaises(AuthError):
            self.store.authenticate(active.token)
        expired = self.store.create_link_challenge(self.owner.user_id)
        self.now += LINK_SECONDS
        with self.assertRaises(AuthError):
            self.store.confirm_link(expired, 42, frozenset({42}))


if __name__ == "__main__":
    unittest.main()
