from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from bot.handlers.common import HandlerDeps, get_lang, reply_menu, user_id_from_update
from bot.i18n import I18N
from bot.states import State


async def menu_cmd(
    update: Update, context: ContextTypes.DEFAULT_TYPE, deps: HandlerDeps
) -> None:
    user_id = user_id_from_update(update)
    if user_id is None:
        return
    lang = await get_lang(deps.storage, user_id)
    await deps.storage.set_state(user_id, State.IDLE)
    await reply_menu(update, context, deps, lang, I18N.t(lang, "menu_title"))


async def menu_by_text(
    update: Update, context: ContextTypes.DEFAULT_TYPE, deps: HandlerDeps
) -> None:
    user_id = user_id_from_update(update)
    if user_id is None or update.message is None:
        return
    lang = await get_lang(deps.storage, user_id)
    text = (update.message.text or "").strip()

    mapping = {
        I18N.t(lang, "btn_help"): "/help",
        I18N.t(lang, "btn_list_vms"): "/list_vms",
        I18N.t(lang, "btn_create_vm"): "/create_vm",
        I18N.t(lang, "btn_vm_status"): "/status",
        I18N.t(lang, "btn_locations"): "/locations",
        I18N.t(lang, "btn_os_list"): "/os",
        I18N.t(lang, "btn_settings"): "/settings",
        I18N.t(lang, "btn_vm_mgmt"): "/vm_mgmt",
    }

    cmd = mapping.get(text)
    if cmd is None:
        return

    # Dispatch by invoking command handlers via chat text
    await context.bot.send_message(chat_id=update.effective_chat.id, text=cmd)
