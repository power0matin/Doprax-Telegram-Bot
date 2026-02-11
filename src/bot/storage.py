from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Optional

import aiosqlite

from bot.states import State


@dataclass(frozen=True)
class UserPrefs:
    user_id: int
    lang: str
    verbose: bool


@dataclass(frozen=True)
class UserSession:
    user_id: int
    state: State
    state_updated_at: int


@dataclass(frozen=True)
class CreateDraft:
    user_id: int
    provider_name: str
    plan: str
    preferred_location: str
    vm_name: str
    os_slug: str
    updated_at: int


class Storage:
    """SQLite persistence layer (async)."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._conn: Optional[aiosqlite.Connection] = None

    async def open(self) -> None:
        self._conn = await aiosqlite.connect(self._db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL;")
        await self._conn.execute("PRAGMA foreign_keys=ON;")
        await self._init_schema()

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("Storage not opened")
        return self._conn

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
        now = int(time.time())
        await self.conn.execute(
            "INSERT OR IGNORE INTO users(user_id, lang, verbose) VALUES(?, 'en', 0);",
            (user_id,),
        )
        await self.conn.execute(
            "INSERT OR IGNORE INTO sessions(user_id, state, state_updated_at, create_lock) "
            "VALUES(?, 'IDLE', ?, 0);",
            (user_id, now),
        )
        await self.conn.execute(
            "INSERT OR IGNORE INTO drafts(user_id, provider_name, plan, preferred_location, vm_name, os_slug, updated_at) "
            "VALUES(?, '', '', '', '', '', ?);",
            (user_id, now),
        )
        await self.conn.commit()

    async def get_prefs(self, user_id: int) -> UserPrefs:
        await self.ensure_user(user_id)
        row = await (
            await self.conn.execute("SELECT * FROM users WHERE user_id=?;", (user_id,))
        ).fetchone()
        assert row is not None
        return UserPrefs(
            user_id=user_id, lang=row["lang"], verbose=bool(row["verbose"])
        )

    async def set_lang(self, user_id: int, lang: str) -> None:
        await self.ensure_user(user_id)
        await self.conn.execute(
            "UPDATE users SET lang=? WHERE user_id=?;", (lang, user_id)
        )
        await self.conn.commit()

    async def toggle_verbose(self, user_id: int) -> bool:
        await self.ensure_user(user_id)
        prefs = await self.get_prefs(user_id)
        new_val = 0 if prefs.verbose else 1
        await self.conn.execute(
            "UPDATE users SET verbose=? WHERE user_id=?;", (new_val, user_id)
        )
        await self.conn.commit()
        return bool(new_val)

    async def get_session(self, user_id: int) -> UserSession:
        await self.ensure_user(user_id)
        row = await (
            await self.conn.execute(
                "SELECT * FROM sessions WHERE user_id=?;", (user_id,)
            )
        ).fetchone()
        assert row is not None
        return UserSession(
            user_id=user_id,
            state=State(row["state"]),
            state_updated_at=int(row["state_updated_at"]),
        )

    async def set_state(self, user_id: int, state: State) -> None:
        await self.ensure_user(user_id)
        now = int(time.time())
        await self.conn.execute(
            "UPDATE sessions SET state=?, state_updated_at=? WHERE user_id=?;",
            (state.value, now, user_id),
        )
        await self.conn.commit()

    async def get_create_lock(self, user_id: int) -> bool:
        await self.ensure_user(user_id)
        row = await (
            await self.conn.execute(
                "SELECT create_lock FROM sessions WHERE user_id=?;", (user_id,)
            )
        ).fetchone()
        assert row is not None
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
        now = int(time.time())
        await self.conn.execute(
            "UPDATE drafts SET provider_name='', plan='', preferred_location='', vm_name='', os_slug='', updated_at=? "
            "WHERE user_id=?;",
            (now, user_id),
        )
        await self.conn.commit()

    async def update_draft(self, user_id: int, **fields: Any) -> None:
        await self.ensure_user(user_id)
        now = int(time.time())
        allowed = {"provider_name", "plan", "preferred_location", "vm_name", "os_slug"}
        parts: list[str] = []
        values: list[Any] = []
        for k, v in fields.items():
            if k in allowed:
                parts.append(f"{k}=?")
                values.append(v)
        parts.append("updated_at=?")
        values.append(now)
        values.append(user_id)
        q = f"UPDATE drafts SET {', '.join(parts)} WHERE user_id=?;"
        await self.conn.execute(q, tuple(values))
        await self.conn.commit()

    async def get_draft(self, user_id: int) -> CreateDraft:
        await self.ensure_user(user_id)
        row = await (
            await self.conn.execute("SELECT * FROM drafts WHERE user_id=?;", (user_id,))
        ).fetchone()
        assert row is not None
        return CreateDraft(
            user_id=user_id,
            provider_name=row["provider_name"],
            plan=row["plan"],
            preferred_location=row["preferred_location"],
            vm_name=row["vm_name"],
            os_slug=row["os_slug"],
            updated_at=int(row["updated_at"]),
        )

    async def ratelimit_check(self, user_id: int, cooldown_seconds: int) -> bool:
        """Return True if allowed now, else False."""
        await self.ensure_user(user_id)
        now = int(time.time())
        row = await (
            await self.conn.execute(
                "SELECT last_ts FROM ratelimits WHERE user_id=?;", (user_id,)
            )
        ).fetchone()
        last = int(row["last_ts"]) if row is not None else 0
        if now - last < cooldown_seconds:
            return False
        await self.conn.execute(
            "INSERT INTO ratelimits(user_id, last_ts) VALUES(?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET last_ts=excluded.last_ts;",
            (user_id, now),
        )
        await self.conn.commit()
        return True
