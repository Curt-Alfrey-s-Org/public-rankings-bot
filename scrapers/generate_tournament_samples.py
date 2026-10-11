#!/usr/bin/env python3
"""
Tournament Sample Data Generator

Generates realistic historical tournament and match data for testing the
head-to-head feature. Creates matches between real players in the database,
including specific matchups between Debbie Teichert and Allison Fisher.

This is a fallback solution since WPBA/WPA archives don't provide detailed
historical match data in a scrapable format.
"""

import os
import random
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
from sqlalchemy import create_engine, text

logger = logging.getLogger(__name__)

# Tournament templates with realistic data
TOURNAMENT_TEMPLATES = [
    {
        "name": "US Open",
        "association": "WPBA",
        "locations": ["Las Vegas, NV", "Atlantic City, NJ", "Reno, NV"],
        "championship": "US Open",
        "typical_rounds": 6,
    },
    {
        "name": "World 9-Ball Championship",
        "association": "WPA",
        "locations": ["Doha, Qatar", "Manila, Philippines", "Jacksonville, FL"],
        "championship": "WPA World 9-Ball",
        "typical_rounds": 7,
    },
    {
        "name": "WPBA Masters",
        "association": "WPBA",
        "locations": ["Las Vegas, NV", "Chicago, IL"],
        "championship": "WPBA Masters",
        "typical_rounds": 5,
    },
    {
        "name": "Derby City Classic",
        "association": "WPBA",
        "locations": ["Louisville, KY"],
        "championship": "Derby City Classic",
        "typical_rounds": 5,
    },
    {
        "name": "Iron City Invitational",
        "association": "WPBA",
        "locations": ["Birmingham, AL"],
        "championship": "WPBA Iron City",
        "typical_rounds": 4,
    },
    {
        "name": "European Open",
        "association": "WPA",
        "locations": ["Vienna, Austria", "Berlin, Germany", "Amsterdam, Netherlands"],
        "championship": "WPA European Open",
        "typical_rounds": 5,
    },
    {
        "name": "China Open",
        "association": "WPA",
        "locations": ["Shanghai, China", "Beijing, China"],
        "championship": "WPA China Open",
        "typical_rounds": 6,
    },
    {
        "name": "Carolina Classic",
        "association": "WPBA",
        "locations": ["Charlotte, NC", "Raleigh, NC"],
        "championship": "Carolina Classic",
        "typical_rounds": 4,
    },
]


class TournamentSampleGenerator:
    """Generates sample tournament and match data"""

    def __init__(self, database_url: str):
        self.engine = create_engine(database_url)
        self.top_players = []
        self.all_player_names = []
        
    def load_players(self):
        """Load real players from the database"""
        logger.info("Loading players from database...")
        
        with self.engine.connect() as conn:
            # Get top players for featured matches
            result = conn.execute(text("""
                SELECT DISTINCT player_name, MIN(rank) as min_rank
                FROM rankings 
                GROUP BY player_name
                ORDER BY min_rank 
                LIMIT 50
            """))
            self.top_players = [row[0] for row in result]
            
            # Get all players for random matches
            result = conn.execute(text("""
                SELECT DISTINCT player_name, MIN(rank) as min_rank
                FROM rankings 
                GROUP BY player_name
                ORDER BY min_rank 
                LIMIT 200
            """))
            self.all_player_names = [row[0] for row in result]
        
        logger.info(f"Loaded {len(self.top_players)} top players and {len(self.all_player_names)} total players")
    
    def generate_tournaments(self, num_tournaments: int = 20, start_year: int = 2010) -> List[Dict]:
        """Generate tournament metadata"""
        tournaments = []
        current_date = datetime(start_year, 1, 1)
        
        for i in range(num_tournaments):
            template = random.choice(TOURNAMENT_TEMPLATES)
            
            # Generate date (spread across years)
            year = start_year + (i * 5) // num_tournaments  # Distribute across years
            month = random.randint(1, 12)
            day = random.randint(1, 28)
            current_date = datetime(year, month, day)
            
            tournament_id = f"{year}_{template['association'].lower()}_{template['championship'].lower().replace(' ', '_')}_{i}"
            
            tournament = {
                "tournament_id": tournament_id,
                "name": f"{year} {template['name']}",
                "year": year,
                "date": current_date.strftime("%Y-%m-%d"),
                "location": random.choice(template["locations"]),
                "association": template["association"],
                "championship": template["championship"],
                "status": "completed",
                "typical_rounds": template["typical_rounds"],
            }
            
            tournaments.append(tournament)
        
        return sorted(tournaments, key=lambda x: x["date"])
    
    def generate_match_score(self, is_early_round: bool = False) -> Tuple[int, int]:
        """Generate realistic match scores (race format)"""
        if is_early_round:
            # Early rounds: race to 7 or 9
            race_to = random.choice([7, 9])
        else:
            # Later rounds: race to 9, 11, or 13
            race_to = random.choice([9, 11, 13])
        
        # Winner gets race_to, loser gets 0 to race_to - 2
        winner_score = race_to
        loser_score = random.randint(max(0, race_to - 5), race_to - 1)
        
        return winner_score, loser_score
    
    def generate_matches_for_tournament(self, tournament: Dict) -> List[Dict]:
        """Generate matches for a single tournament"""
        matches = []
        num_rounds = tournament["typical_rounds"]
        
        # Start with more players in early rounds
        players_in_round = 32  # Start with 32 players
        
        for round_num in range(1, num_rounds + 1):
            num_matches = max(1, players_in_round // 2)
            is_early_round = round_num <= 2
            
            # Select players for this round
            if round_num == 1:
                # Early round: mix of top players and others
                round_players = (
                    random.sample(self.top_players, min(16, len(self.top_players))) +
                    random.sample(self.all_player_names, min(16, len(self.all_player_names)))
                )
                random.shuffle(round_players)
            else:
                # Later rounds: mostly top players
                round_players = random.sample(
                    self.top_players, 
                    min(players_in_round, len(self.top_players))
                )
            
            for match_num in range(1, num_matches + 1):
                if len(round_players) < 2:
                    break
                
                operator = round_players.pop(0)
                player2 = round_players.pop(0)
                
                # Generate score
                winner_score, loser_score = self.generate_match_score(is_early_round)
                
                # Randomly determine winner
                if random.random() > 0.5:
                    p1_score, p2_score = winner_score, loser_score
                    winner = operator
                else:
                    p1_score, p2_score = loser_score, winner_score
                    winner = player2
                
                match = {
                    "tournament_id": tournament["tournament_id"],
                    "round_num": round_num,
                    "match_num": match_num,
                    "operator_name": operator,
                    "player2_name": player2,
                    "operator_score": p1_score,
                    "player2_score": p2_score,
                    "winner_name": winner,
                    "notes": self._generate_match_note(round_num, num_rounds),
                }
                
                matches.append(match)
            
            # Reduce players for next round
            players_in_round = players_in_round // 2
        
        return matches
    
    def _generate_match_note(self, round_num: int, total_rounds: int) -> str:
        """Generate a descriptive note for a match"""
        if round_num == total_rounds:
            return "Finals"
        elif round_num == total_rounds - 1:
            return "Semi-finals"
        elif round_num == total_rounds - 2:
            return "Quarter-finals"
        elif round_num == 1:
            return "Opening round"
        else:
            return f"Round {round_num}"
    
    def add_featured_matches(self, tournaments: List[Dict]) -> List[Dict]:
        """Add specific featured matches including Debbie Teichert vs Allison Fisher"""
        featured_matches = []
        
        # Find Debbie Teichert and Allison Fisher variants in database
        debbie_names = [name for name in self.all_player_names if "Debbie" in name and "Teichert" in name]
        allison_names = [name for name in self.all_player_names if "Allison" in name and "Fisher" in name]
        
        if not debbie_names:
            logger.warning("Could not find Debbie Teichert in database")
            return featured_matches
        
        if not allison_names:
            logger.warning("Could not find Allison Fisher in database")
            return featured_matches
        
        debbie = debbie_names[0]
        allison = allison_names[0]
        
        logger.info(f"Creating featured matches: {debbie} vs {allison}")
        
        # Create 3-5 matches between Debbie and Allison across different tournaments
        num_featured = min(5, len(tournaments))
        featured_tournaments = random.sample(tournaments, num_featured)
        
        for i, tournament in enumerate(featured_tournaments):
            # Vary who wins
            if i % 3 == 0:
                # Debbie wins
                winner_score, loser_score = self.generate_match_score(is_early_round=False)
                match = {
                    "tournament_id": tournament["tournament_id"],
                    "round_num": random.randint(3, tournament["typical_rounds"] - 1),
                    "match_num": random.randint(1, 4),
                    "operator_name": debbie,
                    "player2_name": allison,
                    "operator_score": winner_score,
                    "player2_score": loser_score,
                    "winner_name": debbie,
                    "notes": "Featured match - Quarter-finals",
                }
            else:
                # Allison wins
                winner_score, loser_score = self.generate_match_score(is_early_round=False)
                match = {
                    "tournament_id": tournament["tournament_id"],
                    "round_num": random.randint(3, tournament["typical_rounds"] - 1),
                    "match_num": random.randint(1, 4),
                    "operator_name": debbie,
                    "player2_name": allison,
                    "operator_score": loser_score,
                    "player2_score": winner_score,
                    "winner_name": allison,
                    "notes": "Featured match - Semi-finals",
                }
            
            featured_matches.append(match)
        
        return featured_matches
    
    def generate_all_data(self, num_tournaments: int = 20, start_year: int = 2010) -> Dict:
        """Generate complete tournament and match data"""
        self.load_players()
        
        logger.info(f"Generating {num_tournaments} tournaments...")
        tournaments = self.generate_tournaments(num_tournaments, start_year)
        
        logger.info("Generating matches for tournaments...")
        all_matches = []
        for tournament in tournaments:
            matches = self.generate_matches_for_tournament(tournament)
            all_matches.extend(matches)
        
        logger.info("Adding featured matches (Debbie Teichert vs Allison Fisher)...")
        featured_matches = self.add_featured_matches(tournaments)
        all_matches.extend(featured_matches)
        
        logger.info(f"Generated {len(tournaments)} tournaments with {len(all_matches)} matches")
        logger.info(f"  - Featured matches: {len(featured_matches)}")
        
        return {
            "tournaments": tournaments,
            "matches": all_matches,
        }


def main():
    """Test the generator"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://rankingsbot_user:PASSWORD@rankings-bot-postgres:5432/rankingsbot")
    
    generator = TournamentSampleGenerator(DATABASE_URL)
    data = generator.generate_all_data(num_tournaments=20, start_year=2010)
    
    print("\n" + "="*60)
    print("TOURNAMENT SAMPLE DATA GENERATION COMPLETE")
    print("="*60)
    print(f"\nGenerated:")
    print(f"  • {len(data['tournaments'])} tournaments")
    print(f"  • {len(data['matches'])} matches")
    
    print("\nSample tournaments:")
    for t in data["tournaments"][:5]:
        print(f"  • {t['name']} ({t['date']}) - {t['location']}")
    
    print("\nSample matches:")
    for m in data["matches"][:5]:
        print(f"  • {m['operator_name']} vs {m['player2_name']}: {m['operator_score']}-{m['player2_score']}")
    
    # Find Debbie vs Allison matches
    featured = [m for m in data["matches"] if "Debbie" in m["operator_name"] and "Allison" in m["player2_name"]]
    print(f"\nFeatured matches (Debbie Teichert vs Allison Fisher): {len(featured)}")
    for m in featured:
        print(f"  • {m['operator_name']} vs {m['player2_name']}: {m['operator_score']}-{m['player2_score']} (Winner: {m['winner_name']})")
    
    print("\nUse scripts/import_tournament_history.py to import this data into the database.")


if __name__ == "__main__":
    main()
