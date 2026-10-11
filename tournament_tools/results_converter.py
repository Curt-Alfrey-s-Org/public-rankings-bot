#!/usr/bin/env python3
"""
WPBA to WPA Tournament Results Converter
"""

import re
import sys
from typing import List, Dict
from player_database import get_player_country, split_player_name


def parse_wpba_results(text: str) -> List[Dict]:
    """Parse WPBA results format"""
    results = []
    lines = text.strip().split('\n')
    
    for line in lines:
        if not line.strip():
            continue
            
        parts = re.split(r'\t+|\s{2,}', line.strip())
        
        if len(parts) < 2:
            continue
            
        try:
            position = int(parts[0])
            full_name = parts[1].strip()
            
            prize = ""
            if len(parts) > 2:
                prize_text = parts[-1].strip()
                prize = re.sub(r'[\$,]', '', prize_text)
            
            results.append({
                'position': position,
                'full_name': full_name,
                'prize': prize
            })
        except (ValueError, IndexError):
            continue
    
    return results


def convert_to_wpa_format(results: List[Dict], tournament_name: str = "") -> str:
    """Convert to WPA format"""
    output = []
    
    if tournament_name:
        output.append(tournament_name)
        output.append("")
    
    output.append("Position\tFamily Name\tGiven Names\tCountry\tR-points\tAward")
    
    for result in results:
        full_name = result['full_name']
        family_name, given_names = split_player_name(full_name)
        country = get_player_country(full_name)
        prize = result['prize']
        
        line = f"{result['position']}\t{family_name}\t{given_names}\t{country}\t\t{prize}"
        output.append(line)
    
    return '\n'.join(output)


def main():
    print("=" * 80)
    print("WPBA → WPA Tournament Results Converter")
    print("=" * 80)
    print()
    print("Paste WPBA results below (press Ctrl+D when done):")
    print()
    
    input_text = sys.stdin.read()
    
    if not input_text.strip():
        print("\n✗ No input provided")
        sys.exit(1)
    
    results = parse_wpba_results(input_text)
    
    if not results:
        print("\n✗ Could not parse any results")
        sys.exit(1)
    
    print(f"\n✓ Parsed {len(results)} results")
    print()
    
    # Check if stdin is a terminal (interactive)
    tournament_name = ""
    if sys.stdout.isatty():
        try:
            tournament_name = input("Enter tournament name (or press Enter to skip): ").strip()
        except EOFError:
            print("(Using default tournament name)")
    else:
        print("(Using default tournament name)")
    
    wpa_output = convert_to_wpa_format(results, tournament_name)
    
    print("\n" + "=" * 80)
    print("WPA FORMAT OUTPUT")
    print("=" * 80)
    print()
    print(wpa_output)
    print()
    
    filename = "wpa_results.txt"
    with open(filename, 'w') as f:
        f.write(wpa_output)
    
    print("=" * 80)
    print(f"✓ Saved to: {filename}")
    print("=" * 80)


if __name__ == "__main__":
    main()
