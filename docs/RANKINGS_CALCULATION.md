# How Rankings Are Calculated and Where Tournament Data Comes From

## Tournament file (most recent data from email)

**File:** `tournament_tools/final_results.txt`

This is the **most recent tournament results** file, typically imported from email (e.g. Iron City Invitational VI). Format is WPA-style, tab-separated:

- **Header:** `Position`, `Family Name`, `Given Names`, `Country`, `R-points`, `Award`
- **Rows:** Position (1, 2, 3…), family name, given names, country code, and **Award** = R-points earned at that event (e.g. 11000 for 1st, 7000 for 2nd, 4800 for 3rd). Lower positions may have empty points.

**How it’s included in rankings**

- When you run **Refresh** (API or `python3 scripts/refresh_rankings.py`) or initial load, the bot checks for `tournament_tools/final_results.txt`.
- **If that file exists:** WPBA rankings are loaded from it (position → rank, Award → points, name and country from columns), saved to the database, and then **the file is deleted**. So the tournament data is added into the rankings once; after that the file is gone and the next refresh uses the official WPBA PDF.
- **If the file is missing:** WPBA rankings are scraped from the official WPBA PDF instead.

So: add your tournament data by placing `final_results.txt` in `tournament_tools/`, then run Refresh (or load initial data); the info is imported into the rankings and the file is removed so it isn’t used again.

**Related files**

- `tournament_tools/iron_city_full.txt` — Raw WPBA-style paste (position, name, prize) before conversion.
- `tournament_tools/results_converter.py` — Converts WPBA-style paste to WPA format; output can be saved as `final_results.txt` or merged into it.
- `tournament_tools/wpa_results.txt` — WPA-format output from the converter (no tournament header).
- `tournament_tools/load_final_results.py` — Parser used by the refresh script to read `final_results.txt` and produce the list saved as WPBA snapshot.

---

## How WPBA rankings are calculated (official)

WPBA rankings are **cumulative**: a player’s ranking points are the sum of **R-points** earned at sanctioned events over the ranking period (e.g. a season or rolling window). Each event awards R-points by finishing position (e.g. 1st = 11000, 2nd = 7000, 3rd = 4800, …). The official list is published by WPBA (e.g. “2026 WPBA Ranking Post ICB VI MASTER” PDF), which already incorporates recent events including Iron City VI.

**In this bot**

- **When using the tournament file:** The “rankings” are the **single event** in `final_results.txt`: position in that event = rank, Award column = points. So you see that tournament’s finishing order and R-points as the WPBA list.
- **When using the PDF:** The bot scrapes the official PDF; that list is already the full WPBA ranking (sum of events) as published by WPBA.

So “how rankings are calculated” in the official sense: **sum of R-points from events**. In the bot, we either show (1) that full list from the PDF or (2) the single-tournament snapshot from `final_results.txt` when that file is present.

---

## How WPA rankings work

WPA rankings are scraped from **wpapool.com/rankings/** (or the current WPA rankings URL). The bot does not use a local tournament file for WPA; it always uses the live (or cached) scrape. Calculation rules are set by WPA; we only ingest and display the published list.

---

## Summary

| Source              | What it is                          | When used                          |
|---------------------|--------------------------------------|------------------------------------|
| `final_results.txt` | One tournament (e.g. Iron City VI)   | WPBA rankings when file exists     |
| WPBA PDF            | Official full WPBA ranking list      | WPBA when `final_results.txt` missing |
| WPA website         | Official WPA ranking list            | Always for WPA                     |

**To use your tournament file:** Keep `tournament_tools/final_results.txt` in place with the WPA-style columns (Position, Family Name, Given Names, Country, R-points, Award). Run Refresh from the web app or `python3 scripts/refresh_rankings.py`; WPBA rankings will then come from that file.
