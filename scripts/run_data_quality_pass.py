#!/usr/bin/env python3
"""Phase 5 data quality pass — crosswalk summary, drift checks, alias seeding.

Usage:
  python scripts/run_data_quality_pass.py
  python scripts/run_data_quality_pass.py --apply-aliases
"""

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

from api.services.data_quality_pass import DataQualityPass


def main() -> int:
    ap = argparse.ArgumentParser(description="Run Phase 5 data quality pass")
    ap.add_argument("--apply-aliases", action="store_true", help="Seed player_name_aliases")
    ap.add_argument("--begin-year", type=int, default=2020)
    ap.add_argument("--end-year", type=int, default=None)
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    report = DataQualityPass().run(
        begin_year=args.begin_year,
        end_year=args.end_year,
        apply_aliases=args.apply_aliases,
    )
    print(json.dumps(report, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
