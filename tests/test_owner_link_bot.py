"""Trusted, opt-in Telegram link handler checks without polling."""

from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from autocad_assistance.bot.owner_link import register_owner_link_handler
from autocad_assistance.services.auth_store import AuthStore


class OwnerLinkBotTests(unittest.IsolatedAsyncioTestCase):
    async def test_bot_registers_link_only_when_auth_root_is_configured(self):
        from autocad_assistance.bot import run

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "auth"
            with patch("autocad_assistance.bot.run.db.init_db"):
                with patch.dict(os.environ, {"GEOAI_AUTH_ROOT": str(root)}):
                    enabled = run.build_app(token="123456:OFFLINE_TEST_ONLY")
                with patch.dict(os.environ, {"GEOAI_AUTH_ROOT": ""}):
                    disabled = run.build_app(token="123456:OFFLINE_TEST_ONLY")
            self.assertTrue(any("link" in handler.commands for handler in enabled.handlers[-1]))
            self.assertNotIn(-1, disabled.handlers)

    async def test_private_admin_update_confirms_the_owner_link_once(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "auth"
            store = AuthStore(root)
            owner = store.create_owner("owner", "Synthetic-only-owner-passphrase-123")
            code = store.create_link_challenge(owner.user_id)
            handlers = []
            app = SimpleNamespace(add_handler=lambda handler, group: handlers.append((handler, group)))
            with patch("autocad_assistance.bot.owner_link.ADMIN_IDS", [42]):
                register_owner_link_handler(app, root)
            self.assertEqual(handlers[0][1], -1)
            callback = handlers[0][0].callback
            message = SimpleNamespace(reply_text=AsyncMock())
            context = SimpleNamespace(args=[code])
            unauthorized = SimpleNamespace(
                effective_message=message,
                effective_user=SimpleNamespace(id=7),
                effective_chat=SimpleNamespace(type="private"),
            )
            await callback(unauthorized, context)
            self.assertIsNone(store.get_user(owner.user_id).telegram_user_id)
            group_update = SimpleNamespace(
                effective_message=message,
                effective_user=SimpleNamespace(id=42),
                effective_chat=SimpleNamespace(type="group"),
            )
            await callback(group_update, context)
            self.assertIsNone(store.get_user(owner.user_id).telegram_user_id)
            trusted = SimpleNamespace(
                effective_message=message,
                effective_user=SimpleNamespace(id=42),
                effective_chat=SimpleNamespace(type="private"),
            )
            await callback(trusted, context)
            self.assertEqual(store.get_user(owner.user_id).telegram_user_id, 42)
            await callback(trusted, context)
            self.assertEqual(store.get_user(owner.user_id).telegram_user_id, 42)


if __name__ == "__main__":
    unittest.main()
