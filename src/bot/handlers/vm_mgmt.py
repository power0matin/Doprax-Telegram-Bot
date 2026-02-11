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
from bot.keyboards import CB, vm_mgmt_inline


async def vm_mgmt_cmd(
    update: Update, context: ContextTypes.DEFAULT_TYPE, deps: HandlerDeps
) -> None:
    user_id = user_id_from_update(update)
    if user_id is None:
        return
    lang = await get_lang(deps.storage, user_id)
    await reply_menu(update, context, deps, lang, I18N.t(lang, "btn_vm_mgmt"))
    if update.effective_chat is None:
        return
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=I18N.t(lang, "btn_vm_mgmt"),
        reply_markup=vm_mgmt_inline(lang),
        parse_mode=ParseMode.MARKDOWN,
    )


async def vm_mgmt_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE, deps: HandlerDeps
) -> str | None:
    """Returns an action string for main to dispatch."""
    if update.callback_query is None:
        return None
    await safe_answer_callback(update)
    data = update.callback_query.data or ""
    if not data.startswith(CB.MENU):
        return None
    return data.split(":", 1)[1]
