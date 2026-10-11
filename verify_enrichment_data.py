#!/usr/bin/env python3
"""
Verification script to check if database enrichment is actually working.
Queries the rankings table to verify country, license, and fargo fields are populated.
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Any
import json

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

def check_database_connection():
    """Test database connection and basic functionality."""
    print("🔍 Testing database connection...")

    try:
        # Set minimal environment for testing
        os.environ['JWT_SECRET'] = 'test123'
        os.environ['DATABASE_URL'] = os.environ.get('DATABASE_URL', 'postgresql://rankingsbot_user:PASSWORD@rankings-bot-postgres:5432/rankingsbot')

        from database.postgres_manager import PostgresManager
        db = PostgresManager()

        # Test basic connection
        with db.engine.connect() as conn:
            result = conn.execute("SELECT 1 as test")
            if result.fetchone()[0] == 1:
                print("✅ Database connection successful")
                return True
            else:
                print("❌ Database connection test failed")
                return False

    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False

def get_enrichment_statistics():
    """Get statistics about enriched data in the database."""
    print("\n📊 Gathering enrichment statistics...")

    try:
        from database.postgres_manager import PostgresManager
        db = PostgresManager()

        with db.engine.connect() as conn:
            # Get overall statistics
            result = conn.execute("""
                SELECT
                    COUNT(*) as total_records,
                    COUNT(CASE WHEN country IS NOT NULL AND country != '' THEN 1 END) as country_records,
                    COUNT(CASE WHEN license_number IS NOT NULL AND license_number != '' THEN 1 END) as license_records,
                    COUNT(CASE WHEN fargo_rating IS NOT NULL THEN 1 END) as fargo_records,
                    COUNT(CASE WHEN country IS NOT NULL AND license_number IS NOT NULL AND fargo_rating IS NOT NULL THEN 1 END) as fully_enriched
                FROM rankings
            """)

            stats = dict(result.fetchone())
            print(f"📈 Total records: {stats['total_records']}")
            print(f"🌍 Country populated: {stats['country_records']} ({stats['country_records']/stats['total_records']*100:.1f}%)")
            print(f"📄 License populated: {stats['license_records']} ({stats['license_records']/stats['total_records']*100:.1f}%)")
            print(f"🎯 Fargo populated: {stats['fargo_records']} ({stats['fargo_records']/stats['total_records']*100:.1f}%)")
            print(f"✨ Fully enriched: {stats['fully_enriched']} ({stats['fully_enriched']/stats['total_records']*100:.1f}%)")

            return stats

    except Exception as e:
        print(f"❌ Failed to get enrichment statistics: {e}")
        return None

def get_sample_enriched_records(limit: int = 5):
    """Get sample records showing enriched data."""
    print(f"\n🔍 Sample enriched records (limit: {limit})...")

    try:
        from database.postgres_manager import PostgresManager
        db = PostgresManager()

        with db.engine.connect() as conn:
            result = conn.execute("""
                SELECT
                    player_name,
                    ranking_system,
                    rank,
                    points,
                    country,
                    license_number,
                    fargo_rating,
                    snapshot_date
                FROM rankings
                WHERE (country IS NOT NULL OR license_number IS NOT NULL OR fargo_rating IS NOT NULL)
                ORDER BY player_name, ranking_system
                LIMIT %s
            """, (limit,))

            records = []
            for row in result.fetchall():
                record = {
                    'player_name': row[0],
                    'ranking_system': row[1],
                    'rank': row[2],
                    'points': row[3],
                    'country': row[4],
                    'license_number': row[5],
                    'fargo_rating': row[6],
                    'snapshot_date': str(row[7])
                }
                records.append(record)

            if records:
                print("✅ Found enriched records:")
                for i, record in enumerate(records, 1):
                    enriched_fields = []
                    if record['country']:
                        enriched_fields.append(f"country: {record['country']}")
                    if record['license_number']:
                        enriched_fields.append(f"license: {record['license_number']}")
                    if record['fargo_rating']:
                        enriched_fields.append(f"fargo: {record['fargo_rating']}")

                    print(f"  {i}. {record['player_name']} ({record['ranking_system']})")
                    print(f"     Rank: {record['rank']}, Points: {record['points']}")
                    print(f"     Enriched: {', '.join(enriched_fields)}")
                    print(f"     Date: {record['snapshot_date']}")
                    print()
            else:
                print("❌ No enriched records found")

            return records

    except Exception as e:
        print(f"❌ Failed to get sample enriched records: {e}")
        return []

def get_cross_system_players():
    """Check for players that appear in multiple systems (eligible for enrichment)."""
    print("\n🔗 Checking cross-system players...")

    try:
        from database.postgres_manager import PostgresManager
        db = PostgresManager()

        with db.engine.connect() as conn:
            # Count players in multiple systems
            result = conn.execute("""
                SELECT COUNT(DISTINCT player_name) as cross_system_count
                FROM rankings
                WHERE player_name IN (
                    SELECT player_name
                    FROM rankings
                    GROUP BY player_name
                    HAVING COUNT(DISTINCT ranking_system) > 1
                )
            """)

            cross_system_count = result.fetchone()[0]

            # Get total unique players
            result = conn.execute("SELECT COUNT(DISTINCT player_name) as total_players FROM rankings")
            total_players = result.fetchone()[0]

            print(f"👥 Total unique players: {total_players}")
            print(f"🔄 Cross-system players: {cross_system_count} ({cross_system_count/total_players*100:.1f}%)")

            return cross_system_count, total_players

    except Exception as e:
        print(f"❌ Failed to check cross-system players: {e}")
        return 0, 0

def run_enrichment_and_compare():
    """Run enrichment and compare before/after statistics."""
    print("\n🔄 Running enrichment process...")

    # Get before statistics
    print("📊 BEFORE enrichment:")
    before_stats = get_enrichment_statistics()

    if not before_stats:
        print("❌ Cannot proceed without database access")
        return

    try:
        # Run enrichment
        from database.postgres_manager import PostgresManager
        db = PostgresManager()

        print("\n⚙️  Running enrichment...")
        enrichment_result = db.enrich_player_data()

        print("✅ Enrichment completed:")
        print(f"   Players processed: {enrichment_result.get('processed_players', 0)}")
        print(f"   Records enriched: {enrichment_result.get('enriched_records', 0)}")
        print(f"   Fields filled: {enrichment_result.get('fields_filled', 0)}")
        print(".2f")
        # Get after statistics
        print("\n📊 AFTER enrichment:")
        after_stats = get_enrichment_statistics()

        if after_stats:
            # Compare results
            print("\n📈 COMPARISON:")
            improvements = {
                'country': after_stats['country_records'] - before_stats['country_records'],
                'license': after_stats['license_records'] - before_stats['license_records'],
                'fargo': after_stats['fargo_records'] - before_stats['fargo_records'],
                'fully_enriched': after_stats['fully_enriched'] - before_stats['fully_enriched']
            }

            for field, improvement in improvements.items():
                status = "📈" if improvement > 0 else "➡️" if improvement == 0 else "📉"
                print(f"   {field}: {improvement:+d} {status}")

            if any(improvement > 0 for improvement in improvements.values()):
                print("\n🎉 Enrichment successfully improved data quality!")
            else:
                print("\n🤔 No improvements detected - data may already be fully enriched")

    except Exception as e:
        print(f"❌ Enrichment failed: {e}")

def check_recent_enrichment_activity():
    """Check for recent enrichment activity in the database."""
    print("\n🕐 Checking recent enrichment activity...")

    try:
        from database.postgres_manager import PostgresManager
        db = PostgresManager()

        with db.engine.connect() as conn:
            # Check for records updated in the last hour
            result = conn.execute("""
                SELECT COUNT(*) as recent_updates
                FROM rankings
                WHERE updated_at > CURRENT_TIMESTAMP - INTERVAL '1 hour'
                AND (country IS NOT NULL OR license_number IS NOT NULL OR fargo_rating IS NOT NULL)
            """)

            recent_updates = result.fetchone()[0]

            if recent_updates > 0:
                print(f"✅ Recent enrichment activity detected: {recent_updates} records updated in last hour")
            else:
                print("⚠️  No recent enrichment activity (last hour)")

            # Check last enrichment timestamp
            result = conn.execute("""
                SELECT MAX(updated_at) as last_enrichment
                FROM rankings
                WHERE country IS NOT NULL OR license_number IS NOT NULL OR fargo_rating IS NOT NULL
            """)

            last_enrichment = result.fetchone()[0]
            if last_enrichment:
                print(f"🕐 Last enrichment timestamp: {last_enrichment}")
            else:
                print("📅 No enrichment timestamps found")

    except Exception as e:
        print(f"❌ Failed to check recent activity: {e}")

def main():
    """Main verification function."""
    print("🔬 DATABASE ENRICHMENT VERIFICATION")
    print("=" * 50)

    # Check database connection
    if not check_database_connection():
        print("\n❌ Cannot proceed without database access")
        return 1

    # Get current enrichment statistics
    stats = get_enrichment_statistics()
    if not stats:
        return 1

    # Get sample enriched records
    samples = get_sample_enriched_records()

    # Check cross-system players
    cross_count, total_count = get_cross_system_players()

    # Check recent activity
    check_recent_enrichment_activity()

    # Run enrichment and compare
    if cross_count > 0:
        run_enrichment_and_compare()
    else:
        print("\n⚠️  No cross-system players found - enrichment may not be applicable")

    print("\n" + "=" * 50)
    print("🎯 VERIFICATION COMPLETE")

    # Overall assessment
    if stats and stats['total_records'] > 0:
        enrichment_rate = (stats['country_records'] + stats['license_records'] + stats['fargo_records']) / (stats['total_records'] * 3) * 100
        if enrichment_rate > 50:
            print("✅ GOOD: Database has substantial enriched data")
        elif enrichment_rate > 20:
            print("🟡 FAIR: Database has some enriched data")
        else:
            print("❌ POOR: Database lacks enriched data")
    else:
        print("❓ UNKNOWN: Unable to assess enrichment status")

    return 0

if __name__ == "__main__":
    sys.exit(main())