# Rankings Import & Historical Data — Step-by-Step

How to get **tournament history** and **Artistic Pool Professional** rankings from the WPA previous-ranking page, and how to import rankings from **PDF/CSV/XLSX** so **all columns** (including License, Stops, Date) show on the Rankings page.

---

## 1. Historical scraper (previous-ranking page)

Tournament history and historical snapshots (Men, Women, Heyball Men/Women, **Artistic Pool Professional**) are scraped from:

**https://wpapool.com/previous-ranking/**

### Run historical scrape

**Option A — Full refresh (includes historical)**  
- In the app: Admin → **Update rankings**, or  
- `POST /api/rankings/refresh`  

This runs the main WPBA/WPA scrapes and then the historical scraper.

**Option B — Historical only**  
From project root:

```bash
python3 scripts/refresh_historical_rankings.py
```

Or the test script (also saves to DB):

```bash
python3 scrape_historical.py
```

### After scraping

Refresh the materialized view and restart API if needed:

```bash
# If using Postgres
psql -U rankings -d rankings -c "REFRESH MATERIALIZED VIEW mv_latest_rankings;"

# Restart API to clear cache (if applicable)
sudo systemctl restart rankings-bot-api
```

---

## 2. WPA Artistic Pool Professional (API + frontend)

- **API:** `GET /api/rankings/wpa-artistic` (paginated, same shape as other ranking endpoints).
- **Frontend:** Rankings page has an **Artistic Pool** tab; data comes from the previous-ranking page (section “ARTISTIC POOL PROFESSIONAL RANKINGS”).
- **DB:** Run migration so the ranking type exists:  
  `alembic upgrade head`  
  (Migration `025_add_wpa_artistic_ranking_type.py` adds `WPA_Artistic` to `ranking_types`.)

If the Artistic tab is empty, run the historical scraper (step 1); the WPA page may not always publish that section.

---

## 3. PDF / file import (and all columns on Rankings page)

### Import path (step-by-step)

1. **Admin** → **Data Input** (or equivalent) → **Import rankings from file**.
2. Choose **system**: WPBA, WPA, WPBA_Women, WPA_Women, or WPA_Men.
3. Upload a **PDF, DOCX, XLSX, XML, CSV, or TXT** file.  
   - Parser expects: **Rank/Position**, **Name**, **Points**, **Country**.  
   - Optional columns (if headers present): **License** (or “WPA License”, “License number”), **Stops** (or “Stops played”, “Tournaments”).
4. Rows are parsed and saved. **All parsed columns** (including `license_number`, `stops_played`) are passed to `save_rankings` and stored.
5. **Rankings page** shows: Rank, Player Name, Country, License, Stops, Fargo, ALFA, Points, **Date** (snapshot date). Stops and License are shown for all associations when data exists.

### WPA PDF example

For a WPA PDF such as:

- [WPA-World-Rankings-SH_SS-5_20_23-FINAL.pdf](https://wpapool.com/wp-content/uploads/2023/11/WPA-World-Rankings-SH_SS-5_20_23-FINAL.pdf)

use **Import rankings from file** with system **WPA** (or **WPA_Women** / **WPA_Men** as appropriate). If the PDF has tables with Rank, Name, Points, Country (and optionally License/Stops), they will be extracted and stored; snapshot date will be the import date unless you add a dedicated PDF-date parser later.

### Columns from imports

- **Persisted:** `player_name`, `rank`, `points`, `country`, `license_number`, `stops_played`, `snapshot_date` (first-class columns); any other parsed columns go into `source_data` JSONB.  
- **Shown on Rankings page:** Rank, Player Name, Country, License, Stops, Fargo, ALFA, Points, Date, plus any columns from `source_data` (UI shows columns dynamically from API).  
- **Fargo / ALFA:** Filled by enrichment or other jobs, not by the file parser.  
- **Table design:** See [RANKINGS_TABLE_DESIGN.md](RANKINGS_TABLE_DESIGN.md).

---

## 4. Summary

| Step | What | Command / Where |
|------|------|------------------|
| Historical scraper | Scrape previous-ranking (Men, Women, Heyball, Artistic) | `python3 scripts/refresh_historical_rankings.py` or full refresh |
| WPA Artistic tab | API + frontend | Already added; run migration + historical scrape |
| PDF/CSV import | Import file and show all columns | Admin → Import file; parser passes license_number, stops_played |
| All columns on Rankings | Date, Stops for all associations | Table shows Rank, Name, Country, License, Stops, Fargo, ALFA, Points, Date |

See also: [WPA_HISTORICAL_RANKINGS_INTEGRATION.md](../WPA_HISTORICAL_RANKINGS_INTEGRATION.md) for previous-ranking page format and troubleshooting.
