"""Explicit, bounded maintenance command for expired temporary uploads."""

from __future__ import annotations

import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3

from autocad_assistance.services.project_store import ProjectStore


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--upload-root", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--apply", action="store_true", help="Remove expired temporary uploads")
    args = parser.parse_args(argv)
    if not 1 <= args.limit <= 100:
        parser.error("--limit must be between 1 and 100")
    if not args.project_root.is_dir() or not args.upload_root.is_dir():
        parser.error("Both explicit storage roots must already exist")
    database = args.project_root / "projects.sqlite3"
    if not database.is_file():
        parser.error("Existing project database is required")
    with closing(sqlite3.connect(f"file:{database}?mode=ro", uri=True)) as db:
        if db.execute("PRAGMA user_version").fetchone()[0] != 3:
            parser.error("Migrate the project database separately before cleanup")
    report = ProjectStore(args.project_root).cleanup_expired_uploads(
        args.upload_root, limit=args.limit, apply=args.apply,
    )
    print(json.dumps({
        "mode": "apply" if args.apply else "dry-run",
        "candidates": report.candidates,
        "removed": report.removed,
        "failed": report.failed,
    }, sort_keys=True))
    return 1 if report.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
