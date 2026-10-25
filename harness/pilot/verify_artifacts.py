"""Verify exact product and operational overlay archives against their Git source."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import tarfile
from tempfile import TemporaryDirectory


def digest(path: Path) -> str:
    value = sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def checked(result: bool, label: str) -> None:
    if not result:
        raise SystemExit(f"artifact verification failed: {label}")


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--product", type=Path, required=True)
    parser.add_argument("--overlay", type=Path, required=True)
    parser.add_argument("--repo", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    product = manifest["product"]
    overlay = manifest["operational_overlay"]
    for path, record in ((args.product, product), (args.overlay, overlay)):
        checked(path.is_file() and not path.is_symlink(), f"{path.name}: missing/linked")
        checked(path.stat().st_size == record["archive_bytes"], f"{path.name}: size")
        checked(digest(path) == record["archive_sha256"], f"{path.name}: SHA-256")
    checked(git(args.repo, "cat-file", "-t", product["git_commit"]) == "commit",
            "product source object")
    checked(git(args.repo, "cat-file", "-t", overlay["source_commit"]) == "commit",
            "overlay source object")
    checked(git(args.repo, "rev-parse", f"{overlay['source_commit']}:pilot_ops")
            == overlay["source_tree"], "overlay source tree")
    with TemporaryDirectory(prefix="geoai-artifact-verify-") as temporary:
        product_rebuilt = Path(temporary) / "product.tar"
        overlay_rebuilt = Path(temporary) / "overlay.tar"
        subprocess.run(
            ["git", "-C", str(args.repo), "archive", "--format=tar",
             f"--output={product_rebuilt}", product["git_commit"]],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(args.repo), "archive", "--format=tar",
             f"--output={overlay_rebuilt}", overlay["source_commit"], "pilot_ops"],
            check=True,
        )
        checked(digest(product_rebuilt) == product["archive_sha256"],
                "product Git archive reproducibility")
        checked(digest(overlay_rebuilt) == overlay["archive_sha256"],
                "overlay Git archive reproducibility")
    with tarfile.open(args.product, "r:") as archive:
        product_files = [member for member in archive if member.isfile()]
    checked(len(product_files) == product["tracked_files"], "product file count")
    found = {}
    with tarfile.open(args.overlay, "r:") as archive:
        for member in archive:
            checked(member.isdir() or member.isfile(), "overlay unsafe entry")
            if member.isfile():
                checked(member.name not in found, "overlay duplicate entry")
                source = archive.extractfile(member)
                checked(source is not None, "overlay unreadable entry")
                found[member.name] = sha256(source.read()).hexdigest()
    checked(found == overlay["files_sha256"], "overlay file hashes")
    print(json.dumps({
        "product_commit": product["git_commit"],
        "product_archive_sha256": product["archive_sha256"],
        "overlay_source_commit": overlay["source_commit"],
        "overlay_tree": overlay["source_tree"],
        "overlay_archive_sha256": overlay["archive_sha256"],
        "overlay_files": len(found), "status": "verified",
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
