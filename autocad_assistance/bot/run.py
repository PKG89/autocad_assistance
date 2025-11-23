import logging
import atexit
import signal
import traceback
import os
from datetime import datetime
from pathlib import Path

from telegram.ext import ApplicationBuilder, CommandHandler
from autocad_assistance.config import BOT_TOKEN
from autocad_assistance.bot.start import register_basic_handlers, start, cancel
from autocad_assistance.bot.file_handlers import (
    handle_file,
    handle_file_text,
    process_main_menu_text,
    handle_mapping_callback,
    handle_mapping_text,
    handle_scale_callback,
    handle_scale_text,
    handle_kml_projection,
    handle_kml_points,
    handle_tin_callback,
    handle_tin_refine_toggle,
)
 # start_kml_flow is available via kml_handlers but not needed here
from autocad_assistance.keyboard import MAIN_MENU_FILTER
from autocad_assistance.state import (
    STATE_FILE,
    STATE_MAPPING,
    STATE_SCALE,
    STATE_WORKFLOW,
    STATE_KML_PROJECTION,
    STATE_KML_POINTS,
)
from telegram.ext import (
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

logger = logging.getLogger(__name__)

def _write_termination_log(reason: str) -> None:
    try:
        log_path = Path(__file__).resolve().parents[1] / "bot_shutdown.log"
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(f"--- {datetime.utcnow().isoformat()}Z PID={os.getpid()} reason={reason}\n")
            fh.write("".join(traceback.format_stack()))
            fh.write("\n")
    except Exception:
        # best-effort logging, avoid raising in signal handlers
        pass


def _signal_handler(sig, frame):
    try:
        _write_termination_log(f"signal={sig}")
    finally:
        # exit so the Application gets torn down as well
        import sys

        sys.exit(0)


# Register signal handlers early so we capture external terminations
try:
    signal.signal(signal.SIGINT, _signal_handler)
except Exception:
    pass
try:
    signal.signal(signal.SIGTERM, _signal_handler)
except Exception:
    pass
try:
    # Windows Ctrl-Break
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, _signal_handler)
except Exception:
    pass


@atexit.register
def _on_exit():
    _write_termination_log("atexit")


async def _noop(update, context):
    """Async no-op handler used as a safe placeholder for routes that are
    intentionally left unimplemented during testing.
    """
    return None


def main() -> None:
    # Build app and run. `build_app` registers handlers (ConversationHandler,
    # basic handlers, etc.) so we only need to start polling here.
    app = build_app()

    try:
        app.run_polling()
    except Exception as exc:
        logger.exception("Ошибка при запуске polling: %s", exc)


def build_app(token: str | None = None, allow_missing_token: bool = False):
    """Construct and return the telegram Application without running it.

    If `allow_missing_token` is True and no token is provided, a harmless
    dummy token will be used so the Application object can be constructed
    for tests that don't actually call network operations.
    """
    use_token = token if token is not None else BOT_TOKEN
    if not use_token and allow_missing_token:
        use_token = "TEST:000"
    if not use_token:
        raise RuntimeError("BOT_TOKEN is not configured; pass token or set allow_missing_token=True for tests")

    app = ApplicationBuilder().token(use_token).build()

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            MessageHandler(filters.Document.ALL, handle_file),
        ],
        states={
            STATE_FILE: [
                CommandHandler("start", start),
                MessageHandler(MAIN_MENU_FILTER, process_main_menu_text),
                MessageHandler(filters.Document.ALL, handle_file),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_file_text),
            ],
            STATE_MAPPING: [
                CommandHandler("start", start),
                MessageHandler(MAIN_MENU_FILTER, process_main_menu_text),
                CallbackQueryHandler(handle_mapping_callback),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_mapping_text),
            ],
            STATE_SCALE: [
                CommandHandler("start", start),
                MessageHandler(MAIN_MENU_FILTER, process_main_menu_text),
                CallbackQueryHandler(handle_scale_callback, pattern="^scale_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_scale_text),
            ],
            STATE_WORKFLOW: [
                CommandHandler("start", start),
                MessageHandler(MAIN_MENU_FILTER, process_main_menu_text),
                # Let top-level CallbackQueryHandlers handle workflow button clicks;
                # removing the no-op handler prevents swallowing the callback.
                MessageHandler(filters.Document.ALL, handle_file),
            ],
            STATE_KML_PROJECTION: [
                CommandHandler("start", start),
                # Allow main menu text to interrupt the flow
                MessageHandler(MAIN_MENU_FILTER, process_main_menu_text),
                # Expect a WKT/PROJ/EPSG description here
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_kml_projection),
                MessageHandler(filters.Document.ALL, _noop),
            ],
            STATE_KML_POINTS: [
                CommandHandler("start", start),
                # Allow main menu text to interrupt the flow
                MessageHandler(MAIN_MENU_FILTER, process_main_menu_text),
                # Text or document containing points should be handled by the
                # KML points handler (it validates presence of projection first).
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_kml_points),
                MessageHandler(filters.Document.ALL, handle_kml_points),
            ],
        },
    fallbacks=[CommandHandler("cancel", cancel)],
    )

    register_basic_handlers(app)
    app.add_handler(conv_handler)
    # Ensure reply-keyboard main menu text and inline callbacks are handled.
    # ReplyKeyboard uses normal text messages, so register a MessageHandler
    # with the prebuilt MAIN_MENU_FILTER from `keyboard.py`.
    try:
        app.add_handler(MessageHandler(MAIN_MENU_FILTER, process_main_menu_text))
    except Exception:
        # best-effort: continue if registration fails
        logger.exception("Failed to register MAIN_MENU_FILTER handler")
    else:
        logger.info("Registered MAIN_MENU_FILTER -> process_main_menu_text")

    # Inline callback handlers for the workflow buttons. These match the
    # callback_data values produced by `keyboard.build_workflow_keyboard`.
    try:
        # workflow mapping/scale/generate/newfile
        app.add_handler(CallbackQueryHandler(handle_mapping_callback, pattern="^workflow_mapping$"))
        app.add_handler(CallbackQueryHandler(handle_scale_callback, pattern="^workflow_scale$"))
        app.add_handler(CallbackQueryHandler(handle_tin_callback, pattern="^workflow_tin$"))
        app.add_handler(CallbackQueryHandler(handle_tin_refine_toggle, pattern="^workflow_refine$"))
        # For generate and newfile, we provide lightweight handlers that
        # currently call the no-op placeholder (application logic lives in
        # other modules like dxf_generator). Keep them logged so clicks are visible.
        async def _workflow_generate(update, context):
            logger.info("workflow_generate pressed: %s", update.callback_query.data)
            await update.callback_query.answer()
            
            # Проверяем, что данные готовы для генерации
            final_data = context.user_data.get("final_data")
            if final_data is None:
                await update.callback_query.edit_message_text(
                    "❌ Сначала нужно загрузить файл и настроить соответствие колонок.",
                    reply_markup=None
                )
                return
            
            # Получаем параметры масштаба
            scale_factor = context.user_data.get("scale_factor", 1.0)
            scale_label = context.user_data.get("scale_label", "1:1000")
            
            try:
                # Показываем прогресс
                await update.callback_query.edit_message_text(
                    f"🔄 Генерация DXF запущена (масштаб {scale_label})...",
                    reply_markup=None
                )
                
                # Создаем временный файл для DXF
                import tempfile
                import os
                
                temp_dir = tempfile.mkdtemp()
                output_filename = f"generated_{context.user_data.get('original_filename', 'drawing')}.dxf"
                output_path = os.path.join(temp_dir, output_filename)
                
                # Импортируем и вызываем генератор DXF
                from autocad_assistance.dxf_generator import generate_dxf_ezdxf
                tin_settings = {
                    "codes": list(context.user_data.get("tin_codes") or []),
                    "scale_value": context.user_data.get("scale_value"),
                    "refine": bool(context.user_data.get("tin_refine")),
                }
                generate_dxf_ezdxf(final_data, output_path, scale_factor, tin_settings=tin_settings)
                
                # Отправляем файл пользователю
                with open(output_path, 'rb') as dxf_file:
                    await context.bot.send_document(
                        chat_id=update.effective_chat.id,
                        document=dxf_file,
                        filename=output_filename,
                        caption=f"✅ DXF файл создан (масштаб {scale_label})\n📊 Обработано точек: {len(final_data)}"
                    )
                
                # Показываем меню workflow
                from autocad_assistance.state import show_workflow_menu
                await show_workflow_menu(update, context, notice="✅ DXF файл успешно создан и отправлен!")
                
                # Очищаем временный файл
                try:
                    os.unlink(output_path)
                    os.rmdir(temp_dir)
                except Exception:
                    pass
                    
            except Exception as exc:
                logger.exception("Ошибка при генерации DXF: %s", exc)
                await update.callback_query.edit_message_text(
                    f"❌ Ошибка при генерации DXF: {str(exc)}",
                    reply_markup=None
                )

        async def _workflow_newfile(update, context):
            logger.info("workflow_newfile pressed: %s", update.callback_query.data)
            await update.callback_query.answer()
            await update.callback_query.edit_message_text("Готово. Отправьте новый файл.", reply_markup=None)

        app.add_handler(CallbackQueryHandler(_workflow_generate, pattern="^workflow_generate$"))
        app.add_handler(CallbackQueryHandler(_workflow_newfile, pattern="^workflow_newfile$"))

        # Generic handlers: scale selection is handled by handle_scale_callback
        app.add_handler(CallbackQueryHandler(handle_scale_callback, pattern="^scale_"))
        app.add_handler(CallbackQueryHandler(handle_tin_callback, pattern=r"^tin_(?:toggle|page|done|cancel)"))
        # Mapping choices from mapping keyboard (callback_data '1' or '2')
        app.add_handler(CallbackQueryHandler(handle_mapping_callback, pattern="^[12]$"))
    except Exception:
        logger.exception("Failed to register inline callback handlers")

    # Final diagnostic: register a logging-only MessageHandler for any text
    # that wasn't handled earlier. This helps capture unexpected payloads
    # (hidden characters, whitespace) when testing ReplyKeyboard buttons.
    async def _log_unhandled_text(update, context):
        try:
            txt = update.message.text if update.message else None
            logger.warning("Unhandled text message: %r", txt)
        except Exception:
            logger.exception("Error logging unhandled text")

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _log_unhandled_text))
    # Wrap the Application.stop method so we always write a termination
    # diagnostic when the application lifecycle is requested to stop. This
    # helps us tell whether stop was triggered internally by the code or
    # externally (signal/atexit). Support both sync and async stop methods.
    try:
        import inspect

        _orig_stop = app.stop

        if inspect.iscoroutinefunction(_orig_stop):
            async def _wrapped_stop(*args, **kwargs):
                _write_termination_log("app.stop (async)")
                return await _orig_stop(*args, **kwargs)

            app.stop = _wrapped_stop
        else:
            def _wrapped_stop(*args, **kwargs):
                _write_termination_log("app.stop")
                return _orig_stop(*args, **kwargs)

            app.stop = _wrapped_stop
    except Exception:
        # Best-effort: don't crash if inspecting or wrapping fails.
        pass
    return app
