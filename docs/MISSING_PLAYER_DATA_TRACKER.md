# Missing Player Data Tracker

_Last updated: 2026-03-09 22:40:20 UTC_

## Scope

- All ranking systems latest snapshots: `WPBA_Women`, `WPA_Women`, `WPA_Men`, `WPA_Heyball_Men`, `WPA_Heyball_Women`, `WPA_Artistic`
- Manual-research list includes players missing Fargo ratings
- Focus on players that genuinely exist but don't have Fargo ratings (not debug/test data)
- Fuzzy matching attempted but unsuccessful for these players

## Fargo Rating Coverage Summary

| System | Total Players | Missing Fargo | Coverage |
|---|---:|---:|---:|---:|
| WPBA_Women | 167 | 1 | 99.4% |
| WPA_Women | 155 | 21 | 86.5% |
| WPA_Men | 279 | 20 | 92.8% |
| WPA_Heyball_Men | 206 | 174 | 15.5% |
| WPA_Heyball_Women | 118 | 83 | 29.7% |
| WPA_Artistic | 27 | 26 | 3.7% |
| **Overall** | **952** | **325** | **65.9%** |

## Reports

- `reports/players_needing_fargo_manual_research_20260308_224020.csv` (325 rows - all missing Fargo ratings, sorted by name complexity)
- `reports/fargo_manual_import_template_ALL_20260309.csv` (301 rows - historical)
- `reports/fargo_manual_import_template_3plus_tokens_20260309.csv` (75 rows - historical)

## Priority Manual Research (By System)

### WPBA_Women (1 missing - 99.4% coverage)
- `3500` (appears to be a license number rather than name)

### WPA_Women (21 missing - 86.5% coverage)
Priority (2-part names): Orr, Sue; Myers, Eva
Others: Margarita Fefilova, Ayala, Soledad Ayala, etc.

### WPA_Men (20 missing - 92.8% coverage)
Priority (2-part names): Various international players
Complex names need careful research to avoid false matches.

### WPA_Heyball_Men (174 missing - 15.5% coverage)
Majority of players missing Fargo ratings. Many appear to be international players who may not have Fargo accounts.

### WPA_Heyball_Women (83 missing - 29.7% coverage)
Similar to Heyball Men - many international players without Fargo ratings.

### WPA_Artistic (26 missing - 3.7% coverage)
Very low coverage - most artistic pool players don't have Fargo ratings.

## Next Steps

1. **Manual Research Priority**: Focus on core systems (WPBA_Women, WPA_Women, WPA_Men) first, as they have the highest coverage potential
2. **Heyball & Artistic**: These systems have many international players who may genuinely not have Fargo ratings
3. **FargoRate Website**: Check https://fargorate.com/top-ten-lists for the 4 categories of top 100 players
4. **EST Ratings**: Players without Fargo ratings can still get EST ratings for live ranking updates
5. **PRO Features**: Fargo and ALFA ratings are PRO features - ensure frontend properly gates them

