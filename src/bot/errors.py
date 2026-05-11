from __future__ import annotations

from dataclasses import dataclass


class BotError(Exception):
    """Base class for controlled bot errors."""


@dataclass(frozen=True, slots=True)
class DopraxError(BotError):
    """Base Doprax error with a user-safe message key."""

    message_key: str
    details: str = ""


class DopraxAuthError(DopraxError):
    """Authentication or authorization failed."""


class DopraxNotFound(DopraxError):
    """The requested Doprax resource was not found."""


class DopraxValidationError(DopraxError):
    """The Doprax API rejected the request payload."""


class DopraxRateLimited(DopraxError):
    """The Doprax API rate limit was exceeded."""


class DopraxServerError(DopraxError):
    """The Doprax API returned a server-side error."""


class DopraxNetworkError(DopraxError):
    """The Doprax API could not be reached reliably."""
