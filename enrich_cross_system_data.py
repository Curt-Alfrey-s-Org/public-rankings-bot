#!/usr/bin/env python3
"""
Cross-System Data Enrichment

For players appearing in multiple ranking systems, fill missing data fields
(license_number, fargo_rating, country) from other systems where the player has that data.

Logic:
- If license_number is missing in one system but present in another for same player → copy it
- If fargo_rating is missing in one system but present in another → copy it (use highest if multiple)
- If country is missing in one system but present in another → copy it
- If data is missing across ALL systems for a player → leave NULL (frontend shows "No data")

Requires DATABASE_URL (same as API). Example:
  DATABASE_URL=postgresql://rankingsbot_user:PASSWORD@rankings-bot-postgres:5432/rankingsbot python3 enrich_cross_system_data.py
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
import argparse
from typing import Dict, List, Optional
import asyncio
import sys


def get_db_connection():
    """Connect to the rankings PostgreSQL database. Uses DATABASE_URL from env."""
    url = os.getenv("DATABASE_URL", "postgresql://rankingsbot_user:PASSWORD@rankings-bot-postgres:5432/rankingsbot").strip()
    return psycopg2.connect(url)


def get_cross_system_players(cursor) -> List[str]:
    """Get list of players appearing in multiple ranking systems."""
    cursor.execute("""
        SELECT DISTINCT player_name
        FROM rankings
        WHERE player_name IN (
            SELECT player_name
            FROM rankings
            GROUP BY player_name
            HAVING COUNT(DISTINCT ranking_system) > 1
        )
        ORDER BY player_name;
    """)
    return [row['player_name'] for row in cursor.fetchall()]


def get_player_data_across_systems(cursor, player_name: str) -> Dict:
    """Get all data for a player across all ranking systems."""
    cursor.execute("""
        SELECT 
            id,
            player_name,
            ranking_system,
            snapshot_date,
            license_number,
            fargo_rating,
            country,
            rank
        FROM rankings
        WHERE player_name = %s
        ORDER BY snapshot_date DESC, ranking_system;
    """, (player_name,))
    return cursor.fetchall()


def find_best_values(records: List[Dict]) -> Dict[str, Optional[str]]:
    """
    Find the best value for each field across all systems.
    
    Rules:
    - license_number: Use first non-null value
    - fargo_rating: Use highest non-null value (most up-to-date rating)
    - country: Use first non-null value
    """
    best_license = None
    best_fargo = None
    best_country = None
    
    for record in records:
        if record['license_number'] and not best_license:
            best_license = record['license_number']
        
        if record['fargo_rating']:
            if best_fargo is None or record['fargo_rating'] > best_fargo:
                best_fargo = record['fargo_rating']
        
        if record['country'] and not best_country:
            best_country = record['country']
    
    return {
        'license_number': best_license,
        'fargo_rating': best_fargo,
        'country': best_country
    }


def enrich_player_records(cursor, player_name: str, dry_run: bool = True, source_columns: Optional[set] = None) -> Dict:
    """
    Enrich all records for a player with data from other systems.
    
    Returns statistics about updates performed.
    """
    records = get_player_data_across_systems(cursor, player_name)
    
    if not records:
        return {'updated': 0, 'skipped': 0}
    
    best_values = find_best_values(records)
    
    updates_count = 0
    skipped_count = 0
    
    print(f"\n{'='*80}")
    print(f"Player: {player_name}")
    print(f"Best values found: License={best_values['license_number']}, "
          f"Fargo={best_values['fargo_rating']}, Country={best_values['country']}")
    print(f"{'='*80}")
    
    for record in records:
        updates = []
        update_fields = []
        
        # Check what needs updating
        if not record['license_number'] and best_values['license_number']:
            updates.append(f"license_number: NULL → {best_values['license_number']}")
            update_fields.append('license_number')
        
        if not record['fargo_rating'] and best_values['fargo_rating']:
            updates.append(f"fargo_rating: NULL → {best_values['fargo_rating']}")
            update_fields.append('fargo_rating')
        
        if not record['country'] and best_values['country']:
            updates.append(f"country: NULL → {best_values['country']}")
            update_fields.append('country')
        
        if updates:
            print(f"  [{record['ranking_system']}] {', '.join(updates)}")
            
            if not dry_run:
                # Build dynamic UPDATE query
                set_clauses = []
                params = []
                
                if 'license_number' in update_fields:
                    set_clauses.append("license_number = %s")
                    params.append(best_values['license_number'])
                    if source_columns and 'license_source' in source_columns:
                        set_clauses.append("license_source = %s")
                        params.append("cross_system")
                
                if 'fargo_rating' in update_fields:
                    set_clauses.append("fargo_rating = %s")
                    params.append(best_values['fargo_rating'])
                
                if 'country' in update_fields:
                    set_clauses.append("country = %s")
                    params.append(best_values['country'])
                    if source_columns and 'country_source' in source_columns:
                        set_clauses.append("country_source = %s")
                        params.append("cross_system")
                
                params.append(record['id'])
                
                update_query = f"""
                    UPDATE rankings
                    SET {', '.join(set_clauses)}
                    WHERE id = %s;
                """
                
                cursor.execute(update_query, params)
            
            updates_count += 1
        else:
            skipped_count += 1
    
    return {'updated': updates_count, 'skipped': skipped_count}


def main():
    parser = argparse.ArgumentParser(
        description='Enrich player data across ranking systems'
    )
    parser.add_argument(
        '--execute',
        action='store_true',
        help='Actually perform updates (default is dry-run)'
    )
    parser.add_argument(
        '--player',
        type=str,
        help='Process only a specific player (for testing)'
    )
    
    args = parser.parse_args()
    
    if not args.execute:
        print("\n" + "="*80)
        print("DRY RUN MODE - No changes will be made to the database")
        print("Use --execute to actually perform updates")
        print("="*80)
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = 'rankings' "
            "AND column_name IN ('country_source', 'license_source')"
        )
        source_columns = {row['column_name'] for row in cursor.fetchall()}
        
        # Get players to process
        if args.player:
            players = [args.player]
        else:
            players = get_cross_system_players(cursor)
        
        print(f"\nFound {len(players)} players appearing in multiple systems")
        
        total_updated = 0
        total_skipped = 0
        
        for player in players:
            stats = enrich_player_records(cursor, player, dry_run=not args.execute, source_columns=source_columns)
            total_updated += stats['updated']
            total_skipped += stats['skipped']
        
        if args.execute:
            conn.commit()
            print("\n" + "="*80)
            print("DATABASE UPDATED")
            print(f"Total records updated: {total_updated}")
            print(f"Total records skipped (no changes needed): {total_skipped}")
            print("="*80)
            
            print("\nRefreshing materialized view...")
            cursor.execute("REFRESH MATERIALIZED VIEW mv_latest_rankings;")
            conn.commit()
            print("✓ Materialized view refreshed")

            print("\nInvalidating API cache...")
            try:
                # Import and invalidate server-side cache
                import sys
                sys.path.insert(0, os.path.dirname(__file__))

                # Set a dummy JWT_SECRET if not set to allow cache invalidation
                if not os.getenv('JWT_SECRET'):
                    os.environ['JWT_SECRET'] = 'dummy-secret-for-cache-invalidation'

                from api.routes.rankings import _write_cache_version
                _write_cache_version()
                print("✓ API cache invalidated")
            except Exception as e:
                print(f"⚠️  API cache invalidation failed: {e}")

            print("\nBroadcasting cache invalidation...")
            try:
                # Import and run cache invalidation broadcast
                from api.notifications import broadcast_cache_invalidation

                # Run the async broadcast
                asyncio.run(broadcast_cache_invalidation(
                    "cross_system_enrichment",
                    {
                        "records_updated": total_updated,
                        "enrichment_type": "cross_system_data_merge"
                    }
                ))
                print("✓ Cache invalidation broadcast sent")
            except Exception as e:
                print(f"⚠️  Cache invalidation broadcast failed: {e}")
        else:
            print("\n" + "="*80)
            print("DRY RUN SUMMARY")
            print(f"Would update {total_updated} records")
            print(f"Would skip {total_skipped} records (no changes needed)")
            print("\nRun with --execute to apply these changes")
            print("="*80)
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        import sys
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
