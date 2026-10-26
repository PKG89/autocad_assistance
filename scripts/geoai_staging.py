"""Build and verify a disposable, synthetic-only GEO AI HTTPS staging root.

No command reads production configuration or changes system services. Backups
require the local server to be stopped and restores always use a new root.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import ssl
import subprocess
import sys
import tarfile
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import urlopen
from uuid import uuid4


MARKER = "GEOAI_SYNTHETIC_STAGE_V1\n"
SCHEMA_VERSION = 5
COMMIT_RE = re.compile(r"[0-9a-f]{40}\Z")


class StageError(ValueError):
    """A staging invariant is unmet; no production fallback is allowed."""


def _absolute(value: str | Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        raise StageError("An absolute path is required")
    for component in (path, *path.parents):
        if component.is_symlink():
            raise StageError("Symlinked path components are forbidden")
    return path.resolve(strict=False)


def _regular(path: Path) -> None:
    if path.is_symlink() or not path.is_file():
        raise StageError(f"Required regular file is missing: {path}")


def _root(value: str | Path) -> Path:
    root = _absolute(value)
    marker = root / ".geoai-synthetic-stage"
    _regular(marker)
    if marker.read_text(encoding="ascii") != MARKER:
        raise StageError("This is not a synthetic staging root")
    return root


def _write_json(path: Path, payload: object) -> None:
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    with temporary.open("x", encoding="utf-8") as target:
        os.chmod(temporary, 0o600)
        json.dump(payload, target, sort_keys=True, separators=(",", ":"))
        target.write("\n")
        target.flush()
        os.fsync(target.fileno())
    os.replace(temporary, path)


def _json(path: Path) -> dict:
    _regular(path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise StageError(f"Invalid JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise StageError(f"Invalid JSON object: {path}")
    return payload


def _sha(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _files(root: Path, *, excluded: frozenset[str] = frozenset()) -> dict[str, str]:
    found = {}
    for current, dirs, files in os.walk(root, followlinks=False):
        parent = Path(current)
        for name in dirs:
            if (parent / name).is_symlink():
                raise StageError("Symlinked directory in staged files")
        for name in files:
            path = parent / name
            if path.is_symlink() or not path.is_file():
                raise StageError("Non-regular staged file")
            relative = path.relative_to(root).as_posix()
            if relative not in excluded:
                found[relative] = _sha(path)
    return dict(sorted(found.items()))


@contextmanager
def _lock(root: Path):
    fd = os.open(root / ".operation.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise StageError("Staging root is active; stop it before this operation") from exc
        yield
    finally:
        os.close(fd)


def _origin(value: str) -> tuple[str, int]:
    parsed = urlsplit(value)
    try:
        port = parsed.port
    except ValueError as exc:
        raise StageError("Invalid HTTPS port") from exc
    if (parsed.scheme != "https" or parsed.hostname not in {"localhost", "127.0.0.1"}
            or port is None or not 1 <= port <= 65535 or parsed.username is not None
            or parsed.password is not None or parsed.path not in {"", "/"}
            or parsed.query or parsed.fragment):
        raise StageError("Only an explicit loopback HTTPS origin is allowed")
    return parsed.hostname, port


def init(root_value: str, lock_value: str, origin: str) -> dict:
    root = _absolute(root_value)
    lock = _absolute(lock_value)
    _regular(lock)
    _origin(origin)
    if root.exists() or not root.parent.is_dir():
        raise StageError("A new root under an existing parent is required")
    root.mkdir(mode=0o700)
    for name in ("releases", "archives", "state/auth", "state/projects",
                 "state/uploads", "state/jobs", "logs", "tls"):
        (root / name).mkdir(parents=True, exist_ok=True, mode=0o700)
    shutil.copyfile(lock, root / "requirements.lock")
    os.chmod(root / "requirements.lock", 0o600)
    _write_json(root / "config.json", {"mode": "synthetic-only", "origin": origin})
    (root / ".geoai-synthetic-stage").write_text(MARKER, encoding="ascii")
    os.chmod(root / ".geoai-synthetic-stage", 0o600)
    return {"root": str(root), "origin": origin, "lockSha256": _sha(root / "requirements.lock")}


def _runtime(python_value: str, lock: Path) -> str:
    # Virtual environments normally make bin/python a symlink. Resolve only
    # this executable; staging roots and files still reject symlink paths.
    python = Path(python_value)
    if not python.is_absolute():
        raise StageError("An absolute Python executable path is required")
    resolved = python.resolve(strict=True)
    _regular(resolved)
    expected = lock.read_text(encoding="utf-8").splitlines()
    try:
        frozen = subprocess.run([str(python), "-m", "pip", "freeze"],
            check=True, capture_output=True, text=True).stdout.splitlines()
        version = subprocess.run([str(python), "-c", "import sys; print(sys.version.split()[0])"],
            check=True, capture_output=True, text=True).stdout.strip()
    except subprocess.CalledProcessError as exc:
        raise StageError("Python runtime cannot be verified") from exc
    if expected != frozen:
        raise StageError("Python package versions differ from the staging lock")
    if not version.startswith("3.13."):
        raise StageError("Python 3.13 is required for this stage")
    return version


def _git(source: Path, *args: str) -> str:
    try:
        result = subprocess.run(["git", "-C", str(source), *args],
            check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        raise StageError("Git source/ref validation failed") from exc
    return result.stdout.strip()


def _extract_archive(archive: Path, release: Path) -> None:
    release.mkdir(mode=0o700)
    with tarfile.open(archive, "r:") as source:
        for member in source:
            name = PurePosixPath(member.name)
            if (name.is_absolute() or not name.parts or any(part in {".", ".."} for part in name.parts)
                    or member.issym() or member.islnk() or not (member.isdir() or member.isfile())):
                raise StageError("Unsafe Git archive member")
            target = release.joinpath(*name.parts)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True, mode=0o755)
                continue
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
            stream = source.extractfile(member)
            if stream is None:
                raise StageError("Git archive member has no bytes")
            with target.open("xb") as output:
                shutil.copyfileobj(stream, output)
            os.chmod(target, 0o644)


def verify(root_value: str, commit: str | None = None) -> dict:
    root = _root(root_value)
    if commit is None:
        commit = _json(root / "current.json").get("commit")
    if not isinstance(commit, str) or COMMIT_RE.fullmatch(commit) is None:
        raise StageError("Invalid release ID")
    release = root / "releases" / commit
    manifest = _json(release / "release.json")
    if (manifest.get("commit") != commit or manifest.get("schemaVersion") != SCHEMA_VERSION
            or manifest.get("lockSha256") != _sha(root / "requirements.lock")):
        raise StageError("Release provenance does not match staging policy")
    archive = root / "archives" / f"{commit}.tar"
    _regular(archive)
    if _sha(archive) != manifest.get("archiveSha256"):
        raise StageError("Release archive checksum mismatch")
    if _files(release, excluded=frozenset({"release.json"})) != manifest.get("files"):
        raise StageError("Release file checksum mismatch")
    return manifest


def build(root_value: str, source_value: str, python_value: str, ref: str = "HEAD") -> dict:
    root = _root(root_value)
    source = _absolute(source_value)
    if not source.is_dir() or root == source or root.is_relative_to(source) or source.is_relative_to(root):
        raise StageError("Source and stage roots must be separate")
    if _git(source, "status", "--porcelain"):
        raise StageError("Build requires a clean Git checkout")
    commit = _git(source, "rev-parse", "--verify", f"{ref}^{{commit}}")
    if COMMIT_RE.fullmatch(commit) is None:
        raise StageError("Git ref did not resolve to a full commit")
    with _lock(root):
        version = _runtime(python_value, root / "requirements.lock")
        archive = root / "archives" / f"{commit}.tar"
        release = root / "releases" / commit
        if release.exists():
            return verify(str(root), commit)
        if archive.exists():
            raise StageError("Orphaned archive needs inspection")
        temporary_archive = root / "archives" / f".{commit}.{uuid4().hex}.tmp"
        try:
            subprocess.run(["git", "-C", str(source), "archive", "--format=tar",
                "--output", str(temporary_archive), commit], check=True,
                capture_output=True)
        except subprocess.CalledProcessError as exc:
            raise StageError("Could not archive the exact Git commit") from exc
        temporary_release = root / "releases" / f".{commit}.{uuid4().hex}.tmp"
        _extract_archive(temporary_archive, temporary_release)
        payload = {
            "commit": commit, "archiveSha256": _sha(temporary_archive),
            "lockSha256": _sha(root / "requirements.lock"),
            "pythonVersion": version, "schemaVersion": SCHEMA_VERSION,
            "files": _files(temporary_release),
        }
        _write_json(temporary_release / "release.json", payload)
        os.replace(temporary_archive, archive)
        os.replace(temporary_release, release)
        return verify(str(root), commit)


def activate(root_value: str, commit: str) -> dict:
    root = _root(root_value)
    with _lock(root):
        verify(str(root), commit)
        _write_json(root / "current.json", {"commit": commit})
        return {"active": commit}


def _current(root: Path) -> str:
    commit = _json(root / "current.json").get("commit")
    verify(str(root), commit)
    return commit


def run(root_value: str) -> None:
    root = _root(root_value)
    with _lock(root):
        commit = _current(root)
        if _runtime(sys.executable, root / "requirements.lock") != verify(str(root), commit)["pythonVersion"]:
            raise StageError("Python version differs from the release build")
        config = _json(root / "config.json")
        if config.get("mode") != "synthetic-only":
            raise StageError("Only synthetic staging mode can run")
        _, port = _origin(config.get("origin", ""))
        certificate, private_key = root / "tls" / "cert.pem", root / "tls" / "key.pem"
        _regular(certificate)
        _regular(private_key)
        if private_key.stat().st_mode & 0o077:
            raise StageError("TLS private key must not be group/world readable")
        sys.path.insert(0, str(root / "releases" / commit))
        # The isolated calculation worker is a child Python process. Keep
        # bytecode caches out of the checksum-verified release in both.
        os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
        sys.dont_write_bytecode = True
        from autocad_assistance.api import create_app
        import uvicorn

        app = create_app(
            auth_root=root / "state" / "auth", project_root=root / "state" / "projects",
            upload_root=root / "state" / "uploads", jobs_root=root / "state" / "jobs",
            auth_origin=config["origin"],
        )
        uvicorn.run(app, host="127.0.0.1", port=port,
            ssl_certfile=str(certificate), ssl_keyfile=str(private_key),
            access_log=False, log_level="warning", server_header=False)


def health(root_value: str) -> dict:
    root = _root(root_value)
    config = _json(root / "config.json")
    origin = config.get("origin", "")
    _origin(origin)
    certificate = root / "tls" / "cert.pem"
    _regular(certificate)
    context = ssl.create_default_context(cafile=str(certificate))
    try:
        with urlopen(f"{origin}/health", context=context, timeout=5) as response:
            payload = json.load(response)
            if response.status != 200 or payload.get("status") != "ok":
                raise StageError("Health endpoint returned an invalid response")
        try:
            urlopen(f"{origin}/api/v1/projects", context=context, timeout=5)
        except HTTPError as exc:
            if exc.code != 401:
                raise StageError("Anonymous project route did not deny access") from exc
        else:
            raise StageError("Anonymous project route was accessible")
    except (OSError, ssl.SSLError) as exc:
        raise StageError("Staging HTTPS health check failed") from exc
    return {"status": "ok", "active": _current(root), "anonymousProjects": 401}


def _copy_regular_tree(source: Path, destination: Path) -> None:
    destination.mkdir(mode=0o700)
    for current, dirs, files in os.walk(source, followlinks=False):
        parent = Path(current)
        relative = parent.relative_to(source)
        target_parent = destination / relative
        target_parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        for name in dirs:
            if (parent / name).is_symlink():
                raise StageError("Symlinked staging directory cannot be backed up")
        for name in files:
            path = parent / name
            _regular(path)
            target = target_parent / name
            shutil.copy2(path, target, follow_symlinks=False)
            if path.stat().st_mode & 0o077 == 0:
                os.chmod(target, 0o600)


def _checkpoint_databases(source: Path, backup_root: Path) -> None:
    import sqlite3

    for relative in ("state/auth/auth.sqlite3", "state/projects/projects.sqlite3"):
        original = source / relative
        if not original.exists():
            continue
        _regular(original)
        target = backup_root / relative
        fresh = target.with_name(target.name + ".consistent")
        with sqlite3.connect(f"file:{original}?mode=ro", uri=True) as src:
            with sqlite3.connect(fresh) as dest:
                src.backup(dest)
                if dest.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise StageError("SQLite backup failed integrity check")
        os.chmod(fresh, 0o600)
        os.replace(fresh, target)
        for suffix in ("-wal", "-shm"):
            target.with_name(target.name + suffix).unlink(missing_ok=True)


def backup(root_value: str, destination_value: str) -> dict:
    root = _root(root_value)
    destination = _absolute(destination_value)
    if (destination.exists() or not destination.parent.is_dir() or
            destination.is_relative_to(root) or root.is_relative_to(destination)):
        raise StageError("Backup requires a fresh directory outside the staging root")
    with _lock(root):
        active = _current(root)
        temporary = destination.with_name(f".{destination.name}.{uuid4().hex}.tmp")
        _copy_regular_tree(root, temporary)
        _checkpoint_databases(root, temporary)
        manifest = {"version": 1, "active": active,
                    "files": _files(temporary, excluded=frozenset({"backup-manifest.json"}))}
        _write_json(temporary / "backup-manifest.json", manifest)
        os.replace(temporary, destination)
        return {"backup": str(destination), "active": active, "files": len(manifest["files"])}


def restore(backup_value: str, destination_value: str) -> dict:
    source = _absolute(backup_value)
    destination = _absolute(destination_value)
    if not source.is_dir() or destination.exists() or not destination.parent.is_dir():
        raise StageError("Restore requires an existing backup and a fresh root")
    manifest = _json(source / "backup-manifest.json")
    if manifest.get("version") != 1 or _files(source, excluded=frozenset({"backup-manifest.json"})) != manifest.get("files"):
        raise StageError("Backup checksum or file set mismatch")
    if destination.is_relative_to(source) or source.is_relative_to(destination):
        raise StageError("Restore target must be separate from the backup")
    temporary = destination.with_name(f".{destination.name}.{uuid4().hex}.tmp")
    _copy_regular_tree(source, temporary)
    (temporary / "backup-manifest.json").unlink()
    os.replace(temporary, destination)
    root = _root(str(destination))
    if _current(root) != manifest.get("active"):
        raise StageError("Restored release does not match backup manifest")
    return {"restored": str(root), "active": manifest["active"]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("init", "build", "verify", "activate", "run", "health", "backup", "restore"):
        commands.add_parser(name)
    commands.choices["init"].add_argument("--root", required=True)
    commands.choices["init"].add_argument("--lock", required=True)
    commands.choices["init"].add_argument("--origin", required=True)
    commands.choices["build"].add_argument("--root", required=True)
    commands.choices["build"].add_argument("--source", required=True)
    commands.choices["build"].add_argument("--python", required=True)
    commands.choices["build"].add_argument("--ref", default="HEAD")
    commands.choices["verify"].add_argument("--root", required=True)
    commands.choices["verify"].add_argument("--commit")
    commands.choices["activate"].add_argument("--root", required=True)
    commands.choices["activate"].add_argument("--commit", required=True)
    commands.choices["run"].add_argument("--root", required=True)
    commands.choices["health"].add_argument("--root", required=True)
    commands.choices["backup"].add_argument("--root", required=True)
    commands.choices["backup"].add_argument("--dest", required=True)
    commands.choices["restore"].add_argument("--backup", required=True)
    commands.choices["restore"].add_argument("--dest", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            result = init(args.root, args.lock, args.origin)
        elif args.command == "build":
            result = build(args.root, args.source, args.python, args.ref)
        elif args.command == "verify":
            result = verify(args.root, args.commit)
        elif args.command == "activate":
            result = activate(args.root, args.commit)
        elif args.command == "run":
            run(args.root)
            return 0
        elif args.command == "health":
            result = health(args.root)
        elif args.command == "backup":
            result = backup(args.root, args.dest)
        else:
            result = restore(args.backup, args.dest)
    except StageError as exc:
        parser.error(str(exc))
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
