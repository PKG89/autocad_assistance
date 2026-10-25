"""Single-owner credentials, revocable sessions and Telegram link proofs."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
import getpass
import hashlib
import hmac
import os
from pathlib import Path
import secrets
import sqlite3
import sys
import time
from typing import Callable, Iterator
from uuid import uuid4


SCRYPT_N = 1 << 17
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_MAXMEM = 256 * 1024 * 1024
IDLE_SECONDS = 30 * 60
ABSOLUTE_SECONDS = 8 * 60 * 60
LINK_SECONDS = 10 * 60
ATTEMPT_WINDOW_SECONDS = 15 * 60
MAX_LOGIN_FAILURES = 5
MAX_GLOBAL_FAILURES = 20
GLOBAL_ATTEMPT_KEY = "global"


class AuthError(ValueError):
    """Credentials or session are invalid; message is safe for a client."""


class AuthBusyError(AuthError):
    """The single bounded password verifier is busy."""


class AuthSetupError(AuthError):
    """The owner cannot be provisioned with these local inputs."""


@dataclass(frozen=True)
class UserRecord:
    user_id: str
    username: str
    telegram_user_id: int | None


@dataclass(frozen=True)
class SessionGrant:
    user: UserRecord
    token: str
    csrf_token: str
    absolute_expires_at: int


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _password_hash(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=SCRYPT_N, r=SCRYPT_R,
        p=SCRYPT_P, maxmem=SCRYPT_MAXMEM, dklen=32,
    )


class AuthStore:
    """Durable identity store independent of project and Telegram DBs."""

    def __init__(self, root: str | Path, *, clock: Callable[[], float] = time.time) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.root, 0o700)
        self.db_path = self.root / "auth.sqlite3"
        self._clock = clock
        self._dummy_salt = secrets.token_bytes(16)
        self._dummy_digest = secrets.token_bytes(32)
        with self._db() as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1):
                raise AuthSetupError("Unsupported identity schema version")
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    username TEXT NOT NULL UNIQUE,
                    password_salt BLOB NOT NULL,
                    password_digest BLOB NOT NULL,
                    telegram_user_id INTEGER UNIQUE,
                    created_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(user_id),
                    csrf_token TEXT NOT NULL,
                    issued_at INTEGER NOT NULL,
                    last_seen_at INTEGER NOT NULL,
                    absolute_expires_at INTEGER NOT NULL,
                    revoked_at INTEGER
                );
                CREATE TABLE IF NOT EXISTS login_attempts (
                    username_hash TEXT PRIMARY KEY,
                    failures INTEGER NOT NULL,
                    window_started_at INTEGER NOT NULL,
                    blocked_until INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS link_challenges (
                    code_hash TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(user_id),
                    expires_at INTEGER NOT NULL,
                    used_at INTEGER
                );
                PRAGMA user_version = 1;
                """
            )
        os.chmod(self.db_path, 0o600)

    def _now(self) -> int:
        return int(self._clock())

    @contextmanager
    def _db(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.db_path, timeout=15, isolation_level=None)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA foreign_keys = ON")
            db.execute("PRAGMA journal_mode = WAL")
            db.execute("PRAGMA synchronous = FULL")
            yield db
        finally:
            db.close()

    @contextmanager
    def _kdf_slot(self) -> Iterator[None]:
        try:
            import fcntl
        except ImportError as exc:
            raise AuthSetupError("Password verification requires a POSIX lock") from exc
        descriptor = os.open(self.root / ".kdf.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        try:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise AuthBusyError("Authentication is busy; retry shortly") from exc
            yield
        finally:
            os.close(descriptor)

    @staticmethod
    def _validate_username(username: str) -> str:
        if not isinstance(username, str) or not 1 <= len(username) <= 64:
            raise AuthSetupError("Username must be 1 to 64 characters")
        if not all(char.isascii() and (char.isalnum() or char in "._-") for char in username):
            raise AuthSetupError("Username contains unsupported characters")
        return username.lower()

    @staticmethod
    def _validate_password(password: str) -> None:
        if not isinstance(password, str) or not 12 <= len(password) <= 256:
            raise AuthSetupError("Password must be 12 to 256 characters")

    def create_owner(self, username: str, password: str) -> UserRecord:
        username = self._validate_username(username)
        self._validate_password(password)
        with self._db() as db:
            if db.execute("SELECT 1 FROM users LIMIT 1").fetchone() is not None:
                raise AuthSetupError("An owner is already provisioned")
        salt = secrets.token_bytes(32)
        with self._kdf_slot():
            digest = _password_hash(password, salt)
        user_id = str(uuid4())
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                if db.execute("SELECT 1 FROM users LIMIT 1").fetchone() is not None:
                    raise AuthSetupError("An owner is already provisioned")
                db.execute(
                    "INSERT INTO users VALUES (?, ?, ?, ?, NULL, ?)",
                    (user_id, username, salt, digest, self._now()),
                )
                db.execute("COMMIT")
            except Exception:
                db.execute("ROLLBACK")
                raise
        return UserRecord(user_id, username, None)

    def get_user(self, user_id: str) -> UserRecord:
        with self._db() as db:
            row = db.execute(
                "SELECT user_id, username, telegram_user_id FROM users WHERE user_id = ?", (user_id,)
            ).fetchone()
        if row is None:
            raise AuthError("Authentication required")
        return UserRecord(**dict(row))

    def _attempt_key(self, username: str) -> str:
        return hashlib.sha256(username.encode("utf-8")).hexdigest()

    def _check_attempts(self, db: sqlite3.Connection, key: str, now: int) -> None:
        row = db.execute("SELECT * FROM login_attempts WHERE username_hash = ?", (key,)).fetchone()
        if row is not None and now < row["blocked_until"]:
            raise AuthError("Invalid credentials")

    def _record_failure(self, db: sqlite3.Connection, key: str, now: int, limit: int) -> None:
        row = db.execute("SELECT * FROM login_attempts WHERE username_hash = ?", (key,)).fetchone()
        if row is None or now - row["window_started_at"] >= ATTEMPT_WINDOW_SECONDS:
            failures = 1
            window_start = now
        else:
            failures = row["failures"] + 1
            window_start = row["window_started_at"]
        blocked_until = now + ATTEMPT_WINDOW_SECONDS if failures >= limit else 0
        db.execute(
            """INSERT INTO login_attempts VALUES (?, ?, ?, ?)
            ON CONFLICT(username_hash) DO UPDATE SET failures=excluded.failures,
            window_started_at=excluded.window_started_at, blocked_until=excluded.blocked_until""",
            (key, failures, window_start, blocked_until),
        )

    def login(self, username: str, password: str, *, previous_token: str | None = None) -> SessionGrant:
        try:
            normalized = self._validate_username(username)
        except AuthSetupError as exc:
            raise AuthError("Invalid credentials") from exc
        if not isinstance(password, str) or len(password) > 256:
            raise AuthError("Invalid credentials")
        now = self._now()
        key = self._attempt_key(normalized)
        with self._kdf_slot():
            with self._db() as db:
                self._check_attempts(db, key, now)
                self._check_attempts(db, GLOBAL_ATTEMPT_KEY, now)
                row = db.execute("SELECT * FROM users WHERE username = ?", (normalized,)).fetchone()
            salt = row["password_salt"] if row is not None else self._dummy_salt
            expected = row["password_digest"] if row is not None else self._dummy_digest
            candidate = _password_hash(password, salt)
            valid = row is not None and hmac.compare_digest(candidate, expected)
            with self._db() as db:
                db.execute("BEGIN IMMEDIATE")
                try:
                    self._check_attempts(db, key, now)
                    self._check_attempts(db, GLOBAL_ATTEMPT_KEY, now)
                    if not valid:
                        self._record_failure(db, key, now, MAX_LOGIN_FAILURES)
                        self._record_failure(db, GLOBAL_ATTEMPT_KEY, now, MAX_GLOBAL_FAILURES)
                        db.execute("COMMIT")
                        raise AuthError("Invalid credentials")
                    db.execute("DELETE FROM login_attempts WHERE username_hash = ?", (key,))
                    if previous_token:
                        db.execute(
                            "UPDATE sessions SET revoked_at = ? WHERE token_hash = ? AND revoked_at IS NULL",
                            (now, _token_hash(previous_token)),
                        )
                    token = secrets.token_urlsafe(32)
                    csrf = secrets.token_urlsafe(32)
                    expires = now + ABSOLUTE_SECONDS
                    db.execute(
                        "INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, NULL)",
                        (_token_hash(token), row["user_id"], csrf, now, now, expires),
                    )
                    db.execute("COMMIT")
                except AuthError:
                    raise
                except Exception:
                    db.execute("ROLLBACK")
                    raise
        return SessionGrant(
            UserRecord(row["user_id"], row["username"], row["telegram_user_id"]),
            token, csrf, expires,
        )

    def authenticate(self, token: str | None, *, touch: bool = True) -> SessionGrant:
        if not isinstance(token, str) or not 20 <= len(token) <= 200 or not token.isascii():
            raise AuthError("Authentication required")
        now = self._now()
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                row = db.execute(
                    """SELECT s.*, u.username, u.telegram_user_id FROM sessions s
                    JOIN users u ON u.user_id = s.user_id WHERE s.token_hash = ?""",
                    (_token_hash(token),),
                ).fetchone()
                if row is None or row["revoked_at"] is not None:
                    raise AuthError("Authentication required")
                if now >= row["absolute_expires_at"] or now - row["last_seen_at"] >= IDLE_SECONDS:
                    db.execute("UPDATE sessions SET revoked_at = ? WHERE token_hash = ?", (now, row["token_hash"]))
                    db.execute("COMMIT")
                    raise AuthError("Authentication required")
                if touch:
                    db.execute("UPDATE sessions SET last_seen_at = ? WHERE token_hash = ?", (now, row["token_hash"]))
                db.execute("COMMIT")
            except AuthError:
                if db.in_transaction:
                    db.execute("ROLLBACK")
                raise
            except Exception:
                db.execute("ROLLBACK")
                raise
        return SessionGrant(
            UserRecord(row["user_id"], row["username"], row["telegram_user_id"]),
            token, row["csrf_token"], row["absolute_expires_at"],
        )

    def check_csrf(self, grant: SessionGrant, candidate: str | None) -> None:
        if not isinstance(candidate, str) or not hmac.compare_digest(grant.csrf_token, candidate):
            raise AuthError("CSRF token is invalid")

    def logout(self, token: str) -> None:
        with self._db() as db:
            db.execute(
                "UPDATE sessions SET revoked_at = ? WHERE token_hash = ? AND revoked_at IS NULL",
                (self._now(), _token_hash(token)),
            )

    def revoke_all(self, user_id: str) -> int:
        with self._db() as db:
            cursor = db.execute(
                "UPDATE sessions SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL",
                (self._now(), user_id),
            )
        return cursor.rowcount

    def create_link_challenge(self, user_id: str) -> str:
        self.get_user(user_id)
        code = secrets.token_urlsafe(16)
        now = self._now()
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                db.execute("DELETE FROM link_challenges WHERE user_id = ?", (user_id,))
                db.execute(
                    "INSERT INTO link_challenges VALUES (?, ?, ?, NULL)",
                    (_token_hash(code), user_id, now + LINK_SECONDS),
                )
                db.execute("COMMIT")
            except Exception:
                db.execute("ROLLBACK")
                raise
        return code

    def confirm_link(self, code: str, telegram_user_id: int, allowed_admin_ids: frozenset[int]) -> UserRecord:
        if not isinstance(telegram_user_id, int) or telegram_user_id <= 0 or telegram_user_id not in allowed_admin_ids:
            raise AuthError("Link confirmation is not allowed")
        if not isinstance(code, str) or not 16 <= len(code) <= 64 or not code.isascii():
            raise AuthError("Link code is invalid")
        now = self._now()
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                challenge = db.execute(
                    "SELECT * FROM link_challenges WHERE code_hash = ?", (_token_hash(code),)
                ).fetchone()
                if challenge is None or challenge["used_at"] is not None or now >= challenge["expires_at"]:
                    raise AuthError("Link code is invalid")
                owner = db.execute("SELECT telegram_user_id FROM users WHERE user_id = ?", (challenge["user_id"],)).fetchone()
                if owner is None or owner["telegram_user_id"] not in (None, telegram_user_id):
                    raise AuthError("A different Telegram account is already linked")
                db.execute(
                    "UPDATE users SET telegram_user_id = ? WHERE user_id = ?",
                    (telegram_user_id, challenge["user_id"]),
                )
                db.execute("UPDATE link_challenges SET used_at = ? WHERE code_hash = ?", (now, challenge["code_hash"]))
                db.execute("DELETE FROM link_challenges WHERE user_id = ? AND code_hash != ?", (challenge["user_id"], challenge["code_hash"]))
                db.execute("UPDATE sessions SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL", (now, challenge["user_id"]))
                db.execute("COMMIT")
            except AuthError:
                db.execute("ROLLBACK")
                raise
            except Exception:
                db.execute("ROLLBACK")
                raise
        return self.get_user(challenge["user_id"])


def main() -> int:
    parser = argparse.ArgumentParser(description="Provision the GEO AI owner locally")
    parser.add_argument("provision-owner", nargs="?")
    parser.add_argument("--root", required=True)
    parser.add_argument("--username", required=True)
    args = parser.parse_args()
    if args.provision_owner != "provision-owner" or not sys.stdin.isatty():
        parser.error("Use provision-owner from an interactive terminal")
    password = getpass.getpass("New owner password: ")
    repeat = getpass.getpass("Repeat password: ")
    if password != repeat:
        parser.error("Passwords do not match")
    owner = AuthStore(args.root).create_owner(args.username, password)
    print(f"Owner provisioned: {owner.user_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
