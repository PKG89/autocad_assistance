"""Utilities for building terrain surfaces (TIN) in DXF output."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable, List, Sequence, Tuple

import numpy as np
from scipy.spatial import Delaunay, QhullError

logger = logging.getLogger(__name__)

GREEN_COLOR = 3
RED_COLOR = 1

TIN_POINT_LAYER = "1 Отметки и точки реального рельефа"
TIN_TRIANGLE_LAYER = "1 реальная поверхность"
REFINED_TRIANGLE_LAYER = "2 отредактированная поверхность"
REFINED_POINT_LAYER = "2 пикеты добавленные"

REFINE_DISTANCE_BY_SCALE = {
    500: 15.0,
    1000: 20.0,
    2000: 35.0,
    5000: 60.0,
}


@dataclass
class TinBuildResult:
    base_points: int = 0
    base_triangles: int = 0
    refined_points: int = 0
    refined_triangles: int = 0


def _normalize_codes(codes: Iterable[str]) -> set[str]:
    return {code.strip().lower() for code in codes if code and str(code).strip()}


def _determine_refine_threshold(scale_value: int) -> float:
    if not REFINE_DISTANCE_BY_SCALE:
        return 0.0
    if scale_value in REFINE_DISTANCE_BY_SCALE:
        return REFINE_DISTANCE_BY_SCALE[scale_value]
    # fallback: choose closest scale by absolute difference
    closest_scale = min(REFINE_DISTANCE_BY_SCALE.keys(), key=lambda s: abs(s - scale_value))
    return REFINE_DISTANCE_BY_SCALE[closest_scale]


def _extract_points_for_codes(final_data, selected_codes: set[str]) -> List[Tuple[float, float, float, str]]:
    points: List[Tuple[float, float, float, str]] = []
    for _, row in final_data.iterrows():
        code = str(row["Code"]).strip()
        if code.lower() not in selected_codes:
            continue
        try:
            x = float(row["X"])
            y = float(row["Y"])
            z = float(row["Z"])
        except (TypeError, ValueError):
            continue
        points.append((x, y, z, code))
    return points


def _add_points_to_layer(msp, points: Sequence[Tuple[float, float, float]], layer: str, color: int) -> None:
    for x, y, z in points:
        try:
            msp.add_point((x, y, z), dxfattribs={"layer": layer, "color": color})
        except Exception as exc:
            logger.debug("Failed to add point (%s, %s, %s) to layer %s: %s", x, y, z, layer, exc)


def _add_triangles(msp, triangles: Sequence[Tuple[Tuple[float, float, float], ...]], layer: str, color: int) -> None:
    for v1, v2, v3 in triangles:
        try:
            msp.add_3dface([v1, v2, v3, v3], dxfattribs={"layer": layer, "color": color})
        except Exception as exc:
            logger.debug("Failed to add triangle on layer %s: %s", layer, exc)


def _triangulate(points: Sequence[Tuple[float, float, float]]) -> List[Tuple[Tuple[float, float, float], Tuple[float, float, float], Tuple[float, float, float]]]:
    if len(points) < 3:
        return []
    coords = np.array([(p[0], p[1]) for p in points], dtype=float)
    try:
        delaunay = Delaunay(coords)
    except QhullError as exc:
        logger.warning("Не удалось построить триангуляцию TIN: %s", exc)
        return []
    simplices = delaunay.simplices
    triangles: List[Tuple[Tuple[float, float, float], Tuple[float, float, float], Tuple[float, float, float]]] = []
    for simplex in simplices:
        v1 = points[int(simplex[0])]
        v2 = points[int(simplex[1])]
        v3 = points[int(simplex[2])]
        triangles.append((v1, v2, v3))
    return triangles


def _find_large_triangles(
    triangles: Sequence[Tuple[Tuple[float, float, float], Tuple[float, float, float], Tuple[float, float, float]]],
    threshold: float,
) -> List[Tuple[float, float, float]]:
    if threshold <= 0:
        return []
    new_points: List[Tuple[float, float, float]] = []
    seen: set[Tuple[int, int, int]] = set()
    for v1, v2, v3 in triangles:
        edges = (
            np.hypot(v1[0] - v2[0], v1[1] - v2[1]),
            np.hypot(v2[0] - v3[0], v2[1] - v3[1]),
            np.hypot(v3[0] - v1[0], v3[1] - v1[1]),
        )
        if all(edge <= threshold for edge in edges):
            continue
        cx = (v1[0] + v2[0] + v3[0]) / 3.0
        cy = (v1[1] + v2[1] + v3[1]) / 3.0
        cz = (v1[2] + v2[2] + v3[2]) / 3.0
        key = (round(cx * 1000), round(cy * 1000), round(cz * 1000))
        if key in seen:
            continue
        seen.add(key)
        new_points.append((cx, cy, cz))
    return new_points


def build_tin_surface(
    final_data,
    msp,
    selected_codes: Iterable[str],
    scale_value: int,
    refine_enabled: bool = False,
    breaklines: Sequence[Sequence[Tuple[float, float, float]]] | None = None,
) -> TinBuildResult:
    """Build terrain surface from selected codes and optional refinement."""
    result = TinBuildResult()
    code_set = _normalize_codes(selected_codes)
    if not code_set:
        logger.info("TIN: codes not selected, skipping surface generation.")
        return result

    points = _extract_points_for_codes(final_data, code_set)
    if len(points) < 3:
        logger.info("TIN: недостаточно точек для построения поверхности (нужно минимум 3).")
        return result

    result.base_points = len(points)
    _add_points_to_layer(msp, [(x, y, z) for x, y, z, _ in points], TIN_POINT_LAYER, GREEN_COLOR)

    # Draw structural breaklines as 3D polylines
    if breaklines:
        for line in breaklines:
            if len(line) < 2:
                continue
            try:
                msp.add_polyline3d(line, dxfattribs={"layer": TIN_TRIANGLE_LAYER, "color": GREEN_COLOR})
            except Exception as exc:
                logger.debug("Failed to add structural polyline: %s", exc)

    base_triangles = _triangulate(points)
    if base_triangles:
        result.base_triangles = len(base_triangles)
        _add_triangles(msp, base_triangles, TIN_TRIANGLE_LAYER, GREEN_COLOR)
    else:
        logger.info("TIN: триангуляция не дала результата.")

    if not refine_enabled or not base_triangles:
        return result

    threshold = _determine_refine_threshold(scale_value)
    if threshold <= 0:
        return result

    refinement_points = _find_large_triangles(base_triangles, threshold)
    if not refinement_points:
        return result

    result.refined_points = len(refinement_points)
    _add_points_to_layer(msp, refinement_points, REFINED_POINT_LAYER, RED_COLOR)

    combined_points = list(points) + [(x, y, z, "refined") for x, y, z in refinement_points]
    refined_triangles = _triangulate([(x, y, z) for x, y, z, _ in combined_points])
    if refined_triangles:
        result.refined_triangles = len(refined_triangles)
        _add_triangles(msp, refined_triangles, REFINED_TRIANGLE_LAYER, RED_COLOR)

    return result
