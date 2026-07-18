from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as package_version
from pathlib import Path
from typing import Any, TypeAlias, cast

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
from bot.states import State, is_create_state
from bot.storage import Storage
from bot.utils import new_correlation_id, redact_secrets

LOGGER = logging.getLogger("doprax_telegram_bot")
TEXT_MESSAGE_FILTER = filters.TEXT & ~filters.COMMAND

TelegramApplication: TypeAlias = Application[Any, Any, Any, Any, Any, Any]
HandlerCallable: TypeAlias = Callable[..., Coroutine[Any, Any, Any]]
TelegramHandler: TypeAlias = Callable[[Update, ContextTypes.DEFAULT_TYPE], Coroutine[Any, Any, Any]]


def _setup_logging(level: str) -> None:
    logging.basicConfig(level=level, format="%(message)s")


async def _set_commands(app: TelegramApplication) -> None:
    commands = [
        BotCommand("start", "Launch the Doprax assistant"),
        BotCommand("help", "Get guidance and available commands"),
        BotCommand("lang", "Change language"),
        BotCommand("menu", "Open the main control center"),
        BotCommand("list_vms", "View your virtual machines"),
        BotCommand("create_vm", "Create a new VM step by step"),
        BotCommand("status", "Check a VM status"),
        BotCommand("locations", "Browse locations and plans"),
        BotCommand("os", "Browse available operating systems"),
        BotCommand("cancel", "Cancel the current workflow"),
        BotCommand("health", "Check bot and API health"),
    ]
    await app.bot.set_my_commands(commands)


async def _send_localized_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    lang: str,
    message_key: str,
    **kwargs: Any,
) -> None:
    chat = update.effective_chat
    if chat is None:
        return

    await context.bot.send_message(
        chat_id=chat.id,
        text=I18N.t(lang, message_key, **kwargs),
        reply_markup=main_reply_keyboard(lang),
        parse_mode=ParseMode.MARKDOWN,
    )


async def _preprocess(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if context.application is None:
        return True
    deps: HandlerDeps = context.application.bot_data["deps"]
    storage: Storage = deps.storage
    user_id = user_id_from_update(update)
    if user_id is None:
        return True

    await storage.ensure_user(user_id)

    expired = await reset_if_timed_out(
        storage,
        user_id,
        deps.session_timeout_seconds,
    )
    if expired:
        lang = await get_lang(storage, user_id)
        await _send_localized_message(update, context, lang, "timeout_reset")

    is_start_command = bool(
        update.message and update.message.text and update.message.text.strip().startswith("/start")
    )
    is_language_callback = bool(
        update.callback_query
        and update.callback_query.data
        and update.callback_query.data.startswith("LANG:")
    )

    if is_start_command or is_language_callback:
        return True

    allowed = await enforce_ratelimit(
        storage,
        user_id,
        deps.ratelimit_cooldown_seconds,
    )
    if allowed:
        return True

    lang = await get_lang(storage, user_id)
    await _send_localized_message(update, context, lang, "rate_limited")
    return False


async def _unknown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.application is None:
        return
    deps: HandlerDeps = context.application.bot_data["deps"]
    user_id = user_id_from_update(update)
    if user_id is None:
        return

    lang = await get_lang(deps.storage, user_id)
    await _send_localized_message(update, context, lang, "unknown_input")


async def _error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.application is None:
        return
    deps: HandlerDeps = context.application.bot_data["deps"]
    reference = new_correlation_id()
    error = context.error
    LOGGER.error(
        redact_secrets(f"[{reference}] Unhandled error: {error}"),
        exc_info=error,
    )

    if not isinstance(update, Update):
        return

    lang = "en"
    user_id = user_id_from_update(update)
    if user_id is not None:
        try:
            lang = await get_lang(deps.storage, user_id)
            await deps.storage.set_state(user_id, State.IDLE)
            await deps.storage.reset_draft(user_id)
            await deps.storage.set_create_lock(user_id, False)
        except Exception as recovery_error:
            LOGGER.warning(redact_secrets(f"[{reference}] Error recovery failed: {recovery_error}"))
            lang = "en"

    await _send_localized_message(
        update,
        context,
        lang,
        "something_wrong",
        ref=reference,
    )


def _wrap(
    handler: HandlerCallable,
    *args: Any,
    **kwargs: Any,
) -> TelegramHandler:
    async def _inner(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await _preprocess(update, context):
            return
        await handler(update, context, *args, **kwargs)

    return _inner


async def _dispatch_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.application is None:
        return
    deps: HandlerDeps = context.application.bot_data["deps"]
    doprax: DopraxClient = context.application.bot_data["doprax"]
    user_id = user_id_from_update(update)
    if user_id is None:
        return

    session = await deps.storage.get_session(user_id)
    if session.state is State.STATUS_WAIT_CODE:
        await status_by_text(update, context, deps, doprax)
        return

    if is_create_state(session.state):
        await create_by_text(update, context, deps, doprax)
        return

    await menu_by_text(update, context, deps)


async def _dispatch_vm_mgmt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.application is None:
        return
    deps: HandlerDeps = context.application.bot_data["deps"]
    doprax: DopraxClient = context.application.bot_data["doprax"]
    action = await vm_mgmt_callback(update, context, deps)

    if action == "list_vms":
        await list_vms_cmd(update, context, deps, doprax)
        return

    if action == "status_prompt":
        user_id = user_id_from_update(update)
        if user_id is None:
            return

        await deps.storage.set_state(user_id, State.STATUS_WAIT_CODE)
        lang = await get_lang(deps.storage, user_id)
        await _send_localized_message(update, context, lang, "ask_vm_code")
        return

    if action == "refresh_vm_mgmt":
        await vm_mgmt_cmd(update, context, deps)


async def _shutdown(app: TelegramApplication) -> None:
    deps: HandlerDeps = app.bot_data["deps"]
    doprax: DopraxClient = app.bot_data["doprax"]
    await doprax.close()
    await deps.storage.close()


async def _post_init(app: TelegramApplication) -> None:
    deps: HandlerDeps = app.bot_data["deps"]
    doprax: DopraxClient = app.bot_data["doprax"]
    db_path: str = app.bot_data["db_path"]
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    await deps.storage.open()
    await doprax.open()
    await _set_commands(app)


def build_app(cfg: Config) -> TelegramApplication:
    deps = HandlerDeps(storage=Storage(cfg.db_path), logger=LOGGER)
    doprax = DopraxClient(
        DopraxConfig(
            base_url=cfg.doprax_base_url,
            api_key=cfg.doprax_api_key,
            dry_run=cfg.dry_run,
        )
    )

    app = cast(
        TelegramApplication,
        ApplicationBuilder().token(cfg.telegram_bot_token).concurrent_updates(True).build(),
    )
    app.bot_data["deps"] = deps
    app.bot_data["doprax"] = doprax
    app.bot_data["version"] = _safe_version()
    app.bot_data["dry_run"] = cfg.dry_run
    app.bot_data["db_path"] = cfg.db_path

    app.post_init = _post_init
    app.post_shutdown = _shutdown

    return app


def _safe_version() -> str:
    try:
        return package_version("doprax-telegram-bot")
    except PackageNotFoundError:
        return "0.0.0"


def _register_handlers(app: TelegramApplication) -> None:
    deps: HandlerDeps = app.bot_data["deps"]
    doprax: DopraxClient = app.bot_data["doprax"]
    version: str = app.bot_data["version"]
    dry_run: bool = app.bot_data["dry_run"]

    app.add_handler(CommandHandler("start", _wrap(start_cmd, deps)))
    app.add_handler(CallbackQueryHandler(_wrap(lang_callback, deps), pattern=r"^LANG:(fa|en)$"))

    app.add_handler(CommandHandler("help", _wrap(help_cmd, deps)))
    app.add_handler(CommandHandler("menu", _wrap(menu_cmd, deps)))
    app.add_handler(CommandHandler("lang", _wrap(start_cmd, deps)))

    app.add_handler(CommandHandler("vm_mgmt", _wrap(vm_mgmt_cmd, deps)))
    app.add_handler(CallbackQueryHandler(_wrap(_dispatch_vm_mgmt), pattern=r"^MENU:"))

    app.add_handler(CommandHandler("list_vms", _wrap(list_vms_cmd, deps, doprax)))
    app.add_handler(CommandHandler("status", _wrap(status_cmd, deps, doprax)))
    app.add_handler(CallbackQueryHandler(_wrap(status_callback, deps, doprax), pattern=r"^VMSTAT:"))

    app.add_handler(CommandHandler("locations", _wrap(locations_cmd, deps, doprax)))
    app.add_handler(CommandHandler("os", _wrap(os_cmd, deps, doprax)))

    app.add_handler(CommandHandler("create_vm", _wrap(create_vm_cmd, deps, doprax)))
    app.add_handler(CommandHandler("cancel", _wrap(cancel_cmd, deps)))
    app.add_handler(
        CallbackQueryHandler(
            _wrap(create_callback, deps, doprax),
            pattern=r"^(CREATE:|LOCPICK:|OSPICK:)",
        )
    )

    app.add_handler(CommandHandler("settings", _wrap(settings_cmd, deps)))
    app.add_handler(
        CallbackQueryHandler(
            _wrap(settings_callback, deps, version),
            pattern=r"^SET:",
        )
    )

    app.add_handler(CommandHandler("health", _wrap(health_cmd, deps, doprax, dry_run)))
    app.add_handler(MessageHandler(TEXT_MESSAGE_FILTER, _wrap(_dispatch_text)))
    app.add_handler(MessageHandler(filters.ALL, _unknown))
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
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
