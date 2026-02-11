from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from bot.doprax_client import DopraxClient
from bot.handlers.common import HandlerDeps, get_lang, reply_menu, user_id_from_update
from bot.i18n import I18N


async def health_cmd(
    update: Update, context: ContextTypes.DEFAULT_TYPE, deps: HandlerDeps, doprax: DopraxClient, dry_run: bool
) -> None:
    user_id = user_id_from_update(update)
    if user_id is None:
        return
    lang = await get_lang(deps.storage, user_id)

    doprax_status = I18N.t(lang, "health_doprax_ok")
    try:
        await doprax.get_os_list()
    except Exception as e:
        doprax_status = I18N.t(lang, "health_doprax_fail", reason=str(e)[:80])

    await reply_menu(
        update,
        context,
        deps,
        lang,
        I18N.t(lang, "health_ok", doprax=doprax_status, dry_run="1" if dry_run else "0"),
    )
