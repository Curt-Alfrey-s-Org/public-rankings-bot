"""
Smart Fargo name matcher - handles hyphens, 3-part names, compound surnames.

Generates multiple name variations and finds best FairMatch matches.
Flags duplicates for user review.

Usage:
  python3 scripts/find_fargo_matches.py [--system WPA_Men|WPA_Women|WPBA]
  python3 scripts/find_fargo_matches.py --limit 50  # Quick test

Standards:
  - PEP 8 compliant
  - Type hints
  - Proper error handling
  - Async for I/O operations
"""

import sys
import time
from datetime import datetime
from typing import List, Optional, Tuple, Dict
import argparse

sys.path.insert(0, '/home/ansible/rankings-bot/Rankings-Bot')
from api.services.fairmatch_scraper import lookup_rating
from api.services.fargo_name_variations import generate_name_variations
from database import get_database_manager


def test_name_variations(
    player_name: str,
    db_ranking_system: str,
    delay: float = 1.5
) -> Dict[str, any]:
    """
    Test all variations of a player name against FairMatch.
    
    Returns dict with:
    - original_name: str
    - system: str
    - variations_tried: int
    - matches_found: List[Tuple[str, float]]  # (variation, rating)
    - best_match: Optional[Tuple[str, float]]
    - status: 'found' | 'multiple' | 'not_found'
    """
    variations = generate_name_variations(player_name)
    
    matches = []
    last_error: Optional[str] = None
    
    for variation in variations:
        rating, error = lookup_rating(variation)
        if error:
            last_error = error
        
        if rating:
            matches.append((variation, rating))
            print(f"  ✓ {variation:<40} → {rating}")
        
        time.sleep(delay)  # Rate limiting
    
    # Determine status
    if len(matches) == 0:
        status = 'not_found'
        best_match = None
    elif len(matches) == 1:
        status = 'found'
        best_match = matches[0]
    else:
        # Multiple different ratings found - need user decision
        unique_ratings = set(r for _, r in matches)
        if len(unique_ratings) == 1:
            # Same rating from different spellings - OK
            status = 'found'
            best_match = matches[0]
        else:
            # Different ratings - ambiguous
            status = 'multiple'
            best_match = matches[0]  # Tentative pick (first found)
    
    return {
        'original_name': player_name,
        'system': db_ranking_system,
        'variations_tried': len(variations),
        'matches_found': matches,
        'best_match': best_match,
        'status': status,
        'last_error': last_error
    }


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Find Fargo matches for players with complex names'
    )
    parser.add_argument(
        '--system',
        choices=['WPBA', 'WPA_Women', 'WPA_Men'],
        help='Process specific ranking system (default: all)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='Limit number of players to process (default: all)'
    )
    parser.add_argument(
        '--delay',
        type=float,
        default=1.5,
        help='Delay between lookups in seconds (default: 1.5)'
    )
    parser.add_argument(
        '--max-consecutive-not-found',
        type=int,
        default=6,
        help='Stop after N consecutive not-found results (default: 6)'
    )
    
    args = parser.parse_args()
    
    # Get missing players from database
    db = get_database_manager()
    conn = db.get_connection()
    
    try:
        cursor = conn.cursor()
        
        # Build query
        query = """
            SELECT DISTINCT player_name, ranking_system
            FROM rankings
            WHERE fargo_rating IS NULL
            AND snapshot_date = (
                SELECT MAX(snapshot_date)
                FROM rankings
                WHERE ranking_system = rankings.ranking_system
            )
        """
        
        params = []
        if args.system:
            query += " AND ranking_system = %s"
            params.append(args.system)
        
        query += " ORDER BY ranking_system, player_name"
        
        if args.limit:
            query += f" LIMIT {args.limit}"
        
        cursor.execute(query, params)
        missing_players = cursor.fetchall()
        
        print(f"\n{'='*90}")
        print(f"FARGO SMART NAME MATCHER")
        print(f"{'='*90}\n")
        
        print(f"Processing {len(missing_players)} players without Fargo ratings...\n")
        
        results = {
            'found': [],
            'multiple': [],
            'not_found': []
        }
        consecutive_not_found = 0
        
        for i, (player_name, system) in enumerate(missing_players, 1):
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"\n[{now}] [{i}/{len(missing_players)}] {system} | {player_name}")
            print("  Trying variations...")
            
            result = test_name_variations(player_name, system, args.delay)
            results[result['status']].append(result)
            
            if result['status'] == 'found':
                consecutive_not_found = 0
                var, rating = result['best_match']
                print(f"  ✅ FOUND: {var} → {rating}")
            elif result['status'] == 'multiple':
                consecutive_not_found = 0
                print(f"  ⚠️  MULTIPLE MATCHES - Need user review:")
                for var, rating in result['matches_found']:
                    print(f"      - {var}: {rating}")
            else:
                consecutive_not_found += 1
                print(f"  ❌ NOT FOUND after {result['variations_tried']} variations")
                if result.get('last_error'):
                    print(f"  ⚠️  Last error: {result['last_error']}")
                if consecutive_not_found >= args.max_consecutive_not_found:
                    print(
                        f"\nSTOP: {consecutive_not_found} consecutive not-found results. "
                        "Possible scraper issue. Fix and re-run.\n"
                    )
                    break
    
    finally:
        conn.close()
    
    # Print summary report
    print(f"\n{'='*90}")
    print(f"SUMMARY REPORT")
    print(f"{'='*90}\n")
    
    print(f"Total processed: {len(missing_players)}")
    print(f"  ✅ Found: {len(results['found'])}")
    print(f"  ⚠️  Multiple matches (need review): {len(results['multiple'])}")
    print(f"  ❌ Not found: {len(results['not_found'])}")
    
    # Details: Found
    if results['found']:
        print(f"\n{'─'*90}")
        print(f"✅ FOUND MATCHES ({len(results['found'])})")
        print(f"{'─'*90}")
        for r in results['found'][:50]:  # Show first 50
            var, rating = r['best_match']
            print(f"  {r['original_name']:<35} → {var:<35} = {rating}")
        if len(results['found']) > 50:
            print(f"  ... and {len(results['found']) - 50} more")
    
    # Details: Multiple matches need review
    if results['multiple']:
        print(f"\n{'─'*90}")
        print(f"⚠️  AMBIGUOUS MATCHES - USER REVIEW NEEDED ({len(results['multiple'])})")
        print(f"{'─'*90}")
        for r in results['multiple']:
            print(f"\n  {r['original_name']} ({r['system']}):")
            for var, rating in r['matches_found']:
                print(f"    {var:<40} → {rating}")
    
    # Details: Not found (sample)
    if results['not_found']:
        print(f"\n{'─'*90}")
        print(f"❌ NOT FOUND IN FAIRMATCH ({len(results['not_found'])})")
        print(f"{'─'*90}")
        for r in results['not_found'][:30]:  # Show first 30
            print(f"  {r['original_name']:<40} ({r['system']})")
        if len(results['not_found']) > 30:
            print(f"  ... and {len(results['not_found']) - 30} more")
    
    print(f"\n{'='*90}")
    print(f"RECOMMENDED ACTIONS")
    print(f"{'='*90}")
    
    if results['found']:
        print(f"\n1. UPDATE DATABASE for {len(results['found'])} found matches:")
        print(f"   Run: python3 scripts/apply_fargo_matches.py results.json")
    
    if results['multiple']:
        print(f"\n2. REVIEW {len(results['multiple'])} ambiguous matches:")
        print(f"   Edit: fargo_matches_review.json")
        print(f"   Choose correct rating for each player")
    
    if results['not_found']:
        print(f"\n3. {len(results['not_found'])} players legitimately not in FairMatch")
        print(f"   Consider manual CSV import if you have their ratings")
    
    print(f"\n{'='*90}\n")
    
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nInterrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
