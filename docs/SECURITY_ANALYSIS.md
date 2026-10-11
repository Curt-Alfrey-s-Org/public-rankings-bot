# Security Analysis — Rankings Bot

This document analyzes vulnerabilities and recommends hardening measures. It follows OWASP guidance and industry standards.

---

## Executive Summary

| Severity | Count | Status |
|----------|-------|--------|
| Critical | 4 | Must fix before production |
| High | 5 | Fix soon |
| Medium | 6 | Plan remediation |
| Low | 4 | Good to have |

**Overall:** The app has solid foundations (bcrypt, JWT, role-based access, rate limiting) but several critical issues must be addressed for production use.

---

## Critical Vulnerabilities

### 1. JWT Secret Default (CRITICAL)

**Location:** `api/auth.py` line 34

```python
SECRET_KEY = os.getenv("JWT_SECRET", "rankings-bot-change-in-production")
```

**Risk:** If `JWT_SECRET` is unset, anyone who knows the default can forge valid JWTs and impersonate any user, including super_admin.

**Fix:**
- In production, **never** use the default. Fail startup if unset:
  ```python
  SECRET_KEY = os.getenv("JWT_SECRET")
  if not SECRET_KEY or SECRET_KEY == "rankings-bot-change-in-production":
      raise RuntimeError("JWT_SECRET must be set to a strong random value in production")
  ```
- Use a cryptographically random 256-bit secret (e.g. `openssl rand -hex 32`)
- Store in env/systemd, never in code

---

### 2. Super Admin Default Credentials (CRITICAL) — RESOLVED 2026-09-25

> Resolved: `api/auth.py` no longer contains any default/temporary password. Bootstrap users are
> created only from env credentials, production fails fast without `SUPER_ADMIN_PASSWORD`, and
> `must_change_password` is enforced server-side. See docs/AUTH_DESIGN.md. The snippet below is historical.

**Location:** `api/auth.py` lines 187–189

```python
SUPER_ADMIN_DEFAULT_USERNAME = "tornybotca1"
SUPER_ADMIN_DEFAULT_PASSWORD = "<redacted>"
```

**Risk:** Weak default password. If bootstrap creates the user and env is not overridden, attackers can log in as super_admin.

**Fix:**
- Require `SUPER_ADMIN_PASSWORD` in production; fail bootstrap if unset
- Use `scripts/ensure_super_admin.py` to set a strong password after first deploy
- Document: change default immediately after first login

---

### 3. Assets Upload — No Authentication (CRITICAL)

**Location:** `api/routes/assets.py` — `POST /api/assets/upload` and `GET /api/assets`

**Risk:** Unauthenticated users can upload arbitrary files (images/videos) and list them. No auth, no rate limit on upload. Enables:
- Storage abuse
- Malicious content hosting
- Phishing / malware distribution via uploaded files

**Fix:**
- Require authentication: `Depends(get_current_user)` or `Depends(require_admin)`
- Add upload rate limit (e.g. 10 uploads per 15 min per user)
- Validate file content (magic bytes), not just extension
- Consider max file size (e.g. 50–100 MB)

---

### 4. Hardcoded Database Password in Script (CRITICAL)

**Location:** `enrich_cross_system_data.py` line 29

```python
password="rankings123"
```

**Risk:** If script is committed to repo, anyone with access can connect to the database. Same password may be used elsewhere.

**Fix:**
- Use `DATABASE_URL` or `os.getenv("DB_PASSWORD")` from env
- Add `enrich_cross_system_data.py` to `.gitignore` if it contains secrets, or use env-only config

---

## High Vulnerabilities

### 5. Login Endpoint — No Brute-Force Protection

**Location:** `api/routes/auth.py` — `POST /api/auth/login`

**Risk:** Only global rate limit (200 req/min per IP). Login can be brute-forced with 200 attempts per minute.

**Fix:**
- Add login-specific rate limit: e.g. 5 failed attempts per 15 min per IP
- Add account lockout after N failed attempts (e.g. 10) → temporary lock or require captcha
- Implement progressive delays (e.g. exponential backoff)

---

### 6. CORS Too Permissive

**Location:** `api/main.py` lines 463–464

```python
_cors_regex = r"^https?://(192\.168\.\d{1,3}\.\d{1,3}|localhost|[a-zA-Z0-9]([a-zA-Z0-9.-]*[a-zA-Z0-9])?)(:\d+)?$"
```

**Risk:** Regex allows any subdomain and 192.0.2.10. In production, attacker could host a malicious site on a subdomain and make credentialed requests if user is logged in.

**Fix:**
- In production, use explicit `CORS_ORIGINS` only (no regex)
- Restrict to known domains: `https://app.probilliardssoftware.com`, etc.

---

### 7. reCAPTCHA Bypass When Unconfigured

**Location:** `api/services/captcha.py` lines 31–32

```python
if not secret_key:
    return {"success": True, "score": 0.9}  # Allow in dev mode
```

**Risk:** If `RECAPTCHA_SECRET_KEY` is not set, registration bypasses captcha. Bots can create accounts.

**Fix:**
- In production, **require** `RECAPTCHA_SECRET_KEY`; return `{"success": False}` if unset
- Use `DEBUG` or `ALLOW_CAPTCHA_BYPASS` env to enable bypass only in dev

---

### 8. Debug Auth Endpoint Exposes Token Info

**Location:** `api/routes/auth.py` — `GET /api/auth/debug-auth`

**Risk:** No auth required. Returns whether token is present and decoded payload. Information disclosure.

**Fix:**
- Remove in production or protect with `DEBUG` flag
- If kept, require auth and restrict to admin

---

### 9. Admin Terminal — Path Traversal

**Location:** `api/routes/terminal.py` — `ls` with path

```python
if user_input.startswith('ls '):
    path = user_input.replace('ls ', '').strip()
    allowed_paths = ['/home/ansible/rankings-bot', '/home/ansible', '.']
    if any(path.startswith(allowed) for allowed in allowed_paths):
        return f'ls -lah {path}'
```

**Risk:** `path.startswith(allowed)` can be bypassed with `../` (e.g. `ls /home/ansible/rankings-bot/../../etc`). Resolve path and check it stays within allowed dirs.

**Fix:**
- Use `Path(path).resolve()` and verify `str(resolved).startswith(allowed)`
- Ensure no symlink escape

---

## Medium Vulnerabilities

### 10. File Upload — No Content Validation

**Location:** `api/routes/assets.py`

**Risk:** Only extension is checked. Attacker could upload `.jpg` with malicious content. No magic-byte validation.

**Fix:**
- Validate magic bytes (e.g. `python-magic` or `filetype`)
- Reject mismatched extensions

---

### 11. Temporary Password in API Response

**Location:** `api/routes/users.py` — `reset_user_password` returns `temporary_password` in JSON

**Risk:** If response is logged or intercepted, temp password is exposed. Email is also sent.

**Fix:**
- Avoid returning temp password in API response when email is sent
- Log only "password reset sent" not the value
- Ensure HTTPS everywhere

---

### 12. Session Storage for Tokens

**Location:** Frontend uses `sessionStorage` for JWT

**Risk:** Tokens in `sessionStorage` are vulnerable to XSS. If XSS exists, attacker can steal token.

**Fix:**
- Ensure no `dangerouslySetInnerHTML` with user input
- Content Security Policy (CSP) headers
- Consider `httpOnly` cookies for tokens (requires backend changes)

---

### 13. No Security Headers

**Location:** `api/main.py` — only `X-Content-Type-Options: nosniff` is set

**Risk:** Missing headers increase XSS, clickjacking, MIME sniffing risks.

**Fix:** Add middleware:
- `X-Frame-Options: DENY` or `SAMEORIGIN`
- `Content-Security-Policy` (strict)
- `Strict-Transport-Security` (HSTS) when HTTPS
- `X-XSS-Protection: 1; mode=block` (legacy)

---

### 14. Global Rate Limit May Be Too High

**Location:** `api/rate_limiter.py` — 200 req/min per IP

**Risk:** 200/min allows significant scraping or enumeration.

**Fix:**
- Consider 100/min for anonymous, 300/min for authenticated
- Add stricter limits for sensitive endpoints (login, password reset, registration)

---

### 15. Sensitive Data in Logs

**Location:** Various `logger.info` / `logger.exception` calls

**Risk:** Passwords, tokens, or PII could be logged if passed to format strings.

**Fix:**
- Audit logging: never log passwords, tokens, or full tokens
- Use structured logging with redaction for sensitive fields

---

## Low / Informational

### 16. SQL Injection

**Status:** Most queries use SQLAlchemy ORM or parameterized `text()` with `:param`. No direct string concatenation found in core API paths. **Low risk** if pattern is maintained.

### 17. Cursor API Key Storage

**Location:** `api/routes/admin.py` — Cursor API key stored in config file

**Status:** Key is stored server-side. Ensure config file is not in repo and has restricted permissions.

### 18. WebSocket / Real-Time

**Status:** Check if any WebSocket endpoints exist and validate auth on connection.

### 19. Dependency Vulnerabilities

**Recommendation:** Run `pip audit` and `npm audit` regularly. Keep dependencies updated.

---

## Checklist — What to Put in Place

### Immediate (Before Production) — DONE

- [x] Set `JWT_SECRET` to a strong random value; fail startup if default
- [x] Change super_admin default password; require `SUPER_ADMIN_PASSWORD` in prod
- [x] Add authentication to `/api/assets/upload` and `/api/assets`
- [x] Remove hardcoded DB password from `enrich_cross_system_data.py`; use env

### Short Term — DONE

- [x] Add login rate limit (10 / 15 min per IP)
- [x] Restrict CORS to explicit origins in production (no regex when CORS_ORIGINS set)
- [x] Require `RECAPTCHA_SECRET_KEY` in production; disable bypass
- [x] Remove or protect `GET /api/auth/debug-auth` (404 when DEBUG=false)
- [x] Fix admin terminal path traversal

### Medium Term

- [ ] Add file content validation (magic bytes) for uploads
- [ ] Add security headers (CSP, X-Frame-Options, HSTS)
- [ ] Audit logging for sensitive data
- [ ] Consider account lockout after failed logins

### Ongoing

- [ ] Run `pip audit` and `npm audit` in CI
- [ ] Penetration testing before major releases
- [ ] Regular dependency updates

---

## References

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [OWASP Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)
- [OWASP Password Storage](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)

