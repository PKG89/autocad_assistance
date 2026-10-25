"""Polyline helpers for DXF generation."""

import logging
import math
import re
from typing import Dict, List, Sequence, Tuple

from ..config import polyline_layer_mapping, sm_controller_config

logger = logging.getLogger(__name__)


def polyline_group_key(code: object) -> str | None:
    """Use exactly the controller-code grouping accepted by the DXF builder."""
    code_raw = str(code).strip().lower()
    match = re.fullmatch(r"(?P<prefix>[a-zA-Z]+)\d+", code_raw)
    allowed_prefixes = {prefix.lower() for prefix in sm_controller_config.get("polyline_prefixes", set())}
    return code_raw if match and match.group("prefix") in allowed_prefixes else None


def get_polyline_properties(doc, polyline_code: str) -> Dict[str, object]:
    """Return DXF layer attributes for a polyline code."""
    layer_table = doc.layers if doc else None
    layer_name = polyline_layer_mapping.get(polyline_code, "Polylines")

    if layer_table and layer_name in layer_table:
        layer = layer_table.get(layer_name)
        return {
            "layer": layer_name,
            "color": layer.color,
            "linetype": layer.linetype,
        }
    return {
        "layer": "Polylines",
        "color": 7,
        "linetype": "CONTINUOUS",
    }


def _collect_polyline_groups(final_data) -> Dict[str, List[Tuple[int, Tuple[float, float, float, str]]]]:
    groups: Dict[str, List[Tuple[int, Tuple[float, float, float, str]]]] = {}

    for index, row in final_data.iterrows():
        code_raw = polyline_group_key(row["Code"])
        if code_raw is None:
            continue

        try:
            x = float(row["X"])
            y = float(row["Y"])
            z = float(row["Z"])
            comment = str(row.get("Coments", "")).strip()
        except (TypeError, ValueError):
            continue

        groups.setdefault(code_raw, []).append((index, (x, y, z, comment)))
    return groups


def order_polyline_pairs(points: Sequence[tuple[int, tuple]]) -> list[tuple[int, tuple]]:
    """Legacy anchored nearest-neighbor order, retaining source row keys."""
    if not points:
        return []
    ordered_pairs = sorted(points, key=lambda item: item[0])
    if len(ordered_pairs) < 2:
        return ordered_pairs

    remaining = list(ordered_pairs[1:])
    ordered: list[tuple[int, tuple]] = [ordered_pairs[0]]
    current_point = ordered_pairs[0][1][:3]

    while remaining:
        next_item = min(
            remaining,
            key=lambda item: math.hypot(item[1][0] - current_point[0], item[1][1] - current_point[1]),
        )
        ordered.append(next_item)
        current_point = next_item[1][:3]
        remaining.remove(next_item)

    return ordered


def _order_polyline_points(
    points: Sequence[Tuple[int, Tuple[float, float, float, str]]],
    source_order: Sequence[int] | None = None,
) -> List[Tuple[float, float, float, str]]:
    if source_order is None:
        return [item[1] for item in order_polyline_pairs(points)]
    # Mapped job rows use a zero-based DataFrame index; immutable candidate
    # row indexes are one-based. Reject stale or malformed overrides.
    expected = {index + 1 for index, _ in points}
    if (len(source_order) != len(points) or any(type(index) is not int for index in source_order)
            or set(source_order) != expected):
        raise ValueError("Accepted line order does not match source rows")
    by_row = {index + 1: point for index, point in points}
    return [by_row[index] for index in source_order]


def extract_structural_breaklines(final_data, line_orders: dict[str, list[int]] | None = None) -> List[List[Tuple[float, float, float]]]:
    """Return ordered sequences of 3D points usable as structural breaklines."""
    breaklines: List[List[Tuple[float, float, float]]] = []
    groups = _collect_polyline_groups(final_data)
    if line_orders and not set(line_orders).issubset(groups):
        raise ValueError("Accepted line group is absent from source")
    for code, points in groups.items():
        ordered = _order_polyline_points(points, (line_orders or {}).get(code))
        if len(ordered) < 2:
            continue
        breaklines.append([(x, y, z) for x, y, z, _ in ordered])
    return breaklines


def build_polyline_by_code(final_data, msp, doc=None, scale_factor: float = 1.0, text_scale: float = 1.6,
                           line_orders: dict[str, list[int]] | None = None) -> List[List[Tuple[float, float, float]]]:
    """Create LWPOLYLINE entities grouped by controller code and return ordered 3D breaklines."""
    line_text_height = 1.6 * scale_factor
    breaklines: List[List[Tuple[float, float, float]]] = []

    groups = _collect_polyline_groups(final_data)
    if line_orders and not set(line_orders).issubset(groups):
        raise ValueError("Accepted line group is absent from source")
    for group_key, points in groups.items():
        if len(points) < 2:
            continue

        ordered_points = _order_polyline_points(points, (line_orders or {}).get(group_key))
        if len(ordered_points) < 2:
            continue
        breaklines.append([(x, y, z) for x, y, z, _ in ordered_points])

        base_code = re.sub(r"\d+$", "", group_key).lower()
        layer_name = polyline_layer_mapping.get(base_code, "Polylines")
        polyline_attribs = {"layer": layer_name, "color": 7, "linetype": "CONTINUOUS"}

        if doc and layer_name in doc.layers:
            layer_def = doc.layers.get(layer_name)
            polyline_attribs["color"] = layer_def.dxf.color
            polyline_attribs["linetype"] = layer_def.dxf.linetype

        msp.add_lwpolyline([(x, y) for x, y, _, _ in ordered_points], dxfattribs=polyline_attribs)

        for idx in range(len(ordered_points) - 1):
            x1, y1 = ordered_points[idx][:2]
            x2, y2 = ordered_points[idx + 1][:2]
            dx = x2 - x1
            dy = y2 - y1
            length = math.hypot(dx, dy)
            if length == 0:
                continue

            nx = -dy / length
            ny = dx / length
            shift = 1.0 * scale_factor
            mid_x = (x1 + x2) / 2 + nx * shift
            mid_y = (y1 + y2) / 2 + ny * shift
            angle = math.degrees(math.atan2(dy, dx))

            comment = ordered_points[idx][3].strip() if len(ordered_points[idx]) >= 4 else ""
            if not comment:
                continue

            msp.add_mtext(
                comment,
                dxfattribs={
                    "layer": layer_name,
                    "char_height": line_text_height,
                    "style": "Simplex",
                    "color": polyline_attribs["color"],
                    "rotation": angle,
                },
            ).set_location((mid_x, mid_y))
    return breaklines

