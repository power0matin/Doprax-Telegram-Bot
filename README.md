# Doprax Telegram Bot (FA/EN)

![CI](https://github.com/power0matin/doprax-telegram-bot/actions/workflows/ci.yml/badge.svg)
![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)

A production-grade, bilingual (فارسی/English) Telegram bot to manage Doprax VMs using the Doprax VM API.

Maintained by **Matin Shahabadi** — Website: `https://matinshahabadi.ir` — Email: `me@matinshahabadi.ir`

## Overview & Features

- ✅ Async, non-blocking (python-telegram-bot v21+ + httpx async)
- ✅ Fully menu-driven UX:
  - Persistent **Reply Keyboard** main menu
  - Inline “glass” menus for actions and wizard steps
- ✅ Bilingual FA/EN with `/lang` switch at any time
- ✅ Robust finite-state machine (FSM) persisted in SQLite
- ✅ Create VM wizard with validation, Back/Cancel, timeout recovery
- ✅ Rate limiting per user (cooldown)
- ✅ Idempotency guard: prevents double VM creation on double-tap
- ✅ Structured logging (JSON-ish) with secret redaction + correlation id
- ✅ DRY_RUN mode to safely test without real Doprax API calls
- ✅ Always responds in Telegram: global error handler converts exceptions into localized messages

## Screenshots (what to capture)

> Add screenshots later. Suggested captures:

1. `/start` language selection inline buttons (FA/EN)
2. Main reply keyboard menu (all items visible)
3. VM list with inline buttons per VM
4. Create VM wizard:
   - Provider select
   - Plan typed + quick picks
   - Location typed + suggestions
   - OS list select + quick picks
   - Confirm screen (Create/Edit/Cancel)
5. Status view with Refresh inline button
6. Settings menu (language toggle + verbose mode)

## Architecture

```mermaid
flowchart TD
  TG[Telegram Update] --> APP[PTB Application]
  APP --> H[Handlers]
  H -->|read/write| DB[(SQLite via aiosqlite)]
  H -->|async calls| DOP[DopraxClient (httpx)]
  H --> I18N[i18n strings]
  APP --> LOG[Structured Logger]
  DOP -->|DRY_RUN=1| MOCK[Deterministic Mock Responses]
```

### Module layout

- `src/bot/main.py` — entrypoint, app wiring, commands, global error handler
- `src/bot/storage.py` — SQLite persistence for user prefs/state/drafts/ratelimits
- `src/bot/states.py` — explicit FSM states + transition helpers
- `src/bot/doprax_client.py` — isolated Doprax API client, retries, error mapping
- `src/bot/handlers/*` — thin Telegram handlers (no heavy business logic)
- `tests/` — unit tests (i18n, FSM, Doprax client, validation)

## Setup

### Requirements

- Python **3.11+**
- A Telegram bot token (`TELEGRAM_BOT_TOKEN`)
- Doprax API key (`DOPRAX_API_KEY`) unless you run in `DRY_RUN=1`

### Environment Variables

Create `.env` from `.env.example`:

- `TELEGRAM_BOT_TOKEN` (required)
- `DOPRAX_API_KEY` (required unless `DRY_RUN=1`)
- `DOPRAX_BASE_URL` (default `https://www.doprax.com`)
- `LOG_LEVEL` (default `INFO`)
- `DB_PATH` (default `./data/bot.db`)
- `DRY_RUN` (default `0`)

### Local Run

```bash
make install
cp .env.example .env
# edit .env
make run
```

## Docker

```bash
cp .env.example .env
# edit .env
docker compose up --build
```

- Polling mode is used by default.

## Deployment (systemd)

See: `scripts/systemd/doprax-telegram-bot.service`

Example steps:

```bash
sudo mkdir -p /opt/doprax-telegram-bot
# copy repo to /opt/doprax-telegram-bot
cd /opt/doprax-telegram-bot

python -m venv .venv
. .venv/bin/activate
pip install -U pip
pip install .

sudo cp scripts/systemd/doprax-telegram-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now doprax-telegram-bot
sudo journalctl -u doprax-telegram-bot -f
```

> Note: update paths and `User=` inside the systemd unit to match your server.

## Commands

- `/start` — start + language selection
- `/help` — help + quick guidance
- `/lang` — change language
- `/menu` — re-show main menu
- `/list_vms` — list VMs
- `/create_vm` — start create wizard
- `/status <vm_code>` — VM status
- `/locations` — locations & plans mapping
- `/os` — OS list
- `/cancel` — cancel current wizard
- `/health` — bot + Doprax connectivity status

## Menu map

### Reply keyboard (persistent)

- 📌 VM Management
- ➕ Create VM
- 📋 List VMs
- 🔎 VM Status
- 🌍 Locations & Plans
- 💿 OS List
- ⚙️ Settings
- ❓ Help

### Inline menus

- VM Management:
  - List VMs
  - Status by VM Code
  - Refresh

- Create VM Wizard:
  - Provider select
  - Plan input + quick picks
  - Location input + suggested matches
  - VM name input (validated)
  - OS select + quick picks
  - Confirm: ✅ Create | ✏️ Edit | ❌ Cancel

- Settings:
  - Change Language
  - Toggle Verbose Mode
  - About

## Troubleshooting

### Bot not responding

- Verify `TELEGRAM_BOT_TOKEN`
- Check container logs or stdout logs for startup errors
- Confirm Telegram can reach your machine (if behind NAT/firewall)

### API errors

- Check `DOPRAX_API_KEY` and `DOPRAX_BASE_URL`
- Use `/health` to verify connectivity

### Database issues

- Ensure `DB_PATH` directory exists and is writable
- If running docker, confirm volume mapping for `./data`

### Rate limiting

- Slow down repeated clicks/requests (cooldown is per-user)

### DRY_RUN mode

- Set `DRY_RUN=1`
- You may omit `DOPRAX_API_KEY`
- `/health` will show DRY_RUN status

## QA Checklist

- [ ] Test `/start` language selection
- [ ] Test `/menu` and reply keyboard behavior
- [ ] Test create wizard end-to-end (all steps)
- [ ] Test Back/Cancel at each wizard step
- [ ] Test invalid inputs (plan, OS slug, name)
- [ ] Test API downtime (bot must respond and not crash)
- [ ] Test double-tap “Create” (should not create twice)
- [ ] Test status refresh loop
- [ ] Test `DRY_RUN=1` behavior (deterministic results)

## Security Notes

- Never commit `.env` (secrets). Use `.env.example`.
- Logs redact known secrets from env.
- Prefer running the service under a dedicated OS user.
- Protect SQLite DB file permissions (contains user preferences/state/drafts).

See `SECURITY.md` for a concise threat model.

## License

MIT — see `LICENSE`.
