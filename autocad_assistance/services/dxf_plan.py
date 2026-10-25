"""Bounded, read-only model-space projection for an authenticated plan viewer."""

from __future__ import annotations

from collections import Counter
from hashlib import sha256
from io import BytesIO
import math

import ezdxf.recover


MAX_DXF_BYTES = 8 * 1024 * 1024
MAX_ENTITIES = 10_000
MAX_VERTICES = 50_000
MAX_BLOCK_DEPTH = 4
MAX_TEXT_CHARS = 64


class PlanLimitError(ValueError):
    """A configured viewer bound was exceeded."""


class PlanInvalidError(ValueError):
    """The DXF cannot be represented safely by this viewer."""


def project_plan(raw: bytes, job_id: str) -> dict:
    """Return supported local DXF geometry without changing measured values."""

    if not isinstance(raw, bytes) or not raw:
        raise PlanInvalidError("Invalid DXF result")
    if len(raw) > MAX_DXF_BYTES:
        raise PlanLimitError("DXF exceeds viewer byte limit")
    try:
        drawing, audit = ezdxf.recover.read(BytesIO(raw))
        if audit.has_errors:
            raise PlanInvalidError("DXF audit failed")
    except PlanInvalidError:
        raise
    except Exception as exc:
        raise PlanInvalidError("Invalid DXF result") from exc

    used_entities = 0
    used_vertices = 0
    extents = [math.inf, math.inf, -math.inf, -math.inf]
    unsupported: Counter[str] = Counter()
    layers: Counter[str] = Counter()

    def number(value) -> float:
        try:
            result = float(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise PlanInvalidError("Invalid DXF coordinate") from exc
        if not math.isfinite(result):
            raise PlanInvalidError("Non-finite DXF coordinate")
        return result

    def vertex(value) -> list[float]:
        nonlocal used_vertices
        used_vertices += 1
        if used_vertices > MAX_VERTICES:
            raise PlanLimitError("DXF exceeds viewer vertex limit")
        x, y = number(value[0]), number(value[1])
        z = number(value[2]) if len(value) > 2 else 0.0
        extents[0] = min(extents[0], x)
        extents[1] = min(extents[1], y)
        extents[2] = max(extents[2], x)
        extents[3] = max(extents[3], y)
        return [x, y, z]

    def bounded_text(value) -> str:
        return str(value).replace("\x00", "")[:MAX_TEXT_CHARS]

    def convert(entity, inherited_layer: str | None = None, depth: int = 0) -> dict | None:
        nonlocal used_entities
        used_entities += 1
        if used_entities > MAX_ENTITIES:
            raise PlanLimitError("DXF exceeds viewer entity limit")
        kind = entity.dxftype()
        layer = bounded_text(entity.dxf.get("layer", "0"))
        if layer == "0" and inherited_layer is not None:
            layer = inherited_layer
        data: dict = {"type": kind, "layer": layer}
        try:
            if kind == "POINT":
                data["point"] = vertex(entity.dxf.location)
            elif kind == "LINE":
                data["points"] = [vertex(entity.dxf.start), vertex(entity.dxf.end)]
            elif kind == "LWPOLYLINE":
                if entity.has_arc:
                    unsupported["LWPOLYLINE_BULGE"] += 1
                    return None
                elevation = number(entity.dxf.get("elevation", 0))
                data["points"] = [vertex((x, y, elevation)) for x, y in entity.get_points("xy")]
                data["closed"] = bool(entity.closed)
            elif kind == "POLYLINE":
                if entity.has_arc or entity.dxf.get("flags", 0) & (2 | 4 | 16 | 64):
                    unsupported["POLYLINE_CURVE_OR_MESH"] += 1
                    return None
                data["points"] = [vertex(item.dxf.location) for item in entity.vertices]
                data["closed"] = bool(entity.is_closed)
            elif kind == "3DFACE":
                data["points"] = [vertex(entity.dxf.get(f"vtx{i}")) for i in range(4)]
                if data["points"][2] == data["points"][3]:
                    data["points"].pop()
                data["closed"] = True
            elif kind == "CIRCLE":
                data["center"] = vertex(entity.dxf.center)
                radius = number(entity.dxf.radius)
                if radius <= 0:
                    raise PlanInvalidError("Invalid circle radius")
                data["radius"] = radius
                extents[0] = min(extents[0], data["center"][0] - radius)
                extents[1] = min(extents[1], data["center"][1] - radius)
                extents[2] = max(extents[2], data["center"][0] + radius)
                extents[3] = max(extents[3], data["center"][1] + radius)
            elif kind == "ARC":
                center = entity.dxf.center
                radius = number(entity.dxf.radius)
                if radius <= 0:
                    raise PlanInvalidError("Invalid arc radius")
                start = number(entity.dxf.start_angle)
                end = number(entity.dxf.end_angle)
                sweep = (end - start) % 360 or 360
                steps = max(2, min(64, math.ceil(sweep / 10)))
                data["points"] = [vertex((
                    number(center[0]) + radius * math.cos(math.radians(start + sweep * i / steps)),
                    number(center[1]) + radius * math.sin(math.radians(start + sweep * i / steps)),
                    number(center[2]),
                )) for i in range(steps + 1)]
                data["approximate"] = True
            elif kind in {"TEXT", "MTEXT"}:
                data["point"] = vertex(entity.dxf.insert)
                data["text"] = bounded_text(entity.plain_text() if kind == "MTEXT" else entity.dxf.text)
            elif kind == "INSERT":
                data["point"] = vertex(entity.dxf.insert)
                data["name"] = bounded_text(entity.dxf.name)
                data["rotation"] = number(entity.dxf.get("rotation", 0))
                data["scale"] = [number(entity.dxf.get(axis, 1)) for axis in ("xscale", "yscale", "zscale")]
                if depth >= MAX_BLOCK_DEPTH:
                    unsupported["INSERT_DEPTH"] += 1
                    data["children"] = []
                    data["complete"] = False
                else:
                    children = []
                    unsupported_before = sum(unsupported.values())
                    for child in entity.virtual_entities():
                        converted = convert(child, layer, depth + 1)
                        if converted is not None:
                            children.append(converted)
                    data["children"] = children
                    data["complete"] = sum(unsupported.values()) == unsupported_before
            else:
                unsupported[kind] += 1
                return None
        except (PlanInvalidError, PlanLimitError):
            raise
        except Exception as exc:
            raise PlanInvalidError("DXF geometry cannot be projected") from exc
        return data

    entities = []
    def count_layers(entry: dict) -> None:
        layers[entry["layer"]] += 1
        for child in entry.get("children", []):
            count_layers(child)

    try:
        for index, entity in enumerate(drawing.modelspace()):
            converted = convert(entity)
            if converted is not None:
                converted["id"] = str(index)
                count_layers(converted)
                entities.append(converted)
    except (PlanInvalidError, PlanLimitError):
        raise
    except Exception as exc:
        raise PlanInvalidError("DXF model space cannot be projected") from exc
    bounds = None if extents[0] == math.inf else {
        "minX": extents[0], "minY": extents[1],
        "maxX": extents[2], "maxY": extents[3],
    }
    return {
        "jobId": job_id, "resultSha256": sha256(raw).hexdigest(),
        "localCoordinates": True, "bounds": bounds,
        "layers": [{"name": name, "count": count} for name, count in sorted(layers.items())],
        "entities": entities, "unsupported": dict(sorted(unsupported.items())),
        "sourceEntities": len(drawing.modelspace()),
        "expandedEntities": used_entities, "renderedVertices": used_vertices,
    }
