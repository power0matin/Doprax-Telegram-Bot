from __future__ import annotations

import asyncio
import logging
import os
import signal
from importlib.metadata import version as pkg_version
from typing import Any, Callable, Coroutine, Optional

from telegram import BotCommand, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from bot.config import Config
from bot.doprax_client import DopraxClient, DopraxConfig
from bot.handlers.common import (
    HandlerDeps,
    correlation_for_update,
    enforce_ratelimit,
    get_lang,
    json_log,
    reset_if_timed_out,
    user_id_from_update,
)
from bot.handlers.create_vm import (
    cancel_cmd,
    create_by_text,
    create_callback,
    create_vm_cmd,
)
from bot.handlers.health import health_cmd
from bot.handlers.help import help_cmd
from bot.handlers.list_vms import list_vms_cmd
from bot.handlers.locations import locations_cmd
from bot.handlers.menu import menu_by_text, menu_cmd
from bot.handlers.os_list import os_cmd
from bot.handlers.settings import settings_callback, settings_cmd
from bot.handlers.start import lang_callback, start_cmd
from bot.handlers.status import status_by_text, status_callback, status_cmd
from bot.handlers.vm_mgmt import vm_mgmt_callback, vm_mgmt_cmd
from bot.i18n import I18N
from bot.keyboards import main_reply_keyboard
from bot.states import State
from bot.storage import Storage
from bot.utils import new_correlation_id, redact_secrets

LOGGER = logging.getLogger("doprax_telegram_bot")


def _setup_logging(level: str) -> None:
    logging.basicConfig(level=level, format="%(message)s")


async def _set_commands(app: Application) -> None:
    commands = [
        BotCommand("start", "Start"),
        BotCommand("help", "Help"),
        BotCommand("lang", "Change language"),
        BotCommand("menu", "Show menu"),
        BotCommand("list_vms", "List VMs"),
        BotCommand("create_vm", "Create VM wizard"),
        BotCommand("status", "VM status"),
        BotCommand("locations", "Locations & plans"),
        BotCommand("os", "OS list"),
        BotCommand("cancel", "Cancel wizard"),
        BotCommand("health", "Health check"),
    ]
    await app.bot.set_my_commands(commands)


async def _preprocess(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    deps: HandlerDeps = context.application.bot_data["deps"]
    storage: Storage = deps.storage
    uid = user_id_from_update(update)
    if uid is None:
        return True

    # Ensure user exists
    await storage.ensure_user(uid)

    # Timeout recovery
    expired = await reset_if_timed_out(storage, uid, deps.session_timeout_seconds)
    if expired:
        lang = await get_lang(storage, uid)
        if update.effective_chat:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=I18N.t(lang, "timeout_reset"),
                reply_markup=main_reply_keyboard(lang),
                parse_mode=ParseMode.MARKDOWN,
            )

    # Rate limiting (skip for /start and language selection callbacks)
    is_start_cmd = bool(update.message and update.message.text and update.message.text.strip().startswith("/start"))
    is_lang_cb = bool(update.callback_query and update.callback_query.data and update.callback_query.data.startswith("LANG:"))

    if not (is_start_cmd or is_lang_cb):
        allowed = await enforce_ratelimit(storage, uid, deps.ratelimit_cooldown_seconds)
        if not allowed and update.effective_chat:
            lang = await get_lang(storage, uid)
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=I18N.t(lang, "rate_limited"),
                reply_markup=main_reply_keyboard(lang),
                parse_mode=ParseMode.MARKDOWN,
            )
            return False

    return True


async def _unknown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    deps: HandlerDeps = context.application.bot_data["deps"]
    uid = user_id_from_update(update)
    if uid is None:
        return
    lang = await get_lang(deps.storage, uid)
    if update.effective_chat:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=I18N.t(lang, "unknown_input"),
            reply_markup=main_reply_keyboard(lang),
            parse_mode=ParseMode.MARKDOWN,
        )


async def _error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    deps: HandlerDeps = context.application.bot_data["deps"]
    ref = new_correlation_id()
    err = context.error
    # Log stack trace to stdout, but redact secrets
    LOGGER.exception(redact_secrets(f"[{ref}] Unhandled error: {err}"))

    if isinstance(update, Update):
        uid = user_id_from_update(update)
        lang = "en"
        if uid is not None:
            try:
                lang = await get_lang(deps.storage, uid)
                await deps.storage.set_state(uid, State.IDLE)
                await deps.storage.reset_draft(uid)
                await deps.storage.set_create_lock(uid, False)
            except Exception:
                lang = "en"
        if update.effective_chat:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=I18N.t(lang, "something_wrong", ref=ref),
                reply_markup=main_reply_keyboard(lang),
                parse_mode=ParseMode.MARKDOWN,
            )


def _wrap(
    handler: Callable[..., Coroutine[Any, Any, None]],
    *args: Any,
    **kwargs: Any,
) -> Callable[[Update, ContextTypes.DEFAULT_TYPE], Coroutine[Any, Any, None]]:
    async def _inner(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await _preprocess(update, context):
            return
        await handler(update, context, *args, **kwargs)

    return _inner


async def _dispatch_vm_mgmt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    deps: HandlerDeps = context.application.bot_data["deps"]
    doprax: DopraxClient = context.application.bot_data["doprax"]
    action = await vm_mgmt_callback(update, context, deps)
    if action == "list_vms":
        await list_vms_cmd(update, context, deps, doprax)
    elif action == "status_prompt":
        # Enter status prompt state by sending the command path
        uid = user_id_from_update(update)
        if uid is None:
            return
        lang = await get_lang(deps.storage, uid)
        await deps.storage.set_state(uid, State.STATUS_WAIT_CODE)
        if update.effective_chat:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=I18N.t(lang, "ask_vm_code"),
                reply_markup=main_reply_keyboard(lang),
                parse_mode=ParseMode.MARKDOWN,
            )
    elif action == "refresh_vm_mgmt":
        await vm_mgmt_cmd(update, context, deps)


async def _shutdown(app: Application) -> None:
    deps: HandlerDeps = app.bot_data["deps"]
    doprax: DopraxClient = app.bot_data["doprax"]
    await doprax.close()
    await deps.storage.close()


async def _post_init(app: Application) -> None:
    await _set_commands(app)


def build_app(cfg: Config) -> Application:
    deps = HandlerDeps(storage=Storage(cfg.db_path), logger=LOGGER)
    doprax = DopraxClient(
        DopraxConfig(
            base_url=cfg.doprax_base_url,
            api_key=cfg.doprax_api_key,
            dry_run=cfg.dry_run,
        )
    )

    app = (
        ApplicationBuilder()
        .token(cfg.telegram_bot_token)
        .concurrent_updates(True)
        .build()
    )
    app.bot_data["deps"] = deps
    app.bot_data["doprax"] = doprax
    app.bot_data["version"] = _safe_version()
    app.bot_data["dry_run"] = cfg.dry_run

    # Wiring: open resources
    async def _open_resources(_: Application) -> None:
        os.makedirs(os.path.dirname(cfg.db_path) or ".", exist_ok=True)
        await deps.storage.open()
        await doprax.open()

    app.post_init = _post_init
    app.post_shutdown = _shutdown
    app.post_stop = _shutdown
    app.bot_data["open_resources"] = _open_resources

    return app


def _safe_version() -> str:
    try:
        return pkg_version("doprax-telegram-bot")
    except Exception:
        return "0.0.0"


async def _ensure_open(app: Application) -> None:
    open_resources = app.bot_data.get("open_resources")
    if callable(open_resources):
        await open_resources(app)


def _register_handlers(app: Application) -> None:
    deps: HandlerDeps = app.bot_data["deps"]
    doprax: DopraxClient = app.bot_data["doprax"]
    ver: str = app.bot_data["version"]
    dry_run: bool = app.bot_data["dry_run"]

    # /start + language
    app.add_handler(CommandHandler("start", _wrap(start_cmd, deps)))
    app.add_handler(
        CallbackQueryHandler(_wrap(lang_callback, deps), pattern=r"^LANG:(fa|en)$")
    )

    # /help /menu /lang (lang uses same start screen)
    app.add_handler(CommandHandler("help", _wrap(help_cmd, deps)))
    app.add_handler(CommandHandler("menu", _wrap(menu_cmd, deps)))
    app.add_handler(CommandHandler("lang", _wrap(start_cmd, deps)))

    # VM management
    app.add_handler(CommandHandler("vm_mgmt", _wrap(vm_mgmt_cmd, deps)))
    app.add_handler(CallbackQueryHandler(_dispatch_vm_mgmt, pattern=r"^MENU:"))

    # List / status
    app.add_handler(CommandHandler("list_vms", _wrap(list_vms_cmd, deps, doprax)))
    app.add_handler(CommandHandler("status", _wrap(status_cmd, deps, doprax)))
    app.add_handler(
        CallbackQueryHandler(_wrap(status_callback, deps, doprax), pattern=r"^VMSTAT:")
    )
    # Create wizard (text input)
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND, _wrap(create_by_text, deps, doprax)
        )
    )

    # Status lookup (text input)
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND, _wrap(status_by_text, deps, doprax)
        )
    )

    # Reply keyboard text shortcuts (fallback)
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, _wrap(menu_by_text, deps))
    )

    # Locations / OS
    app.add_handler(CommandHandler("locations", _wrap(locations_cmd, deps, doprax)))
    app.add_handler(CommandHandler("os", _wrap(os_cmd, deps, doprax)))

    # Create wizard
    app.add_handler(CommandHandler("create_vm", _wrap(create_vm_cmd, deps, doprax)))
    app.add_handler(CommandHandler("cancel", _wrap(cancel_cmd, deps)))
    app.add_handler(
        CallbackQueryHandler(
            _wrap(create_callback, deps, doprax), pattern=r"^(CREATE:|LOCPICK:|OSPICK:)"
        )
    )


    # Settings
    app.add_handler(CommandHandler("settings", _wrap(settings_cmd, deps)))
    app.add_handler(
        CallbackQueryHandler(_wrap(settings_callback, deps, ver), pattern=r"^SET:")
    )

    # Health
    app.add_handler(CommandHandler("health", _wrap(health_cmd, deps, doprax, dry_run)))



    # Fallback unknown
    app.add_handler(MessageHandler(filters.ALL, _unknown))

    # Global error handler
    app.add_error_handler(_error_handler)


def main() -> None:
    cfg = Config.load()
    _setup_logging(cfg.log_level)
    json_log(
        LOGGER,
        logging.INFO,
        "startup",
        dry_run=cfg.dry_run,
        base_url=cfg.doprax_base_url,
    )

    app = build_app(cfg)
    _register_handlers(app)

    async def runner() -> None:
        await _ensure_open(app)

        # Graceful shutdown signals
        loop = asyncio.get_running_loop()
        stop_event = asyncio.Event()

        def _stop(*_: object) -> None:
            stop_event.set()

        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, _stop)
            except NotImplementedError:
                # Windows
                pass

        await app.initialize()
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)

        await stop_event.wait()

        await app.updater.stop()
        await app.stop()
        await app.shutdown()

    asyncio.run(runner())


if __name__ == "__main__":
    main()
