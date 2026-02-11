# Security Policy

## Supported Versions

Security updates are provided for the latest minor version.

## Threat Model (practical notes)

### Secrets

- `TELEGRAM_BOT_TOKEN` and `DOPRAX_API_KEY` are **high value**.
- Never log them.
- This project redacts secrets in logs via `bot.utils.redact_secrets()`.

### Transport security

- Uses HTTPS endpoints via `httpx`.
- Configure network egress and DNS in production environments.

### Webhook vs polling

- Default is polling for simplicity.
- If switching to webhook, ensure:
  - TLS termination and trusted reverse proxy
  - Strict firewall rules
  - No logging of raw webhook payloads with secrets

### Least privilege

- Run bot under a dedicated OS user.
- Use a dedicated Doprax API key with minimal permissions (if supported).

### Logging and PII

- Telegram user ids are logged for correlation; avoid logging message text.
- Stack traces are logged server-side; user receives a friendly error + reference id.

### Database

- SQLite file contains user language, state, drafts. Protect file permissions.
- Store DB on encrypted disk if required.

## Reporting a Vulnerability

Open a private security advisory or contact maintainers through your organization process.
