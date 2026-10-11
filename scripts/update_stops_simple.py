#!/usr/bin/env python3
"""Simple stops_played updater - no backups, just the update."""
import os
import psycopg2
import sys

try:
    conn = psycopg2.connect(os.getenv("DATABASE_URL", "postgresql://rankingsbot_user:PASSWORD@rankings-bot-postgres:5432/rankingsbot"))
    cur = conn.cursor()
    
    # Check current state
    cur.execute("""
        SELECT COUNT(*) as total, 
               SUM(CASE WHEN stops_played > 0 THEN 1 ELSE 0 END) as with_stops
        FROM rankings WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM rankings)
    """)
    total, with_stops = cur.fetchone()
    print(f"Before: {total} players, {with_stops} with stops > 0")
    
    # Update stops_played from tournament_results
    cur.execute("""
        WITH player_stops AS (
            SELECT player_name, COUNT(DISTINCT tournament_id) as stop_count
            FROM tournament_results
            GROUP BY player_name
        )
        UPDATE rankings r
        SET stops_played = ps.stop_count
        FROM player_stops ps
        WHERE LOWER(r.player_name) = LOWER(ps.player_name)
          AND r.snapshot_date = (SELECT MAX(snapshot_date) FROM rankings)
    """)
    
    updated = cur.rowcount
    conn.commit()
    
    # Check final state
    cur.execute("""
        SELECT COUNT(*) as total,
               SUM(CASE WHEN stops_played > 0 THEN 1 ELSE 0 END) as with_stops,
               ROUND(AVG(stops_played), 2) as avg_stops,
               MAX(stops_played) as max_stops
        FROM rankings WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM rankings)
    """)
    total, with_stops, avg_stops, max_stops = cur.fetchone()
    
    print(f"Updated {updated} records")
    print(f"After: {total} players, {with_stops} with stops > 0")
    print(f"Average: {avg_stops}, Max: {max_stops}")
    
    # Show by ranking system
    cur.execute("""
        SELECT ranking_system, 
               COUNT(*) as total,
               SUM(CASE WHEN stops_played > 0 THEN 1 ELSE 0 END) as with_stops
        FROM rankings
        WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM rankings)
        GROUP BY ranking_system ORDER BY ranking_system
    """)
    
    print("\nBy ranking system:")
    for system, total, with_s in cur.fetchall():
        print(f"  {system}: {with_s}/{total} with stops")
    
    conn.close()
    print("\n✓ Update complete")
    
except Exception as e:
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)
