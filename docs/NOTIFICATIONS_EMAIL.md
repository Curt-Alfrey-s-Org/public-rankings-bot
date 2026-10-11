# Email Notifications for Ranking Changes

Players can sign up to get an email when a specific player's ranking changes (WPBA or WPA). Signup is on the Rankings page: **Get notified when a player's ranking changes** — enter email, player name, and use the current tab (WPBA/WPA).

## Flow

1. **Subscribe** — User enters email + player name on Rankings page and clicks **Notify me**. Stored in `email_rank_subscriptions` (no auth).
2. **Refresh** — When rankings are refreshed (Admin **Refresh** or `scripts/refresh_rankings.py`), new snapshots are saved and movement is computed.
3. **Notify** — After refresh, the app finds recent ranking changes, looks up subscribers for those (player_name, system), and sends one email per subscriber with change details and an unsubscribe link.
4. **Unsubscribe** — Link in email: `{NOTIFY_UNSUBSCRIBE_BASE_URL}/api/rankings/notify-unsubscribe?token=...`. Opens in browser; subscription is removed.

## Configuration

- **NOTIFY_UNSUBSCRIBE_BASE_URL** — Base URL for the unsubscribe link (e.g. `https://your-api-domain.com` or `http://localhost:8003`). Link becomes `{base}/api/rankings/notify-unsubscribe?token=...`.
- **SMTP** (optional) — If not set, notification emails are **logged only** (no send). Set to actually send:
  - **SMTP_HOST** — e.g. `smtp.example.com`, `smtp.sendgrid.net`
  - **SMTP_PORT** — usually `587`
  - **SMTP_USER**, **SMTP_PASSWORD** — auth
  - **SMTP_FROM** — From address (defaults to SMTP_USER)

See `.env.example` for a template.

## API

- **POST /api/rankings/notify-subscribe** — Body: `{ "email": "...", "player_name": "...", "system": "WPBA"|"WPA" }`. No auth.
- **GET /api/rankings/notify-unsubscribe?token=...** — Removes subscription. Returns HTML for browser or JSON. No auth.

## Database

Table: **email_rank_subscriptions** — `email`, `player_name`, `ranking_system`, `unsubscribe_token`, `created_at`. Created by `database/schema.sql` on init.
