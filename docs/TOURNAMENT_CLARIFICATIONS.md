# Tournament System Clarifications

**Date:** February 2026  
**Source:** Repo analysis for tournament wizard improvements

## 1. ALFa vs Fargo Rating

**Finding:** "ALFa" appears only as the company name. There is **no separate "ALFa rating"** in the codebase.

**Schema:** The `players` table uses `fargo_score` (Fargo rating). Leaderboard, PlayerManagement, and [EXTERNALPOOL_ANALYSIS.md](../EXTERNALPOOL_ANALYSIS.md) all reference Fargo.

**Conclusion:** Use `fargo_score` for win probability calculations. Treat "ALFa rating" as Fargo.

---

## 2. License Expiry

**Finding:** 
- `license_expires` in `api/middleware/auth_middleware.py` refers to **app/organization license** (from auth-service), not player WPBA/WPA license.
- `players` table has `license_number` only. No `license_expiry_date` or similar.

**Conclusion:** License expiry for players must be **manually entered**. No WPBA/WPA API for license expiry exists in the repo. Add `license_expiry_date` to players; director enters it when creating/editing a player.

---

## 3. Reminders Channel

**Finding:**
- **Email** is the established channel: `notify-subscribe` for ranking changes, verification, password reset, ALERT_EMAIL for daemon.
- `EXTERNALPOOL_ANALYSIS.md` lists "SMS Match Notifications" as high priority for match alerts.
- No SMS implementation exists in the repo.

**Conclusion:** Use **email** as primary for match reminders (consistent with existing notifications). Add optional SMS later if Twilio/SNS is configured. Config: `MATCH_REMINDER_EMAIL_ENABLED`, `MATCH_REMINDER_SMS_ENABLED`.

---

## 4. Shot / Game / Match Clocks

**Finding:**
- No shot clock, game clock, or match clock fields in schema.
- `matches` has `scheduled_time`, `started_at`, `completed_at`.
- No live timer logic in the codebase.

**Conclusion:** Add schema fields for clocks. Support **both**:
- **Manual entry:** Director can enter elapsed times or final durations.
- **Live timers:** Client computes elapsed from `started_at`; no server-side tick required. Add `shot_clock_seconds` (config), `game_started_at` (per game), and use `started_at` for match clock.
