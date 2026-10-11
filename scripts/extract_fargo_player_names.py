#!/usr/bin/env python3
"""
Extract unique Fargo player names from archives and deduplicate across associations.

Queries fargo_rating_history and player_name_aliases tables to get all unique
player names, then uses name normalization to deduplicate players who appear
in multiple associations (WPBA_Women, WPA_Women, WPA_Men).

Outputs JSON or CSV with player names and their associations.
"""

import argparse
import json
import csv
import sys
from typing import Dict, Set, List
from database import get_database_manager
from api.services.fargo_client import normalized_match_key, canonical_form

# Main associations we care about
MAIN_ASSOCIATIONS = {"WPBA_Women", "WPA_Women", "WPA_Men"}


def extract_fargo_players(conn) -> Dict[str, Dict]:
    """
    Extract unique players from Fargo archives, deduplicated by normalized name key.
    
    Returns:
        Dict mapping normalized_key -> {
            'name': str (canonical name),
            'associations': set of association strings,
            'all_names': set of all name variants found
        }
    """
    player_map: Dict[str, Dict] = {}
    
    # Query fargo_rating_history for distinct player names by ranking_system
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT player_name, ranking_system
        FROM fargo_rating_history
        WHERE ranking_system IN ('WPBA_Women', 'WPA_Women', 'WPA_Men')
        AND player_name IS NOT NULL
        AND TRIM(player_name) != ''
        ORDER BY ranking_system, player_name
    """)
    
    for row in cur.fetchall():
        player_name = row[0].strip()
        ranking_system = row[1]
        
        if not player_name:
            continue
        
        # Use normalized key for deduplication
        key = normalized_match_key(player_name)
        if not key:
            continue
        
        if key not in player_map:
            player_map[key] = {
                'name': player_name,  # Use first name found as canonical
                'associations': set(),
                'all_names': set()
            }
        
        player_map[key]['associations'].add(ranking_system)
        player_map[key]['all_names'].add(player_name)
    
    # Also check player_name_aliases for additional names
    cur.execute("""
        SELECT DISTINCT canonical_name, ranking_system
        FROM player_name_aliases
        WHERE ranking_system IN ('WPBA_Women', 'WPA_Women', 'WPA_Men')
        AND canonical_name IS NOT NULL
        AND TRIM(canonical_name) != ''
    """)
    
    for row in cur.fetchall():
        canonical_name = row[0].strip()
        ranking_system = row[1]
        
        if not canonical_name:
            continue
        
        key = normalized_match_key(canonical_name)
        if not key:
            continue
        
        if key not in player_map:
            player_map[key] = {
                'name': canonical_name,
                'associations': set(),
                'all_names': set()
            }
        
        player_map[key]['associations'].add(ranking_system)
        player_map[key]['all_names'].add(canonical_name)
    
    return player_map


def export_json(player_map: Dict[str, Dict], output_file: str):
    """Export player data as JSON."""
    data = []
    for key, info in sorted(player_map.items(), key=lambda x: x[1]['name']):
        data.append({
            'normalized_key': key,
            'name': info['name'],
            'associations': sorted(list(info['associations'])),
            'all_names': sorted(list(info['all_names']))
        })
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"Exported {len(data)} unique players to {output_file}")


def export_csv(player_map: Dict[str, Dict], output_file: str):
    """Export player data as CSV."""
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['name', 'associations', 'all_names'])
        
        for key, info in sorted(player_map.items(), key=lambda x: x[1]['name']):
            associations_str = ', '.join(sorted(info['associations']))
            all_names_str = ', '.join(sorted(info['all_names']))
            writer.writerow([info['name'], associations_str, all_names_str])
    
    print(f"Exported {len(player_map)} unique players to {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description='Extract unique Fargo player names from archives'
    )
    parser.add_argument(
        '--output',
        '-o',
        default='fargo_players.json',
        help='Output file path (default: fargo_players.json)'
    )
    parser.add_argument(
        '--format',
        '-f',
        choices=['json', 'csv'],
        default='json',
        help='Output format (default: json)'
    )
    parser.add_argument(
        '--stats',
        action='store_true',
        help='Print statistics about extracted players'
    )
    
    args = parser.parse_args()
    
    # Get database connection
    db_manager = get_database_manager()
    conn = db_manager.get_connection()
    
    try:
        # Extract players
        print("Extracting Fargo player names from archives...")
        player_map = extract_fargo_players(conn)
        
        if args.stats:
            print(f"\nStatistics:")
            print(f"  Total unique players (deduplicated): {len(player_map)}")
            
            # Count by association
            assoc_counts = {}
            for info in player_map.values():
                for assoc in info['associations']:
                    assoc_counts[assoc] = assoc_counts.get(assoc, 0) + 1
            
            print(f"\n  Players by association:")
            for assoc in sorted(assoc_counts.keys()):
                print(f"    {assoc}: {assoc_counts[assoc]}")
            
            # Count players in multiple associations
            multi_assoc = sum(1 for info in player_map.values() if len(info['associations']) > 1)
            print(f"\n  Players in multiple associations: {multi_assoc}")
        
        # Export
        if args.format == 'json':
            export_json(player_map, args.output)
        else:
            export_csv(player_map, args.output)
        
        print(f"\nDone! Extracted {len(player_map)} unique players.")
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()


if __name__ == '__main__':
    main()
