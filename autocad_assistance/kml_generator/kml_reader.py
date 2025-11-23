"""Чтение данных из KML файлов для конвертации в DXF."""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from typing import List, Tuple

logger = logging.getLogger(__name__)

# Namespace для KML
KML_NS = {"kml": "http://www.opengis.net/kml/2.2"}


def load_kml_data(file_path: str) -> Tuple[List[Tuple[float, float, float, str]], List[Tuple[List[Tuple[float, float, float]], str]]]:
    """
    Извлекает точки и линии из KML файла.
    
    Возвращает кортеж:
    - Список точек: [(lon, lat, alt, name), ...]
    - Список линий: [(координаты точек линии, имя), ...]
    """
    points_data = []
    lines_data = []
    
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()
    except Exception as e:
        logger.exception("Ошибка при чтении KML файла: %s", e)
        raise ValueError(f"Не удалось прочитать KML файл: {e}") from e
    
    # Обрабатываем Placemarks (точки и линии)
    for placemark in root.findall(".//kml:Placemark", KML_NS):
        name = ""
        name_elem = placemark.find("kml:name", KML_NS)
        if name_elem is not None and name_elem.text:
            name = name_elem.text.strip()
        
        # Обрабатываем точки (Point)
        point_elem = placemark.find(".//kml:Point", KML_NS)
        if point_elem is not None:
            coords_elem = point_elem.find(".//kml:coordinates", KML_NS)
            if coords_elem is not None and coords_elem.text:
                try:
                    coord_text = coords_elem.text.strip()
                    # Формат: lon,lat,alt или lon,lat
                    parts = coord_text.split(",")
                    if len(parts) >= 2:
                        lon = float(parts[0].strip())
                        lat = float(parts[1].strip())
                        alt = float(parts[2].strip()) if len(parts) > 2 else 0.0
                        points_data.append((lon, lat, alt, name))
                        logger.debug("Найдена точка: %s (%f, %f, %f)", name, lon, lat, alt)
                except (ValueError, IndexError) as e:
                    logger.warning("Ошибка при обработке точки: %s", e)
                    continue
        
        # Обрабатываем линии (LineString)
        linestring_elem = placemark.find(".//kml:LineString", KML_NS)
        if linestring_elem is not None:
            coords_elem = linestring_elem.find(".//kml:coordinates", KML_NS)
            if coords_elem is not None and coords_elem.text:
                try:
                    coord_text = coords_elem.text.strip()
                    coords = []
                    # Координаты разделены пробелами или переносами строк
                    for coord_line in coord_text.split():
                        parts = coord_line.split(",")
                        if len(parts) >= 2:
                            lon = float(parts[0].strip())
                            lat = float(parts[1].strip())
                            alt = float(parts[2].strip()) if len(parts) > 2 else 0.0
                            coords.append((lon, lat, alt))
                    
                    if len(coords) >= 2:
                        lines_data.append((coords, name or f"Line_{len(lines_data) + 1}"))
                        logger.debug("Найдена линия: %s с %d точками", name, len(coords))
                except (ValueError, IndexError) as e:
                    logger.warning("Ошибка при обработке линии: %s", e)
                    continue
        
        # Обрабатываем полигоны (Polygon) - берем внешнюю границу как линию
        polygon_elem = placemark.find(".//kml:Polygon", KML_NS)
        if polygon_elem is not None:
            outer_boundary = polygon_elem.find(".//kml:outerBoundaryIs/kml:LinearRing", KML_NS)
            if outer_boundary is not None:
                coords_elem = outer_boundary.find(".//kml:coordinates", KML_NS)
                if coords_elem is not None and coords_elem.text:
                    try:
                        coord_text = coords_elem.text.strip()
                        coords = []
                        for coord_line in coord_text.split():
                            parts = coord_line.split(",")
                            if len(parts) >= 2:
                                lon = float(parts[0].strip())
                                lat = float(parts[1].strip())
                                alt = float(parts[2].strip()) if len(parts) > 2 else 0.0
                                coords.append((lon, lat, alt))
                        
                        if len(coords) >= 2:
                            lines_data.append((coords, name or f"Polygon_{len(lines_data) + 1}"))
                            logger.debug("Найден полигон: %s с %d точками", name, len(coords))
                    except (ValueError, IndexError) as e:
                        logger.warning("Ошибка при обработке полигона: %s", e)
                        continue
    
    logger.info("Извлечено %d точек и %d линий из KML файла", len(points_data), len(lines_data))
    return points_data, lines_data



