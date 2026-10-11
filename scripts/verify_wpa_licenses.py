#!/usr/bin/env python3
"""
WPA License Verification Script

Fetches player license data from wpapool.com/rankings
and verifies against our database
"""

import requests
import json
import logging
from pathlib import Path
from datetime import datetime
import re

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

class WPALicenseVerifier:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        })
        self.output_dir = Path('data/wpa_verification')
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def fetch_wpa_rankings(self):
        """Fetch WPA rankings from wpapool.com"""
        logger.info("Fetching WPA rankings from wpapool.com...")
        
        try:
            # Try women's rankings
            response = self.session.get(
                'https://www.wpapool.com/rankings',
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info(f"✓ Successfully fetched WPA rankings page ({len(response.text)} bytes)")
                return response.text
            else:
                logger.warning(f"HTTP {response.status_code} from wpapool.com")
                return None
        
        except Exception as e:
            logger.error(f"Error fetching WPA rankings: {e}")
            return None
    
    def extract_wpa_players(self, html):
        """Extract player names and potential license info from HTML"""
        players = []
        
        if not html:
            return players
        
        # Look for player names with rank and license patterns
        # Typical formats:
        # 1. PlayerName | License# | Points | Country
        # 2. Rank. PlayerName (License#)
        # 3. PlayerName - License#
        
        patterns = [
            # Pattern: Name with WPA number like WPA - 123
            r'([A-Z][a-zA-Z\s\-\.\']+)\s+WPA\s*[-:]?\s*(\d{1,4})',
            # Pattern: Name with number in parentheses (common ranking format)
            r'([A-Z][a-zA-Z\s\-\.\']+)\s*\((\d{1,4})\)',
            # Pattern: Simple player name line
            r'<td[^>]*>([A-Z][a-zA-Z\s\-\.\']{2,49})</td>',
        ]
        
        for pattern in patterns:
            for match in re.finditer(pattern, html, re.IGNORECASE):
                try:
                    if len(match.groups()) >= 2:
                        player_name = match.group(1).strip()
                        license_num = match.group(2).strip()
                    else:
                        player_name = match.group(1).strip()
                        license_num = ''
                    
                    if player_name and len(player_name) > 2 and len(player_name) < 50:
                        players.append({
                            'name': player_name,
                            'license': license_num if len(license_num) <= 4 else '',
                            'source': 'wpapool.com'
                        })
                except Exception as e:
                    logger.debug("Could not parse WPA player regex match '%s': %s", match.group(0), e)
        
        # Remove duplicates
        seen = set()
        unique = []
        for p in players:
            key = p['name']
            if key not in seen:
                seen.add(key)
                unique.append(p)
        
        return unique
    
    def compare_with_database(self, wpa_players):
        """Compare WPA players with our database"""
        import psycopg2
        
        conn = psycopg2.connect(
            database='rankings',
            user='rankings',
            password='rankings',
            host='localhost'
        )
        cur = conn.cursor()
        
        logger.info(f"\nComparing {len(wpa_players)} WPA players with database...")
        
        # Get our current players
        cur.execute("""
            SELECT DISTINCT player_name, license_number 
            FROM rankings 
            WHERE ranking_system = 'WPBA_Women' OR ranking_system = 'WPA_Women'
            ORDER BY player_name
        """)
        
        our_players = {row[0]: row[1] for row in cur.fetchall()}
        
        # Compare
        matches = []
        no_license_in_wpa = []
        not_in_our_db = []
        license_mismatch = []
        
        for wpa_player in wpa_players:
            name = wpa_player['name']
            wpa_license = wpa_player['license']
            
            if name in our_players:
                our_license = our_players[name]
                
                if wpa_license:
                    if our_license and our_license != wpa_license:
                        license_mismatch.append({
                            'name': name,
                            'wpa_license': wpa_license,
                            'our_license': our_license
                        })
                    elif not our_license:
                        matches.append({
                            'name': name,
                            'license': wpa_license,
                            'action': 'ADD'
                        })
                    else:
                        matches.append({
                            'name': name,
                            'license': wpa_license,
                            'action': 'MATCH'
                        })
                else:
                    no_license_in_wpa.append(name)
            else:
                if wpa_license:
                    not_in_our_db.append({
                        'name': name,
                        'license': wpa_license
                    })
        
        cur.close()
        conn.close()
        
        # Report results
        print("\n" + "=" * 70)
        print("WPA License Verification Report")
        print("=" * 70)
        
        print(f"\n✅ Matching Players (WPA license matches our DB):")
        print(f"   Count: {len(matches)}")
        for m in matches[:10]:
            action = " (ADD)" if m['action'] == 'ADD' else ""
            print(f"   • {m['name']:40} → WPA {m['license']}{action}")
        if len(matches) > 10:
            print(f"   ... and {len(matches) - 10} more")
        
        print(f"\n⚠️  License Mismatches (Different licenses for same player):")
        print(f"   Count: {len(license_mismatch)}")
        for m in license_mismatch[:10]:
            print(f"   • {m['name']:40}")
            print(f"     WPA says: {m['wpa_license']:40}")
            print(f"     We have:  {m['our_license']:40}")
        
        print(f"\n❓ Players in WPA but not in our DB:")
        print(f"   Count: {len(not_in_our_db)}")
        for p in not_in_our_db[:10]:
            print(f"   • {p['name']:40} → WPA {p['license']}")
        if len(not_in_our_db) > 10:
            print(f"   ... and {len(not_in_our_db) - 10} more")
        
        print(f"\n📋 Players in WPA without license shown:")
        print(f"   Count: {len(no_license_in_wpa)}")
        for name in no_license_in_wpa[:10]:
            print(f"   • {name}")
        
        return {
            'matches': matches,
            'mismatches': license_mismatch,
            'not_in_db': not_in_our_db,
            'no_license_in_wpa': no_license_in_wpa
        }
    
    def save_results(self, html_content, verification_results):
        """Save raw HTML and verification results"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Save HTML
        if html_content:
            html_file = self.output_dir / f"wpa_rankings_{timestamp}.html"
            with open(html_file, 'w') as f:
                f.write(html_content)
            logger.info(f"\n📄 HTML saved: {html_file}")
        
        # Save verification results
        json_file = self.output_dir / f"wpa_verification_{timestamp}.json"
        with open(json_file, 'w') as f:
            json.dump(verification_results, f, indent=2)
        logger.info(f"📊 Results saved: {json_file}")
    
    def run(self):
        """Run verification"""
        logger.info("=" * 70)
        logger.info("WPA License Verification")
        logger.info("=" * 70)
        
        # Fetch WPA data
        html = self.fetch_wpa_rankings()
        
        if not html:
            logger.error("Could not fetch WPA rankings")
            return
        
        # Extract players
        logger.info("\nExtracting player data from HTML...")
        players = self.extract_wpa_players(html)
        logger.info(f"✓ Extracted {len(players)} players from WPA")
        
        # Compare with database
        results = self.compare_with_database(players)
        
        # Save results
        self.save_results(html, results)
        
        logger.info("\n" + "=" * 70)
        logger.info("Verification Complete")
        logger.info("=" * 70)

if __name__ == '__main__':
    verifier = WPALicenseVerifier()
    verifier.run()
