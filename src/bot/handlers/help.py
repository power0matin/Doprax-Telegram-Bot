from __future__ import annotations

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from bot.handlers.common import HandlerDeps, get_lang, reply_menu, user_id_from_update
from bot.i18n import I18N


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE, deps: HandlerDeps) -> None:
    user_id = user_id_from_update(update)
    if user_id is None:
        return
    lang = await get_lang(deps.storage, user_id)

    text = (
        f"*{I18N.t(lang, 'help_title')}*\n\n"
        "/start\n"
        "/help\n"
        "/lang\n"
        "/menu\n"
        "/list_vms\n"
        "/create_vm\n"
        "/status <vm_code>\n"
        "/locations\n"
        "/os\n"
        "/cancel\n"
        "/health\n\n"
        + I18N.t(lang, "unknown_input")
    )
    await reply_menu(update, context, deps, lang, text)
