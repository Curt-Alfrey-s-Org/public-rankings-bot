#!/usr/bin/env python3
"""
Name Format Memory System for Fargo Ratings

This script demonstrates how the app now remembers successful name formats
for Fargo rating matching, ensuring future scrapes are complete on the first try.
"""

import os
import sys
import psycopg2
from dotenv import load_dotenv
import re

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

load_dotenv()

def get_name_format_lookup():
    """Get lookup table of successful name formats"""
    conn = psycopg2.connect(os.getenv('DATABASE_URL'))
    cursor = conn.cursor()

    cursor.execute('SELECT player_name, fargo_name_format FROM rankings WHERE fargo_rating IS NOT NULL AND fargo_name_format IS NOT NULL')
    formats = cursor.fetchall()

    cursor.close()
    conn.close()

    # Create normalized lookup
    lookup = {}
    for name, format_type in formats:
        normalized = re.sub(r'[^\w\s]', '', name).lower().strip()
        lookup[normalized] = format_type

    return lookup

def demonstrate_name_format_memory():
    """Show how name format memory works"""
    print("🎯 Name Format Memory System")
    print("=" * 50)

    lookup = get_name_format_lookup()
    print(f"Loaded {len(lookup)} remembered name formats")

    print("\n📋 Examples of remembered formats:")
    examples = list(lookup.items())[:10]
    for normalized_name, format_type in examples:
        print(f"  '{normalized_name}' → format: {format_type}")

    print("\n🚀 How it works for future scrapes:")
    print("  1. When scraping a new player name, normalize it")
    print("  2. Check if we've seen this name before and what format worked")
    print("  3. Use the remembered format for Fargo API lookup")
    print("  4. No more trial-and-error with different name formats!")

    print("\n💡 Benefits:")
    print("  • Faster scrapes (no retry loops)")
    print("  • More complete data (correct format first try)")
    print("  • Better accuracy (uses proven successful formats)")
    print("  • Learns from each successful match")

if __name__ == "__main__":
    demonstrate_name_format_memory()