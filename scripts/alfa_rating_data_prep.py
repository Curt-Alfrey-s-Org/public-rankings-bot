#!/usr/bin/env python3
"""
Alfa Rating v2 - Phase 1: Data Preparation
Extracts, validates, and prepares match data for model training.

Usage:
  python scripts/alfa_rating_data_prep.py --extract --validate --classify
  python scripts/alfa_rating_data_prep.py --extract --output matches.csv
  python scripts/alfa_rating_data_prep.py --validate --input matches.csv
"""

import argparse
import json
import os
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
import numpy as np

# Add parent dirs to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


@dataclass
class MatchRecord:
    """Represents a single match for Alfa rating training."""
    match_id: str
    date: str
    player_1_id: str
    player_1_name: str
    player_2_id: str
    player_2_name: str
    winner_id: str
    winner_games: int
    loser_games: int
    race_to: Optional[int] = None
    table_size: Optional[str] = None  # "7ft", "8ft", "9ft"
    event_type: str = "tournament"  # "league", "tournament", "casual"
    format: str = "9ball"  # "8ball", "9ball", "10ball"
    location_id: Optional[str] = None
    equipment: Optional[Dict] = None  # {"cue_ball": "...", "cloth": "..."}
    fargo_rating_p1: Optional[float] = None
    fargo_rating_p2: Optional[float] = None
    

class DataExtractor:
    """Extracts match data from database."""
    
    def __init__(self, db_connection=None):
        self.db = db_connection
        self.matches: List[MatchRecord] = []
        
    def from_tournament_history(self) -> List[MatchRecord]:
        """Extract matches from tournament_history_matches table."""
        try:
            from database import get_database_manager
            db_mgr = get_database_manager()
        except ImportError as e:
            print(f"ERROR: Could not import database manager: {e}")
            return []
        
        matches = []
        query = """
            SELECT 
                thm.id as match_id,
                thm.match_date,
                thm.operator_name,
                thm.player2_name,
                thm.operator_score,
                thm.player2_score,
                thm.winner_name,
                thm.round_num,
                th.tournament_id,
                th.name as tournament_name,
                th.association,
                th.location,
                tr1.fargo_rating_at_scrape as p1_fargo,
                tr2.fargo_rating_at_scrape as p2_fargo
            FROM tournament_history_matches thm
            JOIN tournament_history th ON thm.tournament_id = th.tournament_id
            LEFT JOIN tournament_results tr1 
                ON th.tournament_id = tr1.tournament_id 
                AND thm.operator_name = tr1.player_name
            LEFT JOIN tournament_results tr2 
                ON th.tournament_id = tr2.tournament_id 
                AND thm.player2_name = tr2.player_name
            WHERE thm.operator_score IS NOT NULL 
                AND thm.player2_score IS NOT NULL
            ORDER BY thm.match_date DESC
        """
        
        try:
            results = db_mgr.query(query) if hasattr(db_mgr, 'query') else []
            for row in results:
                match = self._parse_tournament_row(row)
                if match:
                    matches.append(match)
        except Exception as e:
            print(f"ERROR querying matches: {e}")
            return []
        
        self.matches = matches
        return matches
    
    def _parse_tournament_row(self, row: dict) -> Optional[MatchRecord]:
        """Parse a single tournament match row."""
        try:
            winner_id = row.get('winner_name', '').replace(' ', '_').lower()
            p1_id = row.get('operator_name', '').replace(' ', '_').lower()
            p2_id = row.get('player2_name', '').replace(' ', '_').lower()
            
            p1_score = int(row.get('operator_score', 0))
            p2_score = int(row.get('player2_score', 0))
            race_to = max(p1_score, p2_score)  # Infer race_to from scores
            
            # Determine winner
            if row.get('winner_name') == row.get('operator_name'):
                winner_games = p1_score
                loser_games = p2_score
            else:
                winner_games = p2_score
                loser_games = p1_score
            
            match = MatchRecord(
                match_id=f"{row.get('tournament_id', 'unknown')}_{row.get('match_id', '')}",
                date=str(row.get('match_date', '')),
                player_1_id=p1_id,
                player_1_name=row.get('operator_name', ''),
                player_2_id=p2_id,
                player_2_name=row.get('player2_name', ''),
                winner_id=winner_id if row.get('winner_name') else p1_id if p1_score > p2_score else p2_id,
                winner_games=winner_games,
                loser_games=loser_games,
                race_to=race_to,
                event_type="tournament",
                location_id=row.get('location', ''),
                fargo_rating_p1=float(row.get('p1_fargo')) if row.get('p1_fargo') else None,
                fargo_rating_p2=float(row.get('p2_fargo')) if row.get('p2_fargo') else None,
            )
            return match
        except Exception as e:
            print(f"WARN: Could not parse row: {e}")
            return None
    
    def export_csv(self, output_path: str) -> None:
        """Export matches to CSV."""
        df = pd.DataFrame([asdict(m) for m in self.matches])
        df.to_csv(output_path, index=False)
        print(f"Exported {len(df)} matches to {output_path}")
    
    def export_json(self, output_path: str) -> None:
        """Export matches to JSON."""
        with open(output_path, 'w') as f:
            json.dump([asdict(m) for m in self.matches], f, indent=2, default=str)
        print(f"Exported {len(self.matches)} matches to {output_path}")


class DataValidator:
    """Validates and cleans match data."""
    
    def __init__(self, matches: List[MatchRecord]):
        self.matches = matches
        self.validation_report = {}
    
    def validate_all(self) -> Dict:
        """Run all validation checks."""
        report = {
            "total_matches": len(self.matches),
            "timestamp": datetime.now().isoformat(),
            "checks": {}
        }
        
        report["checks"]["missing_fields"] = self._check_missing_fields()
        report["checks"]["invalid_scores"] = self._check_invalid_scores()
        report["checks"]["duplicate_matches"] = self._check_duplicates()
        report["checks"]["date_range"] = self._check_date_range()
        report["checks"]["player_coverage"] = self._check_player_coverage()
        
        self.validation_report = report
        return report
    
    def _check_missing_fields(self) -> Dict:
        """Check for missing required fields."""
        missing = {
            "match_id": sum(1 for m in self.matches if not m.match_id),
            "date": sum(1 for m in self.matches if not m.date),
            "player_1_name": sum(1 for m in self.matches if not m.player_1_name),
            "player_2_name": sum(1 for m in self.matches if not m.player_2_name),
            "winner_id": sum(1 for m in self.matches if not m.winner_id),
            "winner_games": sum(1 for m in self.matches if m.winner_games is None),
        }
        return {k: v for k, v in missing.items() if v > 0}
    
    def _check_invalid_scores(self) -> Dict:
        """Check for logical score errors."""
        errors = []
        for m in self.matches:
            if m.winner_games is not None and m.loser_games is not None:
                if m.winner_games <= m.loser_games:
                    errors.append(f"{m.match_id}: winner_games ({m.winner_games}) not > loser_games ({m.loser_games})")
        return {"invalid_winners": len(errors), "examples": errors[:5]}
    
    def _check_duplicates(self) -> Dict:
        """Check for duplicate matches."""
        ids = [m.match_id for m in self.matches]
        duplicates = len(ids) - len(set(ids))
        return {"duplicate_match_ids": duplicates}
    
    def _check_date_range(self) -> Dict:
        """Check date range and distribution."""
        dates = [m.date for m in self.matches if m.date]
        if not dates:
            return {"error": "No valid dates"}
        return {
            "earliest": min(dates),
            "latest": max(dates),
            "count": len(dates)
        }
    
    def _check_player_coverage(self) -> Dict:
        """Check unique player count and distribution."""
        players = set()
        for m in self.matches:
            players.add(m.player_1_id)
            players.add(m.player_2_id)
        return {"unique_players": len(players)}
    
    def print_report(self) -> None:
        """Pretty-print validation report."""
        print("\n" + "=" * 70)
        print("DATA VALIDATION REPORT")
        print("=" * 70)
        print(f"Total matches: {self.validation_report.get('total_matches', 0)}")
        print(f"Timestamp: {self.validation_report.get('timestamp', '')}")
        print("\nValidation checks:")
        for check_name, result in self.validation_report.get("checks", {}).items():
            print(f"\n  {check_name}:")
            if isinstance(result, dict):
                for k, v in result.items():
                    print(f"    {k}: {v}")
            else:
                print(f"    {result}")
        print("\n" + "=" * 70 + "\n")


class DataClassifier:
    """Classifies matches by context (table size, format, event type)."""
    
    def __init__(self, matches: List[MatchRecord]):
        self.matches = matches
    
    def infer_context(self) -> List[MatchRecord]:
        """
        Infer missing context from match metadata.
        This is a heuristic approach until explicit context is logged.
        """
        for m in self.matches:
            # Infer table size from location or tournament name (heuristic)
            if not m.table_size:
                m.table_size = self._infer_table_size(m)
            
            # Infer format from tournament name
            if not m.format or m.format == "9ball":
                m.format = self._infer_format(m)
            
            # Infer race_to if missing (already done in extraction, but fallback)
            if not m.race_to:
                m.race_to = max(m.winner_games, m.loser_games)
        
        return self.matches
    
    def _infer_table_size(self, match: MatchRecord) -> str:
        """Heuristic to infer table size from tournament/location."""
        # Default to 9ft (most common tournament table size)
        return "9ft"
    
    def _infer_format(self, match: MatchRecord) -> str:
        """Heuristic to infer game format from tournament name."""
        name = (match.player_1_name or "").lower()
        tournament = (match.location_id or "").lower()
        
        if "8ball" in tournament or "eight" in tournament:
            return "8ball"
        elif "10ball" in tournament or "ten" in tournament:
            return "10ball"
        else:
            return "9ball"  # Default
    
    def classify_by_context(self) -> Dict[str, List[MatchRecord]]:
        """Group matches by context (table size, format, event type)."""
        grouped = {}
        for m in self.matches:
            key = f"{m.event_type}_{m.format}_{m.table_size}"
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(m)
        return grouped


def main():
    parser = argparse.ArgumentParser(
        description="Alfa Rating v2 - Phase 1 Data Preparation"
    )
    parser.add_argument("--extract", action="store_true", help="Extract matches from database")
    parser.add_argument("--validate", action="store_true", help="Validate match data")
    parser.add_argument("--classify", action="store_true", help="Classify matches by context")
    parser.add_argument("--output", type=str, default="data/alfa_matches.csv", 
                        help="Output CSV file path")
    parser.add_argument("--input", type=str, help="Input CSV file (for validation/classification)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    if not any([args.extract, args.validate, args.classify]):
        parser.print_help()
        return
    
    # Ensure data directory exists
    Path("data").mkdir(exist_ok=True)
    
    # Step 1: Extract
    if args.extract:
        print("Extracting matches from database...")
        extractor = DataExtractor()
        matches = extractor.from_tournament_history()
        print(f"Extracted {len(matches)} matches")
        
        if matches:
            # Export
            extractor.export_csv(args.output)
            extractor.export_json(args.output.replace('.csv', '.json'))
            args.input = args.output  # Use extracted data for next steps
    
    # Step 2: Validate
    if args.validate and args.input:
        print(f"Validating matches from {args.input}...")
        df = pd.read_csv(args.input)
        matches = [
            MatchRecord(
                match_id=row['match_id'],
                date=row['date'],
                player_1_id=row['player_1_id'],
                player_1_name=row['player_1_name'],
                player_2_id=row['player_2_id'],
                player_2_name=row['player_2_name'],
                winner_id=row['winner_id'],
                winner_games=int(row['winner_games']),
                loser_games=int(row['loser_games']),
            )
            for _, row in df.iterrows()
        ]
        
        validator = DataValidator(matches)
        report = validator.validate_all()
        validator.print_report()
        
        # Save report
        report_path = args.input.replace('.csv', '_validation.json')
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        print(f"Validation report saved to {report_path}")
    
    # Step 3: Classify
    if args.classify and args.input:
        print(f"Classifying matches from {args.input}...")
        df = pd.read_csv(args.input)
        matches = [
            MatchRecord(
                match_id=row['match_id'],
                date=row['date'],
                player_1_id=row['player_1_id'],
                player_1_name=row['player_1_name'],
                player_2_id=row['player_2_id'],
                player_2_name=row['player_2_name'],
                winner_id=row['winner_id'],
                winner_games=int(row['winner_games']),
                loser_games=int(row['loser_games']),
            )
            for _, row in df.iterrows()
        ]
        
        classifier = DataClassifier(matches)
        matches = classifier.infer_context()
        grouped = classifier.classify_by_context()
        
        print(f"\nMatches grouped by context:")
        for context, group_matches in sorted(grouped.items()):
            print(f"  {context}: {len(group_matches)} matches")
        
        # Save classified data
        classified_path = args.input.replace('.csv', '_classified.csv')
        df_classified = pd.DataFrame([asdict(m) for m in matches])
        df_classified.to_csv(classified_path, index=False)
        print(f"Classified matches saved to {classified_path}")


if __name__ == "__main__":
    main()
