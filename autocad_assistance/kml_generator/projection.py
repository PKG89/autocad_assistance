"""Projection parsing utilities for KML flow."""

from __future__ import annotations

from typing import List, Optional

from pyproj import CRS


def parse_projection_text(text: str) -> CRS:
    cleaned = text.strip()
    if not cleaned:
        raise ValueError("Текст проекции пуст или содержит только пробелы")
    try:
        return CRS.from_wkt(cleaned)
    except Exception:
        pass
    try:
        return CRS.from_string(cleaned)
    except Exception as exc:
        raise ValueError("Не удалось распознать описание проекции") from exc


def build_crs_confirmation(crs: CRS, raw_text: str) -> str:
    name = crs.name or "Неизвестный CRS"
    if "?" in name and raw_text:
        first_part = raw_text.split(",", 1)[0]
        if "[" in first_part:
            candidate = first_part.split("[", 1)[-1].rstrip("]").strip('"')
            if candidate:
                name = candidate

    proj_dict = crs.to_dict()

    def pick(keys: List[str]) -> Optional[float]:
        for key in keys:
            if key in proj_dict:
                return proj_dict[key]
        return None

    def fmt(value: Optional[float], suffix: str = "") -> str:
        if value is None:
            return "—"
        try:
            return f"{float(value):.6f}{suffix}"
        except (TypeError, ValueError):
            return f"{value}{suffix}"

    lon0 = pick(["lon_0", "longitude_of_origin", "central_meridian"])
    lat0 = pick(["lat_0", "latitude_of_origin"])
    k0 = pick(["k", "k_0", "scale_factor"])
    false_easting = pick(["x_0", "false_easting"])
    false_northing = pick(["y_0", "false_northing"])

    lines = [
        "✅ Проекция успешно распознана.",
        f"CRS: {name}",
        f"Долгота начала: {fmt(lon0, '°')}",
        f"Широта начала: {fmt(lat0, '°')}",
        f"Scale factor: {fmt(k0)}",
        f"False easting: {fmt(false_easting, ' м')}",
        f"False northing: {fmt(false_northing, ' м')}",
        "Загрузите файл с точками в формате TXT/CSV.",
    ]
    return "\n".join(lines)
