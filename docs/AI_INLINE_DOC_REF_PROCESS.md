# Inline doc reference process (AI + maintainers)

**Purpose:** Reduce wrong assumptions when AI or humans edit security-sensitive, multi-layer, or infrastructure code. **Comments point at canonical docs** instead of duplicating full explanations in source files.

---

## What to add

1. **Hub doc** — `docs/<DOMAIN>_DOC_HOOKS.md` (or one umbrella index). Contains:
   - Short **rules** (what not to assume).
   - **Table:** repository path → which `docs/...` files to read first.

2. **File header block** — At the top of high-impact modules (after the module docstring / file comment), a compact block:

   ```text
   # Doc refs (AI / maintainers): docs/<HUB>.md; docs/<DETAIL>.md; ...
   ```

   Use the same phrase **`Doc refs (AI / maintainers)`** so ripgrep finds every wired file.

3. **Discovery** — Link hub docs from **docs/INDEX.md** (or the repo’s doc index / README).

---

## When this pays off

| Area | Why |
|------|-----|
| Auth, JWT, roles, admin | Easy to break invariants or duplicate credential stores |
| Networking, Docker, deploy | Loopback vs LAN, tunnel vs host ports, single owner per service |
| Scrapers ↔ DB ↔ API ↔ UI | Data flow and column semantics drift without one narrative |
| Migrations / schema | Schema and running image must stay aligned (container-only upgrades) |
| Single-source config | “Silent fallback” patches violate explicit product rules |

---

## Reference implementation (Rankings Bot)

| Hub | Scope |
|-----|--------|
| [NETWORKING_DOC_HOOKS.md](NETWORKING_DOC_HOOKS.md) | Tunnel, nginx, host **8088**, API bind |
| [AUTH_DOC_HOOKS.md](AUTH_DOC_HOOKS.md) | JWT, users DB, roles, admin vs user APIs |
| [RANKINGS_DATA_DOC_HOOKS.md](RANKINGS_DATA_DOC_HOOKS.md) | WPA/WPBA pipelines, `postgres_manager`, rankings routes, UI |

Other repos can copy this **process** and naming; paths and hub names should match **their** layout and docs.
