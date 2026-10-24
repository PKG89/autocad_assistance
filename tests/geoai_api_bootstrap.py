"""Run the focused API test under Python-level isolation."""

import argparse
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import unittest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    repo = Path(__file__).resolve().parents[1]
    report_roots = (
        Path("/home/geoai/dev-data/geoai-006").resolve(),
        Path("/home/geoai/dev-data/geoai-007").resolve(),
    )
    output = Path(args.output_dir).resolve()
    if not any(output.is_relative_to(root) for root in report_roots):
        raise ValueError("Output must be inside an approved GEOAI API report directory")

    runtime = output / "api-runtime"
    runtime.mkdir()
    for name in ("home", "tmp", "logs", "data", "cache"):
        (runtime / name).mkdir()

    os.environ.clear()
    os.environ.update(
        {
            "PATH": "/usr/bin:/bin",
            "LANG": "C.UTF-8",
            "HOME": str(runtime / "home"),
            "TMPDIR": str(runtime / "tmp"),
            "XDG_CACHE_HOME": str(runtime / "cache"),
            "DATA_DIR": str(runtime / "data"),
            "DB_PATH": str(runtime / "data/test.sqlite3"),
            "UPLOAD_ROOT": str(runtime / "uploads"),
            "BOT_TOKEN": "",
            "ADMIN_IDS": "",
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
    )
    sys.dont_write_bytecode = True
    tempfile.tempdir = str(runtime / "tmp")
    os.chdir(runtime)

    blocked = {"network": 0, "dotenv": 0, "write": 0, "process": 0}

    def deny(category: str) -> None:
        blocked[category] += 1
        raise PermissionError("GEOAI API bootstrap blocked " + category)

    def resolved_path(value):
        if isinstance(value, int):
            return None
        return Path(os.fsdecode(value)).resolve()

    def check_write(value) -> None:
        path = resolved_path(value)
        if path is not None and not path.is_relative_to(runtime):
            deny("write")

    def audit(event, event_args) -> None:
        if event == "open":
            path = resolved_path(event_args[0])
            if path is not None and path.name.startswith(".env"):
                deny("dotenv")
            mode, flags = event_args[1], event_args[2]
            wants_write = (
                isinstance(mode, str) and any(char in mode for char in "wax+")
            ) or flags & (
                os.O_WRONLY
                | os.O_RDWR
                | os.O_CREAT
                | os.O_TRUNC
                | os.O_APPEND
            )
            if wants_write:
                check_write(event_args[0])
        elif event in (
            "socket.connect",
            "socket.bind",
            "socket.sendto",
            "socket.sendmsg",
            "socket.getaddrinfo",
            "socket.gethostbyname",
            "socket.gethostbyaddr",
        ):
            deny("network")
        elif event == "socket.__new__" and event_args[1] in (
            socket.AF_INET,
            socket.AF_INET6,
        ):
            deny("network")
        elif event in (
            "subprocess.Popen",
            "os.system",
            "os.exec",
            "os.posix_spawn",
            "os.fork",
        ):
            deny("process")
        elif event in (
            "os.mkdir",
            "os.remove",
            "os.rmdir",
            "os.rename",
            "os.link",
            "os.symlink",
            "os.chmod",
            "os.truncate",
        ):
            check_write(event_args[0])

    sys.addaudithook(audit)
    sys.path[:0] = [str(repo / "tests"), str(repo)]

    loader = unittest.TestLoader()
    suite = loader.loadTestsFromName("test_api")
    discovered = suite.countTestCases()

    class Result(unittest.TextTestResult):
        def __init__(self, *result_args, **result_kwargs):
            super().__init__(*result_args, **result_kwargs)
            self.passed = 0

        def addSuccess(self, test):
            self.passed += 1
            super().addSuccess(test)

    result = unittest.TextTestRunner(verbosity=2, resultclass=Result).run(suite)
    data = {
        "runner": "unittest",
        "discovered": discovered,
        "run": result.testsRun,
        "passed": result.passed,
        "failed": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
        "blocked_operations_during_tests": blocked,
        "isolation": "Python audit guards; not an OS network sandbox",
    }
    data["status"] = (
        "API_TESTED"
        if result.wasSuccessful()
        and discovered == 6
        and not loader.errors
        and not any(blocked.values())
        else "TEST_FAILURES"
    )
    (runtime / "test-results.json").write_text(
        json.dumps(data, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(data, indent=2))
    return 0 if data["status"] == "API_TESTED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
