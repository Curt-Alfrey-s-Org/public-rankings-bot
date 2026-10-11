# 🏅 WPBA Player License Research & Strategy

**Date:** February 19, 2026  
**Status:** Assessment Phase  
**Goal:** Increase WPBA license coverage from 48.8% to 80%+

---

## 📊 Current License Coverage

```
Total WPBA Women Players:  166
With License Numbers:       81 (48.8%)  ✅
Without License Numbers:    89 (51.2%)  ⚠️

License Types Found:
├─ BCA (Billiard Congress of America):  ~70 players
├─ EPBF (European Pro Billiards Fed):   ~3 players
├─ Other/Mixed:                         ~8 players
└─ No License:                          89 players
```

---

## 🔍 License Sources Research

### 1. **WPBA Official (wpba.com)**
**Status:** ⏳ Need to investigate  
**URL:** https://www.wpba.com  
**Potential:** 
- Player profiles with license info
- Historical tournament records
- Official licensing database

**Method:**
```bash
# Research:
curl -s https://www.wpba.com/players | head -100
# Look for: player names + license numbers
```

**Difficulty:** Medium (may require parsing)  
**Time Cost:** 20 minutes investigation

---

### 2. **BCA Hall of Fame & Membership Database**
**Status:** ⏳ Need to investigate  
**URL:** https://www.bca-pool.com/  
**Potential:**
- BCA licensed players directory
- License numbers in member profiles
- Searchable player database

**Method:**
```bash
# Research:
curl -s "https://www.bca-pool.com/players" 
# Look for patterns in member profiles
```

**Difficulty:** Medium (may need JavaScript handling)  
**Time Cost:** 30 minutes investigation

---

### 3. **External pool site — player profiles**
**Status:** ✅ Already identified  
**URL:** `https://www.digitalpool.com/players`  
**Potential:**
- Player profile pages with license info
- Searchable directory
- Tournament history with license references

**Method:**
```bash
# Use Selenium scraper we already built:
python3 scripts/scrape_externalpool_selenium.py
# Extract license numbers from player profiles
```

**Difficulty:** Low (we have Selenium scraper)  
**Time Cost:** 15 minutes modification

---

### 4. **FargoRate Database**
**Status:** ⏳ Need to investigate  
**URL:** https://www.fargorating.com/  
**Potential:**
- Fargo ratings tied to player profiles
- BCA/IPA license info
- International licensing data

**Method:**
```bash
# Research API or scraping:
curl -s "https://www.fargorating.com/api/players?country=USA"
# Check for license data in responses
```

**Difficulty:** Medium (may have API terms)  
**Time Cost:** 20 minutes investigation

---

### 5. **International Billards Organizations**
**Status:** ⏳ Need to research  

**Organizations:**
- **EPBF** (European Professional Billiards Federation) - for European players
- **IBSF** (International Billiards and Snooker Federation) - for international
- **PBA** (Professional Billiards Association) - for men's/mixed

**Method:**
- Research individual organization websites  
- Look for player directories  
- Check for API access

**Difficulty:** High (multiple sources, varies by org)  
**Time Cost:** 45 minutes investigation

---

### 6. **Tournament Results Archives**
**Status:** ✅ Partially available  
**URL:** External Pool historical tournaments  
**Potential:**
- Tournament brackets show player license info
- Historical licensing data
- License progression over time

**Method:**
```bash
# Already have tournament data:
ls data/externalpool_archive/
# Extract license numbers from bracket display
```

**Difficulty:** Low (source already investigated)  
**Time Cost:** 10 minutes parsing

---

### 7. **LinkedIn & Social Media**
**Status:** ⏳ Manual research  
**Potential:**
- Player profiles with professional info
- License mentions in bios
- Biographical data

**Method:**
- Manual search: Each player name + "BCA license" OR "pool license"
- Automated: Limited by rate limiting and ToS

**Difficulty:** Very High (manual, ethical concerns)  
**Time Cost:** 1-2 hours per 10 players

---

## 🎯 Recommended Priority Order

### Phase 1: Quick Wins (High ROI, Low Effort) 
**Target: +30 licenses (48.8% → 66%)**

```
1. ✅ Extract from tournament brackets (External Pool) → ~10-15 licenses
2. ✅ Parse WPBA.com player pages (if exposed) → ~10-15 licenses  
3. ✅ Cross-reference with FargoRate data → ~5-10 licenses
```

**Time:** ~1 hour  
**Estimated Coverage:** 66%

### Phase 2: Medium Effort Sources
**Target: +20 licenses (66% → 78%)**

```
4. ⚠️ BCA Hall of Fame/Member search → ~15-20 licenses
5. ⚠️ Regional tournament organizing bodies → ~5-10 licenses
```

**Time:** ~2 hours  
**Estimated Coverage:** 78%

### Phase 3: Intensive Manual Work
**Target: +15 licenses (78% → 87%)**

```
6. ❌ LinkedIn/social media research → ~10-20 licenses (very time-intensive)
7. ❌ Direct player contact/surveys → unlimited but slow
```

**Time:** ~3-5 hours  
**Estimated Coverage:** 80-90%

---

## 🏗️ Technical Implementation Plan

### Script 1: License Extraction from Tournament Brackets
```python
# Location: scripts/extract_licenses_from_tournaments.py
# Input: External Pool tournament archives
# Output: CSV with player_name, license_number
# Method: Regex pattern matching in bracket data
```

### Script 2: WPBA.com License Scraper
```python
# Location: scripts/scrape_wpba_licenses.py
# Target: https://www.wpba.com/players or similar
# Method: Selenium/BeautifulSoup
# Output: player_name, license_number, profile_url
```

### Script 3: FargoRate License Lookup
```python
# Location: scripts/lookup_fargorating_licenses.py
# Target: https://www.fargorating.com/
# Method: API calls or web scraping
# Output: Merged license data from Fargo profiles
```

### Database Update Script
```python
# Location: scripts/enrich_licenses.py
# Input: CSV from above scripts
# Method: Fuzzy match player names to existing records
# Output: Updated rankings table with new license numbers
```

---

## 📋 Players Most Likely to Have Licenses (Based on Rank)

**High-ranked players (Ranks 1-20) usually have licenses:**
```
Kristina Tkach          (Rank 1)   - Likely has license ✓
Kelly Fisher            (Rank 2)   - BCA - 509 ✓
Pia Filler              (Rank 3)   - ? (check)
Jasmin Ouschan          (Rank 4)   - ? (check)
Chezka Centeno          (Rank 5)   - ? (check)
```

**Lower-ranked or newer players less likely to have licenses**

---

## 🔗 Specific Websites to Research

| Organization | URL | Data Type | Difficulty |
|--------------|-----|-----------|-----------|
| WPBA | wpba.com/players | Player directory | Medium |
| BCA | bca-pool.com/members | Member database | Hard |
| FargoRate | fargorating.com/api | API/Web | Medium |
| EPBF | epbf.info | Player list | Medium |
| External Pool | `https://www.digitalpool.com/players` | Profiles | Easy |
| APA | apapool.com | Amateur data | Medium |

---

## 💡 Strategy Recommendation

**Start with Phase 1 (quick wins):**
1. Parse existing tournament bracket data for licenses
2. Scrape WPBA.com player pages (if licenses are shown)
3. Cross-reference with FargoRate using player names

**Expected outcome:** 66% coverage in ~1 hour

**Then assess:** If Phase 1 yields 50%+ of missing licenses, continue to Phase 2

---

## 📝 Next Steps

Choose one:

**Option A: Fast + Thorough**
→ Execute Phase 1 → Assess → Decide on Phase 2

**Option B: Comprehensive Research**
→ Manually research each website → Create master plan → Execute

**Option C: Direct Database Cross-Reference**
→ Use existing Fargo ratings data → Cross-match with known licenses → Update DB

---

## 🎯 Success Metrics

| Milestone | Current | Target | Effort |
|-----------|---------|--------|--------|
| Phase 0 (Baseline) | 48.8% (81/166) | - | Done |
| Phase 1 Success | 48.8% | 66% (109/166) | ~1 hour |
| Phase 2 Success | 66% | 78% (129/166) | ~2 hours |
| Phase 3 Success | 78% | 87% (144/166) | ~3-5 hours |

---

**Ready to proceed? Choose an option above and we'll execute it.**
