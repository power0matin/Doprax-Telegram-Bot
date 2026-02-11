from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from bot.doprax_client import DopraxClient
from bot.handlers.common import HandlerDeps, get_lang, reply_menu, user_id_from_update
from bot.i18n import I18N
from bot.utils import compact_lines, safe_get


async def os_cmd(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    deps: HandlerDeps,
    doprax: DopraxClient,
) -> None:
    user_id = user_id_from_update(update)
    if user_id is None:
        return
    lang = await get_lang(deps.storage, user_id)

    os_list = await doprax.get_os_list()

    slugs_raw = [
        str(safe_get(x, "slug", default="")).strip()
        for x in os_list
        if isinstance(x, dict)
    ]
    slugs = sorted({s for s in slugs_raw if s})  # dedupe + sort

    lines = [f"*{I18N.t(lang, 'os_title')}*"] + [f"- `{s}`" for s in slugs[:50]]
    await reply_menu(update, context, deps, lang, compact_lines(lines, limit=60))
