#!/usr/bin/env python3
"""
License Lookup Strategy Based on Country & Organization Correlation

Key Finding: License types correlate strongly with player country:
- BCA (57 players): Primarily US/Canadian players
- EPBF (14 players): European players  
- ACBS (10 players): Asian/Pacific players

Strategy: Use country data to guide license lookup
"""

import psycopg2
import logging
from collections import defaultdict

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

class LicenseCorrelationAnalysis:
    def __init__(self):
        self.conn = psycopg2.connect(
            database='rankings',
            user='rankings',
            password='rankings',
            host='localhost'
        )
    
    def analyze_license_country_correlation(self):
        """Analyze which licenses go with which countries."""
        cur = self.conn.cursor()
        
        print("\n" + "=" * 70)
        print("🌍 License-Country Correlation Analysis")
        print("=" * 70)
        
        # Get license-to-country mapping
        cur.execute("""
            SELECT 
                SUBSTRING(license_number FROM 1 FOR 4) as license_org,
                country,
                COUNT(DISTINCT player_name) as player_count
            FROM rankings 
            WHERE ranking_system = 'WPBA_Women' 
            AND license_number IS NOT NULL AND license_number != ''
            AND country IS NOT NULL AND country != ''
            GROUP BY license_org, country
            ORDER BY license_org, player_count DESC;
        """)
        
        correlations = defaultdict(lambda: defaultdict(int))
        
        for license_org, country, count in cur.fetchall():
            correlations[license_org][country] = count
        
        # Display findings
        for license_org in sorted(correlations.keys()):
            print(f"\n{license_org} License Countries:")
            countries = correlations[license_org]
            for country in sorted(countries, key=lambda x: countries[x], reverse=True):
                pct = countries[country] / sum(countries.values()) * 100
                print(f"  {country:20} → {countries[country]:2} players ({pct:5.1f}%)")
        
        # Now show players WITHOUT license but WITH country
        print("\n" + "=" * 70)
        print("🔍 Players WITHOUT License Grouped by Country")
        print("=" * 70)
        
        cur.execute("""
            SELECT 
                country,
                COUNT(DISTINCT player_name) as count
            FROM rankings 
            WHERE ranking_system = 'WPBA_Women' 
            AND (license_number IS NULL OR license_number = '')
            AND country IS NOT NULL AND country != ''
            GROUP BY country
            ORDER BY count DESC;
        """)
        
        country_gaps = []
        for country, count in cur.fetchall():
            country_gaps.append((country, count))
        
        for country, count in country_gaps:
            print(f"  {country:20} → {count:2} players need licenses")
        
        # Provide targeted search recommendations
        print("\n" + "=" * 70)
        print("🎯 Targeted Search Strategy")
        print("=" * 70)
        
        for country, count in country_gaps:
            likely_org = self._guess_license_org(country)
            print(f"\n{country} ({count} players):")
            print(f"  → Likely License Type: {likely_org}")
            print(f"  → Search: {likely_org} {country} women pool")
            print(f"  → Fallback: WPBA {country} players")
        
        cur.close()
    
    def _guess_license_org(self, country):
        """Guess license organization based on country."""
        # Map countries to likely license organizations
        usa_codes = {'USA', 'United States', 'US'}
        can_codes = {'CAN', 'Canada', 'CDN'}
        eu_codes = {'GBR', 'Great Britain', 'UK', 'FRA', 'France', 'GER', 'Germany', 'SWE', 'Sweden', 
                   'NED', 'Netherlands', 'BEL', 'Belgium', 'ESP', 'Spain', 'ITA', 'Italy', 'NOR', 'Norway'}
        asia_codes = {'TPE', 'Taiwan', 'CHN', 'China', 'JPN', 'Japan', 'KOR', 'Korea', 'THA', 'Thailand', 
                     'MYS', 'Malaysia', 'SGP', 'Singapore', 'INA', 'Indonesia', 'PHL', 'Philippines'}
        
        if country in usa_codes:
            return "BCA (American)"
        elif country in can_codes:
            return "BCA (Canadian)"
        elif country in eu_codes:
            return "EPBF (European)"
        elif country in asia_codes:
            return "ACBS (Asian)"
        else:
            return "Unknown - Research needed"
    
    def get_targeted_search_list(self):
        """Generate list of players to search by country."""
        cur = self.conn.cursor()
        
        print("\n" + "=" * 70)
        print("📝 Targeted Search Lists by Organization")
        print("=" * 70)
        
        # Get players grouped by likely license org
        cur.execute("""
            SELECT DISTINCT player_name, country
            FROM rankings 
            WHERE ranking_system = 'WPBA_Women' 
            AND (license_number IS NULL OR license_number = '')
            AND country IS NOT NULL AND country != ''
            ORDER BY country, player_name;
        """)
        
        players_by_org = defaultdict(list)
        
        for player_name, country in cur.fetchall():
            org = self._guess_license_org(country)
            players_by_org[org].append((player_name, country))
        
        # Generate search lists
        for org in sorted(players_by_org.keys()):
            players = players_by_org[org]
            print(f"\n{org}")
            print("-" * 70)
            print(f"Total players: {len(players)}\n")
            for player_name, country in players[:10]:  # First 10
                print(f"  • {player_name:30} ({country})")
            if len(players) > 10:
                print(f"\n  ... and {len(players) - 10} more")
        
        cur.close()
    
    def run(self):
        """Run full analysis."""
        self.analyze_license_country_correlation()
        self.get_targeted_search_list()
        self.conn.close()

if __name__ == '__main__':
    analysis = LicenseCorrelationAnalysis()
    analysis.run()
