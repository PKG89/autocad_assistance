"""Optional trusted Telegram confirmation for an owner link challenge."""

from __future__ import annotations

from pathlib import Path

from telegram.ext import CommandHandler

from autocad_assistance.config import ADMIN_IDS
from autocad_assistance.services.auth_store import AuthError, AuthStore


def register_owner_link_handler(app, auth_root: str | Path) -> None:
    store = AuthStore(auth_root)
    admins = frozenset(int(user_id) for user_id in ADMIN_IDS)

    async def confirm(update, context) -> None:
        message = update.effective_message
        user = update.effective_user
        chat = update.effective_chat
        if message is None:
            return
        if chat is None or chat.type != "private" or user is None or user.id not in admins:
            await message.reply_text("Подтверждение связи недоступно.")
            return
        arguments = context.args or []
        if len(arguments) != 1:
            await message.reply_text("Используйте /link и одноразовый код из кабинета.")
            return
        try:
            store.confirm_link(arguments[0], user.id, admins)
        except AuthError:
            await message.reply_text("Код недействителен или срок действия истёк.")
            return
        await message.reply_text("Связь с кабинетом подтверждена. Войдите снова.")

    app.add_handler(CommandHandler("link", confirm), group=-1)
