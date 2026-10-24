import os
import tempfile
import chardet
import csv
import re
from typing import List, Optional, Set

from telegram import Update, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from autocad_assistance.keyboard import (
    BUTTON_KML,
    BUTTON_NEW_DXF,
    BUTTON_DOWNLOAD_TEMPLATE,
    BUTTON_HELP,
    BUTTON_INSTRUCTION,
    BUTTON_RESET_STATE,
    MAIN_MENU_KEYBOARD,
    SCALE_OPTIONS,
    SCALE_TEXT_MAP,
    build_mapping_keyboard,
    build_scale_keyboard,
    build_tin_codes_keyboard,
)
from autocad_assistance.state import (
    BASE_SCALE,
    STATE_FILE,
    STATE_MAPPING,
    STATE_SCALE,
    STATE_WORKFLOW,
    
    reset_workflow_state,
    show_workflow_menu,
)
from autocad_assistance.kml_generator.kml_handlers import (
    handle_kml_points as flow_handle_kml_points,
    handle_kml_projection as flow_handle_kml_projection,
    start_kml_flow,
    with_menu_router,
)
from autocad_assistance.bot.start import start, help_command, send_sinokod_document
from autocad_assistance import db

import logging
logger = logging.getLogger(__name__)


TIN_SELECTION_TEXT = (
    "Выберите коды точек, которые будут использованы для построения поверхности TIN. "
    "Нажмите на код, чтобы включить или выключить его. После выбора нажмите «Готово»."
)
TIN_CODES_PREVIEW_LIMIT = 6


def _collect_available_codes(final_data) -> list[str]:
    if final_data is None:
        return []
    try:
        codes_series = final_data["Code"].dropna().astype(str)
    except Exception:
        return []
    unique = sorted({code.strip() for code in codes_series if code and code.strip()})
    return unique


def _format_selected_codes(codes: list[str], selected_indexes: Set[int]) -> str:
    if not codes or not selected_indexes:
        return "Пока ничего не выбрано."
    selected_codes = [codes[idx] for idx in sorted(selected_indexes) if 0 <= idx < len(codes)]
    if not selected_codes:
        return "Пока ничего не выбрано."
    if len(selected_codes) <= TIN_CODES_PREVIEW_LIMIT:
        preview = ", ".join(selected_codes)
    else:
        preview = ", ".join(selected_codes[:TIN_CODES_PREVIEW_LIMIT]) + f" … (+{len(selected_codes) - TIN_CODES_PREVIEW_LIMIT})"
    return f"Выбрано кодов: {len(selected_codes)}\n{preview}"


def detect_delimiter(line: str) -> str:
    for candidate in ("\t", ";", ",", "|"):
        if candidate in line:
            return candidate
    return " "


async def process_main_menu_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[int]:
    text = (update.message.text or "").strip()
    user = update.effective_user
    logger.info("main menu text: %s", text)

    # Обработка альтернативных символов эмодзи (проблема с отображением в некоторых клиентах)
    if text == "♻️   ♻️":  # Альтернативное отображение для BUTTON_NEW_DXF
        text = BUTTON_NEW_DXF
        logger.info("Converted alternative emoji to BUTTON_NEW_DXF")

    if text == BUTTON_NEW_DXF:
        if user:
            db.record_usage(user.id, user.username, "menu_new_dxf")
        reset_workflow_state(context)
        await update.message.reply_text(
            "Отправьте TXT/CSV файл с исходными данными или KML файл для конвертации в DXF. После загрузки начнётся настройка.",
            reply_markup=MAIN_MENU_KEYBOARD,
        )
        return STATE_FILE
    if text == BUTTON_DOWNLOAD_TEMPLATE:
        if user:
            db.record_usage(user.id, user.username, "menu_download_template")
        chat = update.effective_chat
        if await send_sinokod_document(chat):
            await update.message.reply_text(
                "Шаблон SinoKOD отправлен. Проверьте список файлов в чате.",
                reply_markup=MAIN_MENU_KEYBOARD,
            )
        else:
            await update.message.reply_text(
                "Файл SinoKOD.txt не найден. Обратитесь к администратору.",
                reply_markup=MAIN_MENU_KEYBOARD,
            )
        return None
    if text == BUTTON_KML:
        return await start_kml_flow(update, context)
    if text == BUTTON_INSTRUCTION:
        if user:
            db.record_usage(user.id, user.username, "menu_instruction")
        instructions_text = (
            "Инструкция по работе\n"
            "1. Подготовьте TXT/CSV файл с колонками: имя точки, X, Y, Z и код.\n"
            "2. Загрузите файл и сопоставьте поля.\n"
            "3. Выберите масштаб (1:500 / 1:1000 / 1:5000) и создайте DXF."
        )
        await update.message.reply_text(instructions_text, reply_markup=MAIN_MENU_KEYBOARD)
        return None
    if text == BUTTON_HELP:
        await help_command(update, context)
        return None
    if text == BUTTON_RESET_STATE:
        if user:
            db.record_usage(user.id, user.username, "menu_reset_state")
        reset_workflow_state(context)
        await start(update, context)
        return STATE_FILE
    
    # Обработка неизвестного текста
    logger.warning("Unknown main menu text: %s", text)
    await update.message.reply_text(
        "Неизвестная команда. Используйте кнопки меню ниже.",
        reply_markup=MAIN_MENU_KEYBOARD,
    )
    return None


handle_kml_projection = with_menu_router(flow_handle_kml_projection, process_main_menu_text)
handle_kml_points = with_menu_router(flow_handle_kml_points, process_main_menu_text)


async def handle_file_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка текста в режиме STATE_FILE (для проекции KML->DXF)."""
    # Проверяем, находимся ли мы в режиме конвертации KML в DXF
    if context.user_data.get("kml_to_dxf_mode"):
        text = (update.message.text or "").strip()
        
        # Проверяем, не является ли это командой меню
        if text in {
            BUTTON_NEW_DXF,
            BUTTON_RESET_STATE,
            BUTTON_DOWNLOAD_TEMPLATE,
            BUTTON_HELP,
            BUTTON_INSTRUCTION,
            BUTTON_KML,
        }:
            return await process_main_menu_text(update, context) or STATE_FILE
        
        # Пытаемся распарсить проекцию
        try:
            from autocad_assistance.kml_generator.kml_reader import load_kml_data
            from autocad_assistance.kml_generator.kml_to_dxf import kml_to_dxf
            from autocad_assistance.kml_generator.projection import parse_projection_text
            from pyproj import CRS, Transformer
            
            crs = parse_projection_text(text)
            transformer = Transformer.from_crs(CRS.from_epsg(4326), crs, always_xy=True)
            
            # Сохраняем проекцию для будущего использования
            context.user_data["dxf_projection"] = crs
            context.user_data["dxf_transformer"] = transformer
            
            # Загружаем KML данные
            kml_file_path = context.user_data.get("kml_file_path")
            if not kml_file_path:
                await update.message.reply_text(
                    "Ошибка: файл KML не найден. Пожалуйста, загрузите файл заново.",
                    reply_markup=MAIN_MENU_KEYBOARD,
                )
                context.user_data.pop("kml_to_dxf_mode", None)
                return STATE_FILE
            
            points_data, lines_data = load_kml_data(kml_file_path)
            
            # Конвертируем в DXF
            import tempfile
            import os
            temp_dir = tempfile.mkdtemp()
            output_filename = os.path.splitext(os.path.basename(kml_file_path))[0] + ".dxf"
            output_path = os.path.join(temp_dir, output_filename)
            
            kml_to_dxf(points_data, lines_data, transformer, output_path)
            
            # Отправляем DXF файл
            with open(output_path, "rb") as dxf_file:
                await update.message.chat.send_document(
                    document=dxf_file,
                    filename=output_filename,
                    caption=f"✅ DXF файл создан из KML\n📊 Обработано точек: {len(points_data)}, линий: {len(lines_data)}",
                    reply_markup=MAIN_MENU_KEYBOARD,
                )
            
            # Очищаем режим
            context.user_data.pop("kml_to_dxf_mode", None)
            context.user_data.pop("kml_file_path", None)
            
            await update.message.reply_text(
                "Готово! Можете загрузить новый файл или выбрать действие из меню.",
                reply_markup=MAIN_MENU_KEYBOARD,
            )
            return STATE_FILE
            
        except Exception as exc:
            logger.exception("Ошибка при обработке проекции для KML->DXF")
            await update.message.reply_text(
                f"Ошибка при обработке проекции: {exc}\nПопробуйте еще раз или отправьте /cancel.",
                reply_markup=MAIN_MENU_KEYBOARD,
            )
            return STATE_FILE
    
    # Если не в режиме KML->DXF, передаем обработку дальше
    return None


async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    db.record_usage(user.id, user.username, "handle_file")
    if context.user_data.get("kml_mode"):
        return await handle_kml_points(update, context)
    document = update.message.document
    if not document:
        await update.message.reply_text("Пожалуйста, отправьте файл как документ.")
        return STATE_FILE

    file = await document.get_file()
    temp_dir = tempfile.mkdtemp()
    file_path = os.path.join(temp_dir, document.file_name)
    await file.download_to_drive(custom_path=file_path)
    context.user_data["file_path"] = file_path
    context.user_data["original_filename"] = document.file_name
    
    # Проверяем, является ли файл KML
    file_ext = os.path.splitext(document.file_name)[1].lower()
    if file_ext == ".kml":
        # Для KML файлов нужна проекция для конвертации в DXF
        from autocad_assistance.kml_generator.kml_reader import load_kml_data
        from autocad_assistance.kml_generator.kml_to_dxf import kml_to_dxf
        from autocad_assistance.kml_generator.projection import parse_projection_text
        from pyproj import CRS, Transformer
        
        # Проверяем, есть ли уже проекция в контексте
        if "dxf_projection" in context.user_data and "dxf_transformer" in context.user_data:
            # Проекция уже есть, конвертируем сразу
            try:
                points_data, lines_data = load_kml_data(file_path)
                transformer = context.user_data["dxf_transformer"]
                
                output_filename = os.path.splitext(document.file_name)[0] + ".dxf"
                output_path = os.path.join(temp_dir, output_filename)
                
                kml_to_dxf(points_data, lines_data, transformer, output_path)
                
                with open(output_path, "rb") as dxf_file:
                    await update.message.chat.send_document(
                        document=dxf_file,
                        filename=output_filename,
                        caption=f"✅ DXF файл создан из KML\n📊 Обработано точек: {len(points_data)}, линий: {len(lines_data)}",
                        reply_markup=MAIN_MENU_KEYBOARD,
                    )
                
                await update.message.reply_text(
                    "Готово! Можете загрузить новый файл или выбрать действие из меню.",
                    reply_markup=MAIN_MENU_KEYBOARD,
                )
                return STATE_FILE
            except Exception as exc:
                logger.exception("Ошибка при конвертации KML в DXF")
                await update.message.reply_text(
                    f"Ошибка при конвертации KML в DXF: {exc}",
                    reply_markup=MAIN_MENU_KEYBOARD,
                )
                return STATE_FILE
        else:
            # Нужно запросить проекцию
            context.user_data["kml_to_dxf_mode"] = True
            context.user_data["kml_file_path"] = file_path
            await update.message.reply_text(
                "Для конвертации KML в DXF нужна проекция.\n"
                "Отправьте описание проекции (WKT/PROJ/EPSG).",
                reply_markup=MAIN_MENU_KEYBOARD,
            )
            return STATE_FILE

    with open(file_path, "rb") as source:
        raw_data = source.read()
    # Prefer UTF-8 (including BOM) and only fall back to chardet if decoding fails.
    try:
        raw_data.decode("utf-8-sig")
        encoding = "utf-8-sig"
    except UnicodeDecodeError:
        result_encoding = chardet.detect(raw_data) or {}
        encoding = result_encoding.get("encoding") or "utf-8"
        if isinstance(encoding, str) and encoding.lower() == "ascii":
            encoding = "cp1251"
    context.user_data["encoding"] = encoding

    delimiter = " "
    with open(file_path, "r", encoding=encoding) as source:
        for line in source:
            stripped = line.strip()
            if stripped:
                delimiter = detect_delimiter(stripped)
                logger.info("Определён разделитель: %s", repr(delimiter))
                break

    rows = []
    with open(file_path, "r", encoding=encoding) as source:
        reader = csv.reader(source, delimiter=delimiter, skipinitialspace=True)
        for row in reader:
            cleaned = [cell.strip() for cell in row]
            if delimiter == " ":
                cleaned = [cell for cell in cleaned if cell]
            # A header is not a survey point; preserve empty data columns.
            if not rows and [cell.lower() for cell in cleaned[1:4]] in (["x", "y", "z"], ["y", "x", "z"]):
                continue
            if len(cleaned) >= 4:
                rows.append(cleaned)

    if not rows:
        await update.message.reply_text("Файл не содержит достаточного количества данных.")
        return ConversationHandler.END

    import pandas as pd

    data_initial = pd.DataFrame(rows)
    context.user_data["data_initial"] = data_initial
    context.user_data["data_initial_count"] = len(data_initial)
    context.user_data["mapping_ready"] = False
    context.user_data["final_data"] = None
    context.user_data.setdefault("scale_value", BASE_SCALE)

    await update.message.reply_text(
        f"Файл *{document.file_name}* получен. Обнаружено {data_initial.shape[1]} колонок.",
        parse_mode="Markdown",
        reply_markup=MAIN_MENU_KEYBOARD,
    )
    await show_workflow_menu(update, context, notice="Выберите следующий шаг: соответствие, масштаб или генерация.")
    return STATE_WORKFLOW


async def _prompt_scale_selection(update, context) -> InlineKeyboardMarkup:
    keyboard = build_scale_keyboard()
    prompt = "Выберите масштаб: 1:500, 1:1000 / 1:2000 или 1:5000"
    if update.callback_query:
        await update.callback_query.message.reply_text(prompt, reply_markup=keyboard)
    else:
        await update.message.reply_text(prompt, reply_markup=keyboard)
    return keyboard


async def _prompt_mapping_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data_initial = context.user_data.get("data_initial")
    if data_initial is None:
        await update.effective_chat.send_message("Сначала загрузите файл с данными.", reply_markup=MAIN_MENU_KEYBOARD)
        return
    text = (
        f"Выберите вариант соответствия колонок (найдено {data_initial.shape[1]} колонок):\n\n"
        "1 — Point, X, Y, Z, Code\n"
        "2 — Point, Y, X, Z, Code"
    )
    if update.callback_query:
        await update.callback_query.message.reply_text(text, reply_markup=build_mapping_keyboard())
    else:
        await update.message.reply_text(text, reply_markup=build_mapping_keyboard())


async def handle_mapping_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    db.record_usage(user.id, user.username, "handle_mapping_callback")
    query = update.callback_query
    await query.answer()
    mapping_choice = query.data
    # If the workflow mapping button was pressed, prompt the mapping
    # keyboard so the user can choose 1 or 2.
    if mapping_choice == "workflow_mapping":
        await _prompt_mapping_selection(update, context)
        return STATE_MAPPING
    default_mapping = {"Point": 0, "X": 1, "Y": 2, "Z": 3, "Code": 4}
    swapped_mapping = {"Point": 0, "Y": 1, "X": 2, "Z": 3, "Code": 4}
    if mapping_choice == "1":
        mapping = default_mapping
    elif mapping_choice == "2":
        mapping = swapped_mapping
    else:
        await query.edit_message_text("Выберите один из предложенных вариантов.")
        return STATE_MAPPING
    context.user_data["mapping"] = mapping

    data_initial = context.user_data["data_initial"]
    final_rows = []
    for _, row in data_initial.iterrows():
        tokens = list(row.fillna("").astype(str))
        if len(tokens) < 4:
            continue
        point = tokens[mapping["Point"]]
        x = tokens[mapping["X"]]
        y = tokens[mapping["Y"]]
        z = tokens[mapping["Z"]]
        max_required = max(mapping.values())
        code = tokens[mapping["Code"]] if len(tokens) > mapping["Code"] else ""
        comments = " ".join(tokens[max_required + 1 :]) if len(tokens) > max_required + 1 else ""
        final_rows.append([point, x, y, z, code, comments])

    import pandas as pd

    final_data = pd.DataFrame(final_rows, columns=["Point", "X", "Y", "Z", "Code", "Coments"])
    context.user_data["final_data"] = final_data
    context.user_data["mapping_ready"] = True
    await query.edit_message_text("Соответствие колонок применено.")
    await show_workflow_menu(update, context, notice="Соответствие колонок обновлено.")
    return STATE_WORKFLOW


async def handle_mapping_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    db.record_usage(user.id, user.username, "handle_mapping_text")
    text = update.message.text.strip()
    default_mapping = {"Point": 0, "X": 1, "Y": 2, "Z": 3, "Code": 4}
    swapped_mapping = {"Point": 0, "Y": 1, "X": 2, "Z": 3, "Code": 4}
    if text == "1":
        mapping = default_mapping
    elif text == "2":
        mapping = swapped_mapping
    else:
        await update.message.reply_text("Пожалуйста, отправьте 1 или 2.")
        return STATE_MAPPING
    context.user_data["mapping"] = mapping

    data_initial = context.user_data["data_initial"]
    final_rows = []
    for _, row in data_initial.iterrows():
        tokens = list(row.fillna("").astype(str))
        if len(tokens) < 4:
            continue
        point = tokens[mapping["Point"]]
        x = tokens[mapping["X"]]
        y = tokens[mapping["Y"]]
        z = tokens[mapping["Z"]]
        max_required = max(mapping.values())
        code = tokens[mapping["Code"]] if len(tokens) > mapping["Code"] else ""
        comments = " ".join(tokens[max_required + 1 :]) if len(tokens) > max_required + 1 else ""
        final_rows.append([point, x, y, z, code, comments])

    import pandas as pd

    final_data = pd.DataFrame(final_rows, columns=["Point", "X", "Y", "Z", "Code", "Coments"])
    context.user_data["final_data"] = final_data
    context.user_data["mapping_ready"] = True
    await update.message.reply_text("Соответствие колонок применено.", reply_markup=MAIN_MENU_KEYBOARD)
    await show_workflow_menu(update, context, notice="Соответствие колонок обновлено.")
    return STATE_WORKFLOW


async def handle_tin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    data = query.data
    final_data = context.user_data.get("final_data")

    def _cleanup_selection_state() -> None:
        for key in ("tin_selection_message_id", "tin_selection_indexes", "tin_all_codes", "tin_selection_page"):
            context.user_data.pop(key, None)

    if data == "workflow_tin":
        if final_data is None or final_data.empty:
            await query.answer("Сначала загрузите файл и настройте соответствие.", show_alert=True)
            return STATE_WORKFLOW
        codes = _collect_available_codes(final_data)
        if not codes:
            await query.answer("В исходных данных нет кодов для выбора.", show_alert=True)
            return STATE_WORKFLOW

        selected_codes = set(context.user_data.get("tin_codes") or [])
        selected_indexes = {idx for idx, code in enumerate(codes) if code in selected_codes}
        context.user_data["tin_all_codes"] = codes
        context.user_data["tin_selection_indexes"] = selected_indexes
        context.user_data["tin_selection_page"] = 0

        text = f"{TIN_SELECTION_TEXT}\n\n{_format_selected_codes(codes, selected_indexes)}"
        keyboard = build_tin_codes_keyboard(codes, selected_indexes, page=0)

        previous_message_id = context.user_data.get("tin_selection_message_id")
        if previous_message_id:
            try:
                await context.bot.delete_message(chat_id=query.message.chat_id, message_id=previous_message_id)
            except Exception:
                pass

        message = await query.message.reply_text(text, reply_markup=keyboard)
        context.user_data["tin_selection_message_id"] = message.message_id
        await query.answer()
        return STATE_WORKFLOW

    if data.startswith("tin_toggle:"):
        await query.answer()
        try:
            index = int(data.split(":", 1)[1])
        except (ValueError, IndexError):
            return STATE_WORKFLOW
        codes = context.user_data.get("tin_all_codes") or []
        if not codes:
            await query.edit_message_text("Не удалось найти список кодов.", reply_markup=None)
            _cleanup_selection_state()
            return STATE_WORKFLOW
        if not 0 <= index < len(codes):
            return STATE_WORKFLOW
        selected_indexes = set(context.user_data.get("tin_selection_indexes") or set())
        if index in selected_indexes:
            selected_indexes.remove(index)
        else:
            selected_indexes.add(index)
        context.user_data["tin_selection_indexes"] = selected_indexes
        page = context.user_data.get("tin_selection_page", 0)
        text = f"{TIN_SELECTION_TEXT}\n\n{_format_selected_codes(codes, selected_indexes)}"
        keyboard = build_tin_codes_keyboard(codes, selected_indexes, page=page)
        await query.edit_message_text(text, reply_markup=keyboard)
        return STATE_WORKFLOW

    if data.startswith("tin_page:"):
        await query.answer()
        try:
            page = int(data.split(":", 1)[1])
        except (ValueError, IndexError):
            return STATE_WORKFLOW
        codes = context.user_data.get("tin_all_codes") or []
        if not codes:
            await query.edit_message_text("Не удалось найти список кодов.", reply_markup=None)
            _cleanup_selection_state()
            return STATE_WORKFLOW
        context.user_data["tin_selection_page"] = max(page, 0)
        selected_indexes = set(context.user_data.get("tin_selection_indexes") or set())
        text = f"{TIN_SELECTION_TEXT}\n\n{_format_selected_codes(codes, selected_indexes)}"
        keyboard = build_tin_codes_keyboard(codes, selected_indexes, page=context.user_data["tin_selection_page"])
        await query.edit_message_text(text, reply_markup=keyboard)
        return STATE_WORKFLOW

    if data == "tin_done":
        codes = context.user_data.get("tin_all_codes") or []
        selected_indexes = set(context.user_data.get("tin_selection_indexes") or set())
        selected_codes = [codes[idx] for idx in sorted(selected_indexes) if 0 <= idx < len(codes)]
        context.user_data["tin_codes"] = selected_codes
        summary = "TIN-коды не выбраны."
        if selected_codes:
            preview = ", ".join(selected_codes[:TIN_CODES_PREVIEW_LIMIT])
            if len(selected_codes) > TIN_CODES_PREVIEW_LIMIT:
                preview += f" … (+{len(selected_codes) - TIN_CODES_PREVIEW_LIMIT})"
            summary = f"Выбрано кодов: {len(selected_codes)}\n{preview}"
        try:
            await query.edit_message_text(f"Настройка TIN завершена.\n\n{summary}")
        except Exception:
            pass
        _cleanup_selection_state()
        await show_workflow_menu(update, context, notice="Настройки TIN обновлены.")
        return STATE_WORKFLOW

    if data == "tin_cancel":
        try:
            await query.edit_message_text("Настройка TIN отменена.")
        except Exception:
            pass
        _cleanup_selection_state()
        await query.answer()
        return STATE_WORKFLOW

    await query.answer()
    return STATE_WORKFLOW


async def handle_tin_refine_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    new_value = not bool(context.user_data.get("tin_refine"))
    context.user_data["tin_refine"] = new_value
    status_text = "Уточнение рельефа включено" if new_value else "Уточнение рельефа выключено"
    await query.answer(status_text, show_alert=False)
    await show_workflow_menu(update, context, notice=status_text)
    return STATE_WORKFLOW


async def handle_scale_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == "workflow_scale":
        await _prompt_scale_selection(update, context)
        return STATE_SCALE
    option = SCALE_OPTIONS.get(query.data)
    if not option:
        await query.edit_message_text("Неизвестный вариант масштаба.", reply_markup=build_scale_keyboard())
        return STATE_SCALE

    scale_value = option.get("scale", BASE_SCALE)
    scale_factor = max(scale_value / BASE_SCALE, 0.05)
    label = option.get("label", f"1:{scale_value}")
    context.user_data["scale_value"] = scale_value
    context.user_data["scale_label"] = label
    context.user_data["scale_factor"] = scale_factor
    db.record_usage(query.from_user.id, query.from_user.username, f"scale_selected_{query.data}")

    await query.edit_message_text(f"Масштаб {label} выбран.")
    await show_workflow_menu(update, context, notice=f"Масштаб обновлён на {label}.")
    return STATE_WORKFLOW


async def handle_scale_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    text = update.message.text.strip().lower().replace(" ", "")
    scale_value = SCALE_TEXT_MAP.get(text)
    if scale_value is None:
        numbers = [int(num) for num in re.findall(r"\d+", text)]
        for candidate in numbers:
            if candidate in {500, 1000, 2000, 5000}:
                scale_value = candidate
                break

    if scale_value is None:
        await update.message.reply_text(
            "Пожалуйста, выберите масштаб кнопками или отправьте одно из значений: 1:500, 1:1000, 1:2000, 1:5000."
        )
        return STATE_SCALE

    scale_factor = max(scale_value / BASE_SCALE, 0.05)
    label_lookup = next((opt["label"] for opt in SCALE_OPTIONS.values() if opt.get("scale") == scale_value), None)
    label = label_lookup or f"1:{scale_value}"
    context.user_data["scale_value"] = scale_value
    context.user_data["scale_factor"] = scale_factor
    context.user_data["scale_label"] = label
    db.record_usage(user.id, user.username, f"scale_selected_text_{scale_value}")

    await update.message.reply_text(f"Масштаб установлен: {label}.", reply_markup=MAIN_MENU_KEYBOARD)
    await show_workflow_menu(update, context, notice=f"Масштаб обновлён на {label}.")
    return STATE_WORKFLOW


async def handle_wrong_input_in_scale(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Выберите масштаб кнопкой или укажите один из вариантов: 1:500, 1:1000, 1:2000, 1:5000.")
    return STATE_SCALE


async def handle_wrong_input_in_mapping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "На этом этапе ожидается отправка цифры (1 или 2). Используйте /cancel, чтобы начать заново."
    )
    return STATE_MAPPING
