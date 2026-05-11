from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

Lang = str  # "fa" | "en"


@dataclass(frozen=True, slots=True)
class I18n:
    """Simple i18n dictionary with parameter formatting."""

    strings: Mapping[Lang, Mapping[str, str]]

    def t(self, lang: Lang, key: str, **kwargs: Any) -> str:
        table = self.strings.get(lang) or self.strings["en"]
        template = table.get(key) or self.strings["en"].get(key) or key
        try:
            return template.format(**kwargs)
        except Exception:
            # Never crash on formatting errors.
            return template


I18N = I18n(
    strings={
        "en": {
            # General
            "app_name": "Doprax VM Bot",
            "choose_lang": "Choose your language:",
            "lang_set": "Language set to English ✅",
            "menu_title": "Main menu:",
            "help_title": "Help",
            "cancelled": "Cancelled. Back to main menu.",
            "back_to_menu": "Back to main menu.",
            "unknown_input": "I didn't understand that. Please use the buttons or commands.",
            "rate_limited": "You're doing that too fast. Please wait a moment and try again.",
            "timeout_reset": "Your previous session expired due to inactivity. Returning to the main menu.",
            "something_wrong": "Something went wrong. Reference: {ref}. Returning to a safe menu.",
            "health_ok": "✅ Bot is running.\nDoprax connectivity: {doprax}\nDRY_RUN: {dry_run}",
            "health_doprax_ok": "OK",
            "health_doprax_fail": "FAILED ({reason})",
            "about": "This bot manages Doprax VMs via the Doprax API.\n\nVersion: {version}",
            # Buttons / menu
            "btn_vm_mgmt": "📌 VM Management",
            "btn_create_vm": "➕ Create VM",
            "btn_list_vms": "📋 List VMs",
            "btn_vm_status": "🔎 VM Status",
            "btn_locations": "🌍 Locations & Plans",
            "btn_os_list": "💿 OS List",
            "btn_settings": "⚙️ Settings",
            "btn_help": "❓ Help",
            "btn_back": "⬅️ Back",
            "btn_cancel": "❌ Cancel",
            "btn_refresh": "🔄 Refresh",
            "btn_edit": "✏️ Edit",
            "btn_create": "✅ Create",
            "btn_details": "📋 Details",
            "btn_status": "🔎 Status",
            "btn_change_lang": "🌐 Change Language",
            "btn_toggle_verbose": "📝 Toggle Verbose",
            "btn_about": "ℹ️ About",
            # VM list/status
            "vms_title": "Your VMs:",
            "vms_empty": "No VMs found.",
            "vm_line": "• {name} — `{code}` — {status}{loc}",
            "vm_loc": " — {location}",
            "vm_status_title": "VM Status",
            "vm_status_body": "Code: `{code}`\nStatus: {status}\nActive: {active}\nChecked: {checked}",
            "ask_vm_code": "Please send the VM code (example: `abcd1234`).",
            "status_usage": "Usage: /status <vm_code>",
            # Locations / OS
            "locations_title": "Locations & plans mapping (summary):",
            "os_title": "Available OS slugs:",
            # Create wizard
            "create_start": "Create VM wizard started. Choose a provider:",
            "create_provider_set": "Provider set: {provider}",
            "create_plan_ask": "Send a plan name (or tap a quick pick). Example: DO1, H1, SW1",
            "create_plan_set": "Plan set: {plan}",
            "create_location_ask": "Send a preferred location name. Example: Germany, Frankfurt",
            "create_location_set": "Preferred location set: {location}",
            "create_name_ask": "Send a VM name (letters, digits, dash). Max 32 chars.",
            "create_name_set": "VM name set: {name}",
            "create_os_ask": "Choose an OS slug (or tap a quick pick):",
            "create_os_set": "OS slug set: {os_slug}",
            "create_confirm": "Please confirm:\n\nProvider: {provider}\nPlan: {plan}\nPreferred location: {location}\nVM name: {name}\nOS: {os_slug}\n\nResolution:\nLocation code: {location_code}\nMachine type code: {machine_type_code}\n\nSuggestions:\n{suggestions}",
            "create_confirm_no_suggestions": "No alternatives needed.",
            "create_in_progress": "A VM creation is already in progress for you. Please wait.",
            "create_success": "✅ VM created!\nName: {name}\nCode: `{code}`\nInitial status: {status}",
            "create_failed_resolution": "Could not resolve plan/location codes. Try a different plan or location.\nSuggestions:\n{suggestions}",
            "edit_which": "Which field do you want to edit?",
            "edit_hint": "Use the wizard steps via the buttons. Choose a step:",
            "validation_provider": "Invalid provider. Please choose from the buttons.",
            "validation_plan": "Invalid plan. Use 2-16 chars, letters/digits/dash/underscore.",
            "validation_location": "Invalid location. Please send a short text (2-64 chars).",
            "validation_name": "Invalid name. Use letters/digits/dash. Max 32 chars.",
            "validation_os": "Invalid OS slug. Please choose from the list.",
            # Settings
            "settings_title": "Settings:",
            "verbose_on": "Verbose mode: ON",
            "verbose_off": "Verbose mode: OFF",
        },
        "fa": {
            "app_name": "ربات مدیریت VM دوپراکس",
            "choose_lang": "زبان خود را انتخاب کنید:",
            "lang_set": "زبان روی فارسی تنظیم شد ✅",
            "menu_title": "منوی اصلی:",
            "help_title": "راهنما",
            "cancelled": "لغو شد. بازگشت به منوی اصلی.",
            "back_to_menu": "بازگشت به منوی اصلی.",
            "unknown_input": "متوجه نشدم. لطفاً از دکمه‌ها یا دستورها استفاده کنید.",
            "rate_limited": "درخواست‌های پشت سر هم زیاد است. کمی صبر کنید و دوباره تلاش کنید.",
            "timeout_reset": "به دلیل عدم فعالیت، نشست قبلی منقضی شد. بازگشت به منوی اصلی.",
            "something_wrong": "مشکلی پیش آمد. کد پیگیری: {ref}. شما به منوی امن برمی‌گردید.",
            "health_ok": "✅ ربات فعال است.\nوضعیت اتصال به دوپراکس: {doprax}\nDRY_RUN: {dry_run}",
            "health_doprax_ok": "موفق",
            "health_doprax_fail": "ناموفق ({reason})",
            "about": "این ربات مدیریت VMهای دوپراکس را از طریق API انجام می‌دهد.\n\nنسخه: {version}",
            "btn_vm_mgmt": "📌 مدیریت VM",
            "btn_create_vm": "➕ ساخت VM",
            "btn_list_vms": "📋 لیست VMها",
            "btn_vm_status": "🔎 وضعیت VM",
            "btn_locations": "🌍 لوکیشن‌ها و پلن‌ها",
            "btn_os_list": "💿 لیست OS",
            "btn_settings": "⚙️ تنظیمات",
            "btn_help": "❓ راهنما",
            "btn_back": "⬅️ بازگشت",
            "btn_cancel": "❌ لغو",
            "btn_refresh": "🔄 بروزرسانی",
            "btn_edit": "✏️ ویرایش",
            "btn_create": "✅ ساخت",
            "btn_details": "📋 جزئیات",
            "btn_status": "🔎 وضعیت",
            "btn_change_lang": "🌐 تغییر زبان",
            "btn_toggle_verbose": "📝 تغییر حالت نمایش",
            "btn_about": "ℹ️ درباره",
            "vms_title": "VMهای شما:",
            "vms_empty": "هیچ VMای پیدا نشد.",
            "vm_line": "• {name} — `{code}` — {status}{loc}",
            "vm_loc": " — {location}",
            "vm_status_title": "وضعیت VM",
            "vm_status_body": "کد: `{code}`\nوضعیت: {status}\nفعال: {active}\nزمان بررسی: {checked}",
            "ask_vm_code": "لطفاً کد VM را ارسال کنید (مثال: `abcd1234`).",
            "status_usage": "فرمت: /status <vm_code>",
            "locations_title": "خلاصه لوکیشن‌ها و پلن‌ها:",
            "os_title": "اسلاگ‌های OS موجود:",
            "create_start": "ویزارد ساخت VM شروع شد. یک ارائه‌دهنده انتخاب کنید:",
            "create_provider_set": "ارائه‌دهنده انتخاب شد: {provider}",
            "create_plan_ask": "نام پلن را ارسال کنید (یا یکی از گزینه‌های سریع را بزنید). مثال: DO1, H1, SW1",
            "create_plan_set": "پلن تنظیم شد: {plan}",
            "create_location_ask": "لوکیشن ترجیحی را ارسال کنید. مثال: Germany, Frankfurt",
            "create_location_set": "لوکیشن ترجیحی تنظیم شد: {location}",
            "create_name_ask": "نام VM را ارسال کنید (حروف/اعداد/خط تیره). حداکثر ۳۲ کاراکتر.",
            "create_name_set": "نام VM تنظیم شد: {name}",
            "create_os_ask": "یک OS slug انتخاب کنید (یا گزینه سریع):",
            "create_os_set": "OS slug تنظیم شد: {os_slug}",
            "create_confirm": "لطفاً تایید کنید:\n\nارائه‌دهنده: {provider}\nپلن: {plan}\nلوکیشن ترجیحی: {location}\nنام VM: {name}\nOS: {os_slug}\n\nنتیجه تطبیق:\nکد لوکیشن: {location_code}\nکد ماشین: {machine_type_code}\n\nپیشنهادها:\n{suggestions}",
            "create_confirm_no_suggestions": "پیشنهاد جایگزین لازم نیست.",
            "create_in_progress": "در حال حاضر یک ساخت VM برای شما در جریان است. لطفاً صبر کنید.",
            "create_success": "✅ VM ساخته شد!\nنام: {name}\nکد: `{code}`\nوضعیت اولیه: {status}",
            "create_failed_resolution": "امکان تطبیق پلن/لوکیشن نبود. پلن یا لوکیشن را تغییر دهید.\nپیشنهادها:\n{suggestions}",
            "edit_which": "کدام فیلد را می‌خواهید ویرایش کنید؟",
            "edit_hint": "با دکمه‌ها مرحله مورد نظر را انتخاب کنید:",
            "validation_provider": "ارائه‌دهنده نامعتبر است. لطفاً از دکمه‌ها انتخاب کنید.",
            "validation_plan": "پلن نامعتبر است. ۲ تا ۱۶ کاراکتر (حروف/اعداد/خط تیره/underscore).",
            "validation_location": "لوکیشن نامعتبر است. یک متن کوتاه (۲ تا ۶۴ کاراکتر) ارسال کنید.",
            "validation_name": "نام نامعتبر است. فقط حروف/اعداد/خط تیره. حداکثر ۳۲ کاراکتر.",
            "validation_os": "OS slug نامعتبر است. لطفاً از لیست انتخاب کنید.",
            "settings_title": "تنظیمات:",
            "verbose_on": "حالت نمایش: کامل",
            "verbose_off": "حالت نمایش: خلاصه",
        },
    }
)
