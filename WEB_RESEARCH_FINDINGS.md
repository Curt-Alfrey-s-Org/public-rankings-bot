# WPBA Missing Player Data - Web Research Sources

## Search Findings Summary

### Rich Web Data Sources Found

1. **External pool site — tournament brackets** ([vendor site](https://www.digitalpool.com/tournaments)) ✅ ACTIVE
   - `https://www.digitalpool.com/tournaments`
   - Contains 2025-2026 WPBA tournaments with player flags
   - Displays country codes for all registered participants
   - **Status**: Successfully extracted country data for 93+ players

2. **WPBA.com Official Website**
   - https://www.wpba.com
   - Tournament news and coverage with player bios
   - Video archives mention player nationalities
   - **Status**: Limited structured data, mostly narrative

3. **Tournament Result Archives**
   - External Pool stores complete bracket histories
   - Player names with Fargo ratings and flags
   - Past 2-3 years of major WPBA events available

## Data Extraction Summary

**Successfully Populated:**
- 23 unique WPBA women from tournament bracket flags
- 93 total player records updated (multiple snapshots per player)
- Sources: 2026 Classic, 2025 Colorado Classic, 2025 Iron City Invitational

**Remaining Gaps:** 60 players without country data

---

## Recommended Next Steps for Missing Players

### Strategy 1: Expand Tournament Data (Recommended)
Search additional WPBA events on External Pool:
- 2025 Dr Pool Jacoby Tour Championships
- 2025 Iron City Invitational VI
- 2024 tournaments (archived bracket data)
- Regional ladies tournaments

**Why:** Low effort, high accuracy - flags are embedded in tournament HTML

### Strategy 2: Social Media Profile Research
- Instagram/Facebook player profiles mention hometown/country
- YouTube billiards channels often interview international players
- Twitter profiles may list location

**Why:** Public, self-reported data

### Strategy 3: FargoRate Database Investigation
- https://fargo.billiards.net
- Players from non-US regions often have country codes in profiles
- Ratings may include registration country

**Why:** Structured pool player database (requires web scraping API access)

### Strategy 4: Regional Tournament Organizers
- WPBA has regional qualifying tournaments
- Event pages often list player origins
- Some bill players' countries for international appeal

### Strategy 5: BCA Hall of Fame & Records
- BCA maintains historical player records
- Professional player biographies include country

---

## Missing Players to Research (60 Total)

### Group 1: Likely US Players (Based on naming conventions)
- Alexa Zima
- Allison Cuccia
- Amanda Soucy
- April Erfman
- April Gonzales
- Avah Weems
- Beth Fondell
- Bonnie Hunkins
- Camille Campbell
- Carina Gonzalez
- Cathy Tschumper
- Cindy Reiter
- Courtney Ruggerio
- Dawn Fox
- Dawn Hopkins
- ... (more to research)

### Group 2: International-Sounding Names (May have flags in other tournaments)
- Eleanor Callado (Spanish-sounding)
- Farah Tschumm (Arabic/European)
- Farrah Tschumm
- Gina Scoczu
- And 50+ others

---

## Automated Discovery Method

For each missing player, check these URLs in sequence:

```
1. https://www.digitalpool.com/search?query={PLAYER_NAME}
2. https://www.digitalpool.com/tournaments?search={PLAYER_NAME}
3. External Pool tournament bracket archives (2024, 2025, 2026)
```

---

## Current Database Status

**Latest Update: Feb 19, 2026**
- WPBA_Women latest snapshot: 166 players
- With country: 96 players (57.8%)
- Without country: 70 players (42.2%)
- With stops_played: 166 players (100%)

---

## Implementation Notes

1. **Fuzzy matching already implemented** - handles name variations like:
   - "Meng-Hsia Hung" ↔ "Bean Meng-Hsia Hung"
   - Name format differences

2. **Data quality notes:**
   - Tournament flags are authoritative (players register voluntarily)
   - Multiple recent tournaments strengthen confidence
   - International tournaments (WPBA Classic) biased toward verified players

3. **Future phases:**
   - Expand to 2024 tournaments once data validated
   - Integrate social media verification layer
   - Cross-check with FargoRate when API available
