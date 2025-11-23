"""Start/help/cancel handlers and admin wiring for the bot."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from telegram import InputFile, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from autocad_assistance.config import ADMIN_IDS
from autocad_assistance import db
from autocad_assistance.keyboard import MAIN_MENU_KEYBOARD
from autocad_assistance.state import (
    STATE_FILE,
    reset_kml_context,
    reset_workflow_state,
    delete_previous_workflow_message,
)
from autocad_assistance.admin import (
    admin_callback_handler,
    admin_delete_all_stats_callback,
    admin_delete_stats_handler,
    admin_delete_stats_prompt,
    admin_panel,
    admin_user_detail_back,
    admin_users,
    admin_users_callback,
)

logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        user = update.effective_user
        chat = update.effective_chat
        
        # Удаляем предыдущие сообщения workflow меню, если они есть
        if chat:
            try:
                await delete_previous_workflow_message(context, chat.id)
            except Exception as e:
                logger.warning("Failed to delete previous workflow message: %s", e)
        
        # Сбрасываем все данные пользователя в исходное состояние
        reset_workflow_state(context)
        
        db.record_usage(user.id, user.username, "/start")
        
        admin_text = ""
        if user.id in ADMIN_IDS:
            admin_text = "\n\n🛠 *Администратор*: команда /admin откроет панель управления."

        welcome_text = (
            f"🎯 *DXF Generator Bot*\n"
            f"Привет, {user.first_name or 'коллега'}! Я помогу превратить полевые данные в DXF-чертёж.\n\n"
            "📌 *Как начать*\n"
            "1️⃣ Прикрепите файл с точками как документ (скрепка → \"Файл\").\n"
            "2️⃣ Укажите порядок колонок — бот предложит готовые варианты.\n"
            "3️⃣ Выберите масштаб (1:500 / 1:1000 / 1:5000) и получите готовый DXF.\n\n"
            "🧾 *Формат строки*\n"
            "• Имя точки\n"
            "• Координата X\n"
            "• Координата Y\n"
            "• Координата Z\n"
            "• Код (например: k1, gaz1, tr1)\n"
            "• Комментарий — при необходимости\n\n"
            "👇 Используйте клавиши внизу: загрузка файла, шаблон, помощь или настройки масштаба." + admin_text
        )

        reply_kwargs = {"parse_mode": "Markdown", "reply_markup": MAIN_MENU_KEYBOARD}
        message = update.message or update.effective_message
        if message:
            await message.reply_text(welcome_text, **reply_kwargs)
        elif chat:
            await chat.send_message(welcome_text, **reply_kwargs)
        else:
            logger.warning("Unable to respond to /start: no message or chat available")
        return STATE_FILE
    except Exception as e:
        logger.error("Error in start function: %s", e)
        fallback_text = "Произошла ошибка при запуске бота. Попробуйте еще раз."
        message = update.message or update.effective_message
        if message:
            await message.reply_text(
                fallback_text,
                reply_markup=MAIN_MENU_KEYBOARD,
            )
        elif update.effective_chat:
            await update.effective_chat.send_message(
                fallback_text,
                reply_markup=MAIN_MENU_KEYBOARD,
            )
        else:
            logger.warning("Unable to send fallback message for /start error")
        return STATE_FILE


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    db.record_usage(user.id, user.username, "/help")
    help_text = (
        "👋 **Добро пожаловать в DXF Generator Bot!**\n\n"
        "**Как использовать бота:**\n"
        "1. **Формат входного файла:**\n"
        "   - Каждая строка должна содержать:\n"
        "     • Имя точки\n"
        "     • Координата X\n"
        "     • Координата Y\n"
        "     • Координата Z\n"
        "     • Код (например, k1, gaz1, k2, tr1 и т.д.)\n"
        "     • *(Опционально)* Комментарий\n\n"
        "2. **Обработка:**\n"
        "   - После загрузки файла бот определяет кодировку и разделитель,\n"
        "     а затем предлагает выбрать вариант соответствия колонок с помощью кнопок.\n\n"
        "3. **Генерация чертежа:**\n"
        "   - Бот добавляет точки, подписи и вставляет блоки для точек с особыми кодами.\n"
        "   - Точки с кодами, у которых буквенная часть совпадает, но цифры различаются, обрабатываются отдельно –\n"
        "     для каждого полного кода строится отдельная полилиния.\n\n"
        "4. **Результат:**\n"
        "   - Вы получите DXF‑чертёж, сохранённый с именем, основанным на исходном файле (расширение .dxf).\n\n"
        "💡 **Советы:**\n"
        "   • Отправляйте файл как документ.\n"
        "   • Если не уверены – нажмите кнопку «Скачать шаблон» для примера.\n"
        "   • Команды для администрирования доступны только администратору (/admin).\n\n"
        "Спасибо за использование DXF Generator Bot!"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown", reply_markup=MAIN_MENU_KEYBOARD)


async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Simple health-check handler to verify the bot is responsive."""
    user = update.effective_user
    db.record_usage(user.id if user else 0, user.username if user else None, "ping")
    await update.message.reply_text("pong")


async def send_sinokod_document(chat) -> bool:
    # SinoKOD.txt lives in the package-level templates directory
    # (autocad_assistance/templates/SinoKOD.txt). Use the package root
    # (parent of this module's parent) so lookups work whether the package
    # is imported or run as a script.
    sino_path = Path(__file__).resolve().parent.parent / "templates" / "SinoKOD.txt"
    if not sino_path.exists():
        return False
    with sino_path.open("rb") as doc_file:
        await chat.send_document(document=InputFile(doc_file, filename="SinoKOD.txt"))
    return True


async def send_SinoKOD(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    db.record_usage(user.id, user.username, "download_SinoKOD")
    query = update.callback_query
    await query.answer()
    chat = update.effective_chat
    if await send_sinokod_document(chat):
        await query.edit_message_text("📄 Шаблон отправлен. Используйте главное меню, чтобы продолжить.")
    else:
        await query.edit_message_text("⚠️ Файл шаблона не найден.")


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Операция отменена.")
    reset_kml_context(context)
    return ConversationHandler.END


def register_admin_handlers(app: Application) -> None:
    """Attach admin-related handlers to the application."""
    admin_regex = re.compile(r"^\d+\s+\d{4}-\d{2}-\d{2}\s*-\s*\d{4}-\d{2}-\d{2}$")

    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("delete_stats", admin_delete_stats_prompt))
    app.add_handler(MessageHandler(filters.Regex(admin_regex), admin_delete_stats_handler))
    app.add_handler(
        CallbackQueryHandler(
            admin_callback_handler,
            pattern="^(stats|errors|users|user_\\d+(_\\d+)?|users_back|clear_stats)$",
        )
    )
    app.add_handler(CommandHandler("users", admin_users))
    app.add_handler(CallbackQueryHandler(admin_users_callback, pattern="^users_(prev|next)$"))
    app.add_handler(CallbackQueryHandler(admin_user_detail_back, pattern="^users_back$"))
    app.add_handler(CallbackQueryHandler(admin_delete_all_stats_callback, pattern="^delete_all_(yes|no)$"))


def register_basic_handlers(app: Application) -> None:
    """Attach help/SinoKOD/admin handlers in one place."""
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("ping", ping))
    app.add_handler(CallbackQueryHandler(send_SinoKOD, pattern="download_SinoKOD"))
    register_admin_handlers(app)


__all__ = [
    "start",
    "help_command",
    "cancel",
    "send_SinoKOD",
    "send_sinokod_document",
    "register_admin_handlers",
    "register_basic_handlers",
]
