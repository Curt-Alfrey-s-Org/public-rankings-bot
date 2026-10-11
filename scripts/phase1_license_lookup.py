#!/usr/bin/env python3
"""
Phase 1 License Enrichment: Extract licenses from multiple sources

Sources:
1. FargoRate database (by player name)
2. BCA online lookup (by player name)
3. Tournament brackets (embedded license info)
4. ExternalPool player profiles
"""

import requests
import json
import logging
import time
from pathlib import Path
from datetime import datetime
import re

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

class LicenseLookup:
    def __init__(self, output_dir='data/license_data'):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        })
        
        self.results = {}
    
    def lookup_fargorating(self, player_name):
        """Look up player on FargoRate database."""
        try:
            # FargoRate API search
            response = self.session.get(
                f'https://www.fargorating.com/api/players',
                params={'name': player_name},
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Extract player info
                if isinstance(data, list) and len(data) > 0:
                    player = data[0]  # First match
                    
                    # Look for license info in profile
                    license_info = {
                        'source': 'FargoRate',
                        'player_id': player.get('id'),
                        'fargo_rating': player.get('rating'),
                        'country': player.get('country'),
                    }
                    
                    # Check if license number is exposed
                    if 'license' in player:
                        license_info['license_number'] = player['license']
                    if 'bca_number' in player:
                        license_info['bca_number'] = player['bca_number']
                    if 'ipa_number' in player:
                        license_info['ipa_number'] = player['ipa_number']
                    
                    return license_info
        
        except Exception as e:
            logger.debug(f"FargoRate lookup failed for {player_name}: {e}")
        
        return None
    
    def lookup_bca_online(self, player_name):
        """Attempt to look up BCA license via BCA website."""
        try:
            # BCA member search (if available)
            response = self.session.get(
                'https://www.bca-pool.com/search',
                params={'player': player_name},
                timeout=5
            )
            
            if response.status_code == 200:
                # Would need to parse HTML for license number
                # For now, just return that we found a match
                if player_name.lower() in response.text.lower():
                    return {
                        'source': 'BCA',
                        'found_on_bca': True,
                        'note': 'Player found on BCA but license number requires parsing'
                    }
        
        except Exception as e:
            logger.debug(f"BCA lookup failed for {player_name}: {e}")
        
        return None
    
    def extract_from_tournament_brackets(self):
        """Extract license numbers from tournament bracket data."""
        results = {}
        
        # Read archived tournament data
        archive_dir = Path('data/externalpool_archive')
        if not archive_dir.exists():
            logger.warning("No tournament archive found")
            return results
        
        # Pattern: Look for license numbers in tournament data
        # Common formats: "BCA - 123", "EPBF - 456", license numbers often 3-4 digits
        
        license_pattern = r'(?:BCA|EPBF|IPA|PBA|APA)[\s\-]*(\d{1,4})'
        
        for json_file in archive_dir.glob('*.json'):
            try:
                with open(json_file) as f:
                    data = json.load(f)
                
                # Search through all text data
                content = json.dumps(data)
                
                # Look for player + license patterns
                # Pattern: PlayerName ... (BCA - 123)
                player_license_pattern = r'([A-Z][a-zA-Z\s\-\.\']+)\s*[,\(]?\s*(?:BCA|EPBF|IPA|PBA|APA)[\s\-]*(\d{1,4})'
                
                for match in re.finditer(player_license_pattern, content):
                    player_name = match.group(1).strip()
                    license_type = 'BCA'  # Default
                    license_num = match.group(2)
                    
                    if player_name and license_num:
                        results[player_name] = f"{license_type} - {license_num}"
            
            except Exception as e:
                logger.debug(f"Error parsing {json_file}: {e}")
        
        return results
    
    def run_phase1(self):
        """Execute Phase 1: Quick wins from multiple sources."""
        logger.info("=" * 70)
        logger.info("Phase 1: License Extraction from Multiple Sources")
        logger.info("=" * 70)
        
        all_results = {}
        
        # Get WPBA player list from database
        try:
            import psycopg2
            
            conn = psycopg2.connect(
                database='rankings',
                user='rankings',
                password='rankings',
                host='localhost'
            )
            cur = conn.cursor()
            
            # Get players without licenses
            cur.execute("""
                SELECT DISTINCT player_name 
                FROM rankings 
                WHERE ranking_system = 'WPBA_Women' 
                AND (license_number IS NULL OR license_number = '')
                ORDER BY player_name
            """)
            
            players_to_research = [row[0] for row in cur.fetchall()]
            cur.close()
            conn.close()
            
            logger.info(f"\nResearching {len(players_to_research)} players without licenses...")
            
            # Try FargoRate (fastest, most comprehensive)
            logger.info("\n1️⃣  Checking FargoRate database...")
            fargo_matches = 0
            
            for i, player_name in enumerate(players_to_research):
                if i % 10 == 0:
                    logger.info(f"   Progress: {i}/{len(players_to_research)}")
                
                result = self.lookup_fargorating(player_name)
                if result:
                    all_results[player_name] = result
                    fargo_matches += 1
                
                time.sleep(0.2)  # Rate limit
            
            logger.info(f"   ✓ FargoRate found license info for {fargo_matches} players")
            
            # Extract from tournament brackets (no API calls needed)
            logger.info("\n2️⃣  Extracting from tournament brackets...")
            bracket_results = self.extract_from_tournament_brackets()
            logger.info(f"   ✓ Found license info in {len(bracket_results)} tournament records")
            
            # Merge results
            for player, license_data in bracket_results.items():
                if player not in all_results:
                    all_results[player] = {
                        'source': 'Tournament Brackets',
                        'license_number': license_data
                    }
        
        except Exception as e:
            logger.error(f"Error in Phase 1: {e}")
        
        # Save results
        self._save_results(all_results)
        
        logger.info("\n" + "=" * 70)
        logger.info(f"Phase 1 Complete: Found {len(all_results)} potential license matches")
        logger.info("=" * 70)
        
        return all_results
    
    def _save_results(self, results):
        """Save results to JSON."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        output = {
            'timestamp': datetime.now().isoformat(),
            'source': 'Multi-source license lookup',
            'matches_found': len(results),
            'results': results,
        }
        
        filename = self.output_dir / f"phase1_licenses_{timestamp}.json"
        with open(filename, 'w') as f:
            json.dump(output, f, indent=2)
        
        logger.info(f"\n📁 Results saved to: {filename}")
        
        # Also save as CSV for easy review
        csv_file = self.output_dir / f"phase1_licenses_{timestamp}.csv"
        with open(csv_file, 'w') as f:
            f.write("player_name,source,license_number,notes\n")
            for player_name, data in results.items():
                source = data.get('source', 'Unknown')
                license_num = data.get('license_number', '')
                f.write(f'"{player_name}","{source}","{license_num}",""\n')
        
        logger.info(f"📄 CSV saved to: {csv_file}")

if __name__ == '__main__':
    lookup = LicenseLookup()
    results = lookup.run_phase1()
