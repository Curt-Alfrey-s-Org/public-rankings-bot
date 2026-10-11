# Auth & roles — doc hooks for AI and maintainers

**Purpose:** Before changing login, JWT, password storage, or role checks, read the linked docs. **Single source of truth for credentials:** database `users` table (see `api/auth.py` module docstring).

**Process pattern:** [AI_INLINE_DOC_REF_PROCESS.md](AI_INLINE_DOC_REF_PROCESS.md)

---

## Rules (summary)

1. **No env/file login fallbacks** — Bootstrap env vars may create missing users only; login validates against DB.
2. **Role semantics** — `score_keeper` is a device/tablet JWT for director-assigned score entry, not a generic “player” role. Super admin implies full capability set per project standards.
3. **JWT secret** — Must be strong in production; startup checks in `api/main.py`. See **docs/SECURITY_ANALYSIS.md** (or project security doc).
4. **`api/middleware/auth_middleware.py`** — Optional **centralized auth-service** client pattern; not all routes use it. Prefer **docs/AUTH_DESIGN.md** for the app’s primary JWT flow (`api/auth.py` + `auth_sessions`).

---

## File → documentation

| Repository path | Read these docs |
|-----------------|-----------------|
| `api/auth.py` | **docs/AUTH_DESIGN.md**, **docs/ROLES_AND_PERMISSIONS.md**, **docs/ROLE_CAPABILITIES.md** |
| `api/routes/auth.py` | **docs/AUTH_DESIGN.md**, **docs/PRODUCTION_AND_APP_CONVERSION.md** (sessions if referenced) |
| `api/routes/users.py` | **docs/AUTH_DESIGN.md**, **docs/ROLES_AND_PERMISSIONS.md** |
| `api/routes/admin.py` | **docs/ROLES_AND_PERMISSIONS.md**, **docs/ROLE_CAPABILITIES.md**, **docs/PRODUCTION_DEPLOYMENT.md** (rebuild/deploy scripts) |
| `api/main.py` (JWT/CORS/routers) | **docs/AUTH_DESIGN.md**, **docs/SECURITY_ANALYSIS.md** |
| `api/middleware/auth_middleware.py` | **docs/AUTH_DESIGN.md** (contrast with primary `api/auth.py` flow) |
| `frontend/src/contexts/AuthContext.tsx` | **docs/AUTH_DESIGN.md**, **docs/ROLES_AND_PERMISSIONS.md**, **docs/ENV_VARS.md** (`VITE_*` if any) |
