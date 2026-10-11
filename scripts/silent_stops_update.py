#!/usr/bin/env python3
"""Silent stops update - no output, just does the work.
Run inside API container: docker exec rankings-bot-api python scripts/silent_stops_update.py
Backup separately with: ./scripts/backup_postgres.sh
"""
import psycopg2
from datetime import datetime
from pathlib import Path
import os
import sys

try:
    conn = psycopg2.connect(os.getenv("DATABASE_URL", "postgresql://rankingsbot_user:PASSWORD@postgres:5432/rankingsbot"))
    cur = conn.cursor()

    # Get tournament stops data
    cur.execute("""
        SELECT player_name, COUNT(DISTINCT tournament_id) as stops
        FROM tournament_results
        GROUP BY player_name
    """)
    stops_data = cur.fetchall()

    # Update rankings
    for player_name, stop_count in stops_data:
        cur.execute("""
            UPDATE rankings
            SET stops_played = %s
            WHERE LOWER(player_name) = LOWER(%s)
            AND snapshot_date = (SELECT MAX(snapshot_date) FROM rankings)
        """, (stop_count, player_name))

    conn.commit()
    conn.close()

    # Create success marker file
    Path("/tmp/stops_update_success").write_text(datetime.now().strftime("%Y%m%d_%H%M%S"))
    sys.exit(0)

except Exception as e:
    Path("/tmp/stops_update_error").write_text(str(e))
    sys.exit(1)
