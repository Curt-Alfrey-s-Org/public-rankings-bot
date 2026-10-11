# 🚀 License Research Quick Start

**Time to get started:** 5 minutes  
**Time for Phase 1:** 45 minutes  
**Expected result:** +8-13 licenses (48.8% → 54-56%)

## ⚡ Get Started Now

### Step 1: Understand the Gap (5 min)
```bash
cd /home/ansible/rankings-bot
python3 scripts/analyze_license_correlation.py
```

**Output tells you:**
- Which organizations to search (BCA, ACBS, EPBF)
- Which players to search first
- Expected license format for each

### Step 2: Phase 1 Research (45 min)

#### Quick Win #1: ACBS Taiwan → Find 2 licenses (10 min)
```
Players to find:
1. Chia Hua Chen (TPE)
2. Wang Wan-Ling (Taiwan)

Action:
- Google: "Chia Hua Chen" ACBS license
- Google: "Wang Wan-Ling" Taiwan pool license
- Check: Taiwan billiards federation website

Format: ACBS - ### (example: ACBS - 095)
```

#### Quick Win #2: EPBF Spain → Find 1 license (5 min)
```
Player to find:
1. Silvia Lopez (ESP)

Action:
- Google: "Silvia Lopez" Spain EPBF pool
- Check: EPBF.info website (if available)
- Check: Spanish billiards federation

Format: EPBF - ### (example: EPBF - 128)
```

#### Quick Win #3: BCA Hall of Fame → Find 5-10 licenses (30 min)
```
Players to find: Top ranked among these 22 USA/American women:
- Alice Adams
- Barbara Lee  
- Betsy Sundholm
- Chris Honeman
- Jaye Succo
- [+17 more]

Action:
1. Visit: https://www.bca-pool.com/hall-of-fame
2. Search for women's names (Ctrl+F)
3. Record any license numbers found
4. For each name, note: Player Name | BCA - XXX

Format: BCA - ### (example: BCA - 170)
```

#### Result: 3 sources → ~8-13 licenses found

### Step 3: Update Database
```bash
# For each license found, run:
psql "${DATABASE_URL:-postgresql://rankingsbot_user:PASSWORD@rankings-bot-postgres:5432/rankingsbot}" << EOF
UPDATE rankings SET license_number = 'BCA - 170' 
WHERE ranking_system = 'WPBA_Women' AND player_name = 'Ada Lio';
EOF

# Or create CSV and bulk update later:
# player_name,license_number
# Alice Adams,BCA - 123
# Barbara Lee,BCA - 456
```

### Step 4: Verify Progress
```bash
python3 << 'EOF'
import psycopg2
conn = psycopg2.connect(database='rankings', user='rankings', password='rankings', host='localhost')
cur = conn.cursor()
cur.execute("""SELECT COUNT(*) FROM rankings WHERE ranking_system = 'WPBA_Women' 
AND license_number IS NOT NULL""")
result = cur.fetchone()[0]
print(f"✅ Licenses found: {result}/166 ({result/166*100:.1f}%)")
EOF
```

---

## 📋 Copy-Paste Search Phrases

### For Google/Web Search:
```
"{PlayerName}" BCA license number pool
"{PlayerName}" professional pool license
"{PlayerName}" WPBA women's pool
```

### For Organization Sites:
```
BCA: https://www.bca-pool.com/hall-of-fame
EPBF: https://www.epbf.info/
ACBS: Search for Taiwan/Asian federation
```

---

## 📊 Tracking Template

Keep a simple text file or spreadsheet:
```
Player Name | Organization | License Found | Status
Alice Adams | BCA          | BCA - 123     | ✓
Maria Smith | BCA          | ?             | 🔍 Searching
```

---

## 🎯 Phase 1 Checklist

- [ ] Run `analyze_license_correlation.py` (understand the gap)
- [ ] Read LICENSE_RESEARCH_BY_ORG.md (detailed guide)
- [ ] Search ACBS Taiwan players (2 players)
- [ ] Search EPBF Spain player (1 player)
- [ ] Browse BCA Hall of Fame (30 min, target 5-10)
- [ ] Record findings in spreadsheet
- [ ] Update database with found licenses
- [ ] Verify progress with SQL query

---

## Time Budget

| Task | Time | Expected Result |
|------|------|-----------------|
| Understand gap | 5 min | Know what to search |
| ACBS Taiwan | 10 min | +2 licenses |
| EPBF Spain | 5 min | +1 license |
| BCA Hall of Fame | 25 min | +5-10 licenses |
| Database update | 5 min | Live updates |
| Verification | 5 min | Progress confirmed |
| **TOTAL** | **45 min** | **+8-13 licenses** |

---

## 🎓 If You Get Stuck

See these documents for help:
- **LICENSE_RESEARCH_BY_ORG.md** - Detailed org-specific guides
- **LICENSES_ACTION_PLAN.md** - Full implementation strategy
- **LICENSE_RESEARCH_STRATEGY.md** - Strategic overview
- **scripts/analyze_license_correlation.py** - Run to see targets

---

## 💪 Good Luck!

**Phase 1 goal:** 45 minutes → 8-13 new licenses  
**Realistic expectation:** Find most or all of the low-hanging fruit  
**Momentum:** Once you see progress, Phase 2 becomes easier!
