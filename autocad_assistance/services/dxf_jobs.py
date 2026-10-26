"""Isolated DXF rendering service shared by adapters."""

from __future__ import annotations

import math
from pathlib import Path
import shutil
import tempfile
from typing import Any

import pandas as pd

from autocad_assistance.dxf_generator import generate_dxf_ezdxf


class DxfCoordinateValidationError(ValueError):
    """Raised when mapped survey coordinates are invalid for DXF rendering."""


def _to_generator_frame(final_data: Any) -> pd.DataFrame:
    """Normalize accepted adapter payloads to generator DataFrame shape."""
    if isinstance(final_data, pd.DataFrame):
        frame = final_data.copy()
    else:
        frame = pd.DataFrame(final_data)

    expected = ["Point", "X", "Y", "Z", "Code"]
    missing = [name for name in expected if name not in frame.columns]
    if missing:
        raise DxfCoordinateValidationError(f"Missing required fields: {', '.join(missing)}")

    if "Coments" not in frame.columns:
        if "Comments" in frame.columns:
            frame["Coments"] = frame["Comments"]
        else:
            frame["Coments"] = ""
    frame["Coments"] = frame["Coments"].where(frame["Coments"].notna(), "")

    return frame


def _validate_coordinates(frame: pd.DataFrame) -> None:
    if frame.empty:
        raise DxfCoordinateValidationError("Survey data is empty")

    for row_number, (_, row) in enumerate(frame.iterrows(), start=1):
        for axis in ("X", "Y", "Z"):
            value = row[axis]
            stripped = str(value).strip()
            if stripped == "":
                raise DxfCoordinateValidationError(
                    f"Row {row_number} has empty coordinate '{axis}'"
                )
            try:
                numeric = float(stripped)
            except ValueError as exc:
                raise DxfCoordinateValidationError(
                    f"Row {row_number} has non-numeric coordinate '{axis}'"
                ) from exc
            if not math.isfinite(numeric):
                raise DxfCoordinateValidationError(
                    f"Row {row_number} has non-finite coordinate '{axis}'"
                )


def render_dxf_bytes(
    final_data,
    *,
    scale_factor: float = 1.0,
    tin_settings: dict | None = None,
    jobs_root: str | Path | None = None,
    line_orders: dict[str, list[int]] | None = None,
    line_model: dict | None = None,
) -> bytes:
    """Render DXF bytes through the existing geometry engine in an isolated job."""
    frame = _to_generator_frame(final_data)
    _validate_coordinates(frame)

    job_dir = Path(
        tempfile.mkdtemp(
            prefix="dxf-job-",
            dir=str(jobs_root) if jobs_root is not None else None,
        )
    )
    output_path = job_dir / "drawing.dxf"
    try:
        generate_dxf_ezdxf(
            frame,
            str(output_path),
            scale_factor,
            tin_settings=tin_settings,
            **({"line_orders": line_orders} if line_orders else {}),
            **({"line_model": line_model} if line_model is not None else {}),
        )
        return output_path.read_bytes()
    finally:
        shutil.rmtree(job_dir, ignore_errors=True)
