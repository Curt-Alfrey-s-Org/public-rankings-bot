#!/usr/bin/env python3
"""Quick stops updater - writes results to file.
Run inside API container: docker exec rankings-bot-api python scripts/update_stops_quick.py
Backup separately with: ./scripts/backup_postgres.sh
"""
import psycopg2
from datetime import datetime
from pathlib import Path
import os

output = []
output.append("=" * 80)
output.append(f"STOPS_PLAYED UPDATE - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
output.append("=" * 80)

conn = psycopg2.connect(os.getenv("DATABASE_URL", "postgresql://rankingsbot_user:PASSWORD@postgres:5432/rankingsbot"))
cur = conn.cursor()

# Current state
cur.execute("SELECT COUNT(*), SUM(CASE WHEN stops_played > 0 THEN 1 ELSE 0 END), AVG(stops_played), MAX(stops_played) FROM rankings")
total, with_stops, avg, max_stops = cur.fetchone()
output.append(f"\nCURRENT STATE:")
output.append(f"  Total Players: {total}")
output.append(f"  With Stops > 0: {with_stops}")
output.append(f"  Average: {avg:.2f}")
output.append(f"  Max: {max_stops}")

# Get tournament stops data
cur.execute("""
    SELECT player_name, COUNT(DISTINCT tournament_id) as stops
    FROM tournament_results
    GROUP BY player_name
""")
stops_data = cur.fetchall()
output.append(f"\nTOURNAMENT DATA:")
output.append(f"  Players with tournament data: {len(stops_data)}")

if stops_data:
    # Show top 10
    top10 = sorted(stops_data, key=lambda x: x[1], reverse=True)[:10]
    output.append(f"\n  Top 10 by tournament participation:")
    for i, (name, stops) in enumerate(top10, 1):
        output.append(f"    {i:2}. {name:30} {stops:3} tournaments")

# Update rankings
output.append(f"\nUPDATING RANKINGS...")
update_count = 0
for player_name, stop_count in stops_data:
    cur.execute("""
        UPDATE rankings
        SET stops_played = %s
        WHERE LOWER(player_name) = LOWER(%s)
        AND snapshot_date = (SELECT MAX(snapshot_date) FROM rankings)
    """, (stop_count, player_name))
    update_count += cur.rowcount

conn.commit()
output.append(f"  ✓ Updated {update_count} records")

# Final state
cur.execute("""
    SELECT COUNT(*), SUM(CASE WHEN stops_played > 0 THEN 1 ELSE 0 END),
           AVG(stops_played), MAX(stops_played)
    FROM rankings
    WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM rankings)
""")
total, with_stops, avg, max_stops = cur.fetchone()
output.append(f"\nFINAL STATE:")
output.append(f"  Total Players: {total}")
output.append(f"  With Stops > 0: {with_stops} ({with_stops/total*100:.1f}%)")
output.append(f"  Average: {avg:.2f}")
output.append(f"  Max: {max_stops}")

# By system
cur.execute("""
    SELECT ranking_system, COUNT(*), 
           SUM(CASE WHEN stops_played > 0 THEN 1 ELSE 0 END),
           AVG(stops_played)
    FROM rankings
    WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM rankings)
    GROUP BY ranking_system
    ORDER BY ranking_system
""")
output.append(f"\nBY RANKING SYSTEM:")
for system, count, with_s, avg_s in cur.fetchall():
    output.append(f"  {system:20} - {count:4} players, {with_s:4} with stops, avg: {avg_s:.2f}")

output.append(f"\n" + "=" * 80)
output.append("✓ UPDATE COMPLETE")
output.append("=" * 80)

conn.close()

# Write to file
result_text = "\n".join(output)
Path("/tmp/stops_update_result.txt").write_text(result_text)
print(result_text)
