"""Explicit synthetic end-to-end check of exact product tar plus operational overlay.

Run outside the repository with --workspace under the approved disposable
development-data directory. Keeps evidence for review; never reads real data.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import signal
import shutil
import socket
import subprocess
import sys
import tarfile
import time
from uuid import uuid4

import httpx


CURRENT = "79528bb9f6070e458724886a915f9d035cdfd110"
ROLLBACK = "1ea061c1afb4b75b0aba06ae67d402b0a3e815a6"
PASSWORD = "Only-Synthetic-Pilot-Owner-Password-123"
SOURCE = b"Point,X,Y,Z,Code\nP1,123.456,234.567,11.2,K\nP2,124,235,12,K\nP3,125,236,13,K\n"
MAPPING = {"Point": 0, "X": 1, "Y": 2, "Z": 3, "Code": 4}


def run(*args: str, env: dict[str, str] | None = None, ok: bool = True):
    result = subprocess.run(args, env=env, text=True, capture_output=True, timeout=90)
    if ok and result.returncode:
        raise AssertionError(f"{args[0]} failed: {result.stderr[-600:]}")
    return result


def require(response: httpx.Response, code: int) -> dict:
    if response.status_code != code:
        raise AssertionError(f"{response.request.method} {response.request.url}: {response.status_code} {response.text[:350]}")
    return response.json() if response.content else {}


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--rollback", type=Path, required=True)
    parser.add_argument("--overlay-root", type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    work = args.workspace.resolve()
    if work.exists():
        parser.error("workspace must be new")
    work.mkdir(mode=0o700, parents=True)
    for name in ("archives", "releases", "states", "backups", "logs", "tls"):
        (work / name).mkdir(mode=0o700)
    for sha, archive_source in ((CURRENT, args.candidate), (ROLLBACK, args.rollback)):
        archive = work / "archives" / f"{sha}.tar"
        shutil.copyfile(archive_source, archive)
        release = work / "releases" / sha
        release.mkdir(mode=0o700)
        with tarfile.open(archive, "r:") as source:
            source.extractall(release, filter="data")

    port = free_port()
    origin = f"https://127.0.0.1:{port}"
    state = work / "states" / "primary"
    base = {
        "mode": "synthetic", "installation_root": str(work),
        "release_commit": CURRENT,
        "archive_path": str(work / "archives" / f"{CURRENT}.tar"),
        "release_root": str(work / "releases" / CURRENT),
        "state_root": str(state), "auth_root": str(state / "auth"),
        "project_root": str(state / "projects"),
        "upload_root": str(state / "uploads"), "jobs_root": str(state / "jobs"),
        "backup_root": str(work / "backups"), "log_root": str(work / "logs"),
        "auth_origin": origin, "bind_host": "127.0.0.1", "bind_port": port,
    }
    config = work / "config.json"

    def write_config(sha: str, state_name: str) -> None:
        payload = dict(base)
        root = work / "states" / state_name
        payload.update({
            "release_commit": sha, "archive_path": str(work / "archives" / f"{sha}.tar"),
            "release_root": str(work / "releases" / sha),
            "state_root": str(root), "auth_root": str(root / "auth"),
            "project_root": str(root / "projects"),
            "upload_root": str(root / "uploads"), "jobs_root": str(root / "jobs"),
        })
        config.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
        config.chmod(0o600)

    env = dict(os.environ, PYTHONPATH=str(args.overlay_root),
               PYTHONDONTWRITEBYTECODE="1", OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1")

    def cli(*items: str, ok: bool = True):
        return run(sys.executable, "-m", "geoai_pilot_ops", *items,
                   "--config", str(config), env=env, ok=ok)

    write_config(CURRENT, "primary")
    cli("init-state")
    checked = json.loads(cli("check").stdout)
    assert checked["commit"] == CURRENT and checked["files"] == 144

    # A modified extracted file must prevent service startup.
    release_file = work / "releases" / CURRENT / "README.md"
    original = release_file.read_bytes()
    release_file.write_bytes(original + b"\nsynthetic tamper\n")
    assert cli("check", ok=False).returncode == 2
    release_file.write_bytes(original)
    cli("check")

    # Seed one synthetic owner directly in the exact extracted product.
    owner_code = (
        "from autocad_assistance.services.auth_store import AuthStore;"
        f"AuthStore({str(state / 'auth')!r}).create_owner('pilotowner',{PASSWORD!r})"
    )
    seed_env = dict(env, PYTHONPATH=str(work / "releases" / CURRENT))
    run(sys.executable, "-c", owner_code, env=seed_env)
    foreign_code = (
        "from autocad_assistance.services.auth_store import AuthStore;"
        f"s=AuthStore({str(work / 'foreign-auth')!r});"
        f"s.create_owner('foreign',{PASSWORD!r});"
        f"print(s.login('foreign',{PASSWORD!r}).token)"
    )
    foreign_token = run(sys.executable, "-c", foreign_code, env=seed_env).stdout.strip()
    assert foreign_token

    tls = work / "tls"
    cert, key = tls / "cert.pem", tls / "key.pem"
    run("openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
        "-keyout", str(key), "-out", str(cert), "-days", "1",
        "-subj", "/CN=127.0.0.1", "-addext", "subjectAltName=IP:127.0.0.1")
    key.chmod(0o600)
    log = (work / "logs" / "server.log").open("ab")
    process: subprocess.Popen | None = None

    def start() -> httpx.Client:
        nonlocal process
        process = subprocess.Popen(
            [sys.executable, "-m", "geoai_pilot_ops", "serve", "--config", str(config),
             "--tls-cert", str(cert), "--tls-key", str(key)],
            env=env, stdout=log, stderr=subprocess.STDOUT,
        )
        client = httpx.Client(base_url=origin, verify=str(cert), timeout=5)
        for _ in range(100):
            if process.poll() is not None:
                raise AssertionError(f"server exited {process.returncode}; see {log.name}")
            try:
                if client.get("/health").status_code == 200:
                    return client
            except (httpx.TransportError, httpx.TimeoutException):
                pass
            time.sleep(0.1)
        raise AssertionError("HTTPS server did not become healthy")

    def stop(client: httpx.Client) -> None:
        nonlocal process
        client.close()
        assert process is not None
        process.terminate()
        process.wait(timeout=25)
        # Uvicorn 0.53 re-raises the captured termination signal after its
        # graceful shutdown, so the shell observes -SIGTERM on Linux.
        assert process.returncode in (0, -signal.SIGTERM), (
            f"server exited {process.returncode}; see {log.name}"
        )
        with socket.socket() as probe:
            probe.settimeout(1)
            assert probe.connect_ex(("127.0.0.1", port)) != 0
        process = None

    def login(client: httpx.Client) -> dict[str, str]:
        body = require(client.post(
            "/api/v1/auth/login", json={"username": "pilotowner", "password": PASSWORD},
            headers={"Origin": origin},
        ), 200)
        return {"Origin": origin, "X-CSRF-Token": body["csrfToken"]}

    evidence: dict[str, object] = {"mode": "synthetic-only", "release": CURRENT,
                                  "archiveFiles": checked["files"]}
    client = start()
    try:
        require(client.get("/api/v1/projects"), 401)
        require(client.post("/api/v1/auth/login",
                            json={"username": "pilotowner", "password": PASSWORD},
                            headers={"Origin": "https://foreign.example"}), 403)
        foreign = httpx.Client(base_url=origin, verify=str(cert), timeout=5,
                               cookies={"__Host-geoai_session": foreign_token})
        require(foreign.get("/api/v1/projects"), 401)
        foreign.close()
        headers = login(client)
        project = require(client.post("/api/v1/projects",
                                      json={"name": "Synthetic pilot"}, headers=headers), 201)
        project_id = project["projectId"]
        upload = require(client.post("/api/v1/uploads", headers=headers,
                                     files={"file": ("survey.csv", SOURCE, "text/csv")}), 201)
        upload_id = upload["uploadId"]
        require(client.get(f"/api/v1/uploads/{upload_id}/preview"), 200)
        revision = require(client.post(
            f"/api/v1/projects/{project_id}/revisions",
            json={"uploadId": upload_id, "mapping": MAPPING,
                  "coordinateSystem": "local survey grid",
                  "horizontalUnit": "m", "verticalUnit": "m", "scaleFactor": "500"},
            headers=headers,
        ), 201)
        revision_id = revision["revision"]["revisionId"]
        jobs = []
        for _ in range(3):
            body = require(client.post(
                "/api/v1/jobs", json={"revisionId": revision_id, "tinSettings": {}},
                headers={**headers, "Idempotency-Key": str(uuid4())},
            ), 201)
            jobs.append(body["jobId"])
        assert len(set(jobs)) == 3
        observed = set()
        result_hash = None
        for _ in range(240):
            states = [require(client.get(f"/api/v1/jobs/{job}"), 200)["status"] for job in jobs]
            observed.update(states)
            assert states.count("running") <= 1
            if all(status in {"succeeded", "failed", "cancelled"} for status in states):
                assert states == ["succeeded"] * 3, states
                break
            time.sleep(0.05)
        else:
            raise AssertionError("jobs did not finish in 12 seconds")
        result = client.get(f"/api/v1/jobs/{jobs[0]}/result")
        assert result.status_code == 200 and len(result.content) > 100
        result_hash = sha256(result.content).hexdigest()
        evidence.update({"jobs": len(jobs), "jobStatesObserved": sorted(observed),
                         "resultSha256": result_hash, "resultBytes": len(result.content),
                         "https": True, "unauthorizedStatus": 401,
                         "foreignOriginStatus": 403, "foreignSessionStatus": 401})
        assert cli("backup", "--name", "while-active", ok=False).returncode == 2
        assert not (work / "backups" / "while-active").exists()
    finally:
        stop(client)

    # A normal restart must preserve SQLite identity and result bytes.
    client = start()
    try:
        login(client)
        assert require(client.get("/api/v1/projects"), 200)["pagination"]["totalItems"] == 1
        result = client.get(f"/api/v1/jobs/{jobs[0]}/result")
        assert result.status_code == 200 and sha256(result.content).hexdigest() == result_hash
        evidence["restartPreservedResult"] = True
    finally:
        stop(client)

    backup = json.loads(cli("backup", "--name", "good-backup").stdout)
    assert backup["sqlite"] == {"auth/auth.sqlite3": 1, "projects/projects.sqlite3": 8}
    client = start()
    try:
        assert cli("restore", "--backup-name", "good-backup",
                   "--new-state-name", "while-active", ok=False).returncode == 2
        assert not (work / "states" / "while-active").exists()
    finally:
        stop(client)
    bad = work / "backups" / "tampered"
    shutil.copytree(work / "backups" / "good-backup", bad)
    with (bad / "state" / ".geoai-pilot-state").open("ab") as target:
        target.write(b"tampered")
    assert cli("restore", "--backup-name", "tampered",
               "--new-state-name", "rejected", ok=False).returncode == 2
    assert not (work / "states" / "rejected").exists()
    assert cli("restore", "--backup-name", "good-backup",
               "--new-state-name", "restored").returncode == 0
    evidence["backupFiles"] = backup["files"]
    evidence["tamperedBackupRejected"] = True
    evidence["activeRestoreRejected"] = True

    # The same overlay must also start the approved P6 code rollback with
    # restored v8 state and keep the source/result bytes accessible.
    write_config(ROLLBACK, "restored")
    rollback_check = json.loads(cli("check").stdout)
    assert rollback_check["commit"] == ROLLBACK
    client = start()
    try:
        require(client.get("/health"), 200)
        login(client)
        result = client.get(f"/api/v1/jobs/{jobs[0]}/result")
        assert result.status_code == 200 and sha256(result.content).hexdigest() == result_hash
        evidence["rollbackCodeCompatible"] = True
    finally:
        stop(client)
        log.close()

    (work / "evidence.json").write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8",
    )
    print(json.dumps({"workspace": str(work), **evidence}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
