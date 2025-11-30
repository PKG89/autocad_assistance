"""High level DXF generation entry point."""

import logging
import math
import os
import pathlib

import ezdxf
from ezdxf.audit import Auditor

from ..config import (
    TEMPLATE_BLOCKS_FILE,
    label_colors,
    sm_controller_config,
)

from .blocks import build_tower_blocks, get_block_properties
from .polylines import build_polyline_by_code, extract_structural_breaklines, build_vegetation_contours
from .surface import build_tin_surface
from .utils import resolve_scale

logger = logging.getLogger(__name__)


def get_text_scale(scale_factor: float) -> float:
    """Вычисляет размер текста в зависимости от масштаба."""
    # При масштабе 1:1000 (scale_factor = 1.0) размер текста должен быть 1.6
    # При масштабе 1:500 (scale_factor = 0.5) размер текста должен быть 0.8
    # При масштабе 1:5000 (scale_factor = 5.0) размер текста должен быть 8.0
    return 1.6 * scale_factor


def generate_dxf_ezdxf(final_data, output_dxf, scale_factor: float = 1.0, tin_settings: dict | None = None) -> None:
    """Generate a DXF file from prepared survey data."""
    # Используем настройки по умолчанию (все включено)
    settings = {
        "show_points": True,
        "show_codes": True, 
        "show_elevations": True,
        "show_comments": True,
        "show_blocks": True,
        "show_polylines": True,
        "show_towers": True,
        "layer_separation": True,
    }
    
    tin_settings = tin_settings or {}
    tin_enabled = bool(tin_settings.get("enabled", False))
    
    tin_scale_value = tin_settings.get("scale_value")
    if isinstance(tin_scale_value, str):
        try:
            tin_scale_value = int(float(tin_scale_value))
        except ValueError:
            tin_scale_value = None
    refine_tin = bool(tin_settings.get("refine"))

    # Вычисляем размеры текста
    text_scale = get_text_scale(scale_factor)
    logging.debug("CWD = %s", os.getcwd())
    logging.debug("Template absolute path = %s", pathlib.Path(TEMPLATE_BLOCKS_FILE).resolve())

    try:
        doc = ezdxf.readfile(TEMPLATE_BLOCKS_FILE)
    except Exception as exc:
        raise RuntimeError(
            f"Cannot open DXF template {TEMPLATE_BLOCKS_FILE}: {exc}"
        ) from exc

    msp = doc.modelspace()
    for entity in list(msp):
        msp.delete_entity(entity)

    scale_factor = max(scale_factor, 0.05)
    if not tin_scale_value:
        tin_scale_value = max(int(round(scale_factor * 1000)), 1)
    base_offsets = {
        "number": (0.5, 1.5),
        "code": (0.5, -1.5),
        "elevation": (0.5, 0.0),
        "comment": (0.5, -3.0),
    }
    offsets = {
        key: (dx * scale_factor, dy * scale_factor) for key, (dx, dy) in base_offsets.items()
    }

    vl_conf = sm_controller_config.get("vl_support", {})
    vl_codes = {c.lower() for c in vl_conf.get("codes", set())}
    bracing_codes = {c.lower() for c in vl_conf.get("bracing_codes", set())}
    distance_threshold = vl_conf.get("distance_threshold", 50.0)

    for idx, row in final_data.iterrows():
        try:
            x = float(row["X"])
            y = float(row["Y"])
            z = float(row["Z"])
        except (TypeError, ValueError):
            continue

        point_name = str(row["Point"])
        code = str(row["Code"])
        comment = str(row.get("Coments", "")).strip()
        pt_code = code.strip().lower()

        # Слой для точек
        point_layer = "Point" if settings.get("layer_separation", True) else "0"
        # Слой для имен точек
        name_layer = "Name" if settings.get("layer_separation", True) else "0"

        # Add a DXF point entity so the point is visible on the plan.
        if settings.get("show_points", True):
            msp.add_point(
                (x, y, z),
                dxfattribs={
                    "layer": point_layer,
                    "color": label_colors.get("Numbers", 7),
                },
            )

        # Добавляем текст с именем точки в отдельный слой Name
        if settings.get("show_points", True):
            number_text = msp.add_mtext(
                point_name,
                dxfattribs={
                    "layer": name_layer,
                    "char_height": 0.5,  # Фиксированная высота для имен точек
                    "style": "Simplex",
                    "color": label_colors.get("Numbers", 7),
                },
            )
            number_text.set_location((x + offsets["number"][0], y + offsets["number"][1], z))

        # Добавляем коды только если включено в настройках
        if settings.get("show_codes", True):
            code_text = msp.add_mtext(
                code,
                dxfattribs={
                    "layer": "Codes" if settings.get("layer_separation", True) else "0",
                    "char_height": 0.5,  # Фиксированная высота для кодов
                    "style": "Simplex",
                    "color": label_colors.get("Codes", 7),
                },
            )
            code_text.set_location((x + offsets["code"][0], y + offsets["code"][1], z))

        # Добавляем высоты только если включено в настройках
        if settings.get("show_elevations", True):
            elevation_text = msp.add_mtext(
                f"{z:.3f}",
                dxfattribs={
                    "layer": "Elevations" if settings.get("layer_separation", True) else "0",
                    "char_height": 0.5,  # Фиксированная высота для высот
                    "style": "Simplex",
                    "color": label_colors.get("Elevations", 7),
                },
            )
            elevation_text.set_location((x + offsets["elevation"][0], y + offsets["elevation"][1], z))

        # Добавляем комментарии только если включено в настройках
        if settings.get("show_comments", True) and comment:
            comment_text = msp.add_mtext(
                comment,
                dxfattribs={
                    "layer": "Comments" if settings.get("layer_separation", True) else "0",
                    "char_height": 0.5,  # Фиксированная высота для комментариев
                    "style": "Simplex",
                    "color": label_colors.get("Comments", 7),
                },
            )
            comment_text.set_location((x + offsets["comment"][0], y + offsets["comment"][1], z))

        # Добавляем блоки только если включено в настройках
        if settings.get("show_blocks", True):
            if pt_code in vl_codes:
                candidates = []
                for j, other in final_data.iterrows():
                    if j == idx:
                        continue
                    try:
                        ox = float(other["X"])
                        oy = float(other["Y"])
                        other_code = str(other["Code"]).strip().lower()
                    except (TypeError, ValueError):
                        continue
                    if other_code in bracing_codes:
                        dist = math.hypot(ox - x, oy - y)
                        if dist <= distance_threshold:
                            angle = math.degrees(math.atan2(oy - y, ox - x))
                            candidates.append((dist, angle))
                candidates.sort(key=lambda item: item[0])
                count = min(len(candidates), 2)
                if count == 0:
                    rotation_angle = 0.0
                elif count == 1:
                    rotation_angle = candidates[0][1]
                else:
                    rotation_angle = (candidates[0][1] + candidates[1][1]) / 2.0
                block_name = vl_conf.get("blocks", {}).get(count)
                scale_value = resolve_scale(vl_conf.get("scale", 1.0), z) * scale_factor
                if block_name:
                    block_props = get_block_properties(doc, block_name)
                    msp.add_blockref(
                        block_name,
                        (x, y),
                        dxfattribs={
                            "layer": block_props["layer"] if settings.get("layer_separation", True) else "0",
                            "color": block_props["color"],
                            "xscale": scale_value,
                            "yscale": scale_value,
                            "zscale": scale_value,
                            "rotation": rotation_angle,
                        },
                    )
            else:
                for mapping in sm_controller_config.get("block_mapping", {}).values():
                    codes_set = {c.lower() for c in mapping.get("code", set())}
                    if pt_code not in codes_set:
                        continue
                    scale_value = resolve_scale(mapping.get("scale", 1.0), z) * scale_factor
                    block_name = mapping.get("name")
                    if not block_name:
                        continue
                    block_props = get_block_properties(doc, block_name)
                    block_layer = block_props["layer"] if settings.get("layer_separation", True) else "0"
                    msp.add_blockref(
                        block_name,
                        (x, y),
                        dxfattribs={
                            "layer": block_layer,
                            "color": block_props["color"],
                            "xscale": scale_value,
                            "yscale": scale_value,
                            "zscale": scale_value,
                            "rotation": 0.0,
                        },
                    )
                    # Для задвижек (zadv) добавляем текст с номером в том же слое, что и блок
                    if pt_code in {"zadv", "zad", "задв", "зад"} and comment:
                        # Смещение текста справа от блока
                        text_offset_x = 1.5 * scale_factor
                        text_offset_y = 0.0
                        # Формируем текст с префиксом "№"
                        text_content = f"№{comment}"
                        zadv_text = msp.add_mtext(
                            text_content,
                            dxfattribs={
                                "layer": block_layer,
                                "char_height": 0.5,  # Фиксированная высота для текста задвижки
                                "style": "Simplex",
                                "color": block_props["color"],
                            },
                        )
                        zadv_text.set_location((x + text_offset_x, y + text_offset_y, z))
                    break

    # Добавляем полилинии и собираем структурные линии
    breaklines = []
    if settings.get("show_polylines", True):
        breaklines = build_polyline_by_code(final_data, msp, doc, scale_factor, text_scale)
    else:
        breaklines = extract_structural_breaklines(final_data)

    # Добавляем контуры растительности с заливкой
    if settings.get("show_polylines", True):
        try:
            build_vegetation_contours(final_data, msp, doc, scale_factor)
        except Exception as exc:
            logger.warning("Ошибка при построении контуров растительности: %s", exc)

    # Строим TIN если включено - используем все точки из файла
    if tin_enabled:
        try:
            logger.info("TIN: построение поверхности из всех точек файла")
            
            contour_interval = float(tin_settings.get("contour_interval", 1.0))
            
            tin_result = build_tin_surface(
                final_data=final_data,
                msp=msp,
                selected_codes=None,  # None = использовать все точки
                scale_value=tin_scale_value,
                refine_enabled=refine_tin,
                breaklines=breaklines,
                contour_interval=contour_interval,
            )
            logger.info(
                "TIN: points=%d triangles=%d refined_points=%d refined_triangles=%d",
                tin_result.base_points,
                tin_result.base_triangles,
                tin_result.refined_points,
                tin_result.refined_triangles,
            )
        except Exception as exc:
            logger.exception("Ошибка при построении TIN-поверхности: %s", exc)

    # Добавляем башни/вышки только если включено в настройках
    if settings.get("show_towers", True):
        build_tower_blocks(final_data, msp, doc)

    auditor: Auditor = doc.audit()
    if auditor.has_errors:
        logger.warning(
            "DXF audit: fixed %d errors, %d unresolved",
            auditor.fixed_error_count,
            auditor.unfixed_error_count,
        )

    # Проверяем минимальный размер текста для подписей к линиям (они используют text_scale)
    min_text_height = text_scale * 0.1  # Минимальный размер для подписей к линиям
    for entity in msp.query("MTEXT"):
        # Не меняем фиксированные размеры (0.5 для point, elevation, codes, comments)
        if entity.dxf.char_height < 0.5:
            continue
        # Проверяем только подписи к линиям (которые используют text_scale)
        if entity.dxf.char_height < min_text_height:
            entity.dxf.char_height = min_text_height

    for polyline in msp.query("POLYLINE"):
        vertices_attr = getattr(polyline, "vertices")
        vertices = list(vertices_attr()) if callable(vertices_attr) else list(vertices_attr)
        if not vertices:
            continue
        
        # Получаем координаты вершин
        def get_vertex_location(vertex):
            """Получает координаты вершины полилинии."""
            try:
                if hasattr(vertex, 'dxf') and hasattr(vertex.dxf, 'location'):
                    loc = vertex.dxf.location
                    return (loc.x, loc.y, loc.z if hasattr(loc, 'z') else 0.0)
                elif hasattr(vertex, 'location'):
                    loc = vertex.location
                    return (loc.x, loc.y, loc.z if hasattr(loc, 'z') else 0.0)
                else:
                    # Если это уже кортеж координат
                    return tuple(vertex) if isinstance(vertex, (tuple, list)) else None
            except Exception:
                return None
        
        vertex_locations = []
        for vertex in vertices:
            loc = get_vertex_location(vertex)
            if loc is not None:
                vertex_locations.append(loc)
        
        if not vertex_locations:
            continue
        
        # Удаляем дубликаты соседних вершин
        unique = [vertex_locations[0]]
        for loc in vertex_locations[1:]:
            prev_loc = unique[-1]
            # Проверяем, что координаты отличаются (с небольшой погрешностью)
            if abs(loc[0] - prev_loc[0]) > 0.001 or abs(loc[1] - prev_loc[1]) > 0.001:
                unique.append(loc)
        
        if len(unique) != len(vertex_locations):
            # Сохраняем атрибуты перед удалением
            attribs = polyline.dxfattribs()
            # Удаляем полилинию через modelspace
            msp.delete_entity(polyline)
            msp.add_polyline3d(
                unique,
                dxfattribs=attribs,
            )

    doc.header["$ACADVER"] = "AC1032"
    doc.saveas(output_dxf)
