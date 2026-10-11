# Data Enrichment & Scrape Archive System

## Overview

Complete system for enriching WPBA player data with country/license information and archiving raw scrape data for historical reference and gap-filling.

## Current Data Status

### Database (WPBA Women - Latest Snapshot)
```
Total Players:  166
With Country:   81  (48%)
With License:   81  (48%)
With Stops:     166 (100%) ✅
```

### Historical Players (All Snapshots)
```
Total WPBA:     498 players (all dates)
With Country:   249 (50%)  ← Improved via tournament enrichment
With Stops:     Calculated from tournament_results table
```

### Available Tournament Data Archive
```
WPA Women:      155 players with country + tournament history
WPA Men:        279 players with country + tournament history
WPBA Women:     166 players + tournament history (no country/license in PDF)
WPA Heyball:    331 players
WPA Artistic:   132 players
```

## Enrichment Process

### Stage 1: WPA Cross-Population ✅
**Method**: Match WPBA players appearing in WPA rankings
```sql
-- Normalize names: "Firstname Lastname" ↔ "Lastname, Firstname"
-- Find players in both systems with case-insensitive matching
-- Copy country, license_number, fargo_rating from WPA to WPBA
```

**Result**: 81/166 WPBA women players (48%)
**Matched via**: Direct name matching + fuzzy matching

### Stage 2: Tournament Data Enrichment ✅
**Method**: Use per_tournament_rankings.json to link WPBA ↔ WPA
```
File: data/per_tournament_rankings.json (286K)
Contains: Player participation history across tournaments

Script: scripts/enrich_from_tournaments.py
- Loads WPA player country + tournament participation
- Matches WPBA players by name similarity
- Updates WPBA with country from matched WPA record
```

**Result**: +6 additional players (85 → 79 still missing)
**Matched via**: Tournament participation + fuzzy name matching

### Stage 3: Web Scraping (TODO - Future)
**Method**: Search external sources for remaining 79 players
- FargoRate player database
- WPBA official website player profiles
- WPA licensing registry
- Old tournament archives online

## Scrape Archive System

### Backup Location
```
Database Backups:  /home/ansible/rankings-bot/backups/*.dump
Scrape Archives:   /home/ansible/rankings-bot/backups/scrapes/
```

### Files Archived
1. **per_tournament_rankings.json** (286K)
   - Complete player participation history
   - WPA rankings with country data
   - WPBA rankings (no country yet)

2. **PDFs** (when downloaded)
   - WPBA ranking PDFs
   - Historical PDFs from archival

3. **Metadata** (METADATA.json)
   - Backup timestamp
   - Retention expiry date
   - File manifest

### Backup Schedule
```
Manual:    ./scripts/backup_scrapes.sh              (on-demand)
Automatic: Integrate with ranking refresh endpoint
Retention: 30 days (matches database backup retention)
```

### Recent Backups
```
scrapes_20260219_110900.tar.gz (21K) - Latest
```

## Scripts & Commands

### 1. Run Tournament Data Enrichment
```bash
cd /home/ansible/rankings-bot
python3 scripts/enrich_from_tournaments.py
```

Output:
```
Matched: 6 additional players
Total with country: 249/498 (50%)
```

### 2. Backup Scrape Data
```bash
cd /home/ansible/rankings-bot
./scripts/backup_scrapes.sh
```

Creates: `backups/scrapes/scrapes_YYYYMMDD_HHMMSS.tar.gz`

### 3. List Tournament Players with Countries
```bash
python3 << 'EOF'
import json
with open('data/per_tournament_rankings.json') as f:
    data = json.load(f)
    wpa_women = data['wpa_women']['players']
    for p in sorted(wpa_women, key=lambda x: x.get('rank', 999))[:10]:
        print(f"{p['rank']:3} {p['name']:30} {p.get('country', 'N/A')}")
EOF
```

### 4. Check WPBA Coverage
```bash
psql "${DATABASE_URL:-postgresql://rankingsbot_user:PASSWORD@rankings-bot-postgres:5432/rankingsbot}" -c "
SELECT 
    COUNT(*) total,
    COUNT(country) with_country,
    ROUND(100.0 * COUNT(country) / COUNT(*), 0) coverage_pct
FROM rankings 
WHERE ranking_system = 'WPBA_Women'
AND snapshot_date = (SELECT MAX(snapshot_date) FROM rankings WHERE ranking_system = 'WPBA_Women');"
```

## Integration Points

### API Endpoint for Scrape Management
```
GET  /api/backups/list              - List all backups (DB + scrapes)
POST /api/backups/create            - Create DB backup
POST /api/backups/scrape            - Archive current scrapes
GET  /api/backups/scrapes/{name}    - Download scrape archive
```

### Rankings Refresh Flow
```
1. Download WPBA PDF
2. Parse rankings (166 players)
3. Save to database
4. WPA enrichment (↑ to 81 with country)
5. Tournament data enrichment (↑ to 87)
6. Archive scrape data
7. Backup database
```

## Data Sources & Limitations

### WPBA PDF
- **Source**: WPBA official website
- **URL**: https://static1.squarespace.com/static/.../2026+WPBA+Ranking+Post+ICB+VI+MASTER.pdf
- **Data**: Rank, Name, Points (no country/license)
- **Coverage**: Only top-ranked women (126 in earlier PDFs, 166 in current)

### WPA Rankings  
- **Source**: wpapool.com (currently offline/timeouts)
- **Fallback**: Database cache (Feb 18 snapshot)
- **Data**: Rank, Name, Points, License, Country
- **Coverage**: 467 women, 904 men

### Tournament History
- **Source**: Cached per_tournament_rankings.json
- **Updated**: Feb 18, 2026
- **Data**: Player name, country (if in WPA), tournament results
- **Coverage**: 155 WPA women with complete history

## Known Gaps

### WPBA Women Without Country (79 players)
These players:
- Don't appear in WPA rankings (domestic-only)
- May be in historical/archived tournaments
- Could be found via FargoRate/WPBA official database
- Some may have retired from competitive play

**Examples of missing players**:
- Kaylee McIntosh Driskell
- Britney Branham  
- Lindsey Daguio
- (77 others)

## Future Enhancements

### Phase 1: Web Scraping
- FargoRate API integration
- WPBA player profile scraper
- Historical tournament archives

### Phase 2: Manual Curation
- Admin interface to add missing countries
- Verify conflicting data
- Add notes for international players

### Phase 3: Data Quality
- Implement data validation rules
- Flag suspicious entries
- Historical tracking of changes

## Troubleshooting

### Tournament Data Not Found
```bash
ls -lh data/per_tournament_rankings.json
# If missing, run:
python3 scripts/load_per_tournament_rankings_into_tournaments.py
```

### Scrape Archive Issues
```bash
# List all backups
ls -lh backups/scrapes/

# Extract specific backup
tar -xzf backups/scrapes/scrapes_20260219_110900.tar.gz

# Check metadata
zcat backups/scrapes/scrapes_20260219_110900.tar.gz | tar -xzf - --to-stdout scrapes_*/METADATA.json | jq .
```

### Database Enrichment Not Working
```bash
# Check database connection
psql "${DATABASE_URL:-postgresql://rankingsbot_user:PASSWORD@rankings-bot-postgres:5432/rankingsbot}" -c "SELECT COUNT(*) FROM rankings WHERE ranking_system = 'WPBA_Women';"

# Restart API to reload enrichment
sudo systemctl restart rankings-bot-api
```

## Files Involved

```
Core Scripts:
- scripts/backup_scrapes.sh              Archive scraped data
- scripts/enrich_from_tournaments.py     Cross-populate from tournaments
- scripts/backup_postgres.sh             Database backup (existing)
- scripts/automated_backup_with_retention.sh

Data:
- data/per_tournament_rankings.json      Player participation history
- backups/scrapes/                       Scrape archives (30-day retention)
- backups/*.dump                         Database backups (30-day retention)

Documentation:
- SCRAPE_ARCHIVE_STRATEGY.md             Strategy & approach
- DATA_ENRICHMENT.md                     This file
```

## Contact & Support

For questions about data enrichment or scrape archiving:
1. Check recent logs: `logs/scrape_backup.log`
2. Review backup metadata: `backups/scrapes/*/METADATA.json`
3. Test enrichment manually: `python3 scripts/enrich_from_tournaments.py`
