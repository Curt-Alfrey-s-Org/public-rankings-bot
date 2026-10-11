#!/usr/bin/env python3
"""
Enhanced Fargo Rating Enrichment from Backup Data and Historical Patterns

This script recovers missing Fargo ratings by:
1. Using historical name matching patterns from archived enrichment mergers
2. Cross-referencing with backup data containing known Fargo scores
3. Applying intelligent matching with nickname expansion and fuzzy logic
4. Updating the current enrichment merger with improved patterns

Combines the reliability of archived FairMatch scraper patterns with modern fuzzy matching.

Usage:
    python3 scripts/enrich_fargo_from_backup.py              # Dry run
    python3 scripts/enrich_fargo_from_backup.py --execute   # Actually update database
    python3 scripts/enrich_fargo_from_backup.py --system WPA_Men  # Specific system
"""

import argparse
import logging
import sys
import os
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set
from difflib import SequenceMatcher

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s - %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)

# Historical name matching patterns from archived FairMatch scraper
def generate_historical_name_variants(name: str) -> List[str]:
    """
    Generate name variants using historical FairMatch scraper patterns.

    Historical patterns:
    - "Last, First" → ["First Last", "Last, First"]
    - "First Last" → ["First Last", "Last First", "Last, First"]
    """
    variants = []
    name = name.strip()

    if "," in name:
        # Format: "Last, First"
        comma_parts = name.split(",", 1)
        if len(comma_parts) == 2:
            last_name = comma_parts[0].strip()
            first_name = comma_parts[1].strip()
            variants.append(f"{first_name} {last_name}")  # "First Last"
            variants.append(name)  # Original "Last, First"
    else:
        # Standard format "First Last" or space-separated
        variants.append(name)  # Original
        parts = name.split()
        if len(parts) >= 2:
            # Reverse: "Last First" or "Last, First"
            variants.append(" ".join(reversed(parts)))
            variants.append(", ".join(reversed(parts)))

    return list(set(variants))  # Remove duplicates

# Enhanced nickname map combining historical and modern patterns
ENHANCED_NICKNAME_MAP: Dict[str, List[str]] = {
    # From current system
    "alex": ["alexander", "alexandra", "alexis"],
    "jos": ["joseph", "josiah"],
    "bob": ["robert"],
    "bill": ["william"],
    "liz": ["elizabeth"],
    "sue": ["susan", "susanne"],
    "jim": ["james", "jimmy"],
    "rich": ["richard"],
    "tom": ["thomas", "tommy"],
    "dan": ["daniel"],
    "ben": ["benjamin"],
    "ed": ["edward"],
    "fred": ["frederick", "alfred"],
    "mike": ["michael"],
    "nick": ["nicholas"],
    "andy": ["andrew"],
    "dave": ["david"],
    "sam": ["samuel"],
    "frank": ["francis", "franklin"],
    "joe": ["joseph", "joel"],
    "pat": ["patrick", "patricia"],
    "steve": ["stephen", "steven"],
    "chris": ["christopher", "christine"],
    "phil": ["philip", "phillip"],
    "mark": ["marcus"],
    "john": ["jonathan"],
    "luke": ["lukas", "lucas"],
    "max": ["maxwell"],
    "ann": ["anne", "anna"],

    # Additional patterns from historical data analysis
    "mike": ["mickey", "mick"],
    "rick": ["richard", "ricky"],
    "bobby": ["robert"],
    "billy": ["william"],
    "sammy": ["samuel"],
    "jimmie": ["james"],
    "danny": ["daniel"],
    "bennie": ["benjamin"],
    "eddie": ["edward"],
    "freddie": ["frederick"],
    "mickey": ["michael"],
    "nikki": ["nicholas"],
    "andy": ["andrea"],
    "danny": ["dana"],
    "sandy": ["sandra", "alexander"],
    "mandy": ["amanda"],
    "cindy": ["cynthia"],
    "linda": ["melinda"],
    "randy": ["randall"],
}

def normalize_name(name: str) -> str:
    """Normalize name: trim, collapse internal whitespace."""
    if not name or not isinstance(name, str):
        return ""
    return " ".join(name.split()).strip()

def parse_name(name: str) -> Tuple[str, str]:
    """
    Parse name to (first, last) in lowercase.
    Handles: "First Last" or "Last, First" formats.
    """
    if not name:
        return "", ""

    s = normalize_name(name)
    if "," in s:
        # "Last, First" format
        parts = s.split(",", 1)
        last = parts[0].strip().lower()
        first = parts[1].strip().lower() if len(parts) > 1 else ""
    else:
        # "First Last" format
        parts = s.rsplit(" ", 1)
        if len(parts) == 2:
            first = parts[0].strip().lower()
            last = parts[1].strip().lower()
        else:
            first = ""
            last = parts[0].strip().lower() if parts else ""

    return first, last

def canonical_form(name: str) -> str:
    """
    Canonical form for cross-format matching: lowercase "firstname lastname".
    Converts "Last, First" → "first last" for matching.
    """
    first, last = parse_name(name)
    return f"{first} {last}".strip()

def enhanced_names_match(name1: str, name2: str, threshold: float = 0.85) -> bool:
    """
    Enhanced name matching combining historical patterns with fuzzy logic.

    Uses:
    1. Historical name variant generation
    2. Nickname expansion
    3. Canonical form matching
    4. Fuzzy string similarity
    """
    if not name1 or not name2:
        return False

    name1 = normalize_name(name1)
    name2 = normalize_name(name2)

    # Exact match (case-insensitive)
    if name1.lower() == name2.lower():
        return True

    # Generate historical variants for both names
    variants1 = generate_historical_name_variants(name1)
    variants2 = generate_historical_name_variants(name2)

    # Check if any variant combinations match
    for v1 in variants1:
        for v2 in variants2:
            if v1.lower() == v2.lower():
                return True

    # Parse both names
    first1, last1 = parse_name(name1)
    first2, last2 = parse_name(name2)

    # Last names must match closely
    if last1 and last2:
        last_sim = SequenceMatcher(None, last1, last2).ratio()
        if last_sim < 0.9:
            return False

        # First names: check nickname mappings first
        f1_nicknames = ENHANCED_NICKNAME_MAP.get(first1, [first1])
        f2_nicknames = ENHANCED_NICKNAME_MAP.get(first2, [first2])

        # Check if names are in each other's nickname lists
        if first1 in f2_nicknames or first2 in f1_nicknames:
            return True

        # Check if nickname lists overlap
        if set(f1_nicknames) & set(f2_nicknames):
            return True

        # Otherwise check similarity threshold
        first_sim = SequenceMatcher(None, first1, first2).ratio()
        return first_sim >= threshold

    return False

def load_backup_fargo_data() -> Dict[str, float]:
    """
    Load Fargo rating data from backup sources.

    Returns dict mapping canonical player names to Fargo ratings.
    """
    fargo_data = {}

    # Load from recent import data
    import_file = PROJECT_ROOT / "data" / "fargo_import_20260301_1748.json"
    if import_file.exists():
        try:
            with open(import_file, 'r') as f:
                data = json.load(f)
                for player in data.get('players', []):
                    name = player.get('name', '').strip()
                    rating = player.get('fargo_rating')
                    if name and rating and rating > 0:
                        canonical = canonical_form(name)
                        if canonical:
                            fargo_data[canonical] = float(rating)
            logger.info(f"Loaded {len(fargo_data)} Fargo ratings from recent import")
        except Exception as e:
            logger.warning(f"Could not load recent import data: {e}")

    return fargo_data

def get_players_missing_fargo(db) -> List[Tuple[str, str, str]]:
    """
    Get players missing Fargo ratings.

    Returns: [(player_name, ranking_system, license_number), ...]
    """
    conn = db.get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT DISTINCT r.player_name, r.ranking_system, r.license_number
        FROM rankings r
        WHERE r.fargo_rating IS NULL
          AND r.snapshot_date = (SELECT MAX(snapshot_date) FROM rankings)
          AND r.player_name IS NOT NULL
          AND trim(r.player_name) != ''
        ORDER BY r.player_name
    """)

    results = cursor.fetchall()
    conn.close()

    return [(row[0], row[1], row[2] or '') for row in results]

def find_fargo_matches(player_name: str, fargo_data: Dict[str, float]) -> List[Tuple[str, float]]:
    """
    Find potential Fargo rating matches for a player using enhanced matching.

    Returns: [(matched_name, fargo_rating), ...] sorted by confidence
    """
    matches = []

    # Generate all possible name variants for this player
    variants = generate_historical_name_variants(player_name)

    # Check each variant against known Fargo data
    checked_canonicals = set()

    for variant in variants:
        canonical_variant = canonical_form(variant)

        # Skip if we already checked this canonical form
        if canonical_variant in checked_canonicals:
            continue
        checked_canonicals.add(canonical_variant)

        # Direct canonical match
        if canonical_variant in fargo_data:
            matches.append((canonical_variant, fargo_data[canonical_variant]))
            continue

        # Fuzzy match against all known names
        for known_name, rating in fargo_data.items():
            if enhanced_names_match(variant, known_name):
                matches.append((known_name, rating))

    # Remove duplicates, keeping highest rating for each matched name
    unique_matches = {}
    for name, rating in matches:
        if name not in unique_matches or rating > unique_matches[name]:
            unique_matches[name] = rating

    return list(unique_matches.items())

def update_fargo_rating(db, player_name: str, fargo_rating: float, source_name: str, dry_run: bool = True) -> int:
    """Update Fargo rating for all records of a player."""
    if dry_run:
        logger.info(f"DRY RUN: Would update {player_name} with Fargo {fargo_rating} (matched: {source_name})")
        return 1

    conn = db.get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE rankings
        SET fargo_rating = %s,
            fargo_source_name = %s,
            fargo_last_updated = CURRENT_TIMESTAMP
        WHERE player_name = %s
          AND (fargo_rating IS NULL OR fargo_rating = 0)
    """, (fargo_rating, source_name, player_name))

    updated = cursor.rowcount
    conn.commit()
    conn.close()

    return updated

def main():
    parser = argparse.ArgumentParser(description="Enhanced Fargo rating enrichment from backup data")
    parser.add_argument("--execute", action="store_true", help="Apply updates (default: dry run)")
    parser.add_argument("--system", type=str, help="Limit to specific ranking system (e.g., WPA_Men)")
    parser.add_argument("--max-matches", type=int, default=50, help="Maximum players to process (default: 50)")
    args = parser.parse_args()

    try:
        from database import get_database_manager
        db = get_database_manager()
    except ImportError:
        logger.error("Could not import database manager")
        return 1

    # Load backup Fargo data
    logger.info("Loading Fargo rating data from backup sources...")
    fargo_data = load_backup_fargo_data()

    if not fargo_data:
        logger.error("No Fargo data found in backup sources")
        return 1

    # Get players missing Fargo ratings
    logger.info("Finding players missing Fargo ratings...")
    missing_players = get_players_missing_fargo(db)

    if args.system:
        missing_players = [p for p in missing_players if p[1] == args.system]
        logger.info(f"Filtered to {len(missing_players)} players in system {args.system}")

    if not missing_players:
        logger.info("No players missing Fargo ratings!")
        return 0

    # Limit for testing
    if args.max_matches and len(missing_players) > args.max_matches:
        missing_players = missing_players[:args.max_matches]
        logger.info(f"Limited to first {args.max_matches} players for testing")

    logger.info(f"Processing {len(missing_players)} players missing Fargo ratings...")

    total_processed = 0
    total_updated = 0
    total_matches_found = 0

    for player_name, system, license in missing_players:
        matches = find_fargo_matches(player_name, fargo_data)

        if matches:
            # Take the best match (highest rating)
            best_match = max(matches, key=lambda x: x[1])
            matched_name, fargo_rating = best_match

            logger.info(f"✓ {player_name} ({system}) -> Fargo {fargo_rating} (matched: {matched_name})")

            updated = update_fargo_rating(db, player_name, fargo_rating, matched_name, dry_run=not args.execute)
            total_updated += updated
            total_matches_found += 1
        else:
            logger.debug(f"✗ {player_name} ({system}) - No matches found")

        total_processed += 1

        # Progress update
        if total_processed % 10 == 0:
            logger.info(f"Progress: {total_processed}/{len(missing_players)} processed, {total_matches_found} matches found")

    # Summary
    logger.info("=" * 60)
    logger.info("ENHANCED FARGO ENRICHMENT COMPLETE")
    logger.info("=" * 60)
    logger.info(f"Players processed: {total_processed}")
    logger.info(f"Matches found: {total_matches_found}")
    if args.execute:
        logger.info(f"Database records updated: {total_updated}")
    else:
        logger.info("DRY RUN - Use --execute to apply updates")
    logger.info(".1f")

    return 0

if __name__ == "__main__":
    raise SystemExit(main())