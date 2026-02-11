from __future__ import annotations

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from bot.doprax_client import DopraxClient
from bot.handlers.common import HandlerDeps, get_lang, reply_menu, user_id_from_update
from bot.i18n import I18N
from bot.utils import compact_lines, safe_get


async def locations_cmd(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    deps: HandlerDeps,
    doprax: DopraxClient,
) -> None:
    user_id = user_id_from_update(update)
    if user_id is None:
        return
    lang = await get_lang(deps.storage, user_id)

    locs = await doprax.get_locations()
    lines: list[str] = [f"*{I18N.t(lang, 'locations_title')}*"]
    for loc in locs[:10]:
        name = str(safe_get(loc, "locationName", default=""))
        code = str(safe_get(loc, "locationCode", default=""))
        machines = safe_get(loc, "machines", default=[])
        plan_names: list[str] = []
        if isinstance(machines, list):
            for m in machines[:8]:
                plan_names.append(str(safe_get(m, "name", default="")))
        lines.append(f"- {name} (`{code}`): {', '.join([p for p in plan_names if p])}")

    await reply_menu(update, context, deps, lang, compact_lines(lines, limit=30))
