#!/usr/bin/env python3
"""Check what data exists in the rankings database."""

import sys
import os
from pathlib import Path

# Add Rankings-Bot to path
project_root = Path(__file__).parent / "Rankings-Bot"
sys.path.insert(0, str(project_root))

from database import get_database_manager
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def main():
    """Check database contents."""
    try:
        db_manager = get_database_manager()
        conn = db_manager.get_connection()
        cursor = conn.cursor()
        
        # Check which ranking systems have data
        logger.info("=== Ranking Systems in Database ===")
        cursor.execute("""
            SELECT ranking_system, COUNT(*) as player_count, MAX(snapshot_date) as latest_date
            FROM rankings
            GROUP BY ranking_system
            ORDER BY ranking_system
        """)
        
        systems = cursor.fetchall()
        if not systems:
            logger.info("❌ No data in rankings table!")
            logger.info("\nThe database is empty. You need to:")
            logger.info("1. Run scrapers to populate data: POST /api/rankings/refresh")
            logger.info("2. Or import rankings manually")
            conn.close()
            return
        
        for row in systems:
            logger.info(f"{row[0]:<15} {row[1]:>4} players  (latest: {row[2]})")
        
        # Show sample players from each system
        for row in systems:
            system = row[0]
            logger.info(f"\n=== Sample players from {system} ===")
            cursor.execute("""
                SELECT player_name, rank, points, country, license_number, fargo_rating
                FROM rankings
                WHERE ranking_system = ?
                  AND snapshot_date = (SELECT MAX(snapshot_date) FROM rankings WHERE ranking_system = ?)
                ORDER BY rank ASC
                LIMIT 5
            """, (system, system))
            
            players = cursor.fetchall()
            for p in players:
                name = p[0]
                rank = p[1]
                country = p[3] or 'NULL'
                license = p[4] or 'NULL'
                fargo = p[5] or 'NULL'
                logger.info(f"  #{rank:<3} {name:<30} Country: {country:<10} License: {license:<12} Fargo: {fargo}")
        
        # Check for potential name matches across systems
        logger.info("\n=== Checking for potential player matches ===")
        cursor.execute("""
            SELECT DISTINCT w1.player_name, w1.ranking_system, w2.ranking_system
            FROM rankings w1
            JOIN rankings w2 ON LOWER(TRIM(w1.player_name)) = LOWER(TRIM(w2.player_name))
            WHERE w1.ranking_system != w2.ranking_system
            LIMIT 10
        """)
        
        matches = cursor.fetchall()
        if matches:
            logger.info(f"Found {len(matches)} potential matches (showing first 10):")
            for m in matches:
                logger.info(f"  {m[0]} appears in both {m[1]} and {m[2]}")
        else:
            logger.info("❌ No players found in multiple systems")
            logger.info("This means WPBA and WPA player lists don't overlap.")
            logger.info("Enrichment will only work when the same player appears in both systems.")
        
        conn.close()
        
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
