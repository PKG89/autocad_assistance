from __future__ import annotations

import logging
import re
from typing import List, Sequence

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
from telegram.helpers import escape_markdown

from autocad_assistance import db
from autocad_assistance.config import ADMIN_IDS

logger = logging.getLogger(__name__)

USER_LIST_PAGE_SIZE = 9
USER_DETAIL_PAGE_SIZE = 5
DATE_RANGE_PATTERN = re.compile(r"^(\d+)\s+(\d{4}-\d{2}-\d{2})\s*[-–-]\s*(\d{4}-\d{2}-\d{2})$")


def _md(value: object | None) -> str:
    """Escape dynamic text for Markdown v1."""
    if value is None:
        return '-'
    return escape_markdown(str(value), version=1)


async def _ensure_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    if user and user.id in ADMIN_IDS:
        return True

    message = "Нет доступа."
    if update.callback_query:
        await update.callback_query.answer(message, show_alert=True)
    elif update.message:
        await update.message.reply_text(message)
    else:
        chat = update.effective_chat
        if chat:
            await chat.send_message(message)
    return False


def _admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📊 Статистика", callback_data="stats")],
            [InlineKeyboardButton("⚠️ Ошибки", callback_data="errors")],
            [InlineKeyboardButton("👥 Пользователи", callback_data="users")],
            [InlineKeyboardButton("🗑 Очистить статистику", callback_data="clear_stats")],
        ]
    )


async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _ensure_admin(update, context):
        return

    await update.effective_chat.send_message(
        "🛠 *Админ-панель.*\nВыберите действие на клавиатуре ниже.",
        parse_mode="Markdown",
        reply_markup=_admin_keyboard(),
    )
    user = update.effective_user
    if user:
        db.record_usage(user.id, user.username, "/admin")


async def admin_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _ensure_admin(update, context):
        return

    query = update.callback_query
    await query.answer()
    data = query.data
    logger.info("Получены callback данные: %s", data)

    if data == "stats":
        total_users, total_commands = db.get_usage_stats()
        text = (
            "📊 **Статистика использования бота:**\n"
            f"Всего пользователей: {total_users}\n"
            f"Всего команд выполнено: {total_commands}"
        )
        await update.effective_chat.send_message(text, parse_mode="Markdown")
        return

    if data == "errors":
        recent_errors = db.get_recent_errors(limit=5)
        if recent_errors:
            errors_lines = [f"{_md(err[1])}: {_md(err[2])}" for err in recent_errors]
            errors_text = "\n".join(errors_lines)
        else:
            errors_text = "Ошибок нет."
        await update.effective_chat.send_message(
            f"⚠️ **Последние ошибки:**\n{errors_text}",
            parse_mode="Markdown",
        )
        return

    if data == "users":
        await admin_users(update, context, message_obj=query.message)
        return

    if data == "users_back":
        await admin_users(update, context, message_obj=query.message)
        return

    if data == "clear_stats":
        await admin_delete_all_stats_prompt(update, context)
        return

    if data.startswith("user_"):
        await admin_user_detail(update, context)
        return

    await update.effective_chat.send_message("Неизвестная команда.")


def _build_users_keyboard(users: Sequence[tuple[int, str | None, int]], *, has_prev: bool, has_next: bool) -> InlineKeyboardMarkup:
    keyboard: List[List[InlineKeyboardButton]] = [
        [InlineKeyboardButton(f"{uname or '-'} (ID: {uid})", callback_data=f"user_{uid}_0")]
        for uid, uname, _ in users
    ]
    nav_row: List[InlineKeyboardButton] = []
    if has_prev:
        nav_row.append(InlineKeyboardButton("⬅️ Назад", callback_data="users_prev"))
    if has_next:
        nav_row.append(InlineKeyboardButton("➡️ Вперёд", callback_data="users_next"))
    if nav_row:
        keyboard.append(nav_row)
    return InlineKeyboardMarkup(keyboard)


def _fetch_users_page(page: int) -> tuple[int, Sequence[tuple[int, str | None, int]], bool, bool]:
    users = db.get_users_page(page, USER_LIST_PAGE_SIZE)
    if not users and page > 0:
        page = max(0, page - 1)
        users = db.get_users_page(page, USER_LIST_PAGE_SIZE)
    has_prev = page > 0
    next_page = db.get_users_page(page + 1, USER_LIST_PAGE_SIZE)
    has_next = len(next_page) > 0
    return page, users, has_prev, has_next


async def admin_users(update: Update, context: ContextTypes.DEFAULT_TYPE, message_obj=None) -> None:
    if not await _ensure_admin(update, context):
        return

    page, users, has_prev, has_next = _fetch_users_page(0)
    if not users:
        target = message_obj or update.effective_chat
        if target:
            await target.send_message("Список пользователей пуст.")
        return

    context.user_data["users_page"] = page
    text = "📋 **Список пользователей:**\n\n"
    for uid, uname, count in users:
        text += f"• {_md(uname)} (ID: {uid}) - {count} команд\n"

    markup = _build_users_keyboard(users, has_prev=has_prev, has_next=has_next)

    if message_obj:
        try:
            await message_obj.delete()
        except Exception:
            pass

    await update.effective_chat.send_message(text, parse_mode="Markdown", reply_markup=markup)
    user = update.effective_user
    if user:
        db.record_usage(user.id, user.username, "/users")


async def admin_users_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _ensure_admin(update, context):
        return

    query = update.callback_query
    await query.answer()
    current_page = context.user_data.get("users_page", 0)
    if query.data == "users_next":
        current_page += 1
    elif query.data == "users_prev":
        current_page = max(0, current_page - 1)

    page, users, has_prev, has_next = _fetch_users_page(current_page)
    context.user_data["users_page"] = page

    if not users:
        await query.edit_message_text("Список пользователей пуст.")
        return

    text = "📋 **Список пользователей:**\n\n"
    for uid, uname, count in users:
        text += f"• {_md(uname)} (ID: {uid}) - {count} команд\n"

    markup = _build_users_keyboard(users, has_prev=has_prev, has_next=has_next)
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=markup)


async def admin_delete_all_stats_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _ensure_admin(update, context):
        return

    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✅ Да, очистить", callback_data="delete_all_yes")],
            [InlineKeyboardButton("❌ Нет", callback_data="delete_all_no")],
        ]
    )
    await update.effective_chat.send_message(
        "Удалить статистику по всем пользователям?",
        reply_markup=keyboard,
    )


async def admin_delete_all_stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _ensure_admin(update, context):
        return

    query = update.callback_query
    await query.answer()

    if query.data == "delete_all_yes":
        affected = db.delete_all_stats()
        text = f"✅ Удалено записей: {affected}."
    else:
        text = "Операция отменена."

    try:
        await query.message.delete()
    except Exception:
        pass

    await update.effective_chat.send_message(text)
    await admin_panel(update, context)


async def admin_delete_stats_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _ensure_admin(update, context):
        return

    await update.effective_chat.send_message(
        "Введите строку в формате:\n`<user_id> YYYY-MM-DD–YYYY-MM-DD`",
        parse_mode="Markdown",
    )


async def admin_delete_stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _ensure_admin(update, context):
        return

    text = update.message.text.strip()
    match = DATE_RANGE_PATTERN.match(text)
    if not match:
        await update.message.reply_text(
            "Неверный формат. Используйте:`<user_id> YYYY-MM-DD–YYYY-MM-DD`",
            parse_mode="Markdown",
        )
        return

    target_id = int(match.group(1))
    start_date = match.group(2)
    end_date = match.group(3)
    affected = db.delete_user_stats(target_id, start_date, end_date)
    await update.message.reply_text(
        f"✅ Удалено записей: {affected} (user_id={target_id}, период {start_date} – {end_date})."
    )
    await admin_panel(update, context)


async def admin_user_detail(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _ensure_admin(update, context):
        return

    query = update.callback_query
    parts = query.data.split("_")
    if len(parts) < 2:
        await query.edit_message_text("Некорректный идентификатор пользователя.")
        return

    try:
        target_id = int(parts[1])
    except ValueError:
        await query.edit_message_text("Некорректный идентификатор пользователя.")
        return

    current_page = int(parts[2]) if len(parts) > 2 else 0
    total = db.count_user_details(target_id)
    details = db.get_user_details(
        target_id,
        offset=current_page * USER_DETAIL_PAGE_SIZE,
        limit=USER_DETAIL_PAGE_SIZE,
    )

    if not details:
        text = "ℹ️ История пуста: обращений не найдено."
    else:
        text = (
            f"📑 **История пользователя ID: {target_id}** "
            f"(страница {current_page + 1})\n\n"
        )
        for record in details:
            timestamp = _md(record[5])
            command = _md(record[3])
            payload = _md(record[4])
            result = _md(record[6])
            text += f"{timestamp} - {command}: {payload} → {result}\n"
        text += f"\nВсего записей: {total}"

    buttons: List[InlineKeyboardButton] = []
    if current_page > 0:
        buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"user_{target_id}_{current_page - 1}"))
    if (current_page + 1) * USER_DETAIL_PAGE_SIZE < total:
        buttons.append(InlineKeyboardButton("➡️ Вперёд", callback_data=f"user_{target_id}_{current_page + 1}"))
    buttons.append(InlineKeyboardButton("↩️ К списку", callback_data="users_back"))
    markup = InlineKeyboardMarkup([buttons])

    try:
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=markup)
    except Exception:
        await update.effective_chat.send_message(text, parse_mode="Markdown", reply_markup=markup)


async def admin_user_detail_back(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await admin_users(update, context, message_obj=update.callback_query.message if update.callback_query else None)
