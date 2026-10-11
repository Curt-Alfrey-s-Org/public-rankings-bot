#!/usr/bin/env python3
"""
Enrich WPBA player data using tournament participation and web sources.

Strategy:
1. Use tournament data (per_tournament_rankings.json) to link WPBA to WPA players
2. Match players by name and tournament participation
3. For remaining matches, fallback to web scraping (FargoRate, WPBA site)
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set
from difflib import SequenceMatcher

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import get_database_manager, engine
from scrapers.fetch_utils import get_with_retry
import psycopg2

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TournamentDataEnricher:
    """Enrich player data using tournament participation records."""
    
    def __init__(self):
        self.data_file = Path(__file__).parent.parent / 'data' / 'per_tournament_rankings.json'
        self.db_mgr = get_database_manager()
        
    def load_tournament_data(self) -> Dict:
        """Load tournament rankings data."""
        if not self.data_file.exists():
            logger.warning(f"Tournament data file not found: {self.data_file}")
            return {}
        
        with open(self.data_file, 'r') as f:
            return json.load(f)
    
    def name_similarity(self, name1: str, name2: str, threshold: float = 0.8) -> bool:
        """Check if two names are similar enough."""
        # Normalize to lowercase
        n1 = name1.lower().strip()
        n2 = name2.lower().strip()
        
        # Handle "Lastname, Firstname" vs "Firstname Lastname" format
        if ',' in n1 or ',' in n2:
            # Convert to "firstname lastname" format
            if ',' in n1:
                parts = n1.split(',', 1)
                n1 = f"{parts[1].strip()} {parts[0].strip()}".strip()
            if ',' in n2:
                parts = n2.split(',', 1)
                n2 = f"{parts[1].strip()} {parts[0].strip()}".strip()
        
        # Check similarity
        ratio = SequenceMatcher(None, n1, n2).ratio()
        return ratio >= threshold
    
    def enrich_from_tournament_data(self) -> Dict:
        """
        Use tournament data to match WPBA players with WPA players.
        
        Returns:
            Dict with enrichment statistics
        """
        logger.info("Loading tournament data...")
        tournament_data = self.load_tournament_data()
        
        if not tournament_data:
            return {"error": "No tournament data found"}
        
        # Extract WPA player country mappings
        wpa_women_players = tournament_data.get('wpa_women', {}).get('players', [])
        wpa_men_players = tournament_data.get('wpa_men', {}).get('players', [])
        
        wpa_players = {}
        for p in wpa_women_players + wpa_men_players:
            if isinstance(p, dict):
                name = p.get('name', '').strip()
                if name:
                    wpa_players[name] = {
                        'country': p.get('country'),
                        'tournaments': list(p.get('tournament_points', {}).keys()) or []
                    }
        
        logger.info(f"Loaded {len(wpa_players)} WPA players with tournament history")
        
        # Get WPBA players from DB
        conn = psycopg2.connect(os.getenv("DATABASE_URL", "postgresql://rankingsbot_user:PASSWORD@rankings-bot-postgres:5432/rankingsbot"))
        cur = conn.cursor()
        
        cur.execute("""
            SELECT DISTINCT player_name 
            FROM rankings 
            WHERE ranking_system = 'WPBA_Women'
            AND country IS NULL OR country = ''
        """)
        
        wpba_players = [row[0] for row in cur.fetchall()]
        logger.info(f"Found {len(wpba_players)} WPBA women players without country")
        
        # Try to match
        matched = 0
        updated = 0
        
        for wpba_name in wpba_players:
            # Find best match in WPA
            best_match = None
            best_score = 0
            
            for wpa_name in wpa_players.keys():
                if self.name_similarity(wpba_name, wpa_name, threshold=0.75):
                    score = SequenceMatcher(None, wpba_name.lower(), wpa_name.lower()).ratio()
                    if score > best_score:
                        best_score = score
                        best_match = wpa_name
            
            if best_match and wpa_players[best_match].get('country'):
                matched += 1
                country = wpa_players[best_match]['country']
                
                # Update DB
                cur.execute(
                    "UPDATE rankings SET country = %s WHERE player_name = %s AND ranking_system = 'WPBA_Women' AND (country IS NULL OR country = '')",
                    (country, wpba_name)
                )
                updated += 1
                logger.debug(f"Enriched {wpba_name} with country {country} (matched to {best_match})")
        
        conn.commit()
        
        # Summary
        cur.execute("""
            SELECT COUNT(*), COUNT(country) 
            FROM rankings 
            WHERE ranking_system = 'WPBA_Women'
        """)
        total, with_country = cur.fetchone()
        
        cur.close()
        conn.close()
        
        logger.info(f"Enrichment complete:")
        logger.info(f"  - Matched: {matched}")
        logger.info(f"  - Updated: {updated}")
        logger.info(f"  - WPBA Women with country: {with_country}/{total} ({with_country*100//total if total else 0}%)")
        
        return {
            "matched": matched,
            "updated": updated,
            "total_wpba": total,
            "with_country": with_country,
            "coverage_pct": with_country*100//total if total else 0
        }

def main():
    """Run enrichment."""
    enricher = TournamentDataEnricher()
    result = enricher.enrich_from_tournament_data()
    
    logger.info("")
    logger.info("=" * 60)
    logger.info("ENRICHMENT RESULT")
    logger.info("=" * 60)
    for key, value in result.items():
        logger.info(f"{key:20} : {value}")

if __name__ == '__main__':
    main()
