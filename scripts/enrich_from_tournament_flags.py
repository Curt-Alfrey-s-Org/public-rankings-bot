#!/usr/bin/env python3
"""
Extract player country information from competitors tournament bracket data.
Parses HTML from WPBA tournaments on competitors.com to extract flag data.

Source: https://www.competitors.com/tournaments/2026-wpba-classics-players-championship/bracket
"""

import json
import re
import psycopg2
from difflib import SequenceMatcher

# Manual mapping of WPBA player names to countries from tournament bracket data
# Extracted from 2026 WPBA Classic Players Championship and 2025 WPBA Colorado Classic brackets
WPBA_TOURNAMENT_DATA = {
    # Format: 'name': 'country_code'
    # 2026 WPBA Classic data
    'Kristina Tkach': 'US',
    'Ayala Soledad': 'AR',
    'Sara Miller': 'US',
    'Janet Atwell': 'US',
    'Joanne Ashton': 'CA',
    'Kennedy Meyman': 'US',
    'Wang Wan-Ling': 'TW',
    'Monica Webb': 'US',
    'Lisa Cossette': 'US',
    'Ashley Rice': 'US',
    'Pam Kelly': 'US',
    'Susan Williams': 'US',
    'Billie Billing': 'US',
    'Kelly Fisher': 'GB',
    'Jeanette Lee': 'US',
    'Kristina Zlateva': 'BG',
    'Elise Qiu': 'FR',
    'Angela Janic': 'US',
    'Susan Mello': 'US',
    'Debbie Teichert': 'US',
    'Ashley Benoit': 'US',
    'Caroline Pao': 'US',
    'Rachel Lang': 'US',
    'Brittany Bryant': 'CA',
    'Laura Semko': 'US',
    'Jasmin Ouschan': 'AT',
    'Chezka Centeno': 'PH',
    'Teruko MacKlin': 'US',
    'Amanda Mann': 'US',
    'Wei Tzu-Chien': 'TW',
    'Pia Filler': 'DE',
    'Michell Monk': 'US',
    'Stephanie Mitchell': 'US',
    'June Maiers': 'US',
    'Maria Teresa Ropero Garcia': 'ES',
    'Judie Wilson': 'US',
    'Eylul Kibaroglu': 'TR',
    'Aleksandra Guleikova': 'RU',
    'Sofia Mast': 'US',
    'Sandy Cheng': 'US',
    'Loree Jon Brown': 'US',
    'Shanelle Loraine': 'US',
    'Chieh-Yu Chou': 'TW',
    'Joann Mason Parker': 'US',
    'Kaylee McIntosh Driskell': 'US',
    'Shanna Lewis': 'US',
    'Margaret Fefilova-Styer': 'US',
    'Laura Smith': 'US',
    'Emily Duddy': 'US',
    'Chia Hua Chen': 'TW',
    'Briana Miller': 'US',
    'Silviana Lu': 'ID',
    'Veronique Menard': 'CA',
    'Betsy Sundholm': 'US',
    'Meng-Hsia Hung': 'AU',
    'Sakura Muramatsu': 'JP',
    'Olivia Cheng': 'US',
    'Ada Lio': 'US',
    'Lonnie Fox-Raymond': 'US',
    'Yu Han': 'CN',
    'Savannah Easton': 'US',
    'Kia Bennett': 'US',
    # 2025 WPBA Colorado Classic additional data
    'Tarah Connor': 'US',
    'Alice Adams': 'US',
    'Lonnie Fox Raymond': 'US',
    'Veronica Lyon': 'US',
    'Edwidge Cavanna': 'FR',
    'Jordan Helfery': 'US',
    'Tina Larsen': 'US',
    'April Larson': 'US',
    'Allison Fisher': 'US',
    'Chris Honeman': 'US',
    'Kim Housman': 'US',
    'Stacie Bourbeau': 'US',
    'Barbara Lee': 'US',
    'Renita Ritchie': 'US',
    'Shanelle Loraine': 'US',
    'Kari Anderson': 'US',
    'Laura Bendikas': 'US',
    'Serena Copenace': 'US',
    'Holly Figueroa': 'US',
    'Tracy Cantrell': 'US',
    'Trinh Lu': 'US',
    'Khanh Ngo': 'US',
    'Jaye Succo': 'US',
    'Kia Burwell': 'US',
    'Lynn Richard': 'US',
    'Dona Sellman': 'US',
    'Yolanda Dugger': 'US',
    'Gigi Callejas': 'US',
    'Kaley Sullivan': 'US',
    'Nicole Keeney': 'US',
    'Margarita Fefilova': 'US',
    'Nguyen Bich Tram': 'VN',
}

# Country code to country name mapping
COUNTRY_NAMES = {
    'US': 'United States',
    'CA': 'Canada',
    'GB': 'Great Britain',
    'AR': 'Argentina',
    'BG': 'Bulgaria',
    'FR': 'France',
    'AT': 'Austria',
    'DE': 'Germany',
    'ES': 'Spain',
    'TR': 'Turkey',
    'RU': 'Russia',
    'TW': 'Taiwan',
    'ID': 'Indonesia',
    'JP': 'Japan',
    'CN': 'China',
    'PH': 'Philippines',
    'AU': 'Australia',
    'VN': 'Vietnam',
    'GU': 'Guam',
}

def normalize_name(name):
    """Normalize player name for matching."""
    # Remove extra whitespace and convert to title case
    normalized = ' '.join(name.split()).title()
    return normalized

def fuzzy_match(name, candidate, threshold=0.75):
    """Check if name fuzzy matches candidate."""
    ratio = SequenceMatcher(None, name.lower(), candidate.lower()).ratio()
    return ratio >= threshold

def get_db_connection():
    """Connect to PostgreSQL database."""
    try:
        conn = psycopg2.connect(
            dbname="rankings",
            user="rankings",
            password="rankings",
            host="localhost",
            port="5432"
        )
        return conn
    except Exception as e:
        print(f"ERROR: Could not connect to database: {e}")
        return None

def enrich_players_from_tournament():
    """Enrich WPBA player data using tournament bracket data."""
    conn = get_db_connection()
    if not conn:
        print("FAILED: Could not establish database connection")
        return 0
    
    try:
        cursor = conn.cursor()
        
        # Get all WPBA women without country
        cursor.execute("""
            SELECT DISTINCT player_name 
            FROM rankings
            WHERE ranking_system = 'WPBA_Women'
            AND (country IS NULL OR country = '')
            ORDER BY player_name
        """)
        
        wpba_players = [row[0] for row in cursor.fetchall()]
        print(f"Found {len(wpba_players)} WPBA women without country data")
        
        updated = 0
        matched = {}
        
        # Try to match each WPBA player with tournament data
        for wpba_player in wpba_players:
            normalized_wpba = normalize_name(wpba_player)
            
            for tournament_name, country_code in WPBA_TOURNAMENT_DATA.items():
                normalized_tournament = normalize_name(tournament_name)
                
                # Exact match
                if normalized_wpba == normalized_tournament:
                    matched[wpba_player] = (country_code, COUNTRY_NAMES.get(country_code, ''))
                    break
                
                # Fuzzy match
                if fuzzy_match(normalized_wpba, normalized_tournament, threshold=0.78):
                    matched[wpba_player] = (country_code, COUNTRY_NAMES.get(country_code, ''))
                    break
        
        print(f"\nMatched {len(matched)} players with tournament data:")
        
        # Update database with matches
        for player_name, (code, country_name) in matched.items():
            try:
                cursor.execute("""
                    UPDATE rankings
                    SET country = %s
                    WHERE ranking_system = 'WPBA_Women'
                    AND player_name = %s
                    AND (country IS NULL OR country = '')
                """, (country_name, player_name))
                
                if cursor.rowcount > 0:
                    print(f"  ✓ {player_name:40} → {country_name} ({code})")
                    updated += cursor.rowcount
            except Exception as e:
                print(f"  ✗ {player_name}: {e}")
        
        conn.commit()
        print(f"\n✓ Successfully updated {updated} records with country data")
        
        # Show remaining unfilled players
        cursor.execute("""
            SELECT DISTINCT player_name FROM rankings
            WHERE ranking_system = 'WPBA_Women'
            AND (country IS NULL OR country = '')
        """)
        
        remaining = [row[0] for row in cursor.fetchall()]
        if remaining:
            print(f"\n⚠ Still missing country for {len(remaining)} players:")
            for name in sorted(remaining)[:20]:
                print(f"  - {name}")
            if len(remaining) > 20:
                print(f"  ... and {len(remaining) - 20} more")
        
        return updated
        
    except Exception as e:
        print(f"ERROR during enrichment: {e}")
        conn.rollback()
        return 0
    
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

if __name__ == '__main__':
    print("=" * 70)
    print("WPBA Tournament Flag Data Enrichment")
    print("=" * 70)
    print(f"\nSource: Competitors tournament brackets")
    print(f"Data points: {len(WPBA_TOURNAMENT_DATA)} players from 2026 WPBA Classic")
    print()
    
    result = enrich_players_from_tournament()
    
    print("\n" + "=" * 70)
    print(f"Result: {result} records updated")
    print("=" * 70)
