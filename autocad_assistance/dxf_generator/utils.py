"""Utility helpers for DXF generation."""

from collections.abc import Sequence
from typing import Any


def resolve_scale(scale_def: Any, height: float) -> float:
    """Coerce a scale definition (callable/number/sequence) into a float value."""
    if callable(scale_def):
        try:
            return float(scale_def(height))
        except Exception:
            return 1.0
    if isinstance(scale_def, (int, float)):
        return float(scale_def)
    if isinstance(scale_def, Sequence) and not isinstance(scale_def, (str, bytes)):
        for value in scale_def:
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
    return 1.0
