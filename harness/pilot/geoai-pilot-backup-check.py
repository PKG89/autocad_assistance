#!/usr/bin/env python3
"""VM110-only application dump status and integrity gate for vzdump hooks."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
from datetime import datetime, timezone


NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}\Z")
EXPECTED_SQLITE = {"auth/auth.sqlite3": 1, "projects/projects.sqlite3": 8}


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def utc_now():
    return datetime.now(timezone.utc)


def timestamp(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp lacks timezone")
    return parsed.astimezone(timezone.utc)


def files_in(root):
    found = {}
    for current, dirs, files in os.walk(root, followlinks=False):
        parent = Path(current)
        for name in dirs:
            if (parent / name).is_symlink():
                raise ValueError("linked backup directory")
        for name in files:
            path = parent / name
            if path.is_symlink() or not path.is_file():
                raise ValueError("non-regular backup file")
            found[path.relative_to(root).as_posix()] = digest(path)
    return dict(sorted(found.items()))


def verify(root, backup_name, expected_manifest=None):
    if not NAME.fullmatch(backup_name):
        raise ValueError("invalid backup name")
    if root.is_symlink() or not root.is_dir():
        raise ValueError("backup root unavailable")
    folder = root / backup_name
    if folder.is_symlink() or not folder.is_dir():
        raise ValueError("backup directory unavailable")
    manifest_path = folder / "manifest.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ValueError("backup manifest unavailable")
    manifest_sha = digest(manifest_path)
    if expected_manifest is not None and manifest_sha != expected_manifest:
        raise ValueError("backup manifest changed")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("format") != 1 or not isinstance(manifest.get("files"), dict):
        raise ValueError("unsupported backup manifest")
    state = folder / "state"
    if state.is_symlink() or not state.is_dir():
        raise ValueError("backup state unavailable")
    if files_in(state) != manifest["files"]:
        raise ValueError("backup file checksum mismatch")
    if manifest.get("sqlite") != EXPECTED_SQLITE:
        raise ValueError("backup SQLite versions differ")
    for relative, version in EXPECTED_SQLITE.items():
        with sqlite3.connect(f"file:{state / relative}?mode=ro", uri=True) as db:
            if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise ValueError("backup SQLite integrity failed")
            if db.execute("PRAGMA user_version").fetchone()[0] != version:
                raise ValueError("backup SQLite schema differs")
    return {"backupName": backup_name, "manifestSha256": manifest_sha,
            "fileCount": len(manifest["files"]), "sqlite": EXPECTED_SQLITE}


def write_status(path, value):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.parent.is_symlink() or path.is_symlink():
        raise ValueError("linked status path")
    temporary = path.with_name(path.name + f".{os.getpid()}.tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, sort_keys=True, separators=(",", ":"))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("mark", "check"))
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--status", type=Path, required=True)
    parser.add_argument("--attempt", default="")
    parser.add_argument("--result", choices=("running", "success", "failed"))
    parser.add_argument("--backup", default="")
    parser.add_argument("--max-age-seconds", type=int, default=2700)
    parser.add_argument("--at", default="")  # Test-only clock override.
    args = parser.parse_args()
    now = timestamp(args.at) if args.at else utc_now()
    try:
        if args.action == "mark":
            if not NAME.fullmatch(args.attempt) or not args.result:
                raise ValueError("attempt and result required")
            value = {"format": 1, "attemptId": args.attempt,
                     "result": args.result, "updatedAt": now.isoformat()}
            if args.result == "success":
                value.update(verify(args.root, args.backup))
            elif args.backup:
                raise ValueError("backup name only allowed for success")
            write_status(args.status, value)
            print(json.dumps(value, sort_keys=True))
        else:
            if args.max_age_seconds <= 0:
                raise ValueError("max age must be positive")
            if args.status.is_symlink() or not args.status.is_file():
                raise ValueError("dump status missing")
            value = json.loads(args.status.read_text(encoding="utf-8"))
            if value.get("format") != 1 or value.get("result") != "success":
                raise ValueError("latest dump attempt not successful")
            age = (now - timestamp(value["updatedAt"])).total_seconds()
            if age < -60 or age > args.max_age_seconds:
                raise ValueError("successful dump outside age window")
            result = verify(args.root, value["backupName"], value["manifestSha256"])
            result.update({"ok": True, "attemptId": value["attemptId"],
                           "completedAt": value["updatedAt"], "ageSeconds": int(age)})
            print(json.dumps(result, sort_keys=True))
    except (OSError, ValueError, KeyError, sqlite3.DatabaseError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True))
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
