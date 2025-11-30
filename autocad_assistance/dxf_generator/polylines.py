"""Polyline helpers for DXF generation."""

import logging
import math
import random
import re
from typing import Dict, List, Sequence, Tuple

from ..config import polyline_layer_mapping, sm_controller_config, vegetation_contour_codes

logger = logging.getLogger(__name__)


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
    allowed_prefixes = {p.lower() for p in sm_controller_config.get("polyline_prefixes", set())}
    pattern = re.compile(r"^(?P<prefix>[a-zA-Z]+)(?P<number>\d+)$")
    groups: Dict[str, List[Tuple[int, Tuple[float, float, float, str]]]] = {}

    for index, row in final_data.iterrows():
        code_raw = str(row["Code"]).strip().lower()
        match = pattern.match(code_raw)
        if not match:
            continue
        prefix = match.group("prefix")
        if prefix not in allowed_prefixes:
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


def _order_polyline_points(points: Sequence[Tuple[int, Tuple[float, float, float, str]]]) -> List[Tuple[float, float, float, str]]:
    if not points:
        return []
    ordered_pairs = sorted(points, key=lambda item: item[0])
    if len(ordered_pairs) < 2:
        return [ordered_pairs[0][1]]

    remaining = list(ordered_pairs[1:])
    ordered: List[Tuple[float, float, float, str]] = [ordered_pairs[0][1]]
    current_point = ordered_pairs[0][1][:3]

    while remaining:
        next_item = min(
            remaining,
            key=lambda item: math.hypot(item[1][0] - current_point[0], item[1][1] - current_point[1]),
        )
        ordered.append(next_item[1])
        current_point = next_item[1][:3]
        remaining.remove(next_item)

    return ordered


def extract_structural_breaklines(final_data) -> List[List[Tuple[float, float, float]]]:
    """Return ordered sequences of 3D points usable as structural breaklines."""
    breaklines: List[List[Tuple[float, float, float]]] = []
    for points in _collect_polyline_groups(final_data).values():
        ordered = _order_polyline_points(points)
        if len(ordered) < 2:
            continue
        breaklines.append([(x, y, z) for x, y, z, _ in ordered])
    return breaklines


def build_polyline_by_code(final_data, msp, doc=None, scale_factor: float = 1.0, text_scale: float = 1.6) -> List[List[Tuple[float, float, float]]]:
    """Create LWPOLYLINE entities grouped by controller code and return ordered 3D breaklines."""
    line_text_height = 1.6 * scale_factor
    breaklines: List[List[Tuple[float, float, float]]] = []

    groups = _collect_polyline_groups(final_data)
    for group_key, points in groups.items():
        if len(points) < 2:
            continue

        ordered_points = _order_polyline_points(points)
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

        msp.add_lwpolyline([(x, y) for x, y, _ in ordered_points], dxfattribs=polyline_attribs)

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


def _collect_vegetation_contours(final_data) -> Dict[str, List[Tuple[int, Tuple[float, float, float, str]]]]:
    """Собирает точки контуров растительности, группируя их по коду."""
    groups: Dict[str, List[Tuple[int, Tuple[float, float, float, str]]]] = {}
    pattern = re.compile(r"^(?P<prefix>[a-zA-Zа-яА-Я]+)(?P<number>\d+)$", re.IGNORECASE)

    for index, row in final_data.iterrows():
        code_raw = str(row["Code"]).strip()
        code_lower = code_raw.lower()
        
        # Проверяем, является ли код контуром растительности
        match = pattern.match(code_raw)
        if not match:
            continue
        
        prefix = match.group("prefix").lower()
        if prefix not in vegetation_contour_codes:
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


def _is_closed_contour(points: List[Tuple[float, float, float, str]], tolerance: float = 0.1) -> bool:
    """Проверяет, является ли контур замкнутым (первая и последняя точки близки)."""
    if len(points) < 3:
        return False
    first = points[0][:2]
    last = points[-1][:2]
    distance = math.hypot(first[0] - last[0], first[1] - last[1])
    return distance <= tolerance


def _close_contour(points: List[Tuple[float, float, float, str]]) -> List[Tuple[float, float, float, str]]:
    """Замыкает контур, добавляя первую точку в конец, если контур не замкнут."""
    if not points:
        return points
    # Если контур уже замкнут, возвращаем как есть
    if _is_closed_contour(points):
        return points
    # Иначе добавляем первую точку в конец
    return points + [points[0]]


def _point_in_polygon(point: Tuple[float, float], polygon: List[Tuple[float, float]]) -> bool:
    """Проверяет, находится ли точка внутри полигона (алгоритм ray casting)."""
    if len(polygon) < 3:
        return False
    
    x, y = point
    n = len(polygon)
    inside = False
    
    p1x, p1y = polygon[0]
    for i in range(1, n + 1):
        p2x, p2y = polygon[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y
    
    return inside


def _get_polygon_bounds(polygon: List[Tuple[float, float]]) -> Tuple[float, float, float, float]:
    """Возвращает границы полигона (min_x, min_y, max_x, max_y)."""
    if not polygon:
        return (0.0, 0.0, 0.0, 0.0)
    
    xs = [p[0] for p in polygon]
    ys = [p[1] for p in polygon]
    return (min(xs), min(ys), max(xs), max(ys))


def _place_blocks_in_polygon(
    polygon: List[Tuple[float, float]],
    block_name: str,
    msp,
    doc,
    layer_name: str,
    min_distance: float = 10.0,
    max_attempts: int = 1000,
    scale_factor: float = 1.0,
    z: float = 0.0,
) -> int:
    """Размещает блоки случайным образом внутри полигона с минимальным расстоянием между ними.
    
    Returns:
        Количество размещенных блоков
    """
    if len(polygon) < 3:
        return 0
    
    # Получаем границы полигона
    min_x, min_y, max_x, max_y = _get_polygon_bounds(polygon)
    
    # Вычисляем площадь для оценки количества блоков
    area = (max_x - min_x) * (max_y - min_y)
    # Примерная плотность: один блок на каждые (min_distance * 2)^2 единиц площади
    estimated_blocks = max(1, int(area / (min_distance * 2) ** 2))
    
    placed_blocks: List[Tuple[float, float]] = []
    attempts = 0
    
    # Получаем свойства блока
    block_props = {"layer": layer_name, "color": 7}
    if doc:
        try:
            from .blocks import get_block_properties
            props = get_block_properties(doc, block_name)
            block_props.update(props)
        except Exception:
            pass
    
    # Пытаемся разместить блоки
    while len(placed_blocks) < estimated_blocks and attempts < max_attempts:
        attempts += 1
        
        # Генерируем случайную точку внутри bounding box
        x = random.uniform(min_x, max_x)
        y = random.uniform(min_y, max_y)
        
        # Проверяем, находится ли точка внутри полигона
        if not _point_in_polygon((x, y), polygon):
            continue
        
        # Проверяем минимальное расстояние до других блоков
        too_close = False
        for bx, by in placed_blocks:
            distance = math.hypot(x - bx, y - by)
            if distance < min_distance:
                too_close = True
                break
        
        if too_close:
            continue
        
        # Размещаем блок
        try:
            msp.add_blockref(
                block_name,
                (x, y, z),
                dxfattribs={
                    "layer": block_props["layer"],
                    "color": block_props.get("color", 7),
                    "xscale": scale_factor,
                    "yscale": scale_factor,
                    "zscale": scale_factor,
                    "rotation": random.uniform(0, 360),  # Случайный поворот
                },
            )
            placed_blocks.append((x, y))
        except Exception as e:
            logger.warning("Ошибка при размещении блока %s в точке (%.2f, %.2f): %s", 
                          block_name, x, y, e)
            continue
    
    return len(placed_blocks)


def build_vegetation_contours(final_data, msp, doc=None, scale_factor: float = 1.0) -> None:
    """Создает замкнутые контуры растительности с заливкой."""
    groups = _collect_vegetation_contours(final_data)
    
    for group_key, points in groups.items():
        if len(points) < 3:  # Минимум 3 точки для замкнутого контура
            continue

        ordered_points = _order_polyline_points(points)
        if len(ordered_points) < 3:
            continue

        # Замыкаем контур
        closed_points = _close_contour(ordered_points)
        
        # Определяем слой по префиксу кода
        base_code = re.sub(r"\d+$", "", group_key).lower()
        layer_name = polyline_layer_mapping.get(base_code, "(026) Растительность")
        
        # Получаем свойства слоя
        polyline_attribs = {"layer": layer_name, "color": 7, "linetype": "CONTINUOUS"}
        if doc and layer_name in doc.layers:
            layer_def = doc.layers.get(layer_name)
            polyline_attribs["color"] = layer_def.dxf.color
            polyline_attribs["linetype"] = layer_def.dxf.linetype

        # Создаем замкнутую полилинию
        polyline_points = [(x, y) for x, y, _, _ in closed_points]
        polyline = msp.add_lwpolyline(
            polyline_points,
            dxfattribs={
                **polyline_attribs,
                "const_width": 0.0,
            }
        )
        # Делаем полилинию замкнутой
        polyline.close(True)

        # Для леса (les) размещаем блоки "368" вместо заливки
        if "лес" in base_code or "les" in base_code:
            try:
                # Вычисляем среднюю Z координату точек контура
                avg_z = sum(z for _, _, z, _ in closed_points) / len(closed_points) if closed_points else 0.0
                
                block_count = _place_blocks_in_polygon(
                    polygon=polyline_points,
                    block_name="368",
                    msp=msp,
                    doc=doc,
                    layer_name=layer_name,
                    min_distance=10.0,
                    max_attempts=2000,
                    scale_factor=scale_factor,
                    z=avg_z,
                )
                logger.info("Размещено %d блоков '368' в контуре леса %s", block_count, group_key)
            except Exception as e:
                logger.warning("Ошибка при размещении блоков для контура леса %s: %s", group_key, e)
        else:
            # Для остальных типов растительности добавляем заливку (hatch)
            try:
                # Определяем тип заливки в зависимости от типа растительности
                hatch_pattern = "SOLID"  # Сплошная заливка по умолчанию
                if "куст" in base_code or "kust" in base_code:
                    hatch_pattern = "ANSI37"  # Точечная заливка для кустов
                
                hatch = msp.add_hatch(
                    dxfattribs={
                        "layer": layer_name,
                        "color": polyline_attribs["color"],
                        "hatch_style": 0,  # Normal (outermost area)
                    }
                )
                
                # Устанавливаем паттерн заливки
                if hatch_pattern == "SOLID":
                    hatch.set_solid_fill(color=polyline_attribs["color"])
                else:
                    hatch.set_pattern_fill(hatch_pattern, scale=0.5 * scale_factor, angle=0.0)
                
                # Добавляем границу заливки (используем полилинию)
                # Преобразуем точки в формат для hatch path
                path_points = [(x, y) for x, y in polyline_points]
                hatch.paths.add_polyline_path(
                    path_points,
                    is_closed=True
                )
                
                logger.debug("Создан контур растительности: %s с %d точками на слое %s", 
                            group_key, len(closed_points), layer_name)
            except Exception as e:
                logger.warning("Ошибка при создании заливки для контура %s: %s", group_key, e)
                # Продолжаем работу даже если заливка не создалась

