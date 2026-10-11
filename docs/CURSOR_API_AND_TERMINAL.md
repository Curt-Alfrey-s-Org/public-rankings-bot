# Cursor API & Terminal

This doc follows the instructions referenced in **Settings → Admin → Cursor API & Terminal**. Use Cursor CLI and Agent Terminal from your machine to run commands in this project. For teams, the Cursor Admin API provides usage and billing.

---

## 1. Cursor CLI

Run AI agents from your terminal (interactive, shell, or headless).

### Install

**macOS / Linux / WSL:**
```bash
curl https://cursor.com/install-fsS | bash
```

**Windows (PowerShell):**
```powershell
irm https://cursor.com/install?win32=true | iex
```

### Use

- **Interactive:** `agent` then describe your goal; approve or edit proposed commands.
- **With initial prompt:** `agent "refactor the auth module to use JWT tokens"`
- **Non-interactive (scripts/CI):** `agent -p "find and fix performance issues" --model "gpt-5.2"`

From this project root (e.g. `Rankings-Bot` or `rankings-bot`), run `agent` or `agent -p "..."` so the agent has full repo context. Run terminal commands in Cursor IDE (Agent or integrated terminal), not from the web Admin UI. For server commands use SSH or your host’s tools.

**Docs:** [Cursor CLI overview](https://cursor.com/docs/cli/overview) · [Installation](https://cursor.com/docs/cli/installation) · [Using Agent in CLI](https://cursor.com/docs/cli/using)

---

## 2. Agent Terminal

In Cursor IDE, the Agent can run shell commands in a sandbox (macOS/Linux); command history persists. Use it for running scripts, builds, and tests in this repo without leaving the editor.

**Docs:** [Agent Terminal](https://cursor.com/docs/agent/terminal)

---

## 3. Cursor Admin API (Teams)

For **Cursor for Teams**, the Admin API lets you access members, audit logs, daily usage, spending, repo blocklists, and billing groups.

### Get an API key

1. Sign in at [Cursor](https://cursor.com).
2. Open your **Team** settings (e.g. [cursor.com/dashboard](https://cursor.com/dashboard)).
3. Create an API key for the Admin API (see [API Overview](https://cursor.com/docs/api) and [Admin API](https://cursor.com/docs/account/teams/admin-api)).

### Use the API

- **Base URL:** `https://api.cursor.com`
- **Auth:** Basic Authentication — use your API key as the **username** and leave the password empty.

**Example — list team members:**
```bash
curl -X GET "https://api.cursor.com/teams/members" -u "YOUR_API_KEY:"
```

**Example — daily usage (POST):**
```bash
curl -X POST "https://api.cursor.com/teams/daily-usage-data" \
  -u "YOUR_API_KEY:" \
  -H "Content-Type: application/json" \
  -d '{"startDate": 1710720000000, "endDate": 1710892800000}'
```

**Example — spending:**
```bash
curl -X POST "https://api.cursor.com/teams/spend" \
  -u "YOUR_API_KEY:" \
  -H "Content-Type: application/json" \
  -d '{}'
```

### Optional: store key in this project

If you script or integrate the Admin API from this repo, add to `.env` (do not commit the key):

```bash
# Optional: Cursor Team Admin API (usage, billing, members). Get key from cursor.com team settings.
# CURSOR_ADMIN_API_KEY=your_api_key_here
```

Use the key as the Basic auth username when calling `https://api.cursor.com` (see examples above).

**Docs:** [Admin API](https://cursor.com/docs/account/teams/admin-api) · [API authentication](https://cursor.com/docs/api#authentication) · [Rate limits](https://cursor.com/docs/api#rate-limits)
