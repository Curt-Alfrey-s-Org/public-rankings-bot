#!/usr/bin/env python3
"""Single-player Fargo lookup helper (FairMatch or API)."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from typing import Dict, Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.services import fargo_client


logger = logging.getLogger(__name__)


def _lookup_player(name: str, org: str, source: str) -> Dict[str, Any]:
    """Lookup a single player using the requested source."""
    if source == "api":
        row, err = fargo_client.fetch_one_fargo_rating(name, org)
    elif source == "fairmatch":
        row, err = fargo_client.fetch_one_fargo_rating_fairmatch(name)
    else:
        row, err = fargo_client.fetch_one_fargo_rating(name, org)
        if not row and not err and fargo_client.USE_FAIRMATCH_SCRAPE:
            row, err = fargo_client.fetch_one_fargo_rating_fairmatch(name)

    return {
        "player_name": name,
        "org": org,
        "source": source,
        "result": row,
        "error": err,
    }


def main() -> int:
    """CLI entrypoint for single-player Fargo lookup."""
    parser = argparse.ArgumentParser(description="Lookup a single Fargo rating.")
    parser.add_argument("--name", default="Debbie Teichert", help="Player name to look up")
    parser.add_argument("--org", default="WPBA", help="Org code (e.g., WPBA, WPA)")
    parser.add_argument(
        "--source",
        default="auto",
        choices=["auto", "api", "fairmatch"],
        help="Lookup source (default: auto)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    if os.getenv("CHROME_PATH"):
        logger.info("CHROME_PATH=%s", os.getenv("CHROME_PATH"))

    result = _lookup_player(args.name, args.org, args.source)
    print(json.dumps(result, indent=2))

    if result.get("error"):
        logger.error("Lookup failed: %s", result["error"])
        return 1
    if not result.get("result"):
        logger.warning("No rating found for %s", args.name)
        return 2
    logger.info("Lookup succeeded for %s", args.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
