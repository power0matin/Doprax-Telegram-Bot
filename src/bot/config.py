from __future__ import annotations

from dataclasses import dataclass
from os import getenv


@dataclass(frozen=True)
class Config:
    """Application configuration loaded from environment variables."""

    telegram_bot_token: str
    doprax_api_key: str
    doprax_base_url: str
    log_level: str
    db_path: str
    dry_run: bool

    @staticmethod
    def load() -> "Config":
        telegram_bot_token = (getenv("TELEGRAM_BOT_TOKEN") or "").strip()
        doprax_api_key = (getenv("DOPRAX_API_KEY") or "").strip()
        doprax_base_url = (
            getenv("DOPRAX_BASE_URL") or "https://www.doprax.com"
        ).strip()
        log_level = (getenv("LOG_LEVEL") or "INFO").strip().upper()
        db_path = (getenv("DB_PATH") or "./data/bot.db").strip()
        dry_run = (getenv("DRY_RUN") or "0").strip() == "1"

        if not telegram_bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN is required")

        # In DRY_RUN mode, allow missing DOPRAX_API_KEY.
        if not dry_run and not doprax_api_key:
            raise ValueError("DOPRAX_API_KEY is required unless DRY_RUN=1")

        return Config(
            telegram_bot_token=telegram_bot_token,
            doprax_api_key=doprax_api_key,
            doprax_base_url=doprax_base_url,
            log_level=log_level,
            db_path=db_path,
            dry_run=dry_run,
        )
