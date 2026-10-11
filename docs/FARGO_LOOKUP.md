# Fargo Manual CSV Import

The app does **not** scrape FargoRate directly (to avoid rate limits, bugs, and inaccurate fuzzy-name matching). Instead, all Fargo ratings are imported manually using official Fargo CSV/Excel exports.

## How to Import Fargo Ratings

1. **Download your CSV** from FargoRate. It must contain headers for Player Name, Rating, and (optionally) Robustness.
   - E.g., `Name`, `Fargo Rating`, `Robustness`
2. **Move the CSV** into the `Rankings-Bot/data` or `Rankings-Bot/reports` folder (or upload via the UI when the frontend component is built).
3. **Run the Import Script**:
   ```bash
   python3 scripts/import_fargo_csv.py path/to/your/file.csv --system WPBA_Women
   ```

### Script Usage

```bash
python3 scripts/import_fargo_csv.py <path_to_csv> [--system <RANKING_SYSTEM>]
```

- `--system`: The ranking system to link aliases against (e.g., `WPA_Men`, `WPA_Women`, `WPBA_Women`). Default is `WPA`.

### Features of the Importer

- Automatically normalizes names (`First Last` vs `Last, First`).
- Safely updates `fargo_score` and `fargo_robustness` in the `players` table.
- Will not overwrite existing correct licenses or countries (these are locked to authoritative WPA sources).
- Preserves the `fargo_last_updated` timestamp.

## Current (2026) ways to obtain Fargo ratings (research summary)

Official FargoRate provides **no free public bulk API or CSV export** for all players.
- Leagues using **FargoRate LMS** (lms.fargorate.com) can access data inside the system (paid).
- Public individual lookups and top lists exist on fargorate.com and playcsipool.com/fargo-ratings.html.
- Unofficial but functional: the community `fargo` CLI tool (search/lookup/bulk by ID, --json output). See termo.ai or clawhub references. Admins can run it, collect data, format as CSV, and import here.
- Digital Pool profiles (for linked players) also carry Fargo values — see `scripts/enrich_players_fargo_from_digitalpool.py --save`.
- WPBA/WPA organizers frequently share rating lists for events.

**Supported path in this app:** Export candidates (button above) → obtain current ratings from one of the above → paste `name,rating` lines → Import Fargo CSV. The `/api/fargo/sync` and repair buttons now cleanly surface the "use CSV" policy.
