from __future__ import annotations

import time
from typing import Any

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from bot.doprax_client import DopraxClient
from bot.handlers.common import HandlerDeps, get_lang, reply_menu, safe_answer_callback, user_id_from_update
from bot.i18n import I18N
from bot.keyboards import CB, status_refresh_inline
from bot.states import State
from bot.utils import safe_get


async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE, deps: HandlerDeps, doprax: DopraxClient) -> None:
    user_id = user_id_from_update(update)
    if user_id is None:
        return
    lang = await get_lang(deps.storage, user_id)

    if update.message is None:
        return

    parts = (update.message.text or "").strip().split(maxsplit=1)
    if len(parts) == 2 and parts[1].strip():
        vm_code = parts[1].strip()
        await _send_status(update, context, deps, doprax, lang, vm_code)
        return

    # If no arg, enter FSM prompt
    await deps.storage.set_state(user_id, State.STATUS_WAIT_CODE)
    await reply_menu(update, context, deps, lang, I18N.t(lang, "ask_vm_code"))


async def status_by_text(update: Update, context: ContextTypes.DEFAULT_TYPE, deps: HandlerDeps, doprax: DopraxClient) -> None:
    user_id = user_id_from_update(update)
    if user_id is None or update.message is None:
        return
    sess = await deps.storage.get_session(user_id)
    if sess.state != State.STATUS_WAIT_CODE:
        return

    lang = await get_lang(deps.storage, user_id)
    vm_code = (update.message.text or "").strip()
    await deps.storage.set_state(user_id, State.IDLE)
    await _send_status(update, context, deps, doprax, lang, vm_code)


async def status_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, deps: HandlerDeps, doprax: DopraxClient) -> None:
    if update.callback_query is None:
        return
    await safe_answer_callback(update)
    user_id = user_id_from_update(update)
    if user_id is None:
        return
    lang = await get_lang(deps.storage, user_id)
    data = update.callback_query.data or ""
    if not data.startswith(CB.VM_STATUS):
        return
    vm_code = data.split(":", 1)[1]
    await _send_status(update, context, deps, doprax, lang, vm_code)


async def _send_status(
    update: Update, context: ContextTypes.DEFAULT_TYPE, deps: HandlerDeps, doprax: DopraxClient, lang: str, vm_code: str
) -> None:
    if update.effective_chat is None:
        return
    st = await doprax.get_vm_status(vm_code)
    status = str(safe_get(st, "status", default="UNKNOWN"))
    active = str(safe_get(st, "isActive", default="N/A"))
    checked = time.strftime("%Y-%m-%d %H:%M:%S")
    text = f"*{I18N.t(lang, 'vm_status_title')}*\n\n" + I18N.t(
        lang, "vm_status_body", code=vm_code, status=status, active=active, checked=checked
    )
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        reply_markup=status_refresh_inline(lang, vm_code),
        parse_mode=ParseMode.MARKDOWN,
    )
