from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import aiosqlite

from bot.states import State

_DRAFT_FIELDS = ("provider_name", "plan", "preferred_location", "vm_name", "os_slug")


@dataclass(frozen=True, slots=True)
class UserPrefs:
    user_id: int
    lang: str
    verbose: bool


@dataclass(frozen=True, slots=True)
class UserSession:
    user_id: int
    state: State
    state_updated_at: int


@dataclass(frozen=True, slots=True)
class CreateDraft:
    user_id: int
    provider_name: str
    plan: str
    preferred_location: str
    vm_name: str
    os_slug: str
    updated_at: int


class Storage:
    """Async SQLite persistence layer for users, sessions, drafts, and rate limits."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._conn: aiosqlite.Connection | None = None

    async def open(self) -> None:
        self._conn = await aiosqlite.connect(self._db_path)
        self._conn.row_factory = aiosqlite.Row
        await self.conn.execute("PRAGMA journal_mode=WAL;")
        await self.conn.execute("PRAGMA foreign_keys=ON;")
        await self._init_schema()

    async def close(self) -> None:
        if self._conn is None:
            return
        await self._conn.close()
        self._conn = None

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("Storage has not been opened")
        return self._conn

    @staticmethod
    def _now() -> int:
        return int(time.time())

    async def _fetch_one(self, query: str, params: Sequence[Any]) -> aiosqlite.Row:
        cursor = await self.conn.execute(query, params)
        row = await cursor.fetchone()
        if row is None:
            raise RuntimeError("Expected database row was not found")
        return row

    async def _init_schema(self) -> None:
        await self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
              user_id INTEGER PRIMARY KEY,
              lang TEXT NOT NULL DEFAULT 'en',
              verbose INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS sessions (
              user_id INTEGER PRIMARY KEY,
              state TEXT NOT NULL DEFAULT 'IDLE',
              state_updated_at INTEGER NOT NULL DEFAULT 0,
              create_lock INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS drafts (
              user_id INTEGER PRIMARY KEY,
              provider_name TEXT NOT NULL DEFAULT '',
              plan TEXT NOT NULL DEFAULT '',
              preferred_location TEXT NOT NULL DEFAULT '',
              vm_name TEXT NOT NULL DEFAULT '',
              os_slug TEXT NOT NULL DEFAULT '',
              updated_at INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS ratelimits (
              user_id INTEGER PRIMARY KEY,
              last_ts INTEGER NOT NULL DEFAULT 0
            );
            """
        )
        await self.conn.commit()

    async def ensure_user(self, user_id: int) -> None:
        now = self._now()
        await self.conn.execute(
            "INSERT OR IGNORE INTO users(user_id, lang, verbose) VALUES(?, 'en', 0);",
            (user_id,),
        )
        await self.conn.execute(
            """
            INSERT OR IGNORE INTO sessions(user_id, state, state_updated_at, create_lock)
            VALUES(?, 'IDLE', ?, 0);
            """,
            (user_id, now),
        )
        await self.conn.execute(
            """
            INSERT OR IGNORE INTO drafts(
              user_id,
              provider_name,
              plan,
              preferred_location,
              vm_name,
              os_slug,
              updated_at
            )
            VALUES(?, '', '', '', '', '', ?);
            """,
            (user_id, now),
        )
        await self.conn.commit()

    async def get_prefs(self, user_id: int) -> UserPrefs:
        await self.ensure_user(user_id)
        row = await self._fetch_one(
            "SELECT user_id, lang, verbose FROM users WHERE user_id=?;",
            (user_id,),
        )
        return UserPrefs(
            user_id=int(row["user_id"]),
            lang=str(row["lang"]),
            verbose=bool(row["verbose"]),
        )

    async def set_lang(self, user_id: int, lang: str) -> None:
        await self.ensure_user(user_id)
        await self.conn.execute(
            "UPDATE users SET lang=? WHERE user_id=?;",
            (lang, user_id),
        )
        await self.conn.commit()

    async def toggle_verbose(self, user_id: int) -> bool:
        await self.ensure_user(user_id)
        prefs = await self.get_prefs(user_id)
        new_value = 0 if prefs.verbose else 1
        await self.conn.execute(
            "UPDATE users SET verbose=? WHERE user_id=?;",
            (new_value, user_id),
        )
        await self.conn.commit()
        return bool(new_value)

    async def get_session(self, user_id: int) -> UserSession:
        await self.ensure_user(user_id)
        row = await self._fetch_one(
            "SELECT user_id, state, state_updated_at FROM sessions WHERE user_id=?;",
            (user_id,),
        )
        return UserSession(
            user_id=int(row["user_id"]),
            state=State(str(row["state"])),
            state_updated_at=int(row["state_updated_at"]),
        )

    async def set_state(self, user_id: int, state: State) -> None:
        await self.ensure_user(user_id)
        await self.conn.execute(
            "UPDATE sessions SET state=?, state_updated_at=? WHERE user_id=?;",
            (state.value, self._now(), user_id),
        )
        await self.conn.commit()

    async def get_create_lock(self, user_id: int) -> bool:
        await self.ensure_user(user_id)
        row = await self._fetch_one(
            "SELECT create_lock FROM sessions WHERE user_id=?;",
            (user_id,),
        )
        return bool(row["create_lock"])

    async def set_create_lock(self, user_id: int, locked: bool) -> None:
        await self.ensure_user(user_id)
        await self.conn.execute(
            "UPDATE sessions SET create_lock=? WHERE user_id=?;",
            (1 if locked else 0, user_id),
        )
        await self.conn.commit()

    async def reset_draft(self, user_id: int) -> None:
        await self.ensure_user(user_id)
        await self.conn.execute(
            """
            UPDATE drafts
            SET provider_name='',
                plan='',
                preferred_location='',
                vm_name='',
                os_slug='',
                updated_at=?
            WHERE user_id=?;
            """,
            (self._now(), user_id),
        )
        await self.conn.commit()

    async def update_draft(self, user_id: int, **fields: Any) -> None:
        await self.ensure_user(user_id)

        updates: list[str] = []
        values: list[Any] = []
        for field_name in _DRAFT_FIELDS:
            if field_name in fields:
                updates.append(f"{field_name}=?")
                values.append(fields[field_name])

        updates.append("updated_at=?")
        values.extend((self._now(), user_id))

        query = f"UPDATE drafts SET {', '.join(updates)} WHERE user_id=?;"
        await self.conn.execute(query, tuple(values))
        await self.conn.commit()

    async def get_draft(self, user_id: int) -> CreateDraft:
        await self.ensure_user(user_id)
        row = await self._fetch_one(
            """
            SELECT user_id, provider_name, plan, preferred_location, vm_name, os_slug, updated_at
            FROM drafts
            WHERE user_id=?;
            """,
            (user_id,),
        )
        return CreateDraft(
            user_id=int(row["user_id"]),
            provider_name=str(row["provider_name"]),
            plan=str(row["plan"]),
            preferred_location=str(row["preferred_location"]),
            vm_name=str(row["vm_name"]),
            os_slug=str(row["os_slug"]),
            updated_at=int(row["updated_at"]),
        )

    async def ratelimit_check(self, user_id: int, cooldown_seconds: int) -> bool:
        """Return True when the user may perform a rate-limited action now."""
        await self.ensure_user(user_id)
        now = self._now()
        cursor = await self.conn.execute(
            "SELECT last_ts FROM ratelimits WHERE user_id=?;",
            (user_id,),
        )
        row = await cursor.fetchone()
        last_ts = int(row["last_ts"]) if row is not None else 0

        if now - last_ts < cooldown_seconds:
            return False

        await self.conn.execute(
            """
            INSERT INTO ratelimits(user_id, last_ts)
            VALUES(?, ?)
            ON CONFLICT(user_id) DO UPDATE SET last_ts=excluded.last_ts;
            """,
            (user_id, now),
        )
        await self.conn.commit()
        return True
