#!/usr/bin/env python3
"""CLI: compare players.est_rating vs players.fargo_score (Phase 4).

Usage (from repo root, with DATABASE_URL set or in container):
  python scripts/run_est_fargo_comparison.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    from database import get_database_manager
    from api.services.est_fargo_comparison import run_est_fargo_comparison

    db = get_database_manager()
    result = run_est_fargo_comparison(db)
    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
