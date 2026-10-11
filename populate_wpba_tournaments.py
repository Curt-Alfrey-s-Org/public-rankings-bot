#!/usr/bin/env python3
"""
Populate WPBA tournament rankings with the same layout/columns/schema as WPA women tournaments.

This script creates individual WPBA tournament rankings that match the structure of WPA women tournaments,
ensuring each tournament has the proper player rankings with points, ranks, countries, etc.
"""

import sys
import json
from datetime import date
from typing import List, Dict, Any

# Add project root to path
sys.path.insert(0, '.')

try:
    from database import get_database_manager
except ImportError:
    print("Cannot import database module. Please run from project root.")
    sys.exit(1)

def populate_wpba_tournaments():
    """Populate WPBA tournament rankings with sample data matching WPA women schema."""

    db_manager = get_database_manager()

    # Sample player data that would come from WPBA_Women rankings
    sample_players = [
        {
            'name': 'Kristina Tkach',
            'country': 'USA',
            'license_number': 'WPA-001',
            'fargo_rating': 650,
            'alfa_rating': 700,
            'source_data': {
                '2026_wpba_olhausen_iron_city_invitational_vi': '20000',
                '2025_wpba_dr_pool_jacoby_tour_championship': '15750',
                '2025_wpba_olhausen_colorado_classic': '15000',
                '2025_wpba_soaring_eagle_masters': '12750',
                '2025_wpba_olhausen_raxx_mezz_invitational': '10000',
                '2025_wpba_olhausen_iron_city_invitational_v': '4250',
                '2024_wpba_dr_pool_jacoby_tour_championship': '4250',
                '2024_wpba_capital_city_billiards_invitational': '13000',
                '2024_wpba_cuespeed_napa_invitational': '7500',
                '2024_wpba_olhausen_colorado_classic': '9000',
                'wpba_palmetto_billiards_invitational': '4750'
            }
        },
        {
            'name': 'Pia Filler',
            'country': 'GER',
            'license_number': 'WPA-002',
            'fargo_rating': 640,
            'alfa_rating': 690,
            'source_data': {
                '2026_wpba_olhausen_iron_city_invitational_vi': '15000',
                '2025_wpba_dr_pool_jacoby_tour_championship': '22500',
                '2025_wpba_olhausen_colorado_classic': '13000',
                '2025_wpba_soaring_eagle_masters': '8500',
                '2025_wpba_olhausen_raxx_mezz_invitational': '6500',
                '2025_wpba_olhausen_iron_city_invitational_v': '7500',
                # Missing some tournaments (0 points)
            }
        },
        {
            'name': 'Margaret Fefilova-Styer',
            'country': 'USA',
            'license_number': 'WPA-003',
            'fargo_rating': 630,
            'alfa_rating': 680,
            'source_data': {
                '2026_wpba_olhausen_iron_city_invitational_vi': '7500',
                '2025_wpba_dr_pool_jacoby_tour_championship': '18000',
                '2025_wpba_olhausen_colorado_classic': '15000',
                '2025_wpba_soaring_eagle_masters': '7500',
                '2025_wpba_olhausen_raxx_mezz_invitational': '7500',
                '2025_wpba_olhausen_iron_city_invitational_v': '10000',
                '2024_wpba_dr_pool_jacoby_tour_championship': '10500',
                '2024_wpba_capital_city_billiards_invitational': '19500',
                '2024_wpba_cuespeed_napa_invitational': '7500',
                '2024_wpba_olhausen_colorado_classic': '7500',
                'wpba_palmetto_billiards_invitational': '10500'
            }
        }
    ]

    # Save sample WPBA_Women data with tournament columns
    print("Saving WPBA_Women rankings with tournament data...")
    count = db_manager.save_rankings(sample_players, ranking_type='WPBA_Women')
    print(f"Saved {count} WPBA_Women rankings with tournament data")

    # Now run the split function to create individual tournament rankings
    print("\nRunning WPBA tournament split function...")
    split_result = db_manager.split_wpba_women_to_column_buttons()

    print("\nWPBA Tournament Population Results:")
    for tournament_name, player_count in split_result.items():
        print(f"  {tournament_name}: {player_count} players")

    total_players = sum(split_result.values())
    print(f"\nTotal players across all WPBA tournaments: {total_players}")

    # Verify that tournament points sum to overall totals
    print("\nVerifying tournament totals match overall rankings...")
    verify_wpba_totals(db_manager)

def verify_wpba_totals(db_manager):
    """Verify that WPBA tournament points sum to overall totals."""

    # Get WPBA overall rankings
    overall_rankings = db_manager.get_rankings_paginated("WPBA_Women", limit=None)
    if not overall_rankings:
        print("No WPBA_Women rankings found")
        return

    # Get all WPBA tournament rankings
    wpba_tournaments = [
        'WPBA_Women_IronCityVI', 'WPBA_Women_Jacoby2025', 'WPBA_Women_Colorado2025',
        'WPBA_Women_SoaringEagle2025', 'WPBA_Women_RaxxMezz2025', 'WPBA_Women_IronCityV',
        'WPBA_Women_Jacoby2024', 'WPBA_Women_CapitalCity2024', 'WPBA_Women_NAPA2024',
        'WPBA_Women_Colorado2024', 'WPBA_Women_Palmetto'
    ]

    print("Verifying point totals for each player:")
    for player in overall_rankings[:3]:  # Check first 3 players
        player_name = player.get('player_name', player.get('name', 'Unknown'))
        expected_total = player.get('points', 0)

        # Sum points from all tournaments for this player
        tournament_total = 0
        for tournament in wpba_tournaments:
            tournament_rankings = db_manager.get_rankings_paginated(tournament, limit=None)
            for t_player in tournament_rankings:
                if t_player.get('player_name', t_player.get('name')) == player_name:
                    tournament_total += t_player.get('points', 0)
                    break

        match = "✅" if tournament_total == expected_total else "❌"
        print(f"  {player_name}: {tournament_total} (tournament sum) vs {expected_total} (overall) {match}")

if __name__ == "__main__":
    print("Populating WPBA tournaments with WPA women tournament schema...")
    populate_wpba_tournaments()
    print("\nWPBA tournament population complete!")