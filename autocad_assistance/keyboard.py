from __future__ import annotations

import re
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import filters

BUTTON_KML = "🌍 KML 🌍"
BUTTON_NEW_DXF = "🌐 Новый DXF 🌐"
BUTTON_DOWNLOAD_TEMPLATE = "📋 Скачать шаблон 📋"
BUTTON_HELP = "ℹ️ Помощь ℹ️"
BUTTON_INSTRUCTION = "📘 Инструкция 📘"
BUTTON_RESET_STATE = "♻️ Сбросить состояние ♻️"

SCALE_OPTIONS = {
    "scale_500": {"label": "1:500", "scale": 500},
    "scale_1000_2000": {"label": "1:1000 / 1:2000", "scale": 1000},
    "scale_5000": {"label": "1:5000", "scale": 5000},
}

CONTOUR_INTERVAL_OPTIONS = {
    "contour_0.5": {"label": "0.5 м", "interval": 0.5},
    "contour_1.0": {"label": "1.0 м", "interval": 1.0},
    "contour_2.0": {"label": "2.0 м", "interval": 2.0},
    "contour_5.0": {"label": "5.0 м", "interval": 5.0},
}

SCALE_TEXT_MAP = {
    "1:500": 500,
    "500": 500,
    "1/500": 500,
    "1-500": 500,
    "1:1000": 1000,
    "1000": 1000,
    "1/1000": 1000,
    "1:1000/2000": 1000,
    "1000/2000": 1000,
    "1-1000/2000": 1000,
    "1:2000": 2000,
    "2000": 2000,
    "1/2000": 2000,
    "1:5000": 5000,
    "5000": 5000,
    "1/5000": 5000,
}

MAIN_MENU_BUTTON_LABELS = [
    [BUTTON_KML, BUTTON_NEW_DXF],
    [BUTTON_DOWNLOAD_TEMPLATE, BUTTON_HELP],
    [BUTTON_INSTRUCTION, BUTTON_RESET_STATE],
]

MAIN_MENU_KEYBOARD = ReplyKeyboardMarkup(
    [[KeyboardButton(label) for label in row] for row in MAIN_MENU_BUTTON_LABELS],
    resize_keyboard=True,
    one_time_keyboard=False,
)

MAIN_MENU_TEXTS = {label for row in MAIN_MENU_BUTTON_LABELS for label in row}
MAIN_MENU_PATTERN = r"^(" + "|".join(re.escape(label) for label in MAIN_MENU_TEXTS) + r")$"
MAIN_MENU_FILTER = filters.TEXT & filters.Regex(MAIN_MENU_PATTERN)


TIN_CODES_PAGE_SIZE = 8





def build_workflow_keyboard(
    mapping_ready: bool,
    scale_value: int,
    mapping_type: str | None = None,
    tin_enabled: bool = False,
    tin_refine: bool = False,
    contour_interval: float = 1.0,
) -> InlineKeyboardMarkup:
    scale_label = f"1:{scale_value}"

    if mapping_ready and mapping_type:
        if mapping_type == "1":
            mapping_label = "1️⃣ Порядок координат (X,Y)"
        else:
            mapping_label = "1️⃣ Порядок координат (Y,X)"
    else:
        mapping_label = "1️⃣ Порядок координат ⚪"

    scale_button = f"2️⃣ Масштаб ({scale_label})"
    
    # Кнопка TIN (треугольники) - просто включено/выключено
    if tin_enabled:
        refine_text = " (уточнение)" if tin_refine else ""
        tin_label = f"3️⃣ TIN: Включено{refine_text} ✅"
    else:
        tin_label = "3️⃣ TIN: Выключено ⚪"

    buttons = [
        [InlineKeyboardButton(mapping_label, callback_data="workflow_mapping")],
        [InlineKeyboardButton(scale_button, callback_data="workflow_scale")],
        [InlineKeyboardButton(tin_label, callback_data="workflow_tin")],
    ]
    
    # Если TIN включен, добавляем кнопку для настройки интервала горизонталей
    if tin_enabled:
        contour_label = f"4️⃣ Интервал горизонталей: {contour_interval:.1f}м"
        buttons.append([InlineKeyboardButton(contour_label, callback_data="workflow_contour_interval")])
    
    buttons.extend([
        [InlineKeyboardButton("✅ Сформировать DXF", callback_data="workflow_generate")],
        [InlineKeyboardButton("📤 Новый файл", callback_data="workflow_newfile")],
    ])
    
    return InlineKeyboardMarkup(buttons)


def build_tin_codes_keyboard(
    codes: list[str],
    selected_indexes: set[int],
    page: int = 0,
) -> InlineKeyboardMarkup:
    total = len(codes)
    max_page = max((total - 1) // TIN_CODES_PAGE_SIZE, 0)
    page = max(0, min(page, max_page))
    start = page * TIN_CODES_PAGE_SIZE
    end = start + TIN_CODES_PAGE_SIZE

    rows: list[list[InlineKeyboardButton]] = []
    for idx in range(start, min(end, total)):
        code = codes[idx]
        is_selected = idx in selected_indexes
        prefix = "✅" if is_selected else "⚪"
        label = f"{prefix} {code}"
        rows.append([InlineKeyboardButton(label, callback_data=f"tin_toggle:{idx}")])

    navigation_row: list[InlineKeyboardButton] = []
    if page > 0:
        navigation_row.append(InlineKeyboardButton("⬅️", callback_data=f"tin_page:{page - 1}"))
    if page < max_page:
        navigation_row.append(InlineKeyboardButton("➡️", callback_data=f"tin_page:{page + 1}"))
    if navigation_row:
        rows.append(navigation_row)

    rows.append(
        [
            InlineKeyboardButton("✅ Готово", callback_data="tin_done"),
            InlineKeyboardButton("✖️ Отмена", callback_data="tin_cancel"),
        ]
    )
    return InlineKeyboardMarkup(rows)


def build_scale_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(option["label"], callback_data=key)]
        for key, option in SCALE_OPTIONS.items()
    ]
    return InlineKeyboardMarkup(buttons)


def build_mapping_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("1 — Стандартное соответствие", callback_data="1")],
            [InlineKeyboardButton("2 — Перестановка X и Y", callback_data="2")],
        ]
    )


def build_contour_interval_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру для выбора интервала горизонталей."""
    buttons = [
        [InlineKeyboardButton(option["label"], callback_data=key)]
        for key, option in CONTOUR_INTERVAL_OPTIONS.items()
    ]
    return InlineKeyboardMarkup(buttons)
