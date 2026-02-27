from __future__ import annotations
from collections.abc import Iterable, Mapping
import json
import logging
import os
import re
import secrets
import time
from dataclasses import dataclass

SECRET_KEYS = ("TELEGRAM_BOT_TOKEN", "DOPRAX_API_KEY")


def new_correlation_id() -> str:
    """Create a short correlation id for linking logs with user-facing errors."""
    return secrets.token_hex(6)


def redact_secrets(value: str) -> str:
    """Redact known secrets that may appear in logs."""
    redacted = value
    for k in SECRET_KEYS:
        s = (os.getenv(k) or "").strip()
        if s:
            redacted = redacted.replace(s, "***REDACTED***")
    return redacted


def json_log(logger: logging.Logger, level: int, event: str, **fields: Any) -> None:
    """Emit a structured JSON-ish log line to stdout."""
    payload: dict[str, Any] = {
        "ts": int(time.time()),
        "event": event,
        **fields,
    }
    msg = redact_secrets(json.dumps(payload, ensure_ascii=False, default=str))
    logger.log(level, msg)


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    value: str


_PROVIDER_SET = {
    "Digitalocean": "Digitalocean",
    "Hetzner": "Hetzner",
    "OVH": "OVH",
    "Gcore": "Gcore",
    "Vultr": "Vultr",
    "Scaleway": "Scaleway",
}

_PLAN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{1,15}$")
_NAME_RE = re.compile(r"^[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*$")


def validate_provider(text: str) -> ValidationResult:
    """Validate provider name against allowed providers."""
    t = text.strip()
    return ValidationResult(ok=t in _PROVIDER_SET, value=_PROVIDER_SET.get(t, ""))


def validate_plan(text: str) -> ValidationResult:
    """Validate plan string (2-16 chars, letters/digits/dash/underscore)."""
    t = text.strip()
    return ValidationResult(ok=bool(_PLAN_RE.fullmatch(t)), value=t)


def validate_location(text: str) -> ValidationResult:
    """Validate preferred location string (2-64 chars)."""
    t = " ".join(text.strip().split())
    return ValidationResult(ok=2 <= len(t) <= 64, value=t)


def validate_vm_name(text: str) -> ValidationResult:
    """Validate VM name (DNS-ish: letters/digits + dash segments, max 32)."""
    t = text.strip()
    if len(t) < 1 or len(t) > 32:
        return ValidationResult(ok=False, value=t)
    return ValidationResult(ok=bool(_NAME_RE.fullmatch(t)), value=t)


def validate_os_slug(text: str, allowed: Iterable[str]) -> ValidationResult:
    """Validate OS slug is in allowed list."""
    t = text.strip()
    allowed_set = set(allowed)
    return ValidationResult(ok=t in allowed_set, value=t)


def compact_lines(lines: Iterable[str], limit: int = 20) -> str:
    """Join lines with a safe limit."""
    out: list[str] = []
    for i, line in enumerate(lines):
        if i >= limit:
            out.append("…")
            break
        out.append(line)
    return "\n".join(out)


def safe_get(mapping: Mapping[str, Any], *path: str, default: Any = None) -> Any:
    """Safely get nested keys."""
    cur: Any = mapping
    for p in path:
        if not isinstance(cur, dict) or p not in cur:
            return default
        cur = cur[p]
    return cur
