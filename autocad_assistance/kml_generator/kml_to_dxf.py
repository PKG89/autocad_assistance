"""Конвертация данных из KML в DXF формат."""

from __future__ import annotations

import logging
import os
from typing import List, Tuple

import ezdxf

from ..config import TEMPLATE_BLOCKS_FILE

logger = logging.getLogger(__name__)


def kml_to_dxf(
    points_data: List[Tuple[float, float, float, str]],
    lines_data: List[Tuple[List[Tuple[float, float, float]], str]],
    transformer,
    output_path: str,
) -> None:
    """
    Конвертирует данные из KML в DXF формат.
    
    Args:
        points_data: Список точек [(lon, lat, alt, name), ...]
        lines_data: Список линий [(координаты точек линии, имя), ...]
        transformer: Трансформер для конвертации координат из WGS84 в проекцию DXF
        output_path: Путь для сохранения DXF файла
    """
    try:
        # Пытаемся использовать шаблон, если он доступен
        try:
            doc = ezdxf.readfile(TEMPLATE_BLOCKS_FILE)
            logger.debug("Использован шаблон DXF: %s", TEMPLATE_BLOCKS_FILE)
        except Exception:
            # Если шаблон недоступен, создаем новый документ
            doc = ezdxf.new("R2010")
            logger.debug("Создан новый DXF документ")
        
        msp = doc.modelspace()
        
        # Очищаем modelspace, если используем шаблон
        try:
            if TEMPLATE_BLOCKS_FILE and os.path.exists(TEMPLATE_BLOCKS_FILE):
                for entity in list(msp):
                    msp.delete_entity(entity)
        except Exception:
            pass
        
        # Функция для очистки имени слоя от недопустимых символов
        def sanitize_layer_name(name: str) -> str:
            """Очищает имя слоя от недопустимых символов DXF."""
            if not name:
                return "Lines"
            # DXF не допускает: < > / \ " : ; ? * | = `
            invalid_chars = '<>/\\":;?*|=`'
            cleaned = name
            for char in invalid_chars:
                cleaned = cleaned.replace(char, '_')
            # Удаляем пробелы в начале и конце
            cleaned = cleaned.strip()
            # Ограничиваем длину (DXF ограничение - 255 символов, но лучше короче)
            cleaned = cleaned[:31]
            # Если имя слоя пустое после очистки, используем значение по умолчанию
            if not cleaned:
                cleaned = "Lines"
            return cleaned
        
        # Функция для создания слоя, если его нет
        def ensure_layer_exists(layer_name: str):
            """Создает слой, если его нет в документе."""
            sanitized_name = sanitize_layer_name(layer_name)
            if sanitized_name not in doc.layers:
                doc.layers.new(sanitized_name)
                logger.debug("Создан новый слой: %s", sanitized_name)
            return sanitized_name
        
        # Обрабатываем точки
        for lon, lat, alt, name in points_data:
            try:
                # Трансформируем координаты из WGS84 в проекцию DXF
                x, y = transformer.transform([lon], [lat])
                x_val = float(x[0])
                y_val = float(y[0])
                z_val = float(alt)
                
                # Создаем слой для точек, если его нет
                points_layer = ensure_layer_exists("Points")
                
                # Добавляем точку в DXF
                msp.add_point((x_val, y_val, z_val), dxfattribs={"layer": points_layer})
                
                # Добавляем текст с именем точки, если оно есть
                if name:
                    msp.add_text(
                        name,
                        dxfattribs={
                            "layer": points_layer,
                            "height": 1.0,
                        }
                    ).set_placement((x_val, y_val))
                
                logger.debug("Добавлена точка: %s (%f, %f, %f)", name, x_val, y_val, z_val)
            except Exception as e:
                logger.warning("Ошибка при обработке точки %s: %s", name, e)
                continue
        
        # Обрабатываем линии
        for coords, line_name in lines_data:
            if len(coords) < 2:
                continue
            
            try:
                # Трансформируем координаты из WGS84 в проекцию DXF
                lon_values = [coord[0] for coord in coords]
                lat_values = [coord[1] for coord in coords]
                
                x_values, y_values = transformer.transform(lon_values, lat_values)
                
                # Создаем список точек для полилинии
                dxf_points = []
                for i, (lon, lat) in enumerate(zip(lon_values, lat_values)):
                    x_val = float(x_values[i])
                    y_val = float(y_values[i])
                    z_val = float(coords[i][2]) if len(coords[i]) > 2 else 0.0
                    dxf_points.append((x_val, y_val, z_val))
                
                # Определяем слой на основе имени линии
                raw_layer_name = "Lines"
                if line_name:
                    # Пытаемся извлечь имя слоя из имени линии
                    if "_" in line_name:
                        parts = line_name.split("_")
                        if len(parts) > 1:
                            raw_layer_name = parts[-1]  # Берем последнюю часть как имя слоя
                    else:
                        raw_layer_name = line_name
                
                # Очищаем и создаем слой
                layer_name = ensure_layer_exists(raw_layer_name)
                
                # Добавляем полилинию в DXF
                if len(dxf_points) == 2:
                    # Для двух точек используем LINE
                    msp.add_line(
                        dxf_points[0][:2],  # Только X, Y для LINE
                        dxf_points[1][:2],
                        dxfattribs={"layer": layer_name}
                    )
                else:
                    # Для большего количества точек используем LWPOLYLINE
                    msp.add_lwpolyline(
                        [(p[0], p[1]) for p in dxf_points],  # Только X, Y для LWPOLYLINE
                        dxfattribs={"layer": layer_name}
                    )
                
                logger.debug("Добавлена линия: %s с %d точками на слое %s", line_name, len(dxf_points), layer_name)
            except Exception as e:
                logger.warning("Ошибка при обработке линии %s: %s", line_name, e)
                continue
        
        # Сохраняем DXF файл
        doc.saveas(output_path)
        logger.info("DXF файл сохранен: %s", output_path)
        
    except Exception as e:
        logger.exception("Ошибка при создании DXF файла")
        raise RuntimeError(f"Не удалось создать DXF файл: {e}") from e

