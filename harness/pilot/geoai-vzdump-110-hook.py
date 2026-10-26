#!/usr/bin/env python3
"""Pair VM110 vzdump archives with a fresh, verified application dump.

Install as a *per-job* vzdump hook on the two VM110-only backup jobs. A bad or
missing dump leaves the VM archive intact and explicitly labels it VM-only.
"""

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from datetime import datetime, timezone


VMID = "110"
STORE_IDS = {"backup-fast-nfs", "backup-weekly-nfs"}
RUN_DIR = Path("/run/geoai-vzdump-110")
CHECK = ["/usr/sbin/qm", "guest", "exec", VMID, "--", "/usr/bin/python3",
         "/usr/local/sbin/geoai-pilot-backup-check", "check",
         "--root", "/srv/geoai-pilot/backups",
         "--status", "/var/lib/geoai-pilot-backup/latest.json",
         "--max-age-seconds", "2700"]
ARCHIVE = re.compile(r"vzdump-qemu-110-\d{4}_\d{2}_\d{2}-\d{2}_\d{2}_\d{2}\.vma\.zst\Z")


def now():
    return datetime.now(timezone.utc).isoformat()


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_json(path, value):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temp = path.with_name(path.name + f".{os.getpid()}.tmp")
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, sort_keys=True, separators=(",", ":"))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def guest_check():
    try:
        run = subprocess.run(CHECK, capture_output=True, text=True, timeout=180)
        if run.returncode:
            raise ValueError(f"guest-check transport exit {run.returncode}: {run.stderr.strip()[:240]}")
        wrapper = json.loads(run.stdout)
        if wrapper.get("exited") != 1 or wrapper.get("exitcode") != 0 or wrapper.get("out-truncated"):
            raise ValueError("guest checker failed or output truncated")
        result = json.loads(wrapper.get("out-data", ""))
        if result.get("ok") is not True:
            raise ValueError(result.get("error", "guest checker rejected dump"))
        needed = ("attemptId", "backupName", "manifestSha256", "completedAt", "ageSeconds")
        if any(not result.get(key) and result.get(key) != 0 for key in needed):
            raise ValueError("guest checker omitted dump identity")
        return {key: result[key] for key in needed} | {"ok": True}
    except (OSError, ValueError, json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "error": str(exc)[:300]}


def start_record(store, checked):
    return {"format": 1, "vmid": 110, "storageId": store,
            "checkedAt": now(), "appDump": checked}


def pair_record(store, target, started, checked, expected_dir):
    target = Path(target)
    if not ARCHIVE.fullmatch(target.name):
        raise ValueError("unexpected VM110 archive name")
    if target.is_symlink() or not target.is_file() or target.parent.resolve() != expected_dir.resolve():
        raise ValueError("VM110 archive is absent or outside the selected storage")
    tested = subprocess.run(["/usr/bin/zstd", "-tq", str(target)], capture_output=True,
                            text=True, timeout=300)
    if tested.returncode:
        raise ValueError(f"VM110 archive failed zstd integrity test: {tested.stderr.strip()[:240]}")
    stat = target.stat()
    record = {"format": 1, "vmid": 110, "storageId": store,
              "vmBackupId": target.name, "vmBackupCompletedAt": now(),
              "vmBackupBytes": stat.st_size, "vmBackupSha256": sha256(target),
              "vmBackupIntegrity": "zstd-ok",
              "appDumpStatus": "vm-only"}
    if not started or started.get("storageId") != store:
        record["appDumpReason"] = "backup-start status missing"
    elif not started.get("appDump", {}).get("ok"):
        record["appDumpReason"] = started.get("appDump", {}).get("error", "preparation failed")
    elif not checked.get("ok"):
        record["appDumpReason"] = checked.get("error", "post-backup dump check failed")
    else:
        before = started["appDump"]
        identity = ("attemptId", "backupName", "manifestSha256", "completedAt")
        if any(before[key] != checked[key] for key in identity):
            record["appDumpReason"] = "application dump changed during VM backup"
        else:
            record["appDumpStatus"] = "paired"
            record["appDump"] = {key: before[key] for key in identity}
            record["appDump"]["ageAtBackupStartSeconds"] = before["ageSeconds"]
            record["appDump"]["ageAtBackupEndSeconds"] = checked["ageSeconds"]
    return record


def main(argv):
    phase = argv[1] if len(argv) > 1 else ""
    if phase not in ("backup-start", "backup-end", "backup-abort"):
        return 0
    if len(argv) < 4 or argv[3] != VMID:
        return 0
    store = os.environ.get("STOREID", "")
    if store not in STORE_IDS:
        print(f"GEOAI pairing: unexpected storage {store!r}", file=sys.stderr)
        return 1
    state_path = RUN_DIR / f"{store}.json"
    if phase == "backup-start":
        checked = guest_check()
        atomic_json(state_path, start_record(store, checked))
        if not checked["ok"]:
            print(f"GEOAI VM-only: application dump unavailable: {checked['error']}", file=sys.stderr)
        else:
            print(f"GEOAI dump verified: {checked['backupName']} age={checked['ageSeconds']}s")
        return 0
    if phase == "backup-abort":
        state_path.unlink(missing_ok=True)
        print("GEOAI: VM110 backup aborted; no paired application copy", file=sys.stderr)
        return 0
    target = os.environ.get("TARGET", "")
    try:
        started = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        started = None
    checked = guest_check() if started and started.get("appDump", {}).get("ok") else {"ok": False}
    expected_dir = Path("/mnt/pve") / store / "dump"
    try:
        record = pair_record(store, target, started, checked, expected_dir)
        sidecar = Path(target).with_name(Path(target).name + ".geoai.json")
        atomic_json(sidecar, record)
    finally:
        state_path.unlink(missing_ok=True)
    if record["appDumpStatus"] == "paired":
        print(f"GEOAI paired copy: {record['vmBackupId']} sha256={record['vmBackupSha256']}")
    else:
        print(f"GEOAI VM-only copy: {record['vmBackupId']}: {record['appDumpReason']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except (OSError, ValueError) as exc:
        print(f"GEOAI pairing hook failed: {exc}", file=sys.stderr)
        sys.exit(1)
