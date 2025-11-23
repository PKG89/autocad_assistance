"""Geometric helpers used in the KML workflow."""

from __future__ import annotations

from typing import List, Tuple

from pyproj import Transformer


def _evaluate_coordinate_order(xs: List[float], ys: List[float], transformer: Transformer) -> float:
    if not xs or not ys:
        return 0.0
    try:
        lon, lat = transformer.transform(xs, ys)
    except Exception:
        return 0.0
    valid = [(-90 <= la <= 90 and -180 <= lo <= 180) for lo, la in zip(lon, lat)]
    if not valid:
        return 0.0
    return sum(valid) / len(valid)


def infer_coordinate_order(
    x_values: List[float],
    y_values: List[float],
    transformer: Transformer,
) -> Tuple[bool, bool]:
    sample_size = min(len(x_values), 20)
    sample_x = x_values[:sample_size]
    sample_y = y_values[:sample_size]
    score_xy = _evaluate_coordinate_order(sample_x, sample_y, transformer)
    score_yx = _evaluate_coordinate_order(sample_y, sample_x, transformer)
    swap = score_yx > score_xy
    best_score = max(score_xy, score_yx)
    warning = best_score < 0.6
    return swap, warning
