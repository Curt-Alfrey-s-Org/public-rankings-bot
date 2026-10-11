#!/usr/bin/env python3
"""
Simple Data Copy Script

Copies missing data between ranking systems using basic matching.
Much simpler than the complex enrichment system.

Usage:
    python3 scripts/simple_data_copy.py --wpba-from-wpa
    python3 scripts/simple_data_copy.py --heyball-fargo-from-wpa
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import logging
from sqlalchemy import text, create_engine
from sqlalchemy.pool import QueuePool

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_database_url():
    """Get database URL from environment"""
    # Try to load from .env file
    env_file = project_root / '.env'
    if env_file.exists():
        with open(env_file, 'r') as f:
            for line in f:
                if line.startswith('DATABASE_URL='):
                    return line.split('=', 1)[1].strip().strip('"').strip("'")

    # Fallback to constructing from individual vars
    db_vars = {}
    if env_file.exists():
        with open(env_file, 'r') as f:
            for line in f:
                if '=' in line and not line.strip().startswith('#'):
                    key, value = line.split('=', 1)
                    db_vars[key.strip()] = value.strip().strip('"').strip("'")

    if 'POSTGRES_DB' in db_vars and 'POSTGRES_USER' in db_vars and 'POSTGRES_PASSWORD' in db_vars:
        return f"postgresql://{db_vars['POSTGRES_USER']}:change-me@rankings-bot-postgres:5432/{db_vars['POSTGRES_DB']}"

    raise RuntimeError("Could not determine DATABASE_URL")

def copy_wpba_data_from_wpa():
    """Copy country and license data from WPA to WPBA players"""
    logger.info("Starting WPBA data copy from WPA...")

    engine = create_engine(get_database_url(), poolclass=QueuePool)

    with engine.connect() as conn:
        # Get all WPBA players missing country/license data
        wpba_missing = conn.execute(text("""
            SELECT id, player_name, country, license_number
            FROM rankings
            WHERE ranking_system = 'WPBA_Women'
            AND (country IS NULL OR license_number IS NULL)
            ORDER BY player_name
        """)).fetchall()

        logger.info(f"Found {len(wpba_missing)} WPBA players missing country/license data")

        updated_count = 0

        for wpba_record in wpba_missing:
            wpba_id, wpba_name, wpba_country, wpba_license = wpba_record

            # Try to find matching WPA player
            # First try exact name match
            wpa_match = conn.execute(text("""
                SELECT country, license_number
                FROM rankings
                WHERE ranking_system = 'WPA_Women'
                AND player_name = :name
                AND (country IS NOT NULL OR license_number IS NOT NULL)
                LIMIT 1
            """), {'name': wpba_name}).fetchone()

            # If no exact match, try license-based match
            if not wpa_match and wpba_license:
                wpa_match = conn.execute(text("""
                    SELECT country, license_number
                    FROM rankings
                    WHERE ranking_system = 'WPA_Women'
                    AND license_number = :license
                    AND (country IS NOT NULL OR license_number IS NOT NULL)
                    LIMIT 1
                """), {'license': wpba_license}).fetchone()

            # If still no match, try fuzzy name match (simple approach)
            if not wpa_match:
                # Split names and look for matches
                wpba_parts = set(wpba_name.lower().replace(',', '').split())
                wpa_candidates = conn.execute(text("""
                    SELECT player_name, country, license_number
                    FROM rankings
                    WHERE ranking_system = 'WPA_Women'
                    AND (country IS NOT NULL OR license_number IS NOT NULL)
                """)).fetchall()

                for candidate in wpa_candidates:
                    candidate_name, candidate_country, candidate_license = candidate
                    candidate_parts = set(candidate_name.lower().replace(',', '').split())

                    # If names share significant parts (first + last name), consider it a match
                    if len(wpba_parts & candidate_parts) >= 2:  # At least 2 name parts match
                        wpa_match = (candidate_country, candidate_license)
                        logger.debug(f"Fuzzy match: '{wpba_name}' ↔ '{candidate_name}'")
                        break

            # If we found WPA data, copy it to WPBA record
            if wpa_match:
                wpa_country, wpa_license = wpa_match

                # Only update fields that are missing in WPBA
                updates = {}
                if wpba_country is None and wpa_country is not None:
                    updates['country'] = wpa_country
                if wpba_license is None and wpa_license is not None:
                    updates['license_number'] = wpa_license

                if updates:
                    # Build update query
                    set_parts = [f"{field} = :{field}" for field in updates.keys()]
                    set_clause = ", ".join(set_parts)

                    conn.execute(text(f"""
                        UPDATE rankings
                        SET {set_clause}
                        WHERE id = :record_id
                    """), {**updates, 'record_id': wpba_id})

                    updated_count += 1
                    logger.debug(f"Updated WPBA player '{wpba_name}': {updates}")

        conn.commit()
        logger.info(f"✅ WPBA data copy complete: {updated_count} records updated")

def copy_heyball_fargo_from_wpa():
    """Copy Fargo ratings from WPA to Heyball players"""
    logger.info("Starting Heyball Fargo copy from WPA...")

    engine = create_engine(get_database_url(), poolclass=QueuePool)

    with engine.connect() as conn:
        # Get all Heyball players missing Fargo ratings
        heyball_missing = conn.execute(text("""
            SELECT id, player_name, license_number, ranking_system
            FROM rankings
            WHERE ranking_system LIKE 'WPA_Heyball%'
            AND fargo_rating IS NULL
            ORDER BY player_name
        """)).fetchall()

        logger.info(f"Found {len(heyball_missing)} Heyball players missing Fargo ratings")

        # Debug: Show some sample Heyball players
        if heyball_missing:
            logger.info("Sample Heyball players to match:")
            for i, (id, name, license, system) in enumerate(heyball_missing[:3]):
                logger.info(f"  {system}: {name} (license: {license or 'none'})")

            # Debug: Check WPA system data
            wpa_men_count = conn.execute(text("SELECT COUNT(*) FROM rankings WHERE ranking_system = 'WPA_Men' AND fargo_rating IS NOT NULL")).fetchone()[0]
            wpa_women_count = conn.execute(text("SELECT COUNT(*) FROM rankings WHERE ranking_system = 'WPA_Women' AND fargo_rating IS NOT NULL")).fetchone()[0]
            logger.info(f"WPA_Men players with Fargo: {wpa_men_count}")
            logger.info(f"WPA_Women players with Fargo: {wpa_women_count}")

        updated_count = 0

        for heyball_record in heyball_missing[:5]:  # Test just first 5 for debugging
            heyball_id, heyball_name, heyball_license, heyball_system = heyball_record

            logger.debug(f"Processing: {heyball_name} ({heyball_system}) - license: {heyball_license}")

            # Determine which WPA system to match against based on Heyball system
            if heyball_system == 'WPA_Heyball_Men':
                wpa_system = 'WPA_Men'
            elif heyball_system == 'WPA_Heyball_Women':
                wpa_system = 'WPA_Women'
            else:
                continue  # Unknown Heyball system

            # Try to find matching WPA player with Fargo rating
            # First try license-based match
            wpa_match = None
            if heyball_license:
                wpa_match = conn.execute(text("""
                    SELECT fargo_rating
                    FROM rankings
                    WHERE ranking_system = :wpa_system
                    AND license_number = :license
                    AND fargo_rating IS NOT NULL
                    LIMIT 1
                """), {'wpa_system': wpa_system, 'license': heyball_license}).fetchone()
                if wpa_match:
                    logger.debug(f"License match found for {heyball_name}: {wpa_match[0]}")
                else:
                    logger.debug(f"No license match for {heyball_name} with license {heyball_license}")

            # If no license match, try fuzzy name match
            if not wpa_match:
                # Split names and look for matches
                heyball_parts = set(heyball_name.lower().replace(',', '').split())

                wpa_candidates = conn.execute(text("""
                    SELECT player_name, fargo_rating
                    FROM rankings
                    WHERE ranking_system = :wpa_system
                    AND fargo_rating IS NOT NULL
                """), {'wpa_system': wpa_system}).fetchall()

                logger.debug(f"Checking {len(wpa_candidates)} {wpa_system} candidates for fuzzy match with '{heyball_name}'")

                for candidate in wpa_candidates[:5]:  # Check first 5 candidates for debugging
                    candidate_name, candidate_fargo = candidate
                    candidate_parts = set(candidate_name.lower().replace(',', '').split())

                    # More aggressive fuzzy matching - look for any significant overlap
                    common_parts = heyball_parts & candidate_parts
                    logger.debug(f"Comparing '{heyball_name}' parts {heyball_parts} with '{candidate_name}' parts {candidate_parts} - common: {common_parts}")

                    if len(common_parts) >= 1:  # At least 1 name part matches
                        # Additional check: make sure it's not just a common word
                        significant_parts = [part for part in common_parts if len(part) > 2 and part not in ['van', 'der', 'den', 'de', 'la', 'el', 'jr', 'sr']]
                        if significant_parts:
                            wpa_match = (candidate_fargo,)
                            logger.debug(f"✅ Fuzzy match found: '{heyball_name}' ↔ '{candidate_name}' ({wpa_system}) - common: {significant_parts}")
                            break

            # If we found WPA Fargo rating, copy it to Heyball record
            if wpa_match:
                fargo_rating = wpa_match[0]

                # Debug: Check current value before update
                current = conn.execute(text("SELECT fargo_rating FROM rankings WHERE id = :id"), {'id': heyball_id}).fetchone()
                logger.debug(f"Before update: {heyball_name} has fargo_rating = {current[0] if current else 'None'}")

                result = conn.execute(text("""
                    UPDATE rankings
                    SET fargo_rating = :fargo
                    WHERE id = :record_id
                """), {'fargo': fargo_rating, 'record_id': heyball_id})

                # Check if update actually happened
                if result.rowcount > 0:
                    updated_count += 1
                    logger.info(f"✅ Updated {heyball_system} player '{heyball_name}' with Fargo rating: {fargo_rating}")
                else:
                    logger.warning(f"❌ Update failed for {heyball_name} - no rows affected")

                # Debug: Check value after update
                after = conn.execute(text("SELECT fargo_rating FROM rankings WHERE id = :id"), {'id': heyball_id}).fetchone()
                logger.debug(f"After update: {heyball_name} has fargo_rating = {after[0] if after else 'None'}")

        conn.commit()
        logger.info(f"✅ Heyball Fargo copy complete: {updated_count} records updated")

def main():
    import argparse

    parser = argparse.ArgumentParser(description='Simple data copy between ranking systems')
    parser.add_argument('--wpba-from-wpa', action='store_true', help='Copy country/license data from WPA to WPBA')
    parser.add_argument('--heyball-fargo-from-wpa', action='store_true', help='Copy Fargo ratings from WPA to Heyball')

    args = parser.parse_args()

    if args.wpba_from_wpa:
        copy_wpba_data_from_wpa()
    elif args.heyball_fargo_from_wpa:
        copy_heyball_fargo_from_wpa()
    else:
        print("Usage: python3 scripts/simple_data_copy.py --wpba-from-wpa")
        print("   or: python3 scripts/simple_data_copy.py --heyball-fargo-from-wpa")

if __name__ == "__main__":
    main()