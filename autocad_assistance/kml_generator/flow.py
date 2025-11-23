"""Conversation handlers for the KML workflow."""

from __future__ import annotations

import logging
import os
import tempfile
from functools import partial
from itertools import islice
from typing import Awaitable, Callable, Optional, Sequence

import chardet
from pyproj import CRS, Transformer
from pyproj.exceptions import CRSError, ProjError
from telegram import InputFile, Update
from telegram.ext import ContextTypes

from ..keyboard import (
    BUTTON_DOWNLOAD_TEMPLATE,
    BUTTON_HELP,
    BUTTON_INSTRUCTION,
    BUTTON_KML,
    BUTTON_NEW_DXF,
    BUTTON_RESET_STATE,
    MAIN_MENU_KEYBOARD,
)
from ..state import (
    STATE_FILE,
    STATE_KML_POINTS,
    STATE_KML_PROJECTION,
    reset_kml_context,
)
from .. import db
from .conversion import dataframe_to_kml, lines_to_kml
from .dxf_reader import load_dxf_lines
from .geometry import infer_coordinate_order
from .io import load_kml_points, to_float
from .projection import build_crs_confirmation, parse_projection_text

logger = logging.getLogger(__name__)

MenuRouter = Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[Optional[int]]]
_MENU_BUTTONS = {
    BUTTON_NEW_DXF,
    BUTTON_RESET_STATE,
    BUTTON_DOWNLOAD_TEMPLATE,
    BUTTON_HELP,
    BUTTON_INSTRUCTION,
    BUTTON_KML,
}


def _extract_central_meridian(crs: Optional[CRS]) -> Optional[float]:
    if crs is None:
        return None
    try:
        proj_dict = crs.to_dict()
    except Exception:
        return None
    for key in ("lon_0", "longitude_of_origin", "central_meridian"):
        raw_value = proj_dict.get(key)
        if raw_value is None:
            continue
        try:
            return float(raw_value)
        except (TypeError, ValueError):
            continue
    return None


def _coordinates_look_implausible(
    lon_values: Sequence[float],
    lat_values: Sequence[float],
    lon_hint: Optional[float],
    sample_limit: int = 5,
) -> bool:
    sample_pairs = list(islice(zip(lon_values, lat_values), sample_limit))
    if not sample_pairs:
        return False

    for lon, lat in sample_pairs:
        lon = float(lon)
        lat = float(lat)
        if not (-180.0 <= lon <= 180.0 and -90.0 <= lat <= 90.0):
            return True

    if lon_hint is not None:
        threshold = 30.0
        for lon, _ in sample_pairs:
            try:
                if abs(float(lon) - lon_hint) > threshold:
                    return True
            except (TypeError, ValueError):
                return True

    return False


def with_menu_router(handler, menu_router: Optional[MenuRouter]) -> Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[int]]:
    if menu_router is None:
        return handler
    return partial(handler, menu_router=menu_router)


async def start_kml_flow(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    reset_kml_context(context)
    context.user_data["kml_mode"] = True
    message = update.message if update.message else update.callback_query.message
    user = update.effective_user
    if user:
        db.record_usage(user.id, user.username, "menu_kml")
    logger.info("KML flow initiated by %s", user.id if user else "unknown")
    instruction_text = (
        "📍 *Последовательность работы с KML*\n\n"
        "1. Отправьте описание проекции (WKT/PROJ). При необходимости можно воспользоваться ботом @findprjbot или загрузить *.prj*.\n"
        "2. Дождитесь подтверждения проекции.\n"
        "3. Отправьте файл:\n"
        "   • Текстовый файл (TXT/CSV/Excel) с колонками Point, X, Y, Z[, Comment] - для точек\n"
        "   • DXF файл с линиями (LINE, POLYLINE, LWPOLYLINE) - для линий\n"
        "4. Получите KML файл с координатами в формате WGS84.\n\n"
        "Если нужно, опишите проекцию (WKT/PROJ4/EPSG). Если передумали — /cancel."
    )
    await message.reply_text(instruction_text, parse_mode="Markdown", reply_markup=MAIN_MENU_KEYBOARD)
    return STATE_KML_PROJECTION


async def handle_kml_projection(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    menu_router: Optional[MenuRouter] = None,
) -> int:
    logger.info("handle_kml_projection triggered; kml_mode=%s", context.user_data.get("kml_mode"))
    text = (update.message.text or "").strip()
    if text in _MENU_BUTTONS and menu_router:
        result = await menu_router(update, context)
        if result is not None:
            return result
        return STATE_KML_PROJECTION

    logger.info("Received projection text: %s", text[:100] + "..." if len(text) > 100 else text)
    if text.lower() in {"/cancel", "cancel"}:
        reset_kml_context(context)
        await update.message.reply_text("Отмена операции.", reply_markup=MAIN_MENU_KEYBOARD)
        return STATE_FILE

    try:
        crs = parse_projection_text(text)
        transformer = Transformer.from_crs(crs, CRS.from_epsg(4326), always_xy=True)
    except (ValueError, CRSError, ProjError) as exc:
        await update.message.reply_text(
            f"Не удалось распознать описание проекции: {exc}.\nПредоставьте WKT, PROJ4 или код EPSG.",
            reply_markup=MAIN_MENU_KEYBOARD,
        )
        return STATE_KML_PROJECTION

    context.user_data["kml_crs"] = crs
    context.user_data["kml_transformer"] = transformer
    context.user_data["kml_projection_raw"] = text
    context.user_data["kml_lon_hint"] = _extract_central_meridian(crs)
    logger.info("KML projection accepted from %s", update.effective_user.id if update.effective_user else "unknown")
    await update.message.reply_text(
        "✅ Проекция сохранена. Теперь загрузите файл с точками.",
        reply_markup=MAIN_MENU_KEYBOARD,
    )
    confirmation_text = build_crs_confirmation(crs, text)
    await update.message.reply_text(confirmation_text, reply_markup=MAIN_MENU_KEYBOARD)

    return STATE_KML_POINTS


async def handle_wrong_input_in_kml_projection(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    await update.message.reply_text(
        "Загрузите текст с описанием проекции (WKT/PROJ/EPSG). Для выхода используйте /cancel.",
        reply_markup=MAIN_MENU_KEYBOARD,
    )
    return STATE_KML_PROJECTION


async def handle_kml_points(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    menu_router: Optional[MenuRouter] = None,
) -> int:
    text = (update.message.text or "").strip()
    if text in _MENU_BUTTONS and menu_router:
        result = await menu_router(update, context)
        if result is not None:
            return result
        return STATE_KML_POINTS

    transformer: Optional[Transformer] = context.user_data.get("kml_transformer")
    crs: Optional[CRS] = context.user_data.get("kml_crs")
    if transformer is None or crs is None:
        await update.message.reply_text(
            "Сначала отправьте описание проекции.",
            reply_markup=MAIN_MENU_KEYBOARD,
        )
        return STATE_KML_PROJECTION

    document = update.message.document
    if not document:
        await update.message.reply_text(
            "Отправьте TXT/CSV/Excel файл с точками или DXF файл с линиями.",
            reply_markup=MAIN_MENU_KEYBOARD,
        )
        return STATE_KML_POINTS

    file = await document.get_file()
    temp_dir = tempfile.mkdtemp()
    file_path = os.path.join(temp_dir, document.file_name)
    await file.download_to_drive(custom_path=file_path)

    # Проверяем расширение файла
    file_ext = os.path.splitext(document.file_name)[1].lower()
    
    # Обработка DXF файлов
    if file_ext == ".dxf":
        try:
            lines_data = load_dxf_lines(file_path)
            if not lines_data:
                await update.message.reply_text(
                    "Не удалось найти линии в DXF файле. Убедитесь, что файл содержит LINE, POLYLINE или LWPOLYLINE.",
                    reply_markup=MAIN_MENU_KEYBOARD,
                )
                return STATE_KML_POINTS
            
            # Конвертируем линии в KML
            kml_path = os.path.join(temp_dir, os.path.splitext(document.file_name)[0] + ".kml")
            lines_to_kml(lines_data, transformer, kml_path)
            
            with open(kml_path, "rb") as handle:
                await update.message.chat.send_document(
                    document=InputFile(handle, filename=os.path.basename(kml_path)),
                    caption=(
                        f"✅ KML сформирован из DXF файла (CRS: {crs.name or 'неизвестно'}).\n"
                        f"Обработано линий: {len(lines_data)}"
                    ),
                    reply_markup=MAIN_MENU_KEYBOARD,
                )
            
            user = update.effective_user
            if user:
                db.record_usage(
                    user.id,
                    user.username,
                    "KML_generated_from_DXF",
                    file_uploaded=document.file_name,
                    file_generated=os.path.basename(kml_path),
                )
            
            await update.message.chat.send_message(
                "Готово! Пришлите новый файл или /cancel, чтобы выйти из режима KML.",
                reply_markup=MAIN_MENU_KEYBOARD,
            )
            return STATE_KML_POINTS
        except Exception as exc:
            logger.exception("Ошибка при обработке DXF файла")
            await update.message.reply_text(
                f"Ошибка при обработке DXF файла: {exc}",
                reply_markup=MAIN_MENU_KEYBOARD,
            )
            return STATE_KML_POINTS

    # Обработка текстовых файлов (CSV/TXT/Excel)
    with open(file_path, "rb") as handle:
        raw = handle.read(10000)
    encoding_info = chardet.detect(raw)
    encoding = encoding_info.get("encoding", "utf-8") or "utf-8"
    if encoding.lower() == "ascii":
        encoding = "cp1251"

    df = load_kml_points(file_path, encoding)
    if df.empty:
        await update.message.reply_text(
            "Не получилось прочитать точки из файла. Убедитесь, что есть столбцы Point, X, Y, Z[, Comment].",
            reply_markup=MAIN_MENU_KEYBOARD,
        )
        return STATE_KML_POINTS

    try:
        logger.debug("KML DataFrame columns: %s", df.columns.tolist())
        logger.debug("KML DataFrame shape: %s", df.shape)
        logger.debug("KML sample:\n%s", df.head())

        x_values = df["X"].apply(to_float).tolist()
        y_values = df["Y"].apply(to_float).tolist()
        z_values = df["Z"].apply(to_float).tolist()
    except ValueError as exc:
        logger.exception("Failed to convert coordinates: %s", exc)
        await update.message.reply_text(
            "Не удалось интерпретировать координаты. Проверьте, что X/Y/Z числовые.",
            reply_markup=MAIN_MENU_KEYBOARD,
        )
        return STATE_KML_POINTS

    notice_messages = []
    swap, warning = infer_coordinate_order(x_values, y_values, transformer)
    if swap:
        x_values, y_values = y_values, x_values
        df["X"], df["Y"] = df["Y"], df["X"]
        notice_messages.append("Обнаружена перестановка координат X/Y. Столбцы автоматически поменяны местами.")
    if warning:
        notice_messages.append("Координаты выглядят подозрительно. Проверьте правильность данных.")

    try:
        lon, lat = transformer.transform(x_values, y_values)
        lon_hint = context.user_data.get("kml_lon_hint")
        suspicious = _coordinates_look_implausible(lon, lat, lon_hint)
        if suspicious and not swap:
            logger.debug("Coordinates look suspicious; trying Y/X order...")
            lon_alt, lat_alt = transformer.transform(y_values, x_values)
            lon, lat = lon_alt, lat_alt
            df["X"], df["Y"] = df["Y"], df["X"]
            x_values, y_values = y_values, x_values
            swap = True
            notice_messages.append(
                "Координаты в исходном порядке выглядели неверно, столбцы X/Y переставлены."
            )
        elif suspicious:
            notice_messages.append(
                "Координаты остаются вне ожидаемого диапазона; проверьте исходные данные."
            )
        logger.debug("Transformed coordinates (first 5): %s", list(zip(lon[:5], lat[:5])))
    except Exception as exc:
        logger.exception("Transformation error")
        await update.message.reply_text(
            f"Ошибка трансформации координат: {exc}",
            reply_markup=MAIN_MENU_KEYBOARD,
        )
        return STATE_KML_POINTS

    kml_path = os.path.join(temp_dir, os.path.splitext(document.file_name)[0] + ".kml")
    dataframe_to_kml(df, lon, lat, kml_path, altitudes=z_values)

    with open(kml_path, "rb") as handle:
        await update.message.chat.send_document(
            document=InputFile(handle, filename=os.path.basename(kml_path)),
            caption=(
                f"✅ KML сформирован (CRS: {crs.name or 'неизвестно'})."
                + ("\nПроизводилась перестановка X/Y." if swap else "")
            ),
            reply_markup=MAIN_MENU_KEYBOARD,
        )

    for notice in notice_messages:
        await update.message.chat.send_message(notice, reply_markup=MAIN_MENU_KEYBOARD)

    user = update.effective_user
    if user:
        db.record_usage(
            user.id,
            user.username,
            "KML_generated",
            file_uploaded=document.file_name,
            file_generated=os.path.basename(kml_path),
        )

    await update.message.chat.send_message(
        "Готово! Пришлите новый файл или /cancel, чтобы выйти из режима KML.",
        reply_markup=MAIN_MENU_KEYBOARD,
    )
    return STATE_KML_POINTS


async def handle_wrong_input_in_kml_points(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    await update.message.reply_text(
        "Отправьте файл с точками (TXT/CSV/Excel) или DXF файл с линиями. Для выхода выполните /cancel.",
        reply_markup=MAIN_MENU_KEYBOARD,
    )
    return STATE_KML_POINTS
