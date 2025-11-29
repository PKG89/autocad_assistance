from __future__ import annotations

from pathlib import Path
from typing import Iterable

try:
    import pandas as pd
except ModuleNotFoundError:  # pragma: no cover - pandas must be installed in production
    pd = None  # type: ignore

from telegram import Update
from telegram.ext import ContextTypes

if __package__ is None or __package__ == "":
    import sys
    sys.path.append(str(Path(__file__).resolve().parent.parent))

from autocad_assistance.keyboard import build_workflow_keyboard

STATE_FILE, STATE_MAPPING, STATE_SCALE, STATE_WORKFLOW, STATE_KML_PROJECTION, STATE_KML_POINTS = range(6)

BASE_SCALE = 1000


def get_scale_value(context: ContextTypes.DEFAULT_TYPE) -> int:
    """Return the conversation scale value stored in user data."""
    return int(context.user_data.get("scale_value", BASE_SCALE))


def get_scale_factor(context: ContextTypes.DEFAULT_TYPE) -> float:
    """Return the scale factor ensuring a minimal positive value."""
    return max(get_scale_value(context) / BASE_SCALE, 0.05)


def _build_workflow_text(context: ContextTypes.DEFAULT_TYPE, notice: str | None = None) -> str:
    filename = context.user_data.get("original_filename", "(файл не выбран)")
    data_initial = context.user_data.get("data_initial")
    if pd is not None and isinstance(data_initial, pd.DataFrame):
        total_rows = len(data_initial)
    else:
        total_rows = context.user_data.get("data_initial_count", 0)
    mapping_ready = bool(context.user_data.get("mapping_ready"))
    scale_value = get_scale_value(context)
    mapping_status = (
        "Координаты точек определены."
        if mapping_ready
        else "Требуется указать столбцы с координатами точек."
    )
    scale_status = f"Выбран масштаб: 1:{scale_value}"
    
    # TIN статус
    tin_enabled = bool(context.user_data.get("tin_enabled"))
    tin_refine = bool(context.user_data.get("tin_refine"))
    contour_interval = float(context.user_data.get("contour_interval", 1.0))
    if tin_enabled:
        refine_text = " (с уточнением)" if tin_refine else ""
        contour_text = f", интервал горизонталей: {contour_interval:.1f}м"
        tin_status = f"TIN: включено{refine_text}{contour_text}"
    else:
        tin_status = "TIN: выключено"
    
    summary = (
        f"Файл для обработки: {filename}\n"
        f"Всего точек: {total_rows}\n"
        f"{mapping_status}\n"
        f"{scale_status}\n"
        f"{tin_status}\n"
        "Когда все готово, нажмите \"Сгенерировать DXF\"."
    )
    if notice:
        summary = f"{notice}\n\n{summary}"
    return summary

async def delete_previous_workflow_message(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> None:
    message_id = context.user_data.pop("workflow_message_id", None)
    if message_id:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
        except Exception:
            pass


async def show_workflow_menu(update: Update | None, context: ContextTypes.DEFAULT_TYPE, notice: str | None = None) -> None:
    chat = update.effective_chat if update else None
    if chat is None:
        return
    await delete_previous_workflow_message(context, chat.id)
    text = _build_workflow_text(context, notice)
    mapping_ready = bool(context.user_data.get("mapping_ready"))
    scale_value = get_scale_value(context)

    # Determine mapping type for display if coordinates are already selected
    mapping_type = None
    if mapping_ready:
        mapping = context.user_data.get("mapping", {})
        if mapping.get("X") == 1:  # Standard mapping
            mapping_type = "1"
        elif mapping.get("Y") == 1:  # Swapped X and Y
            mapping_type = "2"
    
    # Get TIN settings for display
    tin_enabled = bool(context.user_data.get("tin_enabled"))
    tin_refine = bool(context.user_data.get("tin_refine"))
    contour_interval = float(context.user_data.get("contour_interval", 1.0))

    message = await chat.send_message(
        text,
        reply_markup=build_workflow_keyboard(
            mapping_ready=mapping_ready,
            scale_value=scale_value,
            mapping_type=mapping_type,
            tin_enabled=tin_enabled,
            tin_refine=tin_refine,
            contour_interval=contour_interval,
        ),
    )
    context.user_data["workflow_message_id"] = message.message_id


_KML_STATE_KEYS: Iterable[str] = (
    "kml_mode",
    "kml_crs",
    "kml_transformer",
    "kml_projection_raw",
    "kml_last_points",
    "kml_swap_xy",
)


def reset_kml_context(context: ContextTypes.DEFAULT_TYPE) -> None:
    for key in _KML_STATE_KEYS:
        context.user_data.pop(key, None)


_WORKFLOW_STATE_KEYS: Iterable[str] = (
    "file_path",
    "original_filename",
    "encoding",
    "data_initial",
    "data_initial_count",
    "mapping",
    "mapping_ready",
    "final_data",
    "scale_value",
    "scale_label",
    "scale_factor",
    "workflow_message_id",
    "tin_codes",
    "tin_refine",
    "tin_enabled",
    "contour_interval",
    "tin_all_codes",
    "tin_selection_page",
    "tin_selection_message_id",
    "tin_selection_indexes",
)


def reset_workflow_state(context: ContextTypes.DEFAULT_TYPE) -> None:
    for key in _WORKFLOW_STATE_KEYS:
        context.user_data.pop(key, None)
    reset_kml_context(context)

