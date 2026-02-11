from __future__ import annotations

import time
from typing import Any, Optional

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from bot.doprax_client import DopraxClient
from bot.handlers.common import (
    HandlerDeps,
    get_lang,
    reply_menu,
    safe_answer_callback,
    user_id_from_update,
)
from bot.i18n import I18N
from bot.keyboards import (
    CB,
    create_confirm_inline,
    create_location_inline,
    create_os_inline,
    create_plan_inline,
    create_provider_inline,
)
from bot.states import State, can_transition, previous_state
from bot.utils import (
    compact_lines,
    safe_get,
    validate_location,
    validate_os_slug,
    validate_plan,
    validate_provider,
    validate_vm_name,
)

QUICK_OS = ["ubuntu_22_04", "ubuntu_24_04", "ubuntu_20_04", "centos_stream_9"]


async def create_vm_cmd(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    deps: HandlerDeps,
    doprax: DopraxClient,
) -> None:
    user_id = user_id_from_update(update)
    if user_id is None:
        return
    lang = await get_lang(deps.storage, user_id)

    await deps.storage.reset_draft(user_id)
    await deps.storage.set_state(user_id, State.CREATE_PROVIDER)

    if update.effective_chat is None:
        return
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=I18N.t(lang, "create_start"),
        reply_markup=create_provider_inline(lang),
        parse_mode=ParseMode.MARKDOWN,
    )


async def create_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    deps: HandlerDeps,
    doprax: DopraxClient,
) -> None:
    if update.callback_query is None:
        return
    await safe_answer_callback(update)
    user_id = user_id_from_update(update)
    if user_id is None or update.effective_chat is None:
        return
    lang = await get_lang(deps.storage, user_id)
    sess = await deps.storage.get_session(user_id)
    data = update.callback_query.data or ""
    if (
        not data.startswith(CB.CREATE)
        and not data.startswith(CB.LOC_PICK)
        and not data.startswith(CB.OS_PICK)
    ):
        return

    # Universal cancel/back
    if data == f"{CB.CREATE}cancel":
        await _cancel(update, context, deps, lang, user_id)
        return
    if data == f"{CB.CREATE}back":
        await _back(update, context, deps, doprax, lang, user_id, sess.state)
        return

    # Location pick shortcut
    if data.startswith(CB.LOC_PICK):
        code = data.split(":", 1)[1]
        # store preferred_location as "code:<code>" so we can use it later if needed
        await deps.storage.update_draft(user_id, preferred_location=f"code:{code}")
        await deps.storage.set_state(user_id, State.CREATE_NAME)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=I18N.t(lang, "create_name_ask"),
            reply_markup=create_location_inline(lang, suggestions=None),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    # OS pick
    if data.startswith(CB.OS_PICK):
        os_slug = data.split(":", 1)[1]
        allowed = await _allowed_os(doprax)
        vr = validate_os_slug(os_slug, allowed)
        if not vr.ok:
            await context.bot.send_message(
                chat_id=update.effective_chat.id, text=I18N.t(lang, "validation_os")
            )
            return
        await deps.storage.update_draft(user_id, os_slug=vr.value)
        await deps.storage.set_state(user_id, State.CREATE_CONFIRM)
        await _send_confirm(update, context, deps, doprax, lang, user_id)
        return

    # Step callbacks
    if data.startswith(f"{CB.CREATE}prov:"):
        if sess.state != State.CREATE_PROVIDER:
            await deps.storage.set_state(user_id, State.CREATE_PROVIDER)
        provider = data.split("prov:", 1)[1]
        vr = validate_provider(provider)
        if not vr.ok:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=I18N.t(lang, "validation_provider"),
            )
            return
        await deps.storage.update_draft(user_id, provider_name=vr.value)
        await deps.storage.set_state(user_id, State.CREATE_PLAN)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=I18N.t(lang, "create_provider_set", provider=vr.value)
            + "\n\n"
            + I18N.t(lang, "create_plan_ask"),
            reply_markup=create_plan_inline(lang),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    if data.startswith(f"{CB.CREATE}plan:"):
        plan = data.split("plan:", 1)[1]
        vr = validate_plan(plan)
        if not vr.ok:
            await context.bot.send_message(
                chat_id=update.effective_chat.id, text=I18N.t(lang, "validation_plan")
            )
            return
        await deps.storage.update_draft(user_id, plan=vr.value)
        await deps.storage.set_state(user_id, State.CREATE_LOCATION)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=I18N.t(lang, "create_plan_set", plan=vr.value)
            + "\n\n"
            + I18N.t(lang, "create_location_ask"),
            reply_markup=create_location_inline(lang, suggestions=None),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    if data.startswith(f"{CB.CREATE}confirm:"):
        action = data.split("confirm:", 1)[1]
        if action == "edit":
            # Restart at provider to edit via steps
            await deps.storage.set_state(user_id, State.CREATE_PROVIDER)
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=I18N.t(lang, "edit_hint"),
                reply_markup=create_provider_inline(lang),
                parse_mode=ParseMode.MARKDOWN,
            )
            return
        if action == "create":
            await _perform_create(update, context, deps, doprax, lang, user_id)
            return


async def create_by_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    deps: HandlerDeps,
    doprax: DopraxClient,
) -> None:
    user_id = user_id_from_update(update)
    if user_id is None or update.message is None or update.effective_chat is None:
        return
    lang = await get_lang(deps.storage, user_id)
    sess = await deps.storage.get_session(user_id)
    text = (update.message.text or "").strip()

    if sess.state == State.CREATE_PLAN:
        vr = validate_plan(text)
        if not vr.ok:
            await context.bot.send_message(
                chat_id=update.effective_chat.id, text=I18N.t(lang, "validation_plan")
            )
            return
        await deps.storage.update_draft(user_id, plan=vr.value)
        await deps.storage.set_state(user_id, State.CREATE_LOCATION)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=I18N.t(lang, "create_plan_set", plan=vr.value)
            + "\n\n"
            + I18N.t(lang, "create_location_ask"),
            reply_markup=create_location_inline(lang, suggestions=None),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    if sess.state == State.CREATE_LOCATION:
        vr = validate_location(text)
        if not vr.ok:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=I18N.t(lang, "validation_location"),
            )
            return
        await deps.storage.update_draft(user_id, preferred_location=vr.value)
        await deps.storage.set_state(user_id, State.CREATE_NAME)

        # Provide suggestions (best-effort) based on current draft plan
        draft = await deps.storage.get_draft(user_id)
        suggestions: Optional[list[tuple[str, str]]] = None
        try:
            locs = await doprax.get_locations()
            suggestions = _location_suggestions(locs, vr.value)
        except Exception:
            suggestions = None

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=I18N.t(lang, "create_location_set", location=vr.value)
            + "\n\n"
            + I18N.t(lang, "create_name_ask"),
            reply_markup=create_location_inline(lang, suggestions=suggestions),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    if sess.state == State.CREATE_NAME:
        vr = validate_vm_name(text)
        if not vr.ok:
            await context.bot.send_message(
                chat_id=update.effective_chat.id, text=I18N.t(lang, "validation_name")
            )
            return
        await deps.storage.update_draft(user_id, vm_name=vr.value)
        await deps.storage.set_state(user_id, State.CREATE_OS)

        allowed = await _allowed_os(doprax)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=I18N.t(lang, "create_name_set", name=vr.value)
            + "\n\n"
            + I18N.t(lang, "create_os_ask"),
            reply_markup=create_os_inline(lang, QUICK_OS, allowed),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    if sess.state == State.CREATE_OS:
        allowed = await _allowed_os(doprax)
        vr = validate_os_slug(text, allowed)
        if not vr.ok:
            await context.bot.send_message(
                chat_id=update.effective_chat.id, text=I18N.t(lang, "validation_os")
            )
            return
        await deps.storage.update_draft(user_id, os_slug=vr.value)
        await deps.storage.set_state(user_id, State.CREATE_CONFIRM)
        await _send_confirm(update, context, deps, doprax, lang, user_id)
        return


async def cancel_cmd(
    update: Update, context: ContextTypes.DEFAULT_TYPE, deps: HandlerDeps
) -> None:
    user_id = user_id_from_update(update)
    if user_id is None:
        return
    lang = await get_lang(deps.storage, user_id)
    await _cancel(update, context, deps, lang, user_id)


async def _cancel(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    deps: HandlerDeps,
    lang: str,
    user_id: int,
) -> None:
    await deps.storage.set_state(user_id, State.IDLE)
    await deps.storage.reset_draft(user_id)
    await deps.storage.set_create_lock(user_id, False)
    await reply_menu(update, context, deps, lang, I18N.t(lang, "cancelled"))


async def _back(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    deps: HandlerDeps,
    doprax: DopraxClient,
    lang: str,
    user_id: int,
    state: State,
) -> None:
    prev = previous_state(state)
    if not can_transition(state, prev):
        prev = State.IDLE
    await deps.storage.set_state(user_id, prev)
    if update.effective_chat is None:
        return
    if prev == State.IDLE:
        await reply_menu(update, context, deps, lang, I18N.t(lang, "back_to_menu"))
        return
    if prev == State.CREATE_PROVIDER:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=I18N.t(lang, "create_start"),
            reply_markup=create_provider_inline(lang),
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    if prev == State.CREATE_PLAN:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=I18N.t(lang, "create_plan_ask"),
            reply_markup=create_plan_inline(lang),
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    if prev == State.CREATE_LOCATION:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=I18N.t(lang, "create_location_ask"),
            reply_markup=create_location_inline(lang, suggestions=None),
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    if prev == State.CREATE_NAME:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=I18N.t(lang, "create_name_ask"),
            reply_markup=create_location_inline(lang, suggestions=None),
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    if prev == State.CREATE_OS:
        allowed = await _allowed_os(doprax)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=I18N.t(lang, "create_os_ask"),
            reply_markup=create_os_inline(lang, QUICK_OS, allowed),
            parse_mode=ParseMode.MARKDOWN,
        )
        return


async def _allowed_os(doprax: DopraxClient) -> list[str]:
    os_list = await doprax.get_os_list()
    allowed = [str(safe_get(x, "slug", default="")) for x in os_list]
    return [s for s in allowed if s]


def _location_suggestions(
    locs: list[dict[str, Any]], preferred: str
) -> list[tuple[str, str]]:
    pref = preferred.lower()
    out: list[tuple[str, str]] = []
    for loc in locs:
        name = str(safe_get(loc, "locationName", default=""))
        code = str(safe_get(loc, "locationCode", default=""))
        if not name or not code:
            continue
        if any(tok in name.lower() for tok in pref.split()[:3]):
            out.append((name, code))
    return out[:6]


async def _send_confirm(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    deps: HandlerDeps,
    doprax: DopraxClient,
    lang: str,
    user_id: int,
) -> None:
    if update.effective_chat is None:
        return
    draft = await deps.storage.get_draft(user_id)

    pref = draft.preferred_location
    # If user picked "code:..." keep preferred string for scoring, but we can still resolve via name/plan.
    pref_for_resolve = pref if not pref.startswith("code:") else ""

    location_code, machine_code, suggestions = (
        await doprax.resolve_location_and_machine_codes(
            draft.plan, pref_for_resolve or " "
        )
    )

    suggestions_text = (
        compact_lines(suggestions, limit=8)
        if suggestions
        else I18N.t(lang, "create_confirm_no_suggestions")
    )

    text = I18N.t(
        lang,
        "create_confirm",
        provider=draft.provider_name or "-",
        plan=draft.plan or "-",
        location=draft.preferred_location or "-",
        name=draft.vm_name or "-",
        os_slug=draft.os_slug or "-",
        location_code=location_code or "-",
        machine_type_code=machine_code or "-",
        suggestions=suggestions_text,
    )
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        reply_markup=create_confirm_inline(lang),
        parse_mode=ParseMode.MARKDOWN,
    )


async def _perform_create(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    deps: HandlerDeps,
    doprax: DopraxClient,
    lang: str,
    user_id: int,
) -> None:
    if update.effective_chat is None:
        return

    locked = await deps.storage.get_create_lock(user_id)
    if locked:
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text=I18N.t(lang, "create_in_progress")
        )
        return

    await deps.storage.set_create_lock(user_id, True)
    ref_time = int(time.time())
    try:
        draft = await deps.storage.get_draft(user_id)
        # Resolve codes
        pref_for_resolve = (
            draft.preferred_location
            if not draft.preferred_location.startswith("code:")
            else ""
        )
        location_code, machine_code, suggestions = (
            await doprax.resolve_location_and_machine_codes(
                draft.plan, pref_for_resolve or " "
            )
        )

        # If user explicitly picked a location code, prefer it
        if draft.preferred_location.startswith("code:"):
            location_code = draft.preferred_location.split("code:", 1)[1]

        if not location_code or not machine_code:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=I18N.t(
                    lang,
                    "create_failed_resolution",
                    suggestions=compact_lines(suggestions, limit=8),
                ),
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        payload = {
            "name": draft.vm_name,
            "machine_type_code": machine_code,
            "location_code": location_code,
            "provider_name": draft.provider_name,
            "os_slug": draft.os_slug,
        }

        created = await doprax.create_vm(payload)
        code = str(
            safe_get(created, "vm_code", default=safe_get(created, "code", default=""))
        )
        status = str(safe_get(created, "status", default="UNKNOWN"))

        await deps.storage.set_state(user_id, State.IDLE)
        await deps.storage.reset_draft(user_id)

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=I18N.t(
                lang,
                "create_success",
                name=draft.vm_name,
                code=code or "-",
                status=status,
            ),
            parse_mode=ParseMode.MARKDOWN,
        )
    finally:
        # always clear lock
        await deps.storage.set_create_lock(user_id, False)
        # ensure state doesn't remain in confirm if failed silently
        sess = await deps.storage.get_session(user_id)
        if sess.state != State.IDLE and int(time.time()) - ref_time > 5:
            await deps.storage.set_state(user_id, State.IDLE)
