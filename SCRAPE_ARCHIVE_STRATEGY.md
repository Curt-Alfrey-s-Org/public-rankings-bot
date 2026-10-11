# Scrape Archive & Data Enrichment Strategy

## Current Data Status

### Tournament Rankings Data (`data/per_tournament_rankings.json`)
- **WPA Women**: 155 players with country data ✅
- **WPA Men**: 279 players with country data ✅
- **WPBA Women**: 166 players, NO country/license data ❌
- Contains tournament-by-tournament participation history

### Database Rankings
- **WPBA Women**: 166 players
  - Country: 81/166 (48%) - from WPA enrichment
  - License: 81/166 (48%) - from WPA enrichment
  - Missing: 85 players with no WPA match

### Coverage Gap
85 WPBA women players have no country/license data because:
1. They don't appear in WPA rankings (domestic-only players)
2. No tournament results link them to WPA counterparts
3. WPBA PDF doesn't extract country/license fields

## Solution Strategy

### Phase 1: Archive Scrapes (1-month retention)
- Store raw scrape JSON files alongside database backups
- Archive WPBA PDFs downloaded for parsing
- Automatic cleanup of files older than 30 days
- Version control for scrape metadata

### Phase 2: Enhanced Data Enrichment
- Cross-reference tournament results with player lookup
- Use historical scrape archives to fill gaps
- Implement fallback web scraping for missing players
- Merge data from multiple sources

### Phase 3: Web Scraping for Missing Data
- WPBA website for player profiles
- FargoRate database for player lookups
- WPA licensing database for international players
- Old tournament result archives

## Files Modified
1. `scripts/backup_scrapes.sh` - Archive scrapes with retention
2. `api/routes/rankings.py` - Enhanced refresh endpoint
3. `database/db_manager.py` - Improved enrichment
4. `docs/DATA_ENRICHMENT.md` - New documentation

## Backup Schedule
- Database: Every 2 hours (automated)
- Scrapes: After each ranking refresh (on-demand)
- Retention: 30 days for both

## Data Flow
```
[WPBA PDF] → [Scrape] → [JSON Archive] → [Parse] → [Database]
                           ↓
                    [Tournament Data]
                           ↓
                  [Enrichment Engine]
                           ↓
                   [WPA + Web Sources]
                           ↓
                  [Complete Rankings]
```
