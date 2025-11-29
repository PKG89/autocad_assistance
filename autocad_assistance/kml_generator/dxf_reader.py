"""Чтение линий из DXF файлов для конвертации в KML."""

from __future__ import annotations

import logging
import math
from typing import List, Tuple

import ezdxf

logger = logging.getLogger(__name__)


def load_dxf_lines(file_path: str, min_circle_radius: float = 10.0) -> List[Tuple[List[Tuple[float, float, float]], str]]:
    """
    Извлекает линии, круги и блоки из DXF файла.
    
    Args:
        file_path: Путь к DXF файлу
        min_circle_radius: Минимальный радиус круга для преобразования в полилинию.
                          Круги с радиусом меньше этого значения преобразуются в точки.
                          По умолчанию 10.0 единиц.
    
    Возвращает список кортежей (координаты точек линии/круга/блока, имя слоя).
    Координаты в формате [(x1, y1, z1), (x2, y2, z2), ...]
    Большие круги преобразуются в полилинии из точек по окружности.
    Маленькие круги преобразуются в точки (центр круга).
    Блоки преобразуются в точки (точка вставки).
    """
    lines_data = []
    
    try:
        doc = ezdxf.readfile(file_path)
    except Exception as e:
        logger.exception("Ошибка при чтении DXF файла: %s", e)
        raise ValueError(f"Не удалось прочитать DXF файл: {e}") from e
    
    msp = doc.modelspace()
    
    # Обрабатываем LINE (отдельные линии)
    for line in msp.query("LINE"):
        try:
            start = line.dxf.start
            end = line.dxf.end
            layer = line.dxf.layer or "0"
            # Создаем список точек для линии
            # Проверяем наличие Z координаты
            start_z = 0.0
            end_z = 0.0
            try:
                start_z = float(start.z)
            except (AttributeError, ValueError, TypeError):
                start_z = 0.0
            try:
                end_z = float(end.z)
            except (AttributeError, ValueError, TypeError):
                end_z = 0.0
            
            coords = [
                (float(start.x), float(start.y), start_z),
                (float(end.x), float(end.y), end_z)
            ]
            lines_data.append((coords, layer))
            logger.debug("Найдена LINE на слое %s: от %s до %s", layer, start, end)
        except Exception as e:
            logger.warning("Ошибка при обработке LINE: %s", e)
            continue
    
    # Обрабатываем LWPOLYLINE (легкие полилинии)
    for polyline in msp.query("LWPOLYLINE"):
        try:
            layer = polyline.dxf.layer or "0"
            coords = []
            # Получаем точки полилинии
            points = polyline.get_points("xy")
            # Получаем elevation из DXF атрибутов
            elevation = 0.0
            try:
                elevation = float(polyline.dxf.elevation)
            except (AttributeError, ValueError, TypeError):
                elevation = 0.0
            
            for point in points:
                x, y = float(point[0]), float(point[1])
                # LWPOLYLINE обычно 2D, используем elevation для Z
                coords.append((x, y, elevation))
            
            if len(coords) >= 2:
                lines_data.append((coords, layer))
                logger.debug("Найдена LWPOLYLINE на слое %s с %d точками", layer, len(coords))
        except Exception as e:
            logger.warning("Ошибка при обработке LWPOLYLINE: %s", e)
            continue
    
    # Обрабатываем POLYLINE (полилинии, включая 3D)
    for polyline in msp.query("POLYLINE"):
        try:
            layer = polyline.dxf.layer or "0"
            coords = []
            # Получаем вершины полилинии
            for vertex in polyline.vertices:
                loc = vertex.dxf.location
                x = float(loc.x)
                y = float(loc.y)
                # Проверяем наличие Z координаты
                try:
                    z = float(loc.z)
                except (AttributeError, ValueError, TypeError):
                    z = 0.0
                coords.append((x, y, z))
            
            if len(coords) >= 2:
                lines_data.append((coords, layer))
                logger.debug("Найдена POLYLINE на слое %s с %d точками", layer, len(coords))
        except Exception as e:
            logger.warning("Ошибка при обработке POLYLINE: %s", e)
            continue
    
    # Обрабатываем CIRCLE (круги)
    for circle in msp.query("CIRCLE"):
        try:
            layer = circle.dxf.layer or "0"
            center = circle.dxf.center
            radius = float(circle.dxf.radius)
            
            # Получаем Z координату центра
            center_z = 0.0
            try:
                center_z = float(center.z)
            except (AttributeError, ValueError, TypeError):
                center_z = 0.0
            
            # Если радиус меньше порога, преобразуем круг в точку
            if radius < min_circle_radius:
                # Преобразуем маленький круг в точку (дублируем координаты для совместимости)
                coords = [
                    (float(center.x), float(center.y), center_z),
                    (float(center.x), float(center.y), center_z)
                ]
                lines_data.append((coords, layer))
                logger.debug("Найден маленький CIRCLE на слое %s: центр (%s, %s), радиус %s (преобразован в точку)", 
                           layer, center.x, center.y, radius)
            else:
                # Преобразуем большой круг в полилинию из 32 точек (для хорошего приближения)
                num_points = 32
                coords = []
                for i in range(num_points):
                    angle = 2 * math.pi * i / num_points
                    x = float(center.x) + radius * math.cos(angle)
                    y = float(center.y) + radius * math.sin(angle)
                    coords.append((x, y, center_z))
                
                # Замыкаем круг (добавляем первую точку в конец)
                if len(coords) > 0:
                    coords.append(coords[0])
                
                if len(coords) >= 2:
                    lines_data.append((coords, layer))
                    logger.debug("Найден CIRCLE на слое %s: центр (%s, %s), радиус %s (преобразован в полилинию)", 
                               layer, center.x, center.y, radius)
        except Exception as e:
            logger.warning("Ошибка при обработке CIRCLE: %s", e)
            continue
    
    # Обрабатываем INSERT (блоки) - извлекаем точку вставки
    for insert in msp.query("INSERT"):
        try:
            layer = insert.dxf.layer or "0"
            insertion_point = insert.dxf.insert
            
            # Получаем Z координату точки вставки
            insert_z = 0.0
            try:
                insert_z = float(insertion_point.z)
            except (AttributeError, ValueError, TypeError):
                insert_z = 0.0
            
            # Преобразуем блок в точку (для KML это будет точка)
            # Создаем "линию" из одной точки (дублируем точку для совместимости)
            coords = [
                (float(insertion_point.x), float(insertion_point.y), insert_z),
                (float(insertion_point.x), float(insertion_point.y), insert_z)
            ]
            
            # Получаем имя блока
            block_name = insert.dxf.name or "UNNAMED"
            
            lines_data.append((coords, layer))
            logger.debug("Найден INSERT (блок '%s') на слое %s: точка вставки (%s, %s)", 
                       block_name, layer, insertion_point.x, insertion_point.y)
        except Exception as e:
            logger.warning("Ошибка при обработке INSERT: %s", e)
            continue
    
    logger.info("Извлечено %d объектов (линии/круги/блоки) из DXF файла", len(lines_data))
    return lines_data

