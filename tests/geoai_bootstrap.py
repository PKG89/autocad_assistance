"""Run only test_regressions under Python-level isolation (not an OS sandbox)."""
import argparse
import atexit
import builtins
import io
import json
import logging
import os
from pathlib import Path
import signal
import socket
import sys
import tempfile
import unittest
from unittest.mock import patch

_READY = False

def require_isolation():
    if not _READY:
        raise RuntimeError("Use geoai_bootstrap.py; direct collection is not isolated")

def main():
    global _READY
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    output = Path(args.output_dir).resolve()
    if not output.is_relative_to(Path("/home/geoai/dev-data/geoai-004")):
        raise ValueError("Output must be inside GEOAI-004 report directory")
    runtime = output / "runtime"
    runtime.mkdir()
    for name in ("home", "tmp", "logs", "data", "cache"):
        (runtime / name).mkdir()
    os.environ.clear()
    os.environ.update({
        "PATH": "/usr/bin:/bin", "LANG": "C.UTF-8",
        "HOME": str(runtime / "home"), "TMPDIR": str(runtime / "tmp"),
        "XDG_CACHE_HOME": str(runtime / "cache"),
        "DATA_DIR": str(runtime / "data"), "DB_PATH": str(runtime / "data/test.sqlite3"),
        "BOT_TOKEN": "", "ADMIN_IDS": "", "PROJ_NETWORK": "OFF",
        "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1",
        "PYTHONDONTWRITEBYTECODE": "1", "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
    })
    sys.dont_write_bytecode = True
    tempfile.tempdir = str(runtime / "tmp")
    os.chdir(runtime)
    blocked = {"network": 0, "dotenv": 0, "write": 0, "process": 0}
    def deny(category):
        blocked[category] += 1
        raise PermissionError("GEOAI-004 blocked " + category)
    def path_of(value):
        return Path(os.fsdecode(value)).resolve() if not isinstance(value, int) else None
    def check_write(value):
        path = path_of(value)
        if path is not None and not path.is_relative_to(runtime):
            deny("write")
    def audit(event, args):
        if event == "open":
            path = path_of(args[0])
            if path is not None and path.name.startswith(".env"):
                deny("dotenv")
            mode, flags = args[1], args[2]
            if (isinstance(mode, str) and any(c in mode for c in "wax+")) or flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND):
                check_write(args[0])
        elif event in ("socket.connect", "socket.bind", "socket.sendto", "socket.sendmsg", "socket.getaddrinfo", "socket.gethostbyname", "socket.gethostbyaddr"):
            deny("network")
        elif event == "socket.__new__" and args[1] in (socket.AF_INET, socket.AF_INET6):
            deny("network")
        elif event in ("subprocess.Popen", "os.system", "os.exec", "os.posix_spawn", "os.fork"):
            deny("process")
        elif event in ("os.mkdir", "os.remove", "os.rmdir", "os.rename", "os.link", "os.symlink", "os.chmod", "os.truncate"):
            check_write(args[0])
            if event in ("os.rename", "os.link", "os.symlink"):
                check_write(args[1])
        elif event == "sqlite3.connect" and str(args[0]) != ":memory:":
            check_write(args[0])
    sys.addaudithook(audit)
    # config.py must see no .env, and any attempted open is separately denied.
    original_exists = Path.exists
    patch.object(Path, "exists", lambda p: False if p.name.startswith(".env") else original_exists(p)).start()
    for module in (builtins, io):
        original_open = module.open
        def guarded_open(file, *args, _open=original_open, **kwargs):
            if not isinstance(file, int) and Path(os.fsdecode(file)) == repo / "autocad_assistance/bot_shutdown.log":
                file = runtime / "logs/bot_shutdown.log"
            return _open(file, *args, **kwargs)
        patch.object(module, "open", guarded_open).start()
    original_register, original_signal = atexit.register, signal.signal
    patch.object(atexit, "register", lambda f, *a, **k: f if getattr(f, "__module__", "") == "autocad_assistance.bot.run" else original_register(f, *a, **k)).start()
    patch.object(signal, "signal", lambda s, f: signal.getsignal(s) if getattr(f, "__module__", "") == "autocad_assistance.bot.run" else original_signal(s, f)).start()
    logging.basicConfig(filename=runtime / "logs/python.log", level=logging.INFO)
    # Guard self-checks happen before importing any application module.
    for operation in (lambda: socket.socket(socket.AF_INET, socket.SOCK_STREAM), lambda: open(repo / ".env", "rb"), lambda: open(repo / "GEOAI004_FORBIDDEN_WRITE", "w")):
        try:
            operation()
        except PermissionError:
            pass
        else:
            raise RuntimeError("Isolation guard self-check failed")
    for key in blocked:
        blocked[key] = 0
    from telegram.ext import Application, Updater
    def no_bot_lifecycle(*args, **kwargs):
        raise RuntimeError("Polling/webhook forbidden during GEOAI-004")
    for cls, names in ((Application, ("run_polling", "run_webhook")), (Updater, ("start_polling", "start_webhook"))):
        for name in names:
            patch.object(cls, name, no_bot_lifecycle).start()
    import pyproj.network
    pyproj.network.set_network_enabled(False)
    sys.path[:0] = [str(repo / "tests"), str(repo)]
    sys.modules["geoai_bootstrap"] = sys.modules[__name__]
    _READY = True
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromName("test_regressions")
    discovered = suite.countTestCases()
    class Result(unittest.TextTestResult):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self.passed = 0
        def addSuccess(self, test):
            self.passed += 1
            super().addSuccess(test)
    result = unittest.TextTestRunner(verbosity=2, resultclass=Result).run(suite)
    def ids(items):
        return sorted({getattr(t, "test_case", t).id() for t, _ in items})
    data = {"runner": "unittest", "discovered": discovered, "run": result.testsRun,
            "passed": result.passed, "failed": len(ids(result.failures)),
            "errors": len(ids(result.errors)), "skipped": len(result.skipped),
            "failure_ids": ids(result.failures), "error_ids": ids(result.errors),
            "blocked_operations_during_tests": blocked,
            "isolation": "Python guards/mocks; not an OS network sandbox"}
    data["status"] = "BLOCKED" if loader.errors or any(blocked.values()) else ("BASELINE_TESTED" if result.wasSuccessful() and discovered == 10 else "TEST_FAILURES")
    (runtime / "test-results.json").write_text(json.dumps(data, indent=2) + "\n")
    print(json.dumps(data, indent=2))
    return 0 if data["status"] == "BASELINE_TESTED" else 1

if __name__ == "__main__":
    raise SystemExit(main())
