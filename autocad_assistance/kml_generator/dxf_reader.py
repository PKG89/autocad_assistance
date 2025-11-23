"""Чтение линий из DXF файлов для конвертации в KML."""

from __future__ import annotations

import logging
from typing import List, Tuple

import ezdxf

logger = logging.getLogger(__name__)


def load_dxf_lines(file_path: str) -> List[Tuple[List[Tuple[float, float, float]], str]]:
    """
    Извлекает линии из DXF файла.
    
    Возвращает список кортежей (координаты точек линии, имя слоя).
    Координаты в формате [(x1, y1, z1), (x2, y2, z2), ...]
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
    
    logger.info("Извлечено %d линий из DXF файла", len(lines_data))
    return lines_data

