# Alfa Rollout - Admin Quick Reference

**Keep this guide nearby during rollout.**

---

## Current Status Check

```bash
# Check current phase and percentage
curl -H "Authorization: Bearer $TOKEN" \
  https://your-domain/api/admin/rollout/status

# Expected output:
# Phase 1: Silent Canary (10%)
# Phase 2: Shadow Mode (25%)
# Phase 3: Experimentation (50%)
# Phase 4: Controlled Expansion (75%)
# Phase 5: Full Production (100%)
```

---

## Weekly Checklist

### Before Phase Advance

1. **Check Metrics**
   ```bash
   curl -H "Authorization: Bearer $TOKEN" \
     https://your-domain/api/admin/rollout/status
   ```
   - Brier score below threshold?
   - Error rate < 1%?
   - No anomalies?

2. **Validate Prerequisites**
   ```bash
   curl -X POST -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"phase": X}' \
     https://your-domain/api/admin/rollout/validate-phase
   ```

3. **Review Change Log**
   ```bash
   curl -H "Authorization: Bearer $TOKEN" \
     https://your-domain/api/admin/rollout/change-log?limit=20
   ```

### Advance to Next Phase

```bash
# Update feature flag to new percentage
curl -X PUT -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "flag_name": "alfa_rating_enabled",
    "value": XX,
    "reason": "Phase X approval - all criteria met"
  }' \
  https://your-domain/api/admin/rollout/feature-flags/alfa_rating_enabled
```

---

## Emergency Procedures

### Immediate Rollback (If Issues Detected)

```bash
# ONE COMMAND - this disables Alfa completely
curl -X POST -H "Authorization: Bearer $TOKEN" \
  https://your-domain/api/admin/rollout/rollback
```

**What it does:**
- Sets `alfa_rating_enabled` to 0%
- Disables predictions in API
- Disables anomaly detection
- All API calls use Fargo

**Verify rollback:**
```bash
curl -H "Authorization: Bearer $TOKEN" \
  https://your-domain/api/admin/rollout/status
# Should show: Phase 0, 0%
```

---

## Manual Rollback (Partial)

```bash
# Rollback from 50% to 25%
curl -X PUT -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "flag_name": "alfa_rating_enabled",
    "value": 25,
    "reason": "Rollback to Phase 2 - Brier score degradation"
  }' \
  https://your-domain/api/admin/rollout/feature-flags/alfa_rating_enabled
```

---

## Phase Reference

| Phase | % | Focus | Decision |
|-------|---|-------|----------|
| 0 | 0 | Setup | Pre-launch validation |
| 1 | 10 | Silent | Brier < 0.30 |
| 2 | 25 | Shadow | Brier < 0.27 |
| 3 | 50 | Active | Brier ≥ Fargo |
| 4 | 75 | Expand | Anomaly precision > 80% |
| 5 | 100 | Full | All tests pass |

---

## Metrics Dashboard

**Grafana Location:** `http://your-grafana:3000/d/rollout-metrics`

**Watch these:**
1. **Brier Score Trend** - Should stay below baseline
2. **Match Count** - Volume should increase with percentage
3. **Error Rate** - Should remain < 1%
4. **Anomaly Precision** - Phase 4+: should be > 80%

---

## Support Contacts

- **DevOps:** Infrastructure and Docker issues
- **API Team:** Endpoint and performance issues
- **DB Team:** Database and query issues
- **Analytics:** Metrics and reporting questions

---

## Key Files

| File | Purpose | Access |
|------|---------|--------|
| `config/feature_flags.json` | Master config | Read (API manages) |
| `rollout/deployment.log` | Deployment history | View via API |
| `rollout/checkpoints/` | Rollback snapshots | Restore if needed |
| `scripts/rollout_alfa.sh` | Deploy script | Run from host |
| `scripts/rollback_alfa.sh` | Rollback script | Run from host |

---

## Quick Troubleshooting

**Problem: API still returning Fargo after update**
- Solution: API might be caching. Restart: `curl POST /api/admin/rebuild-website`
- Or: Force flag reload: `./scripts/rollout_alfa.sh reload`

**Problem: Can't update flag**
- Check: Admin permissions?
- Check: JSON format valid?
- Check: Feature flag name correct?
- Check: Value in valid range (0-100)?

**Problem: Metrics dashboard not updating**
- Check: Database connectivity
- Check: rollout_tracking table exists
- Check: API logs: `tail -f rankings_bot.log`

---

## Communication Templates

### Announce Phase Advance

```
Subject: Alfa Rating System - Phase X Deployment

We are advancing to Phase X (YY% rollout) of the Alfa rating system.
Effective immediately, YY% of tournaments will use Alfa predictions.

Previous phase results:
- Brier score: [value] (target: [target])
- Error rate: [value]%
- User feedback: [summary]

This phase will run through [date]. We'll monitor metrics continuously.

Questions? Contact: DevOps Team
```

### Announce Rollback

```
Subject: Alfa Rating System - Rollback to Phase X

Due to [reason], we've rolled back Alfa to Phase X (YY% rollout).

This is a precautionary action. We're investigating and will provide updates.

Status: All systems normal
Impact: Users now seeing Fargo predictions
Timeline: Investigation underway
```

---

## Useful Links

- Grafana: `http://your-grafana:3000`
- Monitoring: `http://your-domain/monitoring`
- API Docs: `http://your-domain/api/docs`
- Logs: `http://your-domain/api/admin/logs/tail`
