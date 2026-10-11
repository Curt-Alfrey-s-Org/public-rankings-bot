# Code Quality Audit (2026-03-27)

Full-repo audit for workarounds, fallbacks, temp fixes, and silent error swallowing. This doc records what was found, what was fixed, and what is acceptable per industry standards.

## What was fixed

### Data fallbacks removed (cause stale/incorrect data)

| Location | What was removed |
|----------|-----------------|
| `frontend/src/pages/Rankings.tsx` | `WPBA_MENU_FALLBACK` hardcoded tournament list (replaced by dynamic API) |
| `frontend/src/api/loginFeatures.ts` | `FALLBACK_DATA` hardcoded features list (API is single source) |
| `database/postgres_manager.py` | `_get_wpba_recent_systems_from_db` DB fallback function (dead code) |
| `database/postgres_manager.py` | `get_wpba_tournament_systems` fallback branch to DB query |
| `api/routes/alfa_ratings.py` | Fallback player count from rankings table when alfa_player_ratings fails |

### Silent error swallowing fixed (add logging)

| File | Change |
|------|--------|
| `scripts/test_live_rating_engine.py` | Bare `except:` changed to `except Exception:` (PEP 8) |
| `api/middleware/prometheus.py` | Two `except Exception: pass` blocks now log via `logger.debug` |
| `api/routes/tournaments.py` | JWT decode `except Exception: pass` now logs |
| `api/services/live_rating_engine.py` | Rollback/close `except Exception: pass` blocks now log |
| `database/postgres_manager.py` | Debug instrumentation `except Exception: pass` blocks now log |
| `database/__init__.py` | `except ImportError: pass` (dotenv) documented with comment |

### Misleading "for now" comments replaced

9 files updated. Comments that described working/intentional behavior now state the rationale directly. Genuinely incomplete features have clear "not yet implemented" markers instead of "for now."

### "Fallback" language cleaned

16 files updated. The word "fallback" replaced with accurate terms: "alternative", "secondary", "variation", "default classification", etc. Only React standard patterns (ErrorBoundary, Suspense, i18n `fallbackLng`) retain the word "fallback" since it's the React API term.

## What is acceptable (per standards)

### React ErrorBoundary / Suspense fallback props

React's ErrorBoundary and Suspense components use `fallback` as a prop name. This is the official React API -- not a data duplication pattern. Files: `ErrorBoundary.tsx`, `App.tsx`, `RouteErrorBoundary.tsx`, `RouteSuspenseFallback.tsx`, `PageErrorFallback.tsx`, `AlfaModuleIndex.tsx`.

### i18n `fallbackLng`

`i18next` uses `fallbackLng` as a configuration key. Standard i18n library behavior.

### Shell script `|| true` in teardown/cleanup

Teardown scripts (`stop.sh`, `full_deploy.sh` cleanup section) use `|| true` so cleanup continues when one step fails. This follows Docker Compose teardown patterns where partial cleanup is better than halting. The `|| true` is NOT used on critical-path commands (build, up, health check).

### Shell script `2>/dev/null` on existence checks

Commands like `docker inspect ... 2>/dev/null` and `docker network inspect ... 2>/dev/null` suppress expected "not found" errors when checking if something exists. Standard Docker scripting pattern.

### `# type: ignore` and `# noqa` in scrapers

Used sparingly in `scrapers/fetch_utils.py` (conditional import) and `scrapers/externalpool_tournament_harvester.py` (broad exception catch in retry loops). These are documented and intentional.

### Narrow-type `except (ValueError, TypeError): pass` in parsers

Used when attempting to parse user-supplied data (CSV values, Fargo ratings). The narrow exception type makes the intent clear -- skip unparseable values. Standard data-import pattern.

### `UiCustomizationContext` `fallback` parameter

The `getText(key, fallback)` API uses "fallback" as a function parameter name meaning "default value when override is not configured." This is standard default-parameter naming, not a data duplication pattern.

## Patterns that remain as known debt

| Pattern | Location | Risk | Notes |
|---------|----------|------|-------|
| `as any` type casts | 14 frontend files | Type safety bypass | Most are around chart libraries (Recharts) or Blob/response types |
| `console.log` in production | `Bracket.tsx`, `TestCenterMonitoring.tsx` | Debug noise | Test/demo paths only |
| Hardcoded container names in shell scripts | `full_deploy.sh`, `stop.sh`, etc. | Drift if compose renames | Standard for Docker Compose projects; names match compose service definitions |
| `sleep 180` in `complete_data_population.sh` | One-off population script | Timing workaround | Not a hot-path script; runs manually during initial setup |
| Hardcoded port 8003 in `fuser -k` | `full_deploy.sh`, `clean_docker_conflicts.sh` | Drift if API_PORT changes | Should use `$API_PORT` variable |
| `rollback_alfa.sh` stub functions | Lines 207, 274 | Misleading rollback | `disable_api_endpoints` and `send_notifications` only log, don't act |

## Rules enforced

- `.cursor/rules/no-workarounds.mdc` -- Always propose root-cause fixes, never workarounds
- `.cursor/rules/no-container-workarounds-drift-guard.mdc` -- Container-only operations, no host-side patches
- `docs/CONTAINER_DRIFT_PREVENTION.md` -- Build-hash verification, no-fallback policy, deployment order
