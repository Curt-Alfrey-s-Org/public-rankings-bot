# Fix .env so verify_production.sh passes

If `./scripts/verify_production.sh` reports `[FAIL]` for JWT_SECRET or DATABASE_URL, fix `Rankings-Bot/.env` as follows.

## 1. JWT_SECRET

The value must be a **strong, unique** string — not a placeholder.

- **Replace** any line like `JWT_SECRET=...change-in-production...` with the generated value, for example:
  ```env
  JWT_SECRET=0foPsSr6iZfU+KpZ51JxkiT1SO8foyzXFkUTqyle61s=
  ```
- Or generate a new one: `openssl rand -base64 32` and set `JWT_SECRET=<that-output>`.
- Use **exactly one** `JWT_SECRET=` line (no spaces around `=`).

## 2. DATABASE_URL

Add this line if it is missing (for the default Postgres from docker-compose):

```env
DATABASE_URL=postgresql://rankingsbot_user:PASSWORD@rankings-bot-postgres:5432/rankingsbot
```

No spaces around `=`. Use your real Postgres URL if you use a different host/user/db.

## 3. Bad line (loqe)

If a script fails with `loqe: command not found`, your `.env` has a bad line (often around line 27) that the shell runs when sourcing `.env`. Edit `.env` and **remove or fix** that line (e.g. a typo like `loqe` instead of a valid variable). The backup script no longer sources `.env`; it only reads `DATABASE_URL` from the file, so backup works even with a bad line. Other scripts may still source `.env`, so fixing the typo is recommended.

## After editing

1. Save `.env`.
2. Restart the API: `sudo systemctl restart rankings-bot-api` or `./scripts/restart_api.sh`.
3. Run: `./scripts/verify_production.sh` — you should see `[PASS]` for JWT_SECRET and DATABASE_URL.
