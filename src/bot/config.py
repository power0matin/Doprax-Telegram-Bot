from __future__ import annotations

from dataclasses import dataclass
from os import getenv

_TRUE_VALUES = {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class Config:
    """Application configuration loaded from environment variables."""

    telegram_bot_token: str
    doprax_api_key: str
    doprax_base_url: str
    log_level: str
    db_path: str
    dry_run: bool

    @staticmethod
    def load() -> Config:
        telegram_bot_token = _env("TELEGRAM_BOT_TOKEN")
        doprax_api_key = _env("DOPRAX_API_KEY")
        doprax_base_url = _env("DOPRAX_BASE_URL", "https://doprax.com")
        log_level = _env("LOG_LEVEL", "INFO").upper()
        db_path = _env("DB_PATH", "./data/bot.db")
        dry_run = _env_bool("DRY_RUN")

        if not telegram_bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN is required")

        if not dry_run and not doprax_api_key:
            raise ValueError("DOPRAX_API_KEY is required unless DRY_RUN=1")

        return Config(
            telegram_bot_token=telegram_bot_token,
            doprax_api_key=doprax_api_key,
            doprax_base_url=doprax_base_url.rstrip("/"),
            log_level=log_level,
            db_path=db_path,
            dry_run=dry_run,
        )


def _env(name: str, default: str = "") -> str:
    return (getenv(name) or default).strip()


def _env_bool(name: str, default: bool = False) -> bool:
    value = getenv(name)
    if value is None:
        return default
    return value.strip().casefold() in _TRUE_VALUES
