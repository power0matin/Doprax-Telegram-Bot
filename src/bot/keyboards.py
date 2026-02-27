from __future__ import annotations

from typing import Iterable, Sequence
from collections.abc import Iterable, Sequence
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from bot.i18n import I18N, Lang


class CB:
    """Callback data prefixes."""

    LANG = "LANG:"
    MENU = "MENU:"
    VM_STATUS = "VMSTAT:"
    VM_DETAILS = "VMDET:"
    CREATE = "CREATE:"
    SETTINGS = "SET:"
    LOC_PICK = "LOCPICK:"
    OS_PICK = "OSPICK:"


def main_reply_keyboard(lang: Lang) -> ReplyKeyboardMarkup:
    t = I18N.t
    rows = [
        [
            KeyboardButton(t(lang, "btn_vm_mgmt")),
            KeyboardButton(t(lang, "btn_create_vm")),
        ],
        [
            KeyboardButton(t(lang, "btn_list_vms")),
            KeyboardButton(t(lang, "btn_vm_status")),
        ],
        [
            KeyboardButton(t(lang, "btn_locations")),
            KeyboardButton(t(lang, "btn_os_list")),
        ],
        [KeyboardButton(t(lang, "btn_settings")), KeyboardButton(t(lang, "btn_help"))],
    ]
    return ReplyKeyboardMarkup(rows, resize_keyboard=True, is_persistent=True)


def lang_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("فارسی", callback_data=f"{CB.LANG}fa"),
                InlineKeyboardButton("English", callback_data=f"{CB.LANG}en"),
            ]
        ]
    )


def vm_mgmt_inline(lang: Lang) -> InlineKeyboardMarkup:
    t = I18N.t
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    t(lang, "btn_list_vms"), callback_data=f"{CB.MENU}list_vms"
                ),
                InlineKeyboardButton(
                    t(lang, "btn_status"), callback_data=f"{CB.MENU}status_prompt"
                ),
            ],
            [
                InlineKeyboardButton(
                    t(lang, "btn_refresh"), callback_data=f"{CB.MENU}refresh_vm_mgmt"
                )
            ],
        ]
    )


def back_cancel_row(
    lang: Lang, back_cb: str, cancel_cb: str
) -> list[InlineKeyboardButton]:
    t = I18N.t
    return [
        InlineKeyboardButton(t(lang, "btn_back"), callback_data=back_cb),
        InlineKeyboardButton(t(lang, "btn_cancel"), callback_data=cancel_cb),
    ]


def create_provider_inline(lang: Lang) -> InlineKeyboardMarkup:
    providers = ["Digitalocean", "Hetzner", "OVH", "Gcore", "Vultr", "Scaleway"]
    rows: list[list[InlineKeyboardButton]] = []
    for i in range(0, len(providers), 2):
        row = [
            InlineKeyboardButton(
                providers[i], callback_data=f"{CB.CREATE}prov:{providers[i]}"
            ),
        ]
        if i + 1 < len(providers):
            row.append(
                InlineKeyboardButton(
                    providers[i + 1],
                    callback_data=f"{CB.CREATE}prov:{providers[i + 1]}",
                )
            )
        rows.append(row)

    rows.append(back_cancel_row(lang, f"{CB.CREATE}back", f"{CB.CREATE}cancel"))
    return InlineKeyboardMarkup(rows)


def create_plan_inline(lang: Lang) -> InlineKeyboardMarkup:
    quick = ["DO1", "DO2", "DO3", "H1", "g1a", "g1b", "V1", "SW1", "SW2"]
    rows: list[list[InlineKeyboardButton]] = []
    for i in range(0, len(quick), 3):
        chunk = quick[i : i + 3]
        rows.append(
            [
                InlineKeyboardButton(x, callback_data=f"{CB.CREATE}plan:{x}")
                for x in chunk
            ]
        )
    rows.append(back_cancel_row(lang, f"{CB.CREATE}back", f"{CB.CREATE}cancel"))
    return InlineKeyboardMarkup(rows)


def create_location_inline(
    lang: Lang, suggestions: Sequence[tuple[str, str]] | None = None
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if suggestions:
        for name, code in suggestions[:6]:
            rows.append(
                [InlineKeyboardButton(f"{name}", callback_data=f"{CB.LOC_PICK}{code}")]
            )
    rows.append(back_cancel_row(lang, f"{CB.CREATE}back", f"{CB.CREATE}cancel"))
    return InlineKeyboardMarkup(rows)


def create_os_inline(
    lang: Lang, quick: Iterable[str], allowed: Iterable[str]
) -> InlineKeyboardMarkup:
    allowed_set = set(allowed)
    quick_list = [q for q in quick if q in allowed_set]
    rows: list[list[InlineKeyboardButton]] = []
    for i in range(0, len(quick_list), 2):
        chunk = quick_list[i : i + 2]
        rows.append(
            [InlineKeyboardButton(x, callback_data=f"{CB.OS_PICK}{x}") for x in chunk]
        )
    rows.append(back_cancel_row(lang, f"{CB.CREATE}back", f"{CB.CREATE}cancel"))
    return InlineKeyboardMarkup(rows)


def create_confirm_inline(lang: Lang) -> InlineKeyboardMarkup:
    t = I18N.t
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    t(lang, "btn_create"), callback_data=f"{CB.CREATE}confirm:create"
                ),
                InlineKeyboardButton(
                    t(lang, "btn_edit"), callback_data=f"{CB.CREATE}confirm:edit"
                ),
            ],
            back_cancel_row(lang, f"{CB.CREATE}back", f"{CB.CREATE}cancel"),
        ]
    )


def settings_inline(lang: Lang) -> InlineKeyboardMarkup:
    t = I18N.t
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    t(lang, "btn_change_lang"), callback_data=f"{CB.SETTINGS}lang"
                )
            ],
            [
                InlineKeyboardButton(
                    t(lang, "btn_toggle_verbose"), callback_data=f"{CB.SETTINGS}verbose"
                )
            ],
            [
                InlineKeyboardButton(
                    t(lang, "btn_about"), callback_data=f"{CB.SETTINGS}about"
                )
            ],
        ]
    )


def vm_list_inline(lang: Lang, vm_code: str) -> InlineKeyboardMarkup:
    t = I18N.t
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    t(lang, "btn_status"), callback_data=f"{CB.VM_STATUS}{vm_code}"
                ),
                InlineKeyboardButton(
                    t(lang, "btn_details"), callback_data=f"{CB.VM_DETAILS}{vm_code}"
                ),
            ]
        ]
    )


def status_refresh_inline(lang: Lang, vm_code: str) -> InlineKeyboardMarkup:
    t = I18N.t
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    t(lang, "btn_refresh"), callback_data=f"{CB.VM_STATUS}{vm_code}"
                )
            ]
        ]
    )
