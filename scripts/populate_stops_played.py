#!/usr/bin/env python3
"""
Populate stops_played column in rankings table.
Run inside API container: docker exec rankings-bot-api python scripts/populate_stops_played.py
Backup separately with: ./scripts/backup_postgres.sh

This script:
1. Analyzes tournament_results to count how many tournaments each player participated in
2. Updates the rankings table with stops_played counts
"""

import sys
from pathlib import Path
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor
import asyncio

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load database URL from environment or use default
import os
DB_URL = os.getenv('DATABASE_URL', 'postgresql://rankingsbot_user:change-me@rankings-bot-postgres:5432/rankingsbot')


def get_connection():
    """Get database connection."""
    return psycopg2.connect(DB_URL)


def analyze_current_state():
    """Analyze current state of stops_played."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    print("=" * 80)
    print("CURRENT STATE ANALYSIS")
    print("=" * 80)
    
    # Overall stats
    cur.execute("""
        SELECT 
            COUNT(*) as total_players,
            SUM(CASE WHEN stops_played > 0 THEN 1 ELSE 0 END) as with_stops,
            AVG(stops_played) as avg_stops,
            MAX(stops_played) as max_stops
        FROM rankings
    """)
    overall = cur.fetchone()
    print(f"\nOverall Rankings:")
    print(f"  Total Players: {overall['total_players']}")
    print(f"  With Stops > 0: {overall['with_stops']}")
    print(f"  Average Stops: {overall['avg_stops']:.2f}")
    print(f"  Max Stops: {overall['max_stops']}")
    
    # By ranking system
    cur.execute("""
        SELECT 
            ranking_system,
            COUNT(*) as players,
            SUM(CASE WHEN stops_played > 0 THEN 1 ELSE 0 END) as with_stops,
            AVG(stops_played) as avg_stops
        FROM rankings
        GROUP BY ranking_system
        ORDER BY ranking_system
    """)
    
    print("\nBy Ranking System:")
    for row in cur.fetchall():
        avg_display = f"{row['avg_stops']:.2f}" if row['avg_stops'] is not None else "0.00"
        print(f"  {row['ranking_system']:20} - {row['players']:4} players, "
              f"{row['with_stops']:4} with stops, avg: {avg_display}")
    
    # Check tournament data availability
    cur.execute("SELECT COUNT(*) as total FROM tournament_results")
    tr_count = cur.fetchone()['total']
    
    cur.execute("SELECT COUNT(DISTINCT tournament_id) as total FROM tournament_results")
    tourn_count = cur.fetchone()['total']
    
    cur.execute("SELECT COUNT(DISTINCT player_name) as total FROM tournament_results")
    player_count = cur.fetchone()['total']
    
    print(f"\nTournament Data Available:")
    print(f"  Total Results: {tr_count}")
    print(f"  Unique Tournaments: {tourn_count}")
    print(f"  Unique Players: {player_count}")
    
    conn.close()
    return overall['with_stops'] == 0


def calculate_stops_from_tournaments():
    """Calculate stops played from tournament_results."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    print("\n" + "=" * 80)
    print("CALCULATING STOPS FROM TOURNAMENT DATA")
    print("=" * 80)
    
    # Get stops per player from tournament_results
    cur.execute("""
        SELECT 
            player_name,
            COUNT(DISTINCT tournament_id) as stops_count
        FROM tournament_results
        GROUP BY player_name
        ORDER BY stops_count DESC
    """)
    
    stops_data = cur.fetchall()
    print(f"\nFound tournament participation data for {len(stops_data)} players")
    
    if stops_data:
        print("\nTop 10 players by tournament participation:")
        for i, row in enumerate(stops_data[:10], 1):
            print(f"  {i:2}. {row['player_name']:30} - {row['stops_count']:3} tournaments")
    
    conn.close()
    return stops_data


def update_stops_played(stops_data):
    """Update rankings table with calculated stops."""
    conn = get_connection()
    cur = conn.cursor()
    
    print("\n" + "=" * 80)
    print("UPDATING RANKINGS TABLE")
    print("=" * 80)
    
    updated_count = 0
    matched_count = 0
    
    for row in stops_data:
        player_name = row['player_name']
        stops_count = row['stops_count']
        
        # Update all ranking_systems for this player
        cur.execute("""
            UPDATE rankings
            SET stops_played = %s
            WHERE 
                LOWER(player_name) = LOWER(%s)
                AND snapshot_date = (SELECT MAX(snapshot_date) FROM rankings)
        """, (stops_count, player_name))
        
        rows_updated = cur.rowcount
        if rows_updated > 0:
            updated_count += rows_updated
            matched_count += 1
    
    conn.commit()

    print(f"\n✓ Updated {updated_count} ranking records")
    print(f"✓ Matched {matched_count} unique players")

    # Broadcast cache invalidation to update UI
    print("\nBroadcasting cache invalidation...")
    try:
        from api.notifications import broadcast_cache_invalidation
        asyncio.run(broadcast_cache_invalidation(
            "stops_data_population",
            {
                "records_updated": updated_count,
                "players_matched": matched_count,
                "enrichment_type": "stops_played_population"
            }
        ))
        print("✓ Cache invalidation broadcast sent")
    except Exception as e:
        print(f"⚠️  Cache invalidation failed: {e}")
    
    # Show summary after update
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN stops_played > 0 THEN 1 ELSE 0 END) as with_stops,
            AVG(stops_played) as avg_stops,
            MAX(stops_played) as max_stops
        FROM rankings
        WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM rankings)
    """)
    result = cur.fetchone()
    
    print(f"\nFinal Statistics (latest snapshot):")
    print(f"  Total Players: {result[0]}")
    print(f"  With Stops > 0: {result[1]}")
    print(f"  Average Stops: {result[2]:.2f}")
    print(f"  Max Stops: {result[3]}")
    
    conn.close()
    return updated_count


def create_backup():
    """Remind to run backup separately (Postgres is Docker-only, no host pg_dump)."""
    print("\n" + "=" * 80)
    print("BACKUP: Run ./scripts/backup_postgres.sh before/after (Docker exec)")
    print("=" * 80)
    return None


def list_backups():
    """List all existing backups."""
    backup_dir = Path("/home/ansible/rankings-bot/backups")
    
    print("\n" + "=" * 80)
    print("EXISTING BACKUPS")
    print("=" * 80)
    
    if not backup_dir.exists():
        print("No backup directory found")
        return []
    
    backups = sorted(backup_dir.glob("rankings_*.sql"), key=lambda p: p.stat().st_mtime, reverse=True)
    
    if not backups:
        print("No backups found")
        return []
    
    print(f"\nFound {len(backups)} backup(s):\n")
    
    for i, backup in enumerate(backups, 1):
        stat = backup.stat()
        size_mb = stat.st_size / 1024 / 1024
        mtime = datetime.fromtimestamp(stat.st_mtime)
        print(f"{i:2}. {backup.name:50} | {size_mb:7.2f} MB | {mtime.strftime('%Y-%m-%d %H:%M:%S')}")
    
    return backups


def main():
    """Main execution."""
    print("\n" + "=" * 80)
    print("POPULATE STOPS_PLAYED COLUMN")
    print("=" * 80)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Step 1: Analyze current state
    needs_update = analyze_current_state()
    
    # Step 2: Create pre-update backup
    print("\n--- Creating PRE-UPDATE backup ---")
    pre_backup = create_backup()
    
    # Step 3: Calculate stops from tournament data
    stops_data = calculate_stops_from_tournaments()
    
    if not stops_data:
        print("\n⚠ No tournament data found. Cannot calculate stops.")
        print("  Run tournament scrapers first to populate tournament_results table.")
        return 1
    
    # Step 4: Update rankings table
    # Auto-proceed if needs_update or if --force flag provided
    if needs_update or "--force" in sys.argv:
        updated = update_stops_played(stops_data)
        
        # Step 5: Create post-update backup
        print("\n--- Creating POST-UPDATE backup ---")
        post_backup = create_backup()
        
        print("\n" + "=" * 80)
        print("✓ STOPS_PLAYED UPDATE COMPLETE")
        print("=" * 80)
        print(f"  Records Updated: {updated}")
        print(f"  Pre-update Backup: {pre_backup}")
        print(f"  Post-update Backup: {post_backup}")
    else:
        print("\n✗ Update cancelled by user")
    
    # Step 6: List all backups
    list_backups()
    
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n✗ Interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n✗ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
