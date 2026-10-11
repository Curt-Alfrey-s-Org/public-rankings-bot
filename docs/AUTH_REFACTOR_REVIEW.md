# Auth refactor review

> **Historical (superseded 2026-09-25):** default passwords were removed; see docs/AUTH_DESIGN.md.

**Scope:** `api/auth.py`, `api/routes/auth.py`, `docs/AUTH_DESIGN.md` (bootstrap and login flow).

---

## Critical issues (must fix)

**None.** No security regressions or correctness bugs identified.

---

## Warnings (should fix)

1. **Password sync on every login (fixed)**  
   Previously the refactor synced the super_admin password to `<old-default>` on every login when using defaults, which would overwrite a changed password. **Change applied:** bootstrap no longer overwrites an existing user’s password; it only creates the user with default password when missing and fixes role/must_change_password. To reset to tornybotca1/<old-default>, run `scripts/ensure_super_admin.py`.

2. **Hardcoded default password in code**  
   `SUPER_ADMIN_DEFAULT_PASSWORD = "<redacted>"` is in source. It’s a known default for “first login then change,” but consider documenting that production should set `SUPER_ADMIN_PASSWORD` in env and change the password after first login so the default isn’t the long-term credential.

---

## Suggestions (consider)

1. **Clarity:** The module docstring in `api/auth.py` says “never used at login” for bootstrap; the new behavior “sync password when using defaults” is a form of bootstrap that affects what login will accept. A one-line note in the docstring that “when using fixed defaults, bootstrap may sync super_admin password to default” would make that explicit.

2. **AUTH_DESIGN.md:** File is currently untracked. If it’s the canonical auth doc, add it to git and keep “Default login (no setup)” and “Recovery” in sync with the code (tornybotca1/<old-default>, when password is synced, when to use the script).

3. **Tests:** Add or run a test that logs in with `tornybotca1` / `<old-default>` after bootstrap and asserts 200 and `role == "super_admin"` to guard against regressions.

---

## Correctness

- **Bootstrap order:** `ensure_super_admin_bootstrap` then `ensure_default_users_bootstrap`; login then calls `authenticate_user`. Order is correct.
- **Login path:** Single path via `POST /login` → bootstrap → `authenticate_user` → JWT. No env read at authentication time; DB is the source of truth for verification. Correct.
- **JWT:** Still created with `create_access_token(user.role, subject=user.username)`. Unchanged and correct.

---

## Security

- Passwords remain hashed with bcrypt; no plaintext storage.
- Default credential `tornybotca1`/`<old-default>` is documented and intended for initial access; recommend changing after first login in production (or setting `SUPER_ADMIN_PASSWORD` in env and not relying on sync).
- No new secrets or credentials logged; no new bypass paths.

---

## Summary

The refactor is **correct and secure** for the intended “login with tornybotca1/<old-default> out of the box” behavior. The main follow-up is to avoid **resetting an existing super_admin password back to <old-default> on every login** when using defaults; restrict that sync to startup-only or to a one-time/reset path.
