#!/usr/bin/env python3
"""Quick script to check which players are in the database"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://rankingsbot_user:PASSWORD@rankings-bot-postgres:5432/rankingsbot")
engine = create_engine(DATABASE_URL)

# Get Debbie and Allison
with engine.connect() as conn:
    result = conn.execute(text("""
        SELECT player_name FROM rankings 
        WHERE player_name ILIKE :pattern1 OR player_name ILIKE :pattern2 
        ORDER BY rank LIMIT 30
    """), {"pattern1": "%debbie%", "pattern2": "%allison%"})
    
    print("Found players:")
    for row in result:
        print(f"  - {row[0]}")
    
    # Get total count
    result = conn.execute(text("SELECT COUNT(*) FROM rankings"))
    total = result.fetchone()[0]
    print(f"\nTotal players in database: {total}")
    
    # Get top 20 players
    result = conn.execute(text("SELECT player_name, rank FROM rankings ORDER BY rank LIMIT 20"))
    print("\nTop 20 players:")
    for row in result:
        print(f"  {row[1]}. {row[0]}")
