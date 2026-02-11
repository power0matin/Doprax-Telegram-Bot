from __future__ import annotations

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from bot.handlers.common import (
    HandlerDeps,
    get_lang,
    reply_menu,
    safe_answer_callback,
    user_id_from_update,
)
from bot.i18n import I18N
from bot.keyboards import CB, lang_keyboard
from bot.states import State


async def start_cmd(
    update: Update, context: ContextTypes.DEFAULT_TYPE, deps: HandlerDeps
) -> None:
    user_id = user_id_from_update(update)
    if user_id is None or update.effective_chat is None:
        return

    await deps.storage.ensure_user(user_id)
    lang = await get_lang(deps.storage, user_id)

    # If user hasn't chosen explicitly, still show selector
    await deps.storage.set_state(user_id, State.IDLE)
    await deps.storage.reset_draft(user_id)

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=I18N.t(lang, "choose_lang"),
        reply_markup=lang_keyboard(),
        parse_mode=ParseMode.MARKDOWN,
    )


async def lang_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE, deps: HandlerDeps
) -> None:
    user_id = user_id_from_update(update)
    if (
        user_id is None
        or update.effective_chat is None
        or update.callback_query is None
    ):
        return
    await safe_answer_callback(update)

    data = update.callback_query.data or ""
    if not data.startswith(CB.LANG):
        return
    lang = data.split(":", 1)[1].strip()
    if lang not in ("fa", "en"):
        lang = "en"
    await deps.storage.set_lang(user_id, lang)
    await deps.storage.set_state(user_id, State.IDLE)

    await reply_menu(
        update,
        context,
        deps,
        lang,
        I18N.t(lang, "lang_set") + "\n\n" + I18N.t(lang, "menu_title"),
    )
