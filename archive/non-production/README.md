## Non-Production Archive

This folder stores legacy frontend files that are not referenced by the current production route tree in `frontend/src/App.tsx`.

Archived on 2026-03-04:

- `frontend/src/components/SplashScreen.tsx`
- `frontend/src/pages/FutureTourneys.tsx`
- `frontend/src/pages/TournamentsLayout.tsx`

Notes:

- `api/routes/splash_v1.py` is intentionally **not** archived because mobile still calls `/api/v1/splash-videos`.
- Additional candidates exist, but only clearly unreferenced files were moved in this pass to avoid removing functionality accidentally.
