# Cross-System Data Safety Measures

## Problem Identified

When filling missing player data across multiple ranking systems (e.g., WPA_Women, WPA_Heyball_Women, WPBA_Women), there's a risk of:

1. **Mixing data from different players** with identical names
2. **Propagating data entry errors** from one system to another
3. **Overwriting correct data** with incorrect data

## Current Conflicts Found

Three players have conflicting data across systems:

| Player | System 1 | Country 1 | System 2 | Country 2 | Notes |
|--------|----------|-----------|----------|-----------|-------|
| Chris Melling | WPA_Men | ENG | WPA_Heyball_Men | FIN | Same license (EPBF-077), same Fargo (799) |
| Joseph Faul | WPA_Men | RSA | WPA_Heyball_Men | GBR | Same license (AAPA-020), no Fargo data |
| Katarzyna Wesolowska | WPA_Women | SLO | WPA_Heyball_Women | POL | Same license (EPBF-055), same Fargo (653) |

## Safety Measures Implemented

### 1. Validation System

**Database Tables:**
- `data_validation_rules` - Stores verified correct data for players
- `validation_conflicts` - Tracks all detected conflicts

**Database Functions:**
- `detect_cross_system_conflicts()` - Scans for conflicting data
- `is_safe_to_merge(player_name)` - Returns TRUE only if no conflicts exist

### 2. Safe Enrichment Script

**File:** `safe_cross_system_enrichment.sql`

**Features:**
- ✅ Detects conflicts BEFORE merging
- ✅ Only merges players with NO conflicts
- ✅ Reports all conflicts for manual review
- ✅ Never overwrites existing data (only fills NULLs)

**Rules:**
- **License conflict**: Different license numbers → SKIP
- **Country conflict**: Different countries → SKIP
- **Fargo conflict**: >50 point difference → SKIP

### 3. Conflict Investigation Tools

**File:** `investigate_conflicts.sql`

Shows detailed view of all conflicting players with:
- All ranking systems they appear in
- Complete data for each system
- Snapshot dates and creation timestamps

## Usage Guide

### Check for Conflicts

```sql
-- View all current conflicts
SELECT * FROM detect_cross_system_conflicts();

-- View unresolved conflicts in tracking table
SELECT * FROM validation_conflicts WHERE resolved = FALSE;
```

### Run Safe Enrichment

```bash
# Preview what will be merged (shows conflicts and safe merges)
sudo docker exec -i rankings-bot-postgres psql -U rankings -d rankings < safe_cross_system_enrichment.sql
```

### Resolve Conflicts Manually

1. **Investigate the player:**
   ```sql
   SELECT * FROM rankings WHERE player_name = 'Chris Melling' ORDER BY ranking_system;
   ```

2. **Research correct data** (check official websites, player profiles)

3. **Fix the incorrect record:**
   ```sql
   UPDATE rankings 
   SET country = 'ENG' 
   WHERE player_name = 'Chris Melling' 
       AND ranking_system = 'WPA_Heyball_Men';
   ```

4. **Mark conflict as resolved:**
   ```sql
   UPDATE validation_conflicts 
   SET resolved = TRUE, 
       resolution_notes = 'Fixed: Chris Melling is English, changed FIN→ENG'
   WHERE player_name = 'Chris Melling' 
       AND conflict_type = 'COUNTRY';
   ```

5. **Add validation rule (optional):**
   ```sql
   INSERT INTO data_validation_rules (player_name, verified_country, verified_license, notes)
   VALUES ('Chris Melling', 'ENG', 'EPBF - 077', 'Verified from WPA official roster');
   ```

### Prevent Future Conflicts

**Option 1: Add Unique Player ID**
- Implement `player_id` system linked to external ID (e.g., Fargo ID)
- Match players across systems by ID instead of name

**Option 2: Manual Verification**
- Before each scrape, run conflict detection
- Review and resolve conflicts before enrichment
- Add validation rules for verified players

## Recommended Workflow

1. **After each scrape:**
   ```sql
   SELECT * FROM detect_cross_system_conflicts();
   ```

2. **Before enrichment:**
   ```bash
   sudo docker exec -i rankings-bot-postgres psql -U rankings -d rankings < investigate_conflicts.sql
   ```

3. **Resolve any conflicts** (see steps above)

4. **Run safe enrichment:**
   ```bash
   sudo docker exec -i rankings-bot-postgres psql -U rankings -d rankings < safe_cross_system_enrichment.sql
   ```

5. **Refresh materialized view and restart API:**
   ```bash
   sudo systemctl restart rankings-bot-api
   ```

## Files Reference

| File | Purpose |
|------|---------|
| `safe_cross_system_enrichment.sql` | Safe data merge with conflict detection |
| `investigate_conflicts.sql` | Detailed conflict investigation report |
| `install_validation_system.sql` | Install validation tables and functions |
| `enrich_cross_system_data.sql` | ⚠️ UNSAFE - No conflict detection (deprecated) |

## Current Status

✅ Validation system installed
✅ 3 conflicts logged and tracked
⏳ **Conflicts need manual resolution before next enrichment**

### Next Steps

1. Research correct country codes for the 3 conflicting players
2. Update incorrect records manually
3. Mark conflicts as resolved
4. Re-run safe enrichment to fill remaining NULL values
5. Consider implementing player_id system for future-proofing

## Important Notes

- The original `enrich_cross_system_data.sql` (unsafe version) only filled NULL values, so it didn't corrupt existing data
- Always use `safe_cross_system_enrichment.sql` going forward
- Backend API will show NULL values as "No data" in the frontend when data is genuinely missing across all systems
- Cross-system enrichment is run manually, not automatically, to maintain data integrity
