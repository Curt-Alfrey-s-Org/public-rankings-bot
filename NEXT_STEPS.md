# Next Steps — Rankings Bot

Copy-paste these on your **Linux server** when ready.

---

## 1. Backups (once + cron) — Done

- One backup run; daily cron at 2:00 AM. Log: Rankings-Bot/backup_postgres.log

---

## 2. Mobile build — Next step

EAS requires auth: run `npx eas-cli login` once (interactive), or set `EXPO_TOKEN` (expo.dev/settings/access-tokens) for CI.

```bash
cd ~/rankings-bot/mobile
npx eas-cli login    # one-time, interactive
npx eas-cli build --platform all --profile preview
```

Non-interactive (e.g. CI): `EXPO_TOKEN=your_token npx eas-cli build --platform all --profile preview --non-interactive`

Test on device: mobile/README.md

**Note:** Waiting on Apple for iOS. Use Android build meanwhile; run `npx eas-cli build --platform android --profile preview`.

---

See CHECKLIST.md for full status.

---

## Operator: `cf-probilliards` — `cloudflared` pin (out-of-alfa-ai scope)

ALFa AI audit **CFT-001** / **CVE GO-2026-4394**: tunnels must run **`cloudflared` ≥ `2026.3.0`**. This repo owns the **`cf-probilliards`** container on **`web-sites` (`apps`)**, started via **`scripts/start_cf_probilliards.sh`** (**`TUNNEL_TOKEN`** in repo **`.env`**).

**On `apps`:**

1. Confirm current binary: `sudo docker exec cf-probilliards cloudflared --version`
2. Ensure **`scripts/start_cf_probilliards.sh`** uses image **`cloudflare/cloudflared:2026.3.0`** (not `:latest`).
3. Recreate: `sudo docker rm -f cf-probilliards` then run **`./scripts/start_cf_probilliards.sh`** from the rankings-bot repo root (same **`tunnel_network`** as **`probilliards-nginx`**).
4. Re-verify: `sudo docker exec cf-probilliards cloudflared --version`

**Reference:** `alfa-ai/docs/audit/research/cloudflare-tunnel.md`. **`cf-alfa`** → **`alfaqd-website`**; **`cf-uspbf`** → **`USPBF`**.
