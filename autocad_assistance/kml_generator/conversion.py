"""Conversion helpers related to KML export."""

from __future__ import annotations

from typing import Iterable, List, Optional, Tuple

import pandas as pd
import simplekml


def dataframe_to_kml(
    df: pd.DataFrame,
    lon: Iterable[float],
    lat: Iterable[float],
    output_path: str,
    altitudes: Optional[Iterable[float]] | None = None,
) -> None:
    """Persist dataframe rows as KML placemarks."""
    kml = simplekml.Kml()
    lons = list(lon)
    lats = list(lat)
    alts = list(altitudes) if altitudes is not None else None

    for idx, (row, longitude, latitude) in enumerate(zip(df.itertuples(index=False), lons, lats)):
        altitude = 0.0
        if alts is not None and idx < len(alts):
            try:
                altitude = float(alts[idx])
            except (TypeError, ValueError):
                altitude = 0.0

        name = str(getattr(row, "Point", getattr(row, "point", f"Point_{idx + 1}")))
        description = (
            f"<b>Point:</b> {name}<br/>"
            f"<b>X:</b> {getattr(row, 'X', getattr(row, 'x', ''))}<br/>"
            f"<b>Y:</b> {getattr(row, 'Y', getattr(row, 'y', ''))}<br/>"
            f"<b>H:</b> {getattr(row, 'Z', getattr(row, 'z', ''))}"
        )
        comment = getattr(row, "Coments", getattr(row, "Comment", ""))
        if comment:
            description += f"<br/><b>Comment:</b> {comment}"

        point = kml.newpoint(name=name, coords=[(longitude, latitude, altitude)])
        point.description = description

    kml.save(output_path)


def lines_to_kml(
    lines_data: List[Tuple[List[Tuple[float, float, float]], str]],
    transformer,
    output_path: str,
) -> None:
    """
    Конвертирует линии, круги и блоки из DXF в KML формат.
    
    Args:
        lines_data: Список кортежей (координаты точек линии/круга/блока, имя слоя)
        transformer: Трансформер для конвертации координат из проекции DXF в WGS84
        output_path: Путь для сохранения KML файла
    """
    kml = simplekml.Kml()
    
    for line_idx, (coords, layer_name) in enumerate(lines_data):
        if len(coords) < 1:
            continue
        
        # Проверяем, является ли это точкой (блоком) - две одинаковые координаты
        is_point = len(coords) == 2 and coords[0] == coords[1]
        
        # Трансформируем координаты в WGS84
        x_values = [coord[0] for coord in coords]
        y_values = [coord[1] for coord in coords]
        
        try:
            lon_values, lat_values = transformer.transform(x_values, y_values)
        except Exception as e:
            # Если трансформация не удалась, пропускаем объект
            continue
        
        if is_point:
            # Создаем точку для блока или маленького круга
            alt = coords[0][2] if len(coords[0]) > 2 else 0.0
            point = kml.newpoint(
                name=f"Point_{line_idx + 1}_{layer_name}",
                description=f"<b>Layer:</b> {layer_name}<br/><b>Type:</b> Point (Block/Circle)",
                coords=[(lon_values[0], lat_values[0], alt)]
            )
        else:
            # Создаем координаты для KML (lon, lat, altitude)
            kml_coords = []
            for i, (lon, lat) in enumerate(zip(lon_values, lat_values)):
                alt = coords[i][2] if len(coords[i]) > 2 else 0.0
                kml_coords.append((lon, lat, alt))
            
            # Создаем линию в KML
            linestring = kml.newlinestring(
                name=f"Line_{line_idx + 1}_{layer_name}",
                description=f"<b>Layer:</b> {layer_name}<br/><b>Points:</b> {len(kml_coords)}",
                coords=kml_coords
            )
            linestring.altitudemode = simplekml.AltitudeMode.clamptoground
    
    kml.save(output_path)
