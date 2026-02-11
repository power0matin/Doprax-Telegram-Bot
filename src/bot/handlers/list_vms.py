from __future__ import annotations

import time
from typing import Any

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from bot.doprax_client import DopraxClient
from bot.handlers.common import HandlerDeps, get_lang, reply_menu, user_id_from_update
from bot.i18n import I18N
from bot.keyboards import vm_list_inline
from bot.utils import safe_get


def _fmt_vm_line(lang: str, vm: dict[str, Any]) -> str:
    name = str(safe_get(vm, "name", default="(no-name)"))
    code = str(safe_get(vm, "vm_code", default=safe_get(vm, "code", default="")))
    status = str(safe_get(vm, "status", default="UNKNOWN"))
    loc = str(safe_get(vm, "location", default=""))
    loc_part = I18N.t(lang, "vm_loc", location=loc) if loc else ""
    return I18N.t(lang, "vm_line", name=name, code=code, status=status, loc=loc_part)


async def list_vms_cmd(
    update: Update, context: ContextTypes.DEFAULT_TYPE, deps: HandlerDeps, doprax: DopraxClient
) -> None:
    user_id = user_id_from_update(update)
    if user_id is None:
        return
    lang = await get_lang(deps.storage, user_id)

    vms = await doprax.list_vms()
    if not vms:
        await reply_menu(update, context, deps, lang, I18N.t(lang, "vms_empty"))
        return

    header = f"*{I18N.t(lang, 'vms_title')}*"
    lines = [header]
    for vm in vms[:20]:
        lines.append(_fmt_vm_line(lang, vm))

    await reply_menu(update, context, deps, lang, "\n".join(lines) + f"\n\n_{time.strftime('%Y-%m-%d %H:%M:%S')}_")

    # Additionally, for convenience, send inline buttons per VM (first few)
    if update.effective_chat is None:
        return
    for vm in vms[:5]:
        code = str(safe_get(vm, "vm_code", default=safe_get(vm, "code", default="")))
        if not code:
            continue
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=_fmt_vm_line(lang, vm),
            reply_markup=vm_list_inline(lang, code),
            parse_mode=ParseMode.MARKDOWN,
        )
