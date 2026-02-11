from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from bot.i18n import I18N, Lang
from bot.keyboards import main_reply_keyboard
from bot.states import State
from bot.storage import Storage
from bot.utils import json_log, new_correlation_id


@dataclass(frozen=True)
class HandlerDeps:
    storage: Storage
    logger: logging.Logger
    session_timeout_seconds: int = 15 * 60
    ratelimit_cooldown_seconds: int = 2


def user_id_from_update(update: Update) -> Optional[int]:
    u = update.effective_user
    return u.id if u else None


async def get_lang(storage: Storage, user_id: int) -> Lang:
    prefs = await storage.get_prefs(user_id)
    return prefs.lang  # type: ignore[return-value]


async def reply_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, deps: HandlerDeps, lang: Lang, text: str) -> None:
    if update.effective_chat is None:
        return
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        reply_markup=main_reply_keyboard(lang),
        parse_mode=ParseMode.MARKDOWN,
    )


async def enforce_ratelimit(storage: Storage, user_id: int, cooldown: int) -> bool:
    return await storage.ratelimit_check(user_id, cooldown_seconds=cooldown)


async def reset_if_timed_out(storage: Storage, user_id: int, timeout_seconds: int) -> bool:
    sess = await storage.get_session(user_id)
    if sess.state == State.IDLE:
        return False
    now = int(time.time())
    if now - sess.state_updated_at > timeout_seconds:
        await storage.set_state(user_id, State.IDLE)
        await storage.reset_draft(user_id)
        await storage.set_create_lock(user_id, False)
        return True
    return False


async def safe_answer_callback(update: Update) -> None:
    if update.callback_query:
        try:
            await update.callback_query.answer()
        except Exception:
            # Telegram may reject if too late; ignore.
            return


async def safe_user_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    deps: HandlerDeps,
    lang: Lang,
    key: str,
    **kwargs: object,
) -> None:
    """Send a localized message safely."""
    if update.effective_chat is None:
        return
    text = I18N.t(lang, key, **kwargs)
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        reply_markup=main_reply_keyboard(lang),
        parse_mode=ParseMode.MARKDOWN,
    )


def log_event(deps: HandlerDeps, event: str, **fields: object) -> None:
    json_log(deps.logger, logging.INFO, event, **fields)


def correlation_for_update(update: Update) -> str:
    # Use Telegram update_id if possible; add randomness for safety
    base = str(update.update_id) if update.update_id is not None else "no_update_id"
    return f"{base}-{new_correlation_id()}"
