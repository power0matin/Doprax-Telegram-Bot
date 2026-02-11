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
from bot.keyboards import CB, lang_keyboard, settings_inline


async def settings_cmd(
    update: Update, context: ContextTypes.DEFAULT_TYPE, deps: HandlerDeps
) -> None:
    user_id = user_id_from_update(update)
    if user_id is None:
        return
    lang = await get_lang(deps.storage, user_id)
    await reply_menu(update, context, deps, lang, I18N.t(lang, "settings_title"))
    if update.effective_chat is None:
        return
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=I18N.t(lang, "settings_title"),
        reply_markup=settings_inline(lang),
        parse_mode=ParseMode.MARKDOWN,
    )


async def settings_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE, deps: HandlerDeps, version: str
) -> None:
    if update.callback_query is None:
        return
    await safe_answer_callback(update)
    user_id = user_id_from_update(update)
    if user_id is None or update.effective_chat is None:
        return
    lang = await get_lang(deps.storage, user_id)
    data = update.callback_query.data or ""
    if not data.startswith(CB.SETTINGS):
        return
    action = data.split(":", 1)[1]

    if action == "lang":
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=I18N.t(lang, "choose_lang"),
            reply_markup=lang_keyboard(),
        )
        return

    if action == "verbose":
        new_verbose = await deps.storage.toggle_verbose(user_id)
        msg = I18N.t(lang, "verbose_on") if new_verbose else I18N.t(lang, "verbose_off")
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text=msg, parse_mode=ParseMode.MARKDOWN
        )
        return

    if action == "about":
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=I18N.t(lang, "about", version=version),
            parse_mode=ParseMode.MARKDOWN,
        )
