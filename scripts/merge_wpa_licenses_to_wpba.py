#!/usr/bin/env python3
"""
Merge WPA Licenses to WPBA Players

Matches WPBA players with WPA players by name (accounting for reversed name formats)
and copies license numbers from WPA to WPBA records where licenses are missing.
"""

import os
import sys
from pathlib import Path
import re
from difflib import SequenceMatcher

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import psycopg2
from database import engine


def normalize_name(name):
    """
    Normalize a name for comparison.
    - Remove extra spaces
    - Convert to lowercase
    - Remove special characters except hyphens and spaces
    """
    if not name:
        return ""
    
    # Remove content in parentheses (nicknames, aliases)
    name = re.sub(r'\([^)]*\)', '', name)
    
    # Remove commas
    name = name.replace(',', ' ')
    
    # Normalize spaces
    name = ' '.join(name.split())
    
    # Lowercase for comparison
    return name.lower().strip()


def get_name_variants(name):
    """
    Generate name variants for matching.
    Returns list of possible name formats:
    1. Original normalized
    2. Reversed (Last First -> First Last)
    3. First word + Last word (for multi-part names)
    """
    normalized = normalize_name(name)
    variants = [normalized]
    
    parts = normalized.split()
    if len(parts) >= 2:
        # Add reversed version
        reversed_name = ' '.join(parts[::-1])
        variants.append(reversed_name)
        
        # Add first + last (skip middle names)
        if len(parts) > 2:
            first_last = f"{parts[0]} {parts[-1]}"
            variants.append(first_last)
            # Also reversed
            variants.append(f"{parts[-1]} {parts[0]}")
    
    return list(set(variants))  # Remove duplicates


def similarity_score(name1, name2):
    """Calculate similarity score between two names (0.0 to 1.0)"""
    return SequenceMatcher(None, normalize_name(name1), normalize_name(name2)).ratio()


def find_best_match(wpba_name, wpa_names_dict, threshold=0.90):
    """
    Find the best matching WPA name for a WPBA name.
    
    Args:
        wpba_name: WPBA player name
        wpa_names_dict: Dict of {normalized_name: (original_name, license)}
        threshold: Minimum similarity score (0.90 = 90% match)
    
    Returns:
        (wpa_name, license, score) or None if no good match
    """
    wpba_variants = get_name_variants(wpba_name)
    
    best_match = None
    best_score = 0
    
    for wpba_variant in wpba_variants:
        for wpa_normalized, (wpa_original, license) in wpa_names_dict.items():
            score = similarity_score(wpba_variant, wpa_normalized)
            
            if score > best_score and score >= threshold:
                best_score = score
                best_match = (wpa_original, license, score)
    
    return best_match


def merge_licenses():
    """Main function to merge licenses from WPA to WPBA"""
    
    conn = psycopg2.connect(os.getenv('DATABASE_URL', 'postgresql://rankingsbot_user:PASSWORD@rankings-bot-postgres:5432/rankingsbot'))
    cur = conn.cursor()
    
    print("=" * 80)
    print("WPA License → WPBA Merge Utility")
    print("=" * 80)
    
    # Get WPBA players without licenses
    cur.execute("""
        SELECT id, player_name, rank
        FROM rankings
        WHERE ranking_system = 'WPBA_Women' AND license_number IS NULL
        ORDER BY rank
    """)
    wpba_players = cur.fetchall()
    print(f"\n✓ Found {len(wpba_players)} WPBA players without licenses")
    
    # Get WPA Women players with licenses
    cur.execute("""
        SELECT DISTINCT ON (player_name, license_number)
            player_name, license_number
        FROM rankings
        WHERE ranking_system = 'WPA_Women' AND license_number IS NOT NULL
        ORDER BY player_name, license_number, rank
    """)
    wpa_data = cur.fetchall()
    print(f"✓ Found {len(wpa_data)} WPA Women players with licenses")
    
    # Also get WPA Men players (some women might be in men's rankings)
    cur.execute("""
        SELECT DISTINCT ON (player_name, license_number)
            player_name, license_number
        FROM rankings
        WHERE ranking_system = 'WPA_Men' AND license_number IS NOT NULL
        ORDER BY player_name, license_number, rank
    """)
    wpa_men_data = cur.fetchall()
    print(f"✓ Found {len(wpa_men_data)} WPA Men players with licenses")
    
    # Combine WPA data and create lookup dict
    all_wpa_data = wpa_data + wpa_men_data
    wpa_lookup = {}
    for wpa_name, license in all_wpa_data:
        normalized = normalize_name(wpa_name)
        # Store all variants
        for variant in get_name_variants(wpa_name):
            if variant not in wpa_lookup:
                wpa_lookup[variant] = (wpa_name, license)
    
    print(f"✓ Created lookup with {len(wpa_lookup)} name variants\n")
    
    # Match and update
    matches = []
    no_matches = []
    
    print("Matching players...\n")
    print(f"{'Rank':<6} {'WPBA Name':<30} {'WPA Name':<30} {'License':<15} {'Score':<6}")
    print("-" * 90)
    
    for wpba_id, wpba_name, rank in wpba_players:
        match = find_best_match(wpba_name, wpa_lookup, threshold=0.90)
        
        if match:
            wpa_name, license, score = match
            matches.append((wpba_id, wpba_name, wpa_name, license, score))
            print(f"{rank:<6} {wpba_name:<30} {wpa_name:<30} {license:<15} {score:.2%}")
        else:
            no_matches.append((wpba_id, wpba_name, rank))
    
    print("\n" + "=" * 80)
    print(f"Matching Summary:")
    print(f"  Matched: {len(matches)}")
    print(f"  No match: {len(no_matches)}")
    print("=" * 80)
    
    if no_matches:
        print(f"\nPlayers without matches (top 20):")
        for wpba_id, wpba_name, rank in no_matches[:20]:
            print(f"  Rank {rank:<4} {wpba_name}")
    
    # Ask for confirmation
    if matches:
        print(f"\n⚠️  Ready to update {len(matches)} WPBA player records with WPA licenses")
        response = input("Proceed with update? (yes/no): ").strip().lower()
        
        if response == 'yes':
            updated = 0
            for wpba_id, wpba_name, wpa_name, license, score in matches:
                try:
                    cur.execute("""
                        UPDATE rankings
                        SET license_number = %s,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """, (license, wpba_id))
                    updated += 1
                except Exception as e:
                    print(f"  ❌ Error updating {wpba_name}: {e}")
            
            conn.commit()
            print(f"\n✓ Updated {updated} WPBA player records with WPA licenses")
            
            # Show updated statistics
            cur.execute("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(CASE WHEN license_number IS NOT NULL THEN 1 END) as with_license,
                    ROUND(100.0 * COUNT(CASE WHEN license_number IS NOT NULL THEN 1 END) / COUNT(*), 1) as pct
                FROM rankings
                WHERE ranking_system = 'WPBA_Women'
            """)
            total, with_license, pct = cur.fetchone()
            print(f"\n✓ WPBA License Coverage: {with_license}/{total} ({pct}%)")
            
        else:
            print("\n❌ Update cancelled")
    
    conn.close()
    print("\n✓ Complete\n")


if __name__ == '__main__':
    try:
        merge_licenses()
    except KeyboardInterrupt:
        print("\n\n❌ Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
