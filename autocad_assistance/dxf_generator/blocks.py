"""Block placement helpers for DXF generation."""

import logging
import math
import re
from collections import defaultdict
from typing import Dict, List, Optional

from ..config import sm_controller_config

logger = logging.getLogger(__name__)


def get_block_properties(doc, block_name: str) -> Dict[str, object]:
    """Extract color/layer defaults from a DXF block definition."""
    if doc and block_name in doc.blocks:
        block = doc.blocks[block_name]
        for entity in block:
            try:
                return {"layer": entity.dxf.layer, "color": entity.dxf.color}
            except Exception:
                continue
    return {"layer": "Blocks", "color": 7}


def _cluster_points_by_distance(points: List[Dict[str, float]], threshold: float) -> List[List[int]]:
    if not points:
        return []

    adjacency: List[set[int]] = [set() for _ in range(len(points))]
    for idx, current in enumerate(points):
        x1, y1 = current["x"], current["y"]
        for other_idx in range(idx + 1, len(points)):
            other = points[other_idx]
            if math.hypot(other["x"] - x1, other["y"] - y1) <= threshold:
                adjacency[idx].add(other_idx)
                adjacency[other_idx].add(idx)

    clusters: List[List[int]] = []
    visited: set[int] = set()
    for idx in range(len(points)):
        if idx in visited:
            continue
        stack = [idx]
        component: List[int] = []
        while stack:
            node = stack.pop()
            if node in visited:
                continue
            visited.add(node)
            component.append(node)
            for neighbour in adjacency[node]:
                if neighbour not in visited:
                    stack.append(neighbour)
        clusters.append(component)
    return clusters


def _iter_entity_xy(entity):
    etype = entity.dxftype()
    if etype == "LWPOLYLINE":
        for x, y, *_ in entity.get_points("xy"):
            yield float(x), float(y)
    elif etype == "POLYLINE":
        for vertex in entity.vertices():
            loc = vertex.dxf.location
            yield float(loc.x), float(loc.y)
    elif etype == "LINE":
        start = entity.dxf.start
        end = entity.dxf.end
        yield float(start.x), float(start.y)
        yield float(end.x), float(end.y)
    elif etype == "POINT":
        pt = entity.dxf.location
        yield float(pt.x), float(pt.y)
    elif etype == "ARC":
        center = entity.dxf.center
        radius = entity.dxf.radius
        yield float(center.x + radius), float(center.y)
        yield float(center.x - radius), float(center.y)
        yield float(center.x), float(center.y + radius)
        yield float(center.x), float(center.y - radius)
    elif etype == "CIRCLE":
        center = entity.dxf.center
        radius = entity.dxf.radius
        yield float(center.x + radius), float(center.y)
        yield float(center.x - radius), float(center.y)
        yield float(center.x), float(center.y + radius)
        yield float(center.x), float(center.y - radius)
    elif etype == "INSERT":
        for virtual in entity.virtual_entities():
            yield from _iter_entity_xy(virtual)


def _infer_fourth_point_from_three(points: List[Dict[str, float]], tolerance: float) -> Optional[Dict[str, float]]:
    if len(points) != 3:
        return None

    for idx, corner in enumerate(points):
        others = [points[j] for j in range(3) if j != idx]
        d1_sq = (corner["x"] - others[0]["x"]) ** 2 + (corner["y"] - others[0]["y"]) ** 2
        d2_sq = (corner["x"] - others[1]["x"]) ** 2 + (corner["y"] - others[1]["y"]) ** 2
        diag_sq = (others[0]["x"] - others[1]["x"]) ** 2 + (others[0]["y"] - others[1]["y"]) ** 2
        if diag_sq == 0:
            continue
        if abs((d1_sq + d2_sq) - diag_sq) <= tolerance * diag_sq:
            return {
                "x": others[0]["x"] + others[1]["x"] - corner["x"],
                "y": others[0]["y"] + others[1]["y"] - corner["y"],
                "z": sum(p["z"] for p in points) / 3.0,
                "code": corner.get("code", ""),
                "point": corner.get("point", ""),
                "comment": corner.get("comment", ""),
            }
    return None


def build_tower_blocks(final_data, msp, doc=None) -> None:
    tower_conf = sm_controller_config.get("tower_config")
    if not tower_conf:
        return

    block_name = tower_conf.get("block_name")
    if not block_name:
        logger.warning("tower_config is missing block_name; skip tower placement")
        return

    if doc and block_name not in doc.blocks:
        logger.warning("Block %s is not present in DXF template", block_name)
        return

    valid_codes = {c.lower() for c in tower_conf.get("codes", set()) if c}
    prefixes = {p.lower() for p in tower_conf.get("prefixes", set()) if p}
    prefix_pattern = None
    if prefixes:
        joined = "|".join(re.escape(p) for p in prefixes)
        prefix_pattern = re.compile(rf"^({joined})(?P<rest>.*)$")

    group_size = max(2, int(tower_conf.get("group_size", 4)))
    min_points = min(group_size, int(tower_conf.get("min_points", group_size)))
    right_angle_tol = float(tower_conf.get("right_angle_tolerance", 0.0))
    max_span = float(tower_conf.get("max_span", 30.0))
    base_width = float(tower_conf.get("base_width", 1.0)) or 1.0
    base_height = float(tower_conf.get("base_height", 1.0)) or 1.0
    zscale = float(tower_conf.get("zscale", 1.0))
    min_scale = float(tower_conf.get("min_scale", 0.01))

    candidates_by_key: Dict[str, List[Dict[str, float]]] = defaultdict(list)
    for _, row in final_data.iterrows():
        code_raw = str(row.get("Code", "")).strip()
        code_lower = code_raw.lower()

        key = None
        if code_lower and code_lower in valid_codes:
            key = code_lower
        elif prefix_pattern:
            match = prefix_pattern.match(code_lower)
            if match:
                key = match.group(1)
        if key is None:
            continue

        try:
            x = float(row["X"])
            y = float(row["Y"])
            z = float(row["Z"])
        except (TypeError, ValueError):
            continue

        candidates_by_key[key].append(
            {
                "x": x,
                "y": y,
                "z": z,
                "point": str(row.get("Point", "")),
                "code": code_raw,
                "comment": str(row.get("Coments", "")),
            }
        )

    if not candidates_by_key:
        return

    block_width = base_width
    block_height = base_height
    if doc and block_name in doc.blocks:
        block = doc.blocks[block_name]
        min_x = min_y = float("inf")
        max_x = max_y = float("-inf")
        for entity in block:
            for x, y in _iter_entity_xy(entity):
                min_x = min(min_x, x)
                max_x = max(max_x, x)
                min_y = min(min_y, y)
                max_y = max(max_y, y)
        if min_x < max_x:
            block_width = max_x - min_x
        if min_y < max_y:
            block_height = max_y - min_y

    for key, points in candidates_by_key.items():
        clusters = _cluster_points_by_distance(points, max_span)
        for component in clusters:
            if len(component) < min_points or len(component) > group_size:
                logger.warning(
                    "Tower group %s has %d points (expected %d-%d)",
                    key,
                    len(component),
                    min_points,
                    group_size,
                )
                continue

            cluster_points = [points[i] for i in component]
            if len(cluster_points) == 3 and min_points <= 3 and group_size >= 4:
                inferred = _infer_fourth_point_from_three(cluster_points, right_angle_tol)
                if inferred:
                    cluster_points.append(inferred)
                else:
                    logger.warning("Cannot infer fourth tower point for %s", key)
                    continue

            if len(cluster_points) != group_size:
                logger.warning(
                    "Tower group %s resolved to %d points; skip placement",
                    key,
                    len(cluster_points),
                )
                continue

            cx = sum(p["x"] for p in cluster_points) / group_size
            cy = sum(p["y"] for p in cluster_points) / group_size
            cz = sum(p["z"] for p in cluster_points) / group_size

            ordered = sorted(
                cluster_points,
                key=lambda p: math.atan2(p["y"] - cy, p["x"] - cx),
            )

            edges = []
            for index in range(group_size):
                current = ordered[index]
                nxt = ordered[(index + 1) % group_size]
                dx = nxt["x"] - current["x"]
                dy = nxt["y"] - current["y"]
                length = math.hypot(dx, dy)
                edges.append({"length": length, "dx": dx, "dy": dy, "index": index})

            major_edge = max(edges, key=lambda e: e["length"])
            opposite_edge = edges[(major_edge["index"] + 2) % group_size]
            perpendicular_edge = edges[(major_edge["index"] + 1) % group_size]
            perpendicular_opposite = edges[(major_edge["index"] + 3) % group_size]

            if (
                major_edge["length"] <= 0
                or perpendicular_edge["length"] <= 0
                or opposite_edge["length"] <= 0
                or perpendicular_opposite["length"] <= 0
            ):
                logger.warning("Tower %s has degenerate geometry", key)
                continue

            rotation = math.degrees(math.atan2(major_edge["dy"], major_edge["dx"]))
            ux = major_edge["dx"] / major_edge["length"]
            uy = major_edge["dy"] / major_edge["length"]
            vx = -uy
            vy = ux

            projections_u = []
            projections_v = []
            for point in cluster_points:
                dx = point["x"] - cx
                dy = point["y"] - cy
                projections_u.append(dx * ux + dy * uy)
                projections_v.append(dx * vx + dy * vy)

            width = max(projections_u) - min(projections_u)
            height = max(projections_v) - min(projections_v)
            xscale = max(width / block_width, min_scale)
            yscale = max(height / block_height, min_scale)

            block_props = get_block_properties(doc, block_name) if doc else {"layer": "Tower", "color": 7}
            layer_override = tower_conf.get("layer")
            color_override = tower_conf.get("color")

            dxfattribs = {
                "layer": layer_override or block_props["layer"],
                "color": color_override if color_override is not None else block_props["color"],
                "xscale": xscale,
                "yscale": yscale,
                "zscale": zscale,
                "rotation": rotation,
            }

            msp.add_blockref(block_name, (cx, cy, cz), dxfattribs=dxfattribs)
            logger.debug(
                "Placed tower block %s for group %s at (%.3f, %.3f) with scale %.3f-%.3f",
                block_name,
                key,
                cx,
                cy,
                xscale,
                yscale,
            )

