from __future__ import annotations

import json
import logging
import os
import re
import secrets
import time
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

SECRET_KEYS = ("TELEGRAM_BOT_TOKEN", "DOPRAX_API_KEY")

_REDACTION_TOKEN = "***REDACTED***"
_PLAN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{1,15}$")
_VM_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

_PROVIDER_ALIASES = {
    "digitalocean": "Digitalocean",
    "digital ocean": "Digitalocean",
    "hetzner": "Hetzner",
    "ovh": "OVH",
    "gcore": "Gcore",
    "vultr": "Vultr",
    "scaleway": "Scaleway",
}


@dataclass(frozen=True, slots=True)
class ValidationResult:
    ok: bool
    value: str


def new_correlation_id() -> str:
    """Create a compact id that links user-facing errors to structured logs."""
    return secrets.token_hex(6)


def redact_secrets(value: str) -> str:
    """Remove configured secrets from strings before they are logged."""
    redacted = value
    for key in SECRET_KEYS:
        secret = (os.getenv(key) or "").strip()
        if secret:
            redacted = redacted.replace(secret, _REDACTION_TOKEN)
    return redacted


def json_log(logger: logging.Logger, level: int, event: str, **fields: Any) -> None:
    """Emit a redacted structured log entry as a single JSON line."""
    payload: dict[str, Any] = {
        "ts": int(time.time()),
        "event": event,
        **fields,
    }
    message = json.dumps(payload, ensure_ascii=False, default=str, sort_keys=True)
    logger.log(level, redact_secrets(message))


def validate_provider(text: str) -> ValidationResult:
    """Validate and normalize a supported cloud provider name."""
    normalized = _normalized_label(text)
    provider = _PROVIDER_ALIASES.get(normalized, "")
    return ValidationResult(ok=bool(provider), value=provider)


def validate_plan(text: str) -> ValidationResult:
    """Validate a Doprax plan slug: 2-16 chars, alnum/dash/underscore."""
    plan = text.strip()
    return ValidationResult(ok=bool(_PLAN_RE.fullmatch(plan)), value=plan)


def validate_location(text: str) -> ValidationResult:
    """Validate a user-facing location label while preserving readable casing."""
    location = " ".join(text.strip().split())
    return ValidationResult(ok=2 <= len(location) <= 64, value=location)


def validate_vm_name(text: str) -> ValidationResult:
    """Validate and normalize a DNS-friendly VM name."""
    name = text.strip().lower()
    if not 1 <= len(name) <= 32:
        return ValidationResult(ok=False, value=name)
    return ValidationResult(ok=bool(_VM_NAME_RE.fullmatch(name)), value=name)


def validate_os_slug(text: str, allowed: Iterable[str]) -> ValidationResult:
    """Validate that the selected OS slug exists in the provider response."""
    slug = text.strip()
    return ValidationResult(ok=slug in set(allowed), value=slug)


def compact_lines(lines: Iterable[str], limit: int = 20) -> str:
    """Join lines with a display-safe maximum number of entries."""
    if limit <= 0:
        return ""

    output: list[str] = []
    for index, line in enumerate(lines):
        if index >= limit:
            output.append("…")
            break
        output.append(line)
    return "\n".join(output)


def safe_get(mapping: Mapping[str, Any], *path: str, default: Any = None) -> Any:
    """Safely read a nested mapping path without raising KeyError/TypeError."""
    current: Any = mapping
    for key in path:
        if not isinstance(current, Mapping) or key not in current:
            return default
        current = current[key]
    return current


def _normalized_label(value: str) -> str:
    return " ".join(value.casefold().strip().split())
