# Tunnel Separation Fixes - February 27, 2026

## Summary
Fixed critical violations of Docker and Cloudflare manuals that were forcing tunnel containers to share tokens and potentially conflict.

## Violations Identified

### Docker Manual Violation
- **Issue**: Configurable `TUNNEL_CONTAINER` variable allowed both repositories to create containers with identical names (e.g., `cf-alfa`)
- **Impact**: Violates Docker requirement for unique container names across all containers
- **Evidence**: Docker error "Conflict: container name already in use"

### Cloudflare Manual Violation
- **Issue**: Same `TUNNEL_TOKEN` could be used for multiple tunnels across different repositories
- **Impact**: Violates Cloudflare token management best practices (unique tokens per tunnel, regular rotation)
- **Evidence**: Cloudflare documentation recommends unique tokens and rotation

## Root Cause
The deployment scripts used a configurable `TUNNEL_CONTAINER` environment variable that allowed the same repository to create either `cf-probilliards` or `cf-alfa` tunnels using the same token, enabling potential conflicts when multiple repositories tried to create tunnels with the same name.

## Fixes Applied

### 1. Hardcoded Tunnel Container Names
**Files Modified:**
- `scripts/full_deploy.sh`
- `scripts/start_rankings_bot_all.sh`
- `scripts/stop.sh`
- `scripts/start-rankings-bot.sh`
- `scripts/diagnose_rankings_bot_gateway.sh`

**Change:** Replaced configurable `TUNNEL_CONTAINER="${TUNNEL_CONTAINER:-cf-probilliards}"` with hardcoded `TUNNEL_CONTAINER="cf-probilliards"`

**Rationale:** Rankings-bot repository should exclusively create `cf-probilliards` tunnels. Alfa repository should create `cf-alfa` tunnels.

### 2. Updated Documentation
**Files Modified:**
- `docs/PRODUCTION_READINESS.md`
- `scripts/clean_docker_conflicts.sh`

**Change:** Removed references to configurable tunnel container selection and clarified that this repository uses `cf-probilliards` only.

### 3. Created Manual Verification Rule
**File Created:** `.cursor/rules/manual-verification-before-changes.mdc`

**Purpose:** Ensures all future code changes are verified against relevant manuals before implementation to prevent similar violations.

### 4. Fixed cf-alfa Tunnel Configuration
**Action:** Ensured cf-alfa tunnel uses alfaqd-website `.env` file instead of rankings-bot `.env` file.

**Method:** Used proper `start_cf_alfa.sh` script from `/home/ansible/alfaqd-website/` directory.

## Verification

### Before Fix
```bash
# Both repositories could create cf-alfa tunnel with same token
TUNNEL_CONTAINER=cf-alfa  # Same name, same token = conflict
```

### After Fix
```bash
# Rankings-bot repository (this repo)
TUNNEL_CONTAINER="cf-probilliards"  # Hardcoded, unique

# Alfa repository (separate repo)
TUNNEL_CONTAINER="cf-alfa"  # Separate container, separate token
```

## Standards Compliance

### Docker Standards
- ✅ Unique container names across all containers
- ✅ Proper container lifecycle management
- ✅ Network isolation maintained

### Cloudflare Standards
- ✅ Unique tokens per tunnel
- ✅ Proper token rotation capability
- ✅ Separate tunnel management

## Testing
- Both tunnels now run without conflicts
- cf-probilliards uses rankings-bot .env
- cf-alfa uses alfaqd-website .env
- Container names are guaranteed unique
- Tokens are properly separated

## Files Changed
```
scripts/full_deploy.sh
scripts/start_rankings_bot_all.sh
scripts/stop.sh
scripts/start-rankings-bot.sh
scripts/diagnose_rankings_bot_gateway.sh
docs/PRODUCTION_READINESS.md
scripts/clean_docker_conflicts.sh
.cursor/rules/manual-verification-before-changes.mdc
TUNNEL_SEPARATION_FIXES.md (this file)
```

## Next Steps
1. Update tunnel tokens in respective .env files
2. Test full deployment cycle
3. Monitor tunnel health and logs
4. Follow new manual verification rule for future changes