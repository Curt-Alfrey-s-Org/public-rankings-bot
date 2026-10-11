#!/usr/bin/env python3
"""
Load initial rankings data (no auto-scraping).
Ingests tournament_tools/final_results.txt into tournament imports when present.
Rankings are not scraped automatically; use Update rankings in the app or
POST /api/rankings/refresh to load WPBA/WPA data.
"""
import sys
from pathlib import Path

# Add project root to path before importing project_root
_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root))

from project_root import PROJECT_ROOT
TOURNAMENT_FILE = PROJECT_ROOT / "tournament_tools" / "final_results.txt"

from database import get_database_manager


def main():
    print("=" * 70)
    print("Loading Initial Rankings Data")
    print("=" * 70)

    db = get_database_manager()

    wpba_rankings = db.get_latest_rankings("WPBA")
    wpa_rankings = db.get_latest_rankings("WPA")

    # WPBA: only ingest from tournament file if present; no scraping
    if not wpba_rankings:
        if TOURNAMENT_FILE.exists():
            print("\nIngesting tournament_tools/final_results.txt into tournament imports...")
            from tournament_tools.load_final_results import parse_final_results, parse_final_results_multi
            blocks = parse_final_results_multi(TOURNAMENT_FILE)
            if not blocks:
                single = parse_final_results(TOURNAMENT_FILE)
                if single:
                    blocks = [single]
            if blocks:
                for idx, raw_results in enumerate(blocks):
                    name = f"Tournament {idx + 1}" if len(blocks) > 1 else "Tournament from file"
                    db.create_tournament_import(name, raw_results, "WPBA")
                print(f"✓ Added {len(blocks)} tournament(s) to Data input. Confirm the tournaments, then Update rankings (using points-based calculation).")
                try:
                    TOURNAMENT_FILE.unlink()
                    print("✓ Deleted tournament file after ingest")
                except OSError as e:
                    print(f"⚠ Could not delete tournament file: {e}")
            else:
                print("✗ No data in tournament file")
        else:
            print("\nNo WPBA data. Use Update rankings in the app or POST /api/rankings/refresh to load data.")
    else:
        print(f"\n✓ WPBA data exists ({len(wpba_rankings)} entries)")

    if not wpa_rankings:
        print("No WPA data. Use Update rankings in the app or POST /api/rankings/refresh to load data.")
    else:
        print(f"✓ WPA data exists ({len(wpa_rankings)} entries)")

    print("\n" + "=" * 70)
    print("Data loading complete!")
    print("=" * 70)

if __name__ == '__main__':
    main()
