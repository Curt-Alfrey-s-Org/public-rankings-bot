# Full Deploy Button Update — February 20, 2026

## Overview

Updated the Full Deploy button in Settings > Admin to use the standardized `--force-docker` flag instead of `--no-cache`.

## Changes Made

### Backend: [api/routes/admin.py](../api/routes/admin.py)

**Function:** `rebuild_all_images()` (lines 395-430)

Changed the command from:
```python
[REBUILD_SHELL, str(path), "--no-cache"]
```

To:
```python
[REBUILD_SHELL, str(path), "--force-docker"]
```

**Affected lines:**
- Line 410: Display command string
- Line 414: Actual subprocess command
- Line 419: Logger message

### Frontend: [frontend/src/pages/SettingsAdmin.tsx](../frontend/src/pages/SettingsAdmin.tsx)

**Updated help text in two locations:**

1. **"Update website" section** (line 953):
   - Changed from: `./scripts/full_deploy.sh`
   - Changed to: `./scripts/full_deploy.sh --force-docker`

2. **"Server controls" section** (line 1023):
   - Changed from: "Full deploy from the web app. Runs scripts on the server."
   - Changed to: "Full deploy: Rebuilds all Docker images and restarts containers. Runs `./scripts/full_deploy.sh --force-docker` on the server."

## Rationale

Per [PRODUCTION_DEPLOYMENT.md](../docs/PRODUCTION_DEPLOYMENT.md) and recent deployment fixes:
- Production mode uses Docker exclusively (systemd service disabled)
- The `--force-docker` flag ensures Docker-only deployment
- This matches the deployment method established on 2026-02-20

## Verification

```bash
# Backend deployed
✅ API container rebuilt and restarted
✅ API Status: healthy (Up 42 seconds)
✅ Uptime: 40.2s

# Frontend deployed
✅ Frontend rebuilt successfully
✅ New SettingsAdmin bundle: SettingsAdmin-CCYB1r85.js (57K)
```

## Testing

To test the updated button:
1. Log in as Super Admin
2. Navigate to Settings > Admin
3. Scroll to "Server controls (Super admin)"
4. Click "Full deploy" button
5. Verify log message shows: `script=.../full_deploy.sh --force-docker`

## Related Documentation

- [DEPLOY_FIX_20260220.md](DEPLOY_FIX_20260220.md) — Dockerfile alembic fix
- [PRODUCTION_CONFIG_20260220.txt](PRODUCTION_CONFIG_20260220.txt) — Production configuration
- [PRODUCTION_DEPLOYMENT.md](../docs/PRODUCTION_DEPLOYMENT.md) — Docker production standards

---
**Status:** ✅ DEPLOYED  
**Date:** February 20, 2026  
**Deployment Mode:** Docker Production
