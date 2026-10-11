# Frontend Live Rebuild Guide

## Overview
This document explains how to live-update the Rankings Bot frontend without requiring a full Docker deployment. This is a **huge time-saver** for iterative development and quick UI changes.

## What Happened
When code changes were made to the React frontend (e.g., adding the Test Tournament toggle and External Pool import UI to `TournamentWizard.tsx`), the changes existed in source files but weren't visible in the browser until the frontend was **rebuilt and re-deployed**.

### The Process

#### Method 1: Manual rebuild on the server (Docker only — no host npm)

From the **repo root** on the machine where Docker runs:

```bash
./scripts/build_frontend_with_docker.sh
```

**What this does:** Starts a short-lived **`node:20-alpine`** container, runs `npm ci` + `npm run build`, writes `frontend/dist/` via bind mount.

**Inside the API container** (Admin Update website): the same script runs; set **`HOST_REPO_ROOT`** in `.env` to the host path of the repo so Docker can mount `frontend/`. See `docs/ENV_VARS.md` and `production/docker-compose.prod.yml`.

**Time:** similar to a local Vite build (network + compile).

#### Method 2: Admin Dashboard Button (Recommended)
Navigate to **Admin → System & Messages → Frontend Rebuild** and click the button. This triggers the rebuild via API without CLI access.

## Why This Works

| Scenario | Solution | Time | Effort |
|----------|----------|------|--------|
| Small UI tweaks | Frontend rebuild | ~5s | 1 click |
| Component logic changes | Frontend rebuild | ~5s | 1 click |
| Backend endpoint/validation changes | Full deploy | ~2-5m | Full pipeline |
| Database schema changes | Full deploy | ~5-10m | Full pipeline |

## What Gets Updated

✅ **React component code**  
✅ **TypeScript type definitions**  
✅ **CSS/Tailwind styling**  
✅ **API client methods** (when they don't require new backend endpoints)  

❌ **Backend Python code** (requires API restart)  
❌ **New API endpoints** (requires API restart)  
❌ **Database migrations** (requires restart + migration)  

## When to Use Frontend Rebuild vs Full Deploy

### Use Frontend Rebuild:
- Added/modified React component UI
- Changed state management or hooks
- Updated Tailwind classes or CSS
- Fixed TypeScript errors
- Modified existing API calls (not new endpoints)

### Use Full Deploy:
- Added new API endpoints
- Modified Python backend logic
- Changed database schema
- Updated dependencies (package.json or requirements.txt)
- Nginx configuration changes

## Admin UI Button

The **Frontend Rebuild** button in Admin Settings → System & Messages provides one-click rebuilding:

1. Navigate to **☰ Menu → Settings → Admin → System & Messages**
2. Scroll to **Frontend Rebuild**
3. Click **Rebuild Frontend**
4. Wait for success message (~6 seconds)
5. Browser automatically reloads with new code

## Behind the Scenes

**Backend:** `POST /api/admin/rebuild-website` runs `scripts/rebuild_website_now.sh`, which uses **`build_frontend_with_docker.sh`** (not host npm).
- Captures output and returns status
- Returns build time, errors (if any), or success

**Security:** Only accessible to `super_admin` role. Regular users cannot trigger rebuilds.

## Troubleshooting

**Button not working?**
- Ensure you're logged in as `super_admin`
- Check browser console for errors (F12)
- Verify frontend directory path is correct in endpoint

**Changes still not showing?**
- Hard refresh browser: **Ctrl+Shift+R** (Windows) or **Cmd+Shift+R** (Mac)
- Clear browser cache: DevTools → Application → Clear Storage
- Verify the code edit actually saved to the source file

**Build fails?**
- Check TypeScript errors in the output
- Verify all imports are correct
- Ensure no syntax errors in modified files

## Example: Adding the Test Tournament Toggle

1. **Edit source:** Modified `frontend/src/pages/TournamentWizard.tsx` (added state + UI)
2. **Rebuild:** Admin **Update website** or `./scripts/build_frontend_with_docker.sh` on the Docker host
3. **Deployed:** New code compiled to `dist/`
4. **Verified:** Browser reloaded, toggle appeared in Step 1

**Total time:** ~10 seconds (instead of 2-5 minutes for full deploy)

## Key Takeaway

**Frontend-only changes = 5-10 second turnaround via one-click rebuild button, not a full deployment pipeline.**

This dramatically accelerates UI iteration, bug fixes, and feature development.
