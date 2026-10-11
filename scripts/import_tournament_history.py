#!/usr/bin/env python3
"""
Tournament History Import Script

Imports tournament and match data into the tournament_history and
tournament_history_matches tables. Uses the sample data generator to
create realistic historical match data.

Usage:
    python3 scripts/import_tournament_history.py [--num-tournaments N] [--start-year YYYY]
    
Options:
    --num-tournaments N   Number of tournaments to generate (default: 20)
    --start-year YYYY    Start year for historical data (default: 2010)
    --clear              Clear existing data before import
"""

import sys
import os
import argparse
import logging
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scrapers.generate_tournament_samples import TournamentSampleGenerator
from sqlalchemy import create_engine, text

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://rankingsbot_user:PASSWORD@rankings-bot-postgres:5432/rankingsbot")


class TournamentHistoryImporter:
    """Imports tournament history data into PostgreSQL"""
    
    def __init__(self, database_url: str = DATABASE_URL):
        self.engine = create_engine(database_url)
        logger.info(f"Connected to database")
    
    def clear_existing_data(self):
        """Clear existing tournament history data"""
        logger.info("Clearing existing tournament history data...")
        
        with self.engine.connect() as conn:
            # Delete in correct order due to foreign keys
            conn.execute(text("DELETE FROM tournament_history_matches"))
            conn.execute(text("DELETE FROM tournament_history"))
            conn.commit()
        
        logger.info("✅ Existing data cleared")
    
    def import_tournaments(self, tournaments: list):
        """Import tournament records (each in its own transaction)"""
        logger.info(f"Importing {len(tournaments)} tournaments...")
        
        imported = 0
        skipped = 0
        
        # Import each tournament individually to avoid transaction rollback issues
        for tournament in tournaments:
            try:
                with self.engine.begin() as conn:  # Each tournament gets its own transaction
                    conn.execute(text("""
                        INSERT INTO tournament_history 
                        (tournament_id, name, year, date, location)
                        VALUES (:tournament_id, :name, :year, :date, :location)
                        ON CONFLICT (tournament_id) DO UPDATE SET
                            name = EXCLUDED.name,
                            year = EXCLUDED.year,
                            date = EXCLUDED.date,
                            location = EXCLUDED.location
                    """), {
                        "tournament_id": tournament["tournament_id"],
                        "name": tournament["name"],
                        "year": tournament["year"],
                        "date": tournament["date"],
                        "location": tournament["location"],
                    })
                imported += 1
            except Exception as e:
                logger.error(f"Failed to import tournament {tournament['tournament_id']}: {e}")
                skipped += 1
        
        logger.info(f"✅ Tournaments imported: {imported}, skipped: {skipped}")
    
    def import_matches(self, matches: list):
        """Import match records (each in its own transaction)"""
        logger.info(f"Importing {len(matches)} matches...")
        
        imported = 0
        skipped = 0
        
        # Import each match individually to avoid transaction rollback issues
        for match in matches:
            try:
                with self.engine.begin() as conn:  # Each match gets its own transaction
                    conn.execute(text("""
                        INSERT INTO tournament_history_matches
                        (tournament_id, round_num, operator_name, player2_name, 
                         operator_score, player2_score, winner_name, notes)
                        VALUES (:tournament_id, :round_num, :operator_name, :player2_name,
                                :operator_score, :player2_score, :winner_name, :notes)
                    """), {
                        "tournament_id": match["tournament_id"],
                        "round_num": str(match.get("round_num", "")),
                        "operator_name": match["operator_name"],
                        "player2_name": match["player2_name"],
                        "operator_score": match.get("operator_score"),
                        "player2_score": match.get("player2_score"),
                        "winner_name": match.get("winner_name"),
                        "notes": match.get("notes"),
                    })
                imported += 1
            except Exception as e:
                logger.debug(f"Failed to import match between {match.get('operator_name')} and {match.get('player2_name')}: {e}")
                skipped += 1
        
        logger.info(f"✅ Matches imported: {imported}, skipped: {skipped}")
    
    def verify_import(self):
        """Verify imported data"""
        logger.info("Verifying imported data...")
        
        with self.engine.connect() as conn:
            # Count tournaments
            result = conn.execute(text("SELECT COUNT(*) FROM tournament_history"))
            tournament_count = result.fetchone()[0]
            
            # Count matches
            result = conn.execute(text("SELECT COUNT(*) FROM tournament_history_matches"))
            match_count = result.fetchone()[0]
            
            # Find Debbie vs Allison matches
            result = conn.execute(text("""
                SELECT 
                    m.operator_name, 
                    m.player2_name, 
                    m.operator_score, 
                    m.player2_score,
                    m.winner_name,
                    t.name as tournament_name,
                    t.date
                FROM tournament_history_matches m
                JOIN tournament_history t ON m.tournament_id = t.tournament_id
                WHERE 
                    (m.operator_name ILIKE :debbie AND m.player2_name ILIKE :allison)
                    OR (m.operator_name ILIKE :allison AND m.player2_name ILIKE :debbie)
                ORDER BY t.date
            """), {"debbie": "%Debbie%Teichert%", "allison": "%Allison%Fisher%"})
            
            featured_matches = result.fetchall()
        
        print("\n" + "="*80)
        print("IMPORT VERIFICATION")
        print("="*80)
        print(f"\n✅ Tournaments imported: {tournament_count}")
        print(f"✅ Matches imported: {match_count}")
        print(f"\n✅ Featured matches (Debbie Teichert vs Allison Fisher): {len(featured_matches)}")
        
        if featured_matches:
            print("\nMatches found:")
            for match in featured_matches:
                print(f"  • {match[5]} ({match[6]})")
                print(f"    {match[0]} vs {match[1]}: {match[2]}-{match[3]}")
                print(f"    Winner: {match[4]}\n")
        else:
            print("\n⚠️  WARNING: No matches found between Debbie Teichert and Allison Fisher!")
        
        print("="*80 + "\n")
        
        return tournament_count, match_count, len(featured_matches)


def main():
    """Main import process"""
    parser = argparse.ArgumentParser(description="Import tournament history data")
    parser.add_argument("--num-tournaments", type=int, default=20, 
                       help="Number of tournaments to generate (default: 20)")
    parser.add_argument("--start-year", type=int, default=2010,
                       help="Start year for historical data (default: 2010)")
    parser.add_argument("--clear", action="store_true",
                       help="Clear existing data before import")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("\n" + "="*80)
    print("TOURNAMENT HISTORY IMPORT")
    print("="*80)
    print(f"\nConfiguration:")
    print(f"  • Number of tournaments: {args.num_tournaments}")
    print(f"  • Start year: {args.start_year}")
    print(f"  • Clear existing data: {args.clear}")
    print(f"  • Database: {DATABASE_URL}")
    print("\n" + "="*80 + "\n")
    
    try:
        # Initialize importer
        importer = TournamentHistoryImporter(DATABASE_URL)
        
        # Clear existing data if requested
        if args.clear:
            importer.clear_existing_data()
        
        # Generate sample data
        logger.info("Generating tournament sample data...")
        generator = TournamentSampleGenerator(DATABASE_URL)
        data = generator.generate_all_data(
            num_tournaments=args.num_tournaments,
            start_year=args.start_year
        )
        
        # Import tournaments
        importer.import_tournaments(data["tournaments"])
        
        # Import matches
        importer.import_matches(data["matches"])
        
        # Verify import
        tournament_count, match_count, featured_count = importer.verify_import()
        
        # Success message
        print("\n✅ Import completed successfully!")
        print(f"   • {tournament_count} tournaments")
        print(f"   • {match_count} matches")
        print(f"   • {featured_count} featured matches (Debbie Teichert vs Allison Fisher)")
        
        print("\nNext steps:")
        print("  1. Test the head-to-head API:")
        print("     curl http://localhost:8003/api/players/{player_id}/head-to-head/{opponent_id}")
        print("  2. Check the frontend head-to-head feature")
        print("  3. Verify match data displays correctly\n")
        
        return 0
        
    except Exception as e:
        logger.error(f"Import failed: {e}", exc_info=True)
        print(f"\n❌ Import failed: {e}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
