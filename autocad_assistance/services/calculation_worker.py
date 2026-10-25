"""Single-purpose child entry point for bounded DXF jobs."""

from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import sys


def _set_limits(output_bytes: int) -> None:
    try:
        import resource
    except ImportError:  # Windows has no resource module.
        return
    memory_bytes = 1536 * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
    resource.setrlimit(resource.RLIMIT_FSIZE, (output_bytes, output_bytes))


def _bind_to_parent(expected_pid: int) -> None:
    """A crashed coordinator must not leave a compute process running."""
    import ctypes

    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(1, signal.SIGKILL, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "Could not bind compute child to coordinator")
    if os.getppid() != expected_pid:
        raise RuntimeError("Coordinator exited before compute child started")


def main() -> int:
    if len(sys.argv) != 4:
        return 2
    job_dir = Path(sys.argv[1])
    output_bytes = int(sys.argv[2])
    _bind_to_parent(int(sys.argv[3]))
    _set_limits(output_bytes)

    from autocad_assistance.services.dxf_jobs import render_dxf_bytes

    request = json.loads((job_dir / "request.json").read_text(encoding="utf-8"))
    rendered = render_dxf_bytes(
        request["rows"],
        scale_factor=request["scale_factor"],
        tin_settings=request["tin_settings"],
        jobs_root=job_dir,
    )
    if len(rendered) > output_bytes:
        return 3
    candidate = job_dir / "result.candidate"
    with candidate.open("xb") as output:
        output.write(rendered)
        output.flush()
        os.fsync(output.fileno())
    return 0


if __name__ == "__main__":
    sys.exit(main())
