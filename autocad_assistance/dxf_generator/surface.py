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
CONTOUR_LAYER = "3 Горизонтали"  # Слой для горизонталей

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


def _extract_points_for_codes(final_data, selected_codes: set[str] | None = None) -> List[Tuple[float, float, float, str]]:
    """
    Извлекает точки из final_data.
    
    Args:
        final_data: DataFrame с колонками Point, X, Y, Z, Code
        selected_codes: Множество кодов (в нижнем регистре) для фильтрации.
                       Если None или пустое множество - используются все точки.
    
    Returns:
        Список точек (x, y, z, code)
    """
    points: List[Tuple[float, float, float, str]] = []
    
    # Если коды не указаны или пустое множество, используем все точки
    use_all_points = selected_codes is None or len(selected_codes) == 0
    
    for _, row in final_data.iterrows():
        try:
            # Извлекаем координаты
            x = float(row["X"])
            y = float(row["Y"])
            z = float(row["Z"])
            code = str(row.get("Code", "")).strip()
            
            # Если фильтрация по кодам включена, проверяем код
            if not use_all_points:
                if code.lower() not in selected_codes:
                    continue
            
            points.append((x, y, z, code))
        except (TypeError, ValueError, KeyError) as e:
            logger.debug("Пропуск строки из-за ошибки извлечения координат: %s", e)
            continue
    
    logger.info("TIN: извлечено %d точек из %d строк данных (использованы %s)", 
                 len(points), len(final_data), "все точки" if use_all_points else f"коды: {selected_codes}")
    
    # Проверяем что координаты не нулевые
    if points:
        sample_point = points[0]
        logger.debug("TIN: пример первой точки: (%s, %s, %s)", sample_point[0], sample_point[1], sample_point[2])
    
    return points


def _add_points_to_layer(msp, points: Sequence[Tuple[float, float, float]], layer: str, color: int) -> None:
    for x, y, z in points:
        try:
            msp.add_point((x, y, z), dxfattribs={"layer": layer, "color": color})
        except Exception as exc:
            logger.debug("Failed to add point (%s, %s, %s) to layer %s: %s", x, y, z, layer, exc)


def _is_degenerate_triangle(v1: Tuple[float, float, float], v2: Tuple[float, float, float], v3: Tuple[float, float, float], tolerance: float = 1e-6) -> bool:
    """
    Проверяет, является ли треугольник вырожденным (коллинеарные точки).
    
    Args:
        v1, v2, v3: Вершины треугольника
        tolerance: Допустимая погрешность для проверки
    
    Returns:
        True если треугольник вырожденный
    """
    import math
    
    # Вычисляем векторы сторон
    dx1 = v2[0] - v1[0]
    dy1 = v2[1] - v1[1]
    dz1 = v2[2] - v1[2]
    
    dx2 = v3[0] - v1[0]
    dy2 = v3[1] - v1[1]
    dz2 = v3[2] - v1[2]
    
    # Вычисляем векторное произведение (площадь параллелограмма)
    cross_x = dy1 * dz2 - dz1 * dy2
    cross_y = dz1 * dx2 - dx1 * dz2
    cross_z = dx1 * dy2 - dy1 * dx2
    
    # Вычисляем длину вектора нормали (удвоенная площадь треугольника)
    area = math.sqrt(cross_x * cross_x + cross_y * cross_y + cross_z * cross_z)
    
    return area < tolerance


def _ensure_counterclockwise(v1: Tuple[float, float, float], v2: Tuple[float, float, float], v3: Tuple[float, float, float]) -> Tuple[Tuple[float, float, float], Tuple[float, float, float], Tuple[float, float, float]]:
    """
    Обеспечивает ориентацию вершин треугольника против часовой стрелки (для правильной нормали).
    В DXF нормаль определяется по правилу правой руки.
    
    Args:
        v1, v2, v3: Вершины треугольника
    
    Returns:
        Кортеж вершин с правильной ориентацией
    """
    import math
    
    # Вычисляем векторное произведение для определения ориентации (в 2D проекции)
    dx1 = v2[0] - v1[0]
    dy1 = v2[1] - v1[1]
    
    dx2 = v3[0] - v1[0]
    dy2 = v3[1] - v1[1]
    
    # Z-компонента векторного произведения (для 2D проекции)
    # Если cross_z < 0, точки по часовой стрелке - меняем порядок
    cross_z = dx1 * dy2 - dy1 * dx2
    
    # Если cross_z < 0, точки по часовой стрелке - меняем порядок
    if cross_z < 0:
        return (v1, v3, v2)
    
    return (v1, v2, v3)


def _filter_triangles_by_max_edge(
    triangles: Sequence[Tuple[Tuple[float, float, float], Tuple[float, float, float], Tuple[float, float, float]]],
    max_edge_length: float = 100.0,
) -> List[Tuple[Tuple[float, float, float], Tuple[float, float, float], Tuple[float, float, float]]]:
    """
    Фильтрует треугольники по максимальной длине стороны.
    
    Args:
        triangles: Список треугольников
        max_edge_length: Максимальная допустимая длина стороны в метрах (по умолчанию 100м)
    
    Returns:
        Отфильтрованный список треугольников
    """
    import math
    
    filtered = []
    skipped_count = 0
    
    for v1, v2, v3 in triangles:
        # Вычисляем длины всех трёх сторон треугольника
        edge1 = math.sqrt((v2[0] - v1[0])**2 + (v2[1] - v1[1])**2 + (v2[2] - v1[2])**2)
        edge2 = math.sqrt((v3[0] - v2[0])**2 + (v3[1] - v2[1])**2 + (v3[2] - v2[2])**2)
        edge3 = math.sqrt((v1[0] - v3[0])**2 + (v1[1] - v3[1])**2 + (v1[2] - v3[2])**2)
        
        # Проверяем что все стороны не превышают максимальную длину
        if edge1 <= max_edge_length and edge2 <= max_edge_length and edge3 <= max_edge_length:
            filtered.append((v1, v2, v3))
        else:
            skipped_count += 1
    
    if skipped_count > 0:
        logger.info("TIN: пропущено %d треугольников с длиной стороны > %.1f м (осталось %d)", 
                   skipped_count, max_edge_length, len(filtered))
    
    return filtered


def _add_triangles(msp, triangles: Sequence[Tuple[Tuple[float, float, float], ...]], layer: str, color: int) -> None:
    """
    Добавляет треугольники в DXF как 3DFACE объекты.
    
    В DXF формате 3DFACE требует 4 точки, но для треугольника последняя точка дублируется.
    Вершины должны быть ориентированы против часовой стрелки для правильной нормали.
    
    Args:
        msp: ModelSpace объект ezdxf
        triangles: Последовательность треугольников, каждый как кортеж из 3 вершин
        layer: Имя слоя
        color: Цвет (код цвета DXF)
    """
    added_count = 0
    skipped_count = 0
    
    for v1, v2, v3 in triangles:
        try:
            # Проверяем на вырожденный треугольник
            if _is_degenerate_triangle(v1, v2, v3):
                skipped_count += 1
                logger.debug("Skipping degenerate triangle: (%s, %s, %s) -> (%s, %s, %s) -> (%s, %s, %s)", 
                           v1[0], v1[1], v1[2], v2[0], v2[1], v2[2], v3[0], v3[1], v3[2])
                continue
            
            # Обеспечиваем правильную ориентацию вершин
            v1_ccw, v2_ccw, v3_ccw = _ensure_counterclockwise(v1, v2, v3)
            
            # В DXF 3DFACE требует 4 точки, для треугольника последняя дублируется
            # Формат: [v1, v2, v3, v3] где v3 дублируется
            msp.add_3dface([v1_ccw, v2_ccw, v3_ccw, v3_ccw], dxfattribs={"layer": layer, "color": color})
            added_count += 1
        except Exception as exc:
            skipped_count += 1
            logger.debug("Failed to add triangle on layer %s: %s", layer, exc)
    
    if skipped_count > 0:
        logger.debug("Skipped %d triangles (degenerate or errors), added %d triangles", skipped_count, added_count)


def _triangulate(
    points: Sequence[Tuple[float, float, float]],
    breaklines: Sequence[Sequence[Tuple[float, float, float]]] | None = None,
) -> List[Tuple[Tuple[float, float, float], Tuple[float, float, float], Tuple[float, float, float]]]:
    """
    Строит триангуляцию Делоне с учетом структурных линий (breaklines).
    
    Args:
        points: Список точек (x, y, z)
        breaklines: Структурные линии разрыва - последовательности точек, которые должны быть рёбрами треугольников
    
    Returns:
        Список треугольников
    """
    if len(points) < 3:
        return []
    
    # Добавляем точки из breaklines в набор точек для триангуляции
    all_points = list(points)
    breakline_edges = []
    
    if breaklines:
        for breakline in breaklines:
            if len(breakline) < 2:
                continue
            # Добавляем точки из breakline, если их еще нет в наборе
            for pt in breakline:
                # Проверяем, есть ли уже такая точка (с небольшой погрешностью)
                found = False
                for existing_pt in all_points:
                    if abs(existing_pt[0] - pt[0]) < 0.01 and abs(existing_pt[1] - pt[1]) < 0.01:
                        found = True
                        break
                if not found:
                    all_points.append(pt)
            
            # Сохраняем рёбра breakline для проверки
            for i in range(len(breakline) - 1):
                breakline_edges.append((breakline[i], breakline[i + 1]))
    
    coords = np.array([(p[0], p[1]) for p in all_points], dtype=float)
    try:
        delaunay = Delaunay(coords)
    except QhullError as exc:
        logger.warning("Не удалось построить триангуляцию TIN: %s", exc)
        return []
    
    simplices = delaunay.simplices
    triangles: List[Tuple[Tuple[float, float, float], Tuple[float, float, float], Tuple[float, float, float]]] = []
    
    for simplex in simplices:
        v1 = all_points[int(simplex[0])]
        v2 = all_points[int(simplex[1])]
        v3 = all_points[int(simplex[2])]
        triangles.append((v1, v2, v3))
    
    # Проверяем, что рёбра breaklines присутствуют в триангуляции
    if breakline_edges:
        logger.info("TIN: проверка %d рёбер breaklines в триангуляции", len(breakline_edges))
        # TODO: В будущем можно добавить проверку и перестроение триангуляции если рёбра отсутствуют
    
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
    selected_codes: Iterable[str] | None = None,
    scale_value: int = 1000,
    refine_enabled: bool = False,
    breaklines: Sequence[Sequence[Tuple[float, float, float]]] | None = None,
    contour_interval: float = 1.0,
) -> TinBuildResult:
    """Build terrain surface from selected codes and optional refinement.
    
    Args:
        final_data: DataFrame с данными точек
        msp: ModelSpace для добавления объектов
        selected_codes: Список кодов для фильтрации. Если None или пустой - используются все точки
        scale_value: Масштаб для определения порога уточнения
        refine_enabled: Включить уточнение рельефа
        breaklines: Структурные линии разрыва
    """
    result = TinBuildResult()
    
    # Нормализуем коды (приводим к нижнему регистру и убираем пробелы)
    # Если коды не переданы или пустой список, используем все точки
    code_set = None
    if selected_codes:
        code_set = _normalize_codes(selected_codes)
        if not code_set:
            code_set = None  # Пустое множество = используем все точки
    
    if code_set is None:
        logger.info("TIN: коды не выбраны, используем все точки из файла")

    points = _extract_points_for_codes(final_data, code_set)
    
    # Проверяем что точки извлечены правильно
    if points:
        sample = points[0]
        logger.info("TIN: пример первой точки: X=%.2f, Y=%.2f, Z=%.2f, Code=%s", 
                   sample[0], sample[1], sample[2], sample[3])
    
    if len(points) < 3:
        logger.warning("TIN: недостаточно точек для построения поверхности (нужно минимум 3, получено %d).", len(points))
        return result

    result.base_points = len(points)
    logger.info("TIN: добавление %d точек на слой", len(points))
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

    # Преобразуем точки в формат для триангуляции (только координаты)
    triangulation_points = [(x, y, z) for x, y, z, _ in points]
    logger.info("TIN: начало триангуляции для %d точек", len(triangulation_points))
    if breaklines:
        logger.info("TIN: учёт %d структурных линий (breaklines)", len(breaklines))
    
    base_triangles = _triangulate(triangulation_points, breaklines=breaklines)
    if base_triangles:
        # Фильтруем треугольники по максимальной длине стороны (100м)
        base_triangles = _filter_triangles_by_max_edge(base_triangles, max_edge_length=100.0)
        
        result.base_triangles = len(base_triangles)
        logger.info("TIN: триангуляция создала %d треугольников (после фильтрации по длине стороны)", len(base_triangles))
        if base_triangles:
            sample_triangle = base_triangles[0]
            logger.info("TIN: пример треугольника: (%s, %s, %s) -> (%s, %s, %s) -> (%s, %s, %s)",
                       sample_triangle[0][0], sample_triangle[0][1], sample_triangle[0][2],
                       sample_triangle[1][0], sample_triangle[1][1], sample_triangle[1][2],
                       sample_triangle[2][0], sample_triangle[2][1], sample_triangle[2][2])
        _add_triangles(msp, base_triangles, TIN_TRIANGLE_LAYER, GREEN_COLOR)
        
        # Строим горизонтали по треугольникам
        if base_triangles:
            # Находим минимальную и максимальную высоту
            all_z = []
            for v1, v2, v3 in base_triangles:
                all_z.extend([v1[2], v2[2], v3[2]])
            if all_z:
                min_z = min(all_z)
                max_z = max(all_z)
                # Используем заданный интервал горизонталей (по умолчанию 1.0м)
                build_contours_from_tin(msp, base_triangles, min_z, max_z, contour_interval)
    else:
        logger.warning("TIN: триангуляция не дала результата.")

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
    refined_triangles = _triangulate([(x, y, z) for x, y, z, _ in combined_points], breaklines=breaklines)
    if refined_triangles:
        # Фильтруем уточнённые треугольники по максимальной длине стороны (100м)
        refined_triangles = _filter_triangles_by_max_edge(refined_triangles, max_edge_length=100.0)
        result.refined_triangles = len(refined_triangles)
        _add_triangles(msp, refined_triangles, REFINED_TRIANGLE_LAYER, RED_COLOR)

    return result


def _intersect_triangle_with_plane(
    v1: Tuple[float, float, float],
    v2: Tuple[float, float, float],
    v3: Tuple[float, float, float],
    z_level: float,
    tolerance: float = 0.01,
) -> List[Tuple[float, float, float]] | None:
    """
    Находит точки пересечения треугольника с горизонтальной плоскостью на заданной высоте.
    
    Args:
        v1, v2, v3: Вершины треугольника
        z_level: Высота горизонтальной плоскости
        tolerance: Допустимая погрешность для проверки пересечения
    
    Returns:
        Список из 2 точек пересечения или None если пересечения нет
    """
    import math
    
    z1, z2, z3 = v1[2], v2[2], v3[2]
    
    # Проверяем, пересекает ли плоскость треугольник
    above = [z >= z_level - tolerance for z in [z1, z2, z3]]
    below = [z <= z_level + tolerance for z in [z1, z2, z3]]
    
    # Если все точки выше или все ниже - пересечения нет
    if all(above) or all(below):
        return None
    
    # Находим рёбра, которые пересекаются с плоскостью
    intersections = []
    
    # Ребро v1-v2
    if (z1 < z_level < z2) or (z2 < z_level < z1):
        if abs(z2 - z1) > tolerance:
            t = (z_level - z1) / (z2 - z1)
            x = v1[0] + t * (v2[0] - v1[0])
            y = v1[1] + t * (v2[1] - v1[1])
            intersections.append((x, y, z_level))
    
    # Ребро v2-v3
    if (z2 < z_level < z3) or (z3 < z_level < z2):
        if abs(z3 - z2) > tolerance:
            t = (z_level - z2) / (z3 - z2)
            x = v2[0] + t * (v3[0] - v2[0])
            y = v2[1] + t * (v3[1] - v2[1])
            intersections.append((x, y, z_level))
    
    # Ребро v3-v1
    if (z3 < z_level < z1) or (z1 < z_level < z3):
        if abs(z1 - z3) > tolerance:
            t = (z_level - z3) / (z1 - z3)
            x = v3[0] + t * (v1[0] - v3[0])
            y = v3[1] + t * (v1[1] - v3[1])
            intersections.append((x, y, z_level))
    
    # Должно быть ровно 2 точки пересечения
    if len(intersections) == 2:
        return intersections
    return None


def _build_contours(
    triangles: Sequence[Tuple[Tuple[float, float, float], Tuple[float, float, float], Tuple[float, float, float]]],
    min_z: float,
    max_z: float,
    contour_interval: float = 1.0,
) -> List[List[Tuple[float, float, float]]]:
    """
    Строит горизонтали (изолинии) по треугольникам TIN.
    
    Args:
        triangles: Список треугольников
        min_z: Минимальная высота
        max_z: Максимальная высота
        contour_interval: Интервал между горизонталями (в метрах)
    
    Returns:
        Список полилиний горизонталей
    """
    if not triangles:
        return []
    
    contours = []
    z_levels = []
    
    # Генерируем уровни горизонталей, кратные 0.5
    # Начинаем с ближайшего кратного 0.5 снизу от min_z
    import math
    base_level = math.floor(min_z * 2) / 2.0  # Округляем вниз до ближайшего 0.5
    
    # Генерируем все уровни кратные 0.5 в диапазоне
    current_z = base_level
    step_05 = 0.5  # Базовый шаг - всегда 0.5
    
    # Вычисляем множитель для интервала (сколько шагов по 0.5)
    # Например: интервал 1.0 = 2 шага по 0.5, интервал 2.0 = 4 шага по 0.5
    interval_multiplier = max(1, int(round(contour_interval / step_05)))
    
    level_count = 0
    while current_z <= max_z:
        if current_z >= min_z:
            # Добавляем каждый N-й уровень в зависимости от интервала
            if level_count % interval_multiplier == 0:
                z_levels.append(current_z)
        current_z += step_05
        level_count += 1
    
    # Для каждого уровня находим пересечения с треугольниками
    for z_level in z_levels:
        segments = []
        for v1, v2, v3 in triangles:
            intersection = _intersect_triangle_with_plane(v1, v2, v3, z_level)
            if intersection:
                segments.append(intersection)
        
        # Объединяем сегменты в полилинии
        if segments:
            # Простой алгоритм соединения сегментов
            used = [False] * len(segments)
            for i, seg in enumerate(segments):
                if used[i]:
                    continue
                used[i] = True
                polyline = [seg[0], seg[1]]
                
                # Ищем следующий сегмент, который соединяется с текущим
                found = True
                while found:
                    found = False
                    for j, other_seg in enumerate(segments):
                        if used[j]:
                            continue
                        # Проверяем соединение с началом полилинии
                        if abs(polyline[0][0] - other_seg[0][0]) < 0.01 and abs(polyline[0][1] - other_seg[0][1]) < 0.01:
                            polyline.insert(0, other_seg[1])
                            used[j] = True
                            found = True
                            break
                        elif abs(polyline[0][0] - other_seg[1][0]) < 0.01 and abs(polyline[0][1] - other_seg[1][1]) < 0.01:
                            polyline.insert(0, other_seg[0])
                            used[j] = True
                            found = True
                            break
                        # Проверяем соединение с концом полилинии
                        elif abs(polyline[-1][0] - other_seg[0][0]) < 0.01 and abs(polyline[-1][1] - other_seg[0][1]) < 0.01:
                            polyline.append(other_seg[1])
                            used[j] = True
                            found = True
                            break
                        elif abs(polyline[-1][0] - other_seg[1][0]) < 0.01 and abs(polyline[-1][1] - other_seg[1][1]) < 0.01:
                            polyline.append(other_seg[0])
                            used[j] = True
                            found = True
                            break
                
                if len(polyline) >= 2:
                    contours.append(polyline)
    
    return contours


def build_contours_from_tin(
    msp,
    triangles: Sequence[Tuple[Tuple[float, float, float], Tuple[float, float, float], Tuple[float, float, float]]],
    min_z: float,
    max_z: float,
    contour_interval: float = 1.0,
) -> None:
    """
    Строит и добавляет горизонтали в DXF.
    
    Args:
        msp: ModelSpace объект ezdxf
        triangles: Список треугольников TIN
        min_z: Минимальная высота
        max_z: Максимальная высота
        contour_interval: Интервал между горизонталями (в метрах)
    """
    if not triangles:
        logger.warning("TIN: нет треугольников для построения горизонталей")
        return
    
    contours = _build_contours(triangles, min_z, max_z, contour_interval)
    
    logger.info("TIN: построено %d горизонталей с интервалом %.1f м", len(contours), contour_interval)
    
    for contour in contours:
        if len(contour) < 2:
            continue
        try:
            msp.add_polyline3d(contour, dxfattribs={"layer": CONTOUR_LAYER, "color": GREEN_COLOR})
        except Exception as exc:
            logger.debug("Failed to add contour line: %s", exc)
