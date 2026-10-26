"""Fail-closed configuration, release verification and offline state operations."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import fcntl
from hashlib import sha256
import importlib
import ipaddress
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sqlite3
import subprocess
import sys
import tarfile
from urllib.parse import urlsplit


RELEASES = {
    "79528bb9f6070e458724886a915f9d035cdfd110": (
        "cada7fb4f2919fe321cffbe74beeec499bc60e833e33f36a94f404560f91ce81",
        8570880,
    ),
    "15374b5c856958fdf67c5efdce68db81e05ac92f": (
        "b6d5ba6ec44554feca4d1e43fb98450fccab13f7d5b003f2c6ddca0e4520df0b",
        8581120,
    ),
    "1ea061c1afb4b75b0aba06ae67d402b0a3e815a6": (
        "9e3858aeec823b64ae7bfa61c69890a93acd1f0f2e29c687ee149afd34229c8f",
        8509440,
    ),
}
MARKER = "GEOAI_PILOT_STATE_V1\n"
LOCK_SHA256 = "d8d2cf3756f29f64246f133f694ee61aa9711f8eb8e95c4fd2039734d381c351"
PYTHON_VERSION = (3, 13, 5)
STATE_NAME = re.compile(r"[a-z][a-z0-9-]{0,47}\Z")
CONFIG_KEYS = {
    "mode", "installation_root", "release_commit", "archive_path",
    "release_root", "state_root", "auth_root", "project_root",
    "upload_root", "jobs_root", "backup_root", "log_root",
    "auth_origin", "bind_host", "bind_port",
}


class PilotError(ValueError):
    """Configuration, artifact or offline-state invariant was not met."""


def _absolute(value: object, label: str) -> Path:
    if not isinstance(value, str) or not value.startswith("/"):
        raise PilotError(f"{label} must be an absolute path")
    path = Path(value)
    if ".." in path.parts or str(path) != value.rstrip("/"):
        raise PilotError(f"{label} must be normalized")
    for part in (path, *path.parents):
        if part.is_symlink():
            raise PilotError(f"{label} contains a symlink")
    return path


def _regular(path: Path, label: str) -> None:
    if path.is_symlink() or not path.is_file():
        raise PilotError(f"{label} must be a regular file")


def _sha(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _origin(value: object, mode: str, port: int) -> str:
    if not isinstance(value, str):
        raise PilotError("auth_origin must be HTTPS")
    parsed = urlsplit(value)
    try:
        parsed_port = parsed.port
    except ValueError as exc:
        raise PilotError("auth_origin port is invalid") from exc
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username
            or parsed.password or parsed.path or parsed.query or parsed.fragment
            or value.endswith("/") or not parsed.netloc):
        raise PilotError("auth_origin must be one exact HTTPS origin")
    hostname = parsed.hostname
    if mode == "synthetic":
        if hostname not in {"localhost", "127.0.0.1"} or parsed_port != port:
            raise PilotError("synthetic origin must match the loopback TLS port")
    else:
        if parsed_port not in (None, 443) or "." not in hostname:
            raise PilotError("pilot origin must be a private HTTPS hostname on port 443")
        try:
            ipaddress.ip_address(hostname)
        except ValueError:
            pass
        else:
            raise PilotError("pilot origin must be a DNS hostname")
        if hostname in {"localhost", "localhost.localdomain"} or hostname.endswith(".invalid"):
            raise PilotError("pilot origin is not a real private hostname")
    return value


@dataclass(frozen=True)
class Config:
    mode: str
    installation_root: Path
    release_commit: str
    archive_path: Path
    release_root: Path
    state_root: Path
    auth_root: Path
    project_root: Path
    upload_root: Path
    jobs_root: Path
    backup_root: Path
    log_root: Path
    auth_origin: str
    bind_host: str
    bind_port: int

    @classmethod
    def load(cls, config_path: str | Path) -> "Config":
        path = _absolute(str(config_path), "config_path")
        _regular(path, "config_path")
        if path.stat().st_mode & 0o022:
            raise PilotError("config_path must not be group/world writable")
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise PilotError("config_path is not valid JSON") from exc
        if not isinstance(raw, dict) or set(raw) != CONFIG_KEYS:
            raise PilotError("config keys differ from the reviewed contract")
        mode = raw["mode"]
        if mode not in {"synthetic", "pilot"}:
            raise PilotError("mode must be synthetic or pilot")
        commit = raw["release_commit"]
        if commit not in RELEASES:
            raise PilotError("release_commit is not approved")
        port = raw["bind_port"]
        if type(port) is not int or not 1024 <= port <= 65535:
            raise PilotError("bind_port must be an unprivileged TCP port")
        if raw["bind_host"] != "127.0.0.1":
            raise PilotError("ASGI may bind only to 127.0.0.1")
        root = _absolute(raw["installation_root"], "installation_root")
        if mode == "pilot" and root != Path("/srv/geoai-pilot"):
            raise PilotError("pilot installation root is fixed to /srv/geoai-pilot")
        if not root.is_dir():
            raise PilotError("installation_root must already exist")
        if root.stat().st_mode & 0o022:
            raise PilotError("installation_root must not be group/world writable")
        paths = {name: _absolute(raw[name], name) for name in (
            "archive_path", "release_root", "state_root", "auth_root",
            "project_root", "upload_root", "jobs_root", "backup_root", "log_root"
        )}
        expected = {
            "archive_path": root / "archives" / f"{commit}.tar",
            "release_root": root / "releases" / commit,
            "backup_root": root / "backups",
            "log_root": root / "logs",
        }
        state = paths["state_root"]
        if state.parent != root / "states" or not STATE_NAME.fullmatch(state.name):
            raise PilotError("state_root must be a named child of installation_root/states")
        expected.update({
            "auth_root": state / "auth", "project_root": state / "projects",
            "upload_root": state / "uploads", "jobs_root": state / "jobs",
        })
        if any(paths[name] != target for name, target in expected.items()):
            raise PilotError("release, state, backup or log paths conflict")
        return cls(
            mode=mode, installation_root=root, release_commit=commit,
            archive_path=paths["archive_path"], release_root=paths["release_root"],
            state_root=state, auth_root=paths["auth_root"],
            project_root=paths["project_root"], upload_root=paths["upload_root"],
            jobs_root=paths["jobs_root"], backup_root=paths["backup_root"],
            log_root=paths["log_root"],
            auth_origin=_origin(raw["auth_origin"], mode, port),
            bind_host="127.0.0.1", bind_port=port,
        )

    def check_state(self) -> None:
        marker = self.state_root / ".geoai-pilot-state"
        _regular(marker, "state marker")
        if marker.stat().st_mode & 0o022 or marker.read_text(encoding="ascii") != MARKER:
            raise PilotError("state marker does not match")
        for directory in (self.state_root, self.auth_root, self.project_root,
                          self.upload_root, self.jobs_root):
            if directory.is_symlink() or not directory.is_dir():
                raise PilotError("state directory is missing or linked")
            if directory.stat().st_mode & 0o077:
                raise PilotError("state directory is accessible outside its owner")


def init_state(config: Config) -> None:
    if config.state_root.exists() or config.state_root.is_symlink():
        raise PilotError("state_root already exists")
    if config.state_root.parent.is_symlink() or not config.state_root.parent.is_dir():
        raise PilotError("states parent must exist and not be linked")
    if config.state_root.parent.stat().st_mode & 0o022:
        raise PilotError("states parent must not be group/world writable")
    config.state_root.mkdir(mode=0o700)
    for child in (config.auth_root, config.project_root, config.upload_root, config.jobs_root):
        child.mkdir(mode=0o700)
    marker = config.state_root / ".geoai-pilot-state"
    marker.write_text(MARKER, encoding="ascii")
    marker.chmod(0o600)


def verify_release(config: Config) -> dict[str, object]:
    _regular(config.archive_path, "exact release archive")
    if config.archive_path.stat().st_mode & 0o022:
        raise PilotError("release archive must not be group/world writable")
    expected_sha, expected_bytes = RELEASES[config.release_commit]
    if config.archive_path.stat().st_size != expected_bytes or _sha(config.archive_path) != expected_sha:
        raise PilotError("release archive size or SHA-256 differs")
    if config.release_root.is_symlink() or not config.release_root.is_dir():
        raise PilotError("release_root is missing or linked")
    if config.release_root.stat().st_mode & 0o022:
        raise PilotError("release_root must not be group/world writable")
    expected_files: dict[str, str] = {}
    with tarfile.open(config.archive_path, "r:") as archive:
        for member in archive:
            relative = PurePosixPath(member.name)
            if (relative.is_absolute() or ".." in relative.parts or
                    not relative.parts or member.issym() or member.islnk()):
                raise PilotError("unsafe release archive entry")
            if member.isdir():
                continue
            if not member.isfile() or member.name in expected_files:
                raise PilotError("unsupported or duplicate archive entry")
            source = archive.extractfile(member)
            if source is None:
                raise PilotError("archive file has no bytes")
            expected_files[member.name] = sha256(source.read()).hexdigest()
    found: dict[str, str] = {}
    for current, dirs, files in os.walk(config.release_root, followlinks=False):
        parent = Path(current)
        for name in dirs:
            if (parent / name).is_symlink():
                raise PilotError("linked release directory")
        for name in files:
            path = parent / name
            _regular(path, "release file")
            if path.stat().st_mode & 0o022:
                raise PilotError("release file is group/world writable")
            found[path.relative_to(config.release_root).as_posix()] = _sha(path)
    if found != expected_files:
        raise PilotError("extracted release differs from the exact archive")
    lock = config.release_root / "harness" / "staging" / "requirements.lock"
    _regular(lock, "release requirements lock")
    if _sha(lock) != LOCK_SHA256 or sys.version_info[:3] != PYTHON_VERSION:
        raise PilotError("release lock or Python version differs")
    try:
        frozen = subprocess.run(
            [sys.executable, "-m", "pip", "freeze"],
            capture_output=True, text=True, check=True, timeout=30,
        ).stdout.splitlines()
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise PilotError("Python packages could not be verified") from exc
    if frozen != lock.read_text(encoding="utf-8").splitlines():
        raise PilotError("Python package versions differ from the release lock")
    return {"commit": config.release_commit, "archiveSha256": expected_sha,
            "files": len(found), "lockSha256": LOCK_SHA256,
            "python": ".".join(map(str, PYTHON_VERSION))}


@contextmanager
def state_lock(config: Config):
    config.check_state()
    path = config.state_root / ".active.lock"
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise PilotError("state is active; stop the service first") from exc
        yield
    finally:
        os.close(fd)


def make_app(config: Config):
    config.check_state()
    verify_release(config)
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    sys.dont_write_bytecode = True
    for name, module in tuple(sys.modules.items()):
        if name == "autocad_assistance" or name.startswith("autocad_assistance."):
            location = getattr(module, "__file__", None)
            if location and not Path(location).resolve().is_relative_to(config.release_root):
                raise PilotError("a different GEO AI codebase is already imported")
    sys.path.insert(0, str(config.release_root))
    module = importlib.import_module("autocad_assistance.api.app")
    if not Path(module.__file__).resolve().is_relative_to(config.release_root):
        raise PilotError("GEO AI import did not come from the exact release")
    return module.create_app(
        auth_root=config.auth_root, project_root=config.project_root,
        upload_root=config.upload_root, jobs_root=config.jobs_root,
        auth_origin=config.auth_origin,
    )


def _state_files(root: Path) -> dict[str, str]:
    found = {}
    for current, dirs, files in os.walk(root, followlinks=False):
        parent = Path(current)
        for name in dirs:
            if (parent / name).is_symlink():
                raise PilotError("linked state directory")
        for name in files:
            path = parent / name
            _regular(path, "state file")
            found[path.relative_to(root).as_posix()] = _sha(path)
    return dict(sorted(found.items()))


def _sqlite_versions(root: Path) -> dict[str, int]:
    versions = {}
    for name, expected in (("auth/auth.sqlite3", 1), ("projects/projects.sqlite3", 8)):
        path = root / name
        _regular(path, name)
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as db:
            if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise PilotError(f"{name} failed SQLite integrity")
            version = db.execute("PRAGMA user_version").fetchone()[0]
        if version != expected:
            raise PilotError(f"{name} has incompatible schema")
        versions[name] = version
    return versions


def backup_state(config: Config, name: str) -> dict[str, object]:
    if not STATE_NAME.fullmatch(name):
        raise PilotError("backup name is invalid")
    if config.backup_root.is_symlink() or not config.backup_root.is_dir():
        raise PilotError("backup_root must exist and not be linked")
    target = config.backup_root / name
    if target.exists() or target.is_symlink():
        raise PilotError("backup target already exists")
    with state_lock(config):
        versions = _sqlite_versions(config.state_root)
        files = _state_files(config.state_root)
        target.mkdir(mode=0o700)
        shutil.copytree(config.state_root, target / "state", symlinks=False)
        if _state_files(target / "state") != files:
            raise PilotError("backup copy differs from source")
        manifest = {"format": 1, "stateName": config.state_root.name,
                    "sqlite": versions, "files": files}
        (target / "manifest.json").write_text(
            json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        (target / "manifest.json").chmod(0o600)
    return {"backup": str(target), "files": len(files), "sqlite": versions}


def restore_state(config: Config, backup_name: str, new_state_name: str) -> dict[str, object]:
    if not STATE_NAME.fullmatch(backup_name) or not STATE_NAME.fullmatch(new_state_name):
        raise PilotError("backup or restore name is invalid")
    source = config.backup_root / backup_name
    target = config.installation_root / "states" / new_state_name
    if source.is_symlink() or not source.is_dir() or target.exists() or target.is_symlink():
        raise PilotError("backup missing or fresh restore target unavailable")
    with state_lock(config):
        manifest_path = source / "manifest.json"
        _regular(manifest_path, "backup manifest")
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise PilotError("backup manifest is invalid") from exc
        files = _state_files(source / "state")
        if manifest.get("format") != 1 or manifest.get("files") != files:
            raise PilotError("backup checksum mismatch")
        if manifest.get("sqlite") != _sqlite_versions(source / "state"):
            raise PilotError("backup schema mismatch")
        if (source / "state" / ".geoai-pilot-state").read_text(encoding="ascii") != MARKER:
            raise PilotError("backup state marker differs")
        shutil.copytree(source / "state", target, symlinks=False)
        if _state_files(target) != files or _sqlite_versions(target) != manifest["sqlite"]:
            raise PilotError("restored state differs")
    return {"state": str(target), "files": len(files), "sqlite": manifest["sqlite"]}
