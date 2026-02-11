from __future__ import annotations

from dataclasses import dataclass


class BotError(Exception):
    """Base class for controlled bot errors."""


@dataclass(frozen=True)
class DopraxError(BotError):
    """Base Doprax error with a user-safe message key."""

    message_key: str
    details: str = ""


class DopraxAuthError(DopraxError):
    pass


class DopraxNotFound(DopraxError):
    pass


class DopraxValidationError(DopraxError):
    pass


class DopraxRateLimited(DopraxError):
    pass


class DopraxServerError(DopraxError):
    pass


class DopraxNetworkError(DopraxError):
    pass
