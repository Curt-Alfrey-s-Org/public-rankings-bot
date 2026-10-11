"""
Live Rating Engine - Real-time Est. Rating Updates

Computes and updates player est_ratings on every rack completion during live tournament play.
Tracks rating transitions with full audit trail for transparency and debugging.

Key Features:
- Elo-style rating updates based on game outcomes
- Confidence scoring based on opponent strength and game context
- Robustness tracking (number of games played)
- Full audit trail with before/after ratings
- Real-time broadcasting of rating changes
"""

import logging
from datetime import datetime
from typing import Dict, Optional, Tuple, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RatingTransition:
    """Represents a rating change event."""
    player_id: str
    player_name: str
    previous_rating: Optional[float]
    new_rating: float
    confidence: float
    robustness: int
    change_amount: float
    formula_version: str = "live_elo_v1"


@dataclass
class GameContext:
    """Context information about a completed game."""
    game_id: int
    match_id: str
    tournament_id: str
    player_id: str
    opponent_id: str
    player_name: str
    opponent_name: str
    outcome: str  # 'win' or 'loss'
    opponent_rating: Optional[float]
    game_metadata: Dict[str, Any]


class LiveRatingEngine:
    """Engine for computing live est_rating updates."""

    # Elo-style constants (defaults; may be overridden by rating_calibration_params)
    K_FACTOR_BASE = 32  # Base K-factor for rating updates
    K_FACTOR_SCALING = 400  # Scaling factor for expected score calculation
    MIN_RATING = 100  # Minimum possible rating
    MAX_RATING = 1000  # Maximum possible rating

    # Confidence and robustness constants
    CONFIDENCE_BASE = 0.5  # Starting confidence for new players
    CONFIDENCE_GROWTH_RATE = 0.1  # How fast confidence grows with games
    MAX_CONFIDENCE = 0.95  # Maximum confidence level
    MIN_GAMES_FOR_HIGH_CONFIDENCE = 10
    # EST should not be more than this many points below Fargo when both exist
    FARGO_FLOOR_SLACK = 50

    def __init__(self, db_manager):
        """Initialize with database manager; load calibrated params when present."""
        self.db = db_manager
        self.k_factor_base = float(self.K_FACTOR_BASE)
        self.confidence_base = float(self.CONFIDENCE_BASE)
        self.confidence_growth_rate = float(self.CONFIDENCE_GROWTH_RATE)
        self.formula_version = "live_elo_v1"
        self._load_calibration_params()

    def _load_calibration_params(self) -> None:
        """Best-effort load of latest est params from rating_calibration_params."""
        try:
            conn = self.db.get_connection()
            cur = conn.cursor()
            cur.execute(
                """
                SELECT DISTINCT ON (parameter_name)
                    parameter_name, parameter_value
                FROM rating_calibration_params
                WHERE rating_type = 'est'
                ORDER BY parameter_name, effective_date DESC
                """
            )
            rows = cur.fetchall()
            conn.close()
            if not rows:
                return
            calibrated = False
            for name, value in rows:
                if value is None:
                    continue
                key = str(name).lower()
                val = float(value)
                if key in ("k_factor_base", "k_factor"):
                    self.k_factor_base = val
                    calibrated = True
                elif key == "confidence_base":
                    self.confidence_base = val
                    calibrated = True
                elif key == "confidence_growth_rate":
                    self.confidence_growth_rate = val
                    calibrated = True
            if calibrated:
                self.formula_version = "live_elo_v1_calibrated"
                logger.info(
                    "LiveRatingEngine using calibrated params k=%s conf_base=%s version=%s",
                    self.k_factor_base,
                    self.confidence_base,
                    self.formula_version,
                )
        except Exception as e:
            logger.debug("LiveRatingEngine calibration load skipped: %s", e)

    def calculate_expected_score(self, player_rating: float, opponent_rating: float) -> float:
        """Calculate expected score using Elo formula."""
        return 1 / (1 + 10 ** ((opponent_rating - player_rating) / self.K_FACTOR_SCALING))

    def calculate_rating_update(self, player_rating: float, opponent_rating: float,
                               actual_score: float, confidence_multiplier: float = 1.0) -> float:
        """
        Calculate rating change using modified Elo formula.

        Args:
            player_rating: Current player rating
            opponent_rating: Opponent's rating
            actual_score: 1.0 for win, 0.0 for loss
            confidence_multiplier: Adjusts K-factor based on confidence

        Returns:
            Rating change amount (positive for wins, negative for losses)
        """
        expected_score = self.calculate_expected_score(player_rating, opponent_rating)
        k_factor = self.k_factor_base * confidence_multiplier

        return k_factor * (actual_score - expected_score)

    def calculate_confidence(self, current_robustness: int) -> float:
        """Calculate confidence score based on number of games played."""
        if current_robustness == 0:
            return self.confidence_base

        # Confidence grows logarithmically with games played
        confidence = self.confidence_base + (
            self.confidence_growth_rate
            * min(current_robustness, self.MIN_GAMES_FOR_HIGH_CONFIDENCE)
        )
        return min(confidence, self.MAX_CONFIDENCE)

    def get_player_current_rating(self, player_id: str) -> Tuple[Optional[float], float, int]:
        """
        Get player's current est_rating, confidence, and robustness.

        Returns:
            (rating, confidence, robustness)
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT est_rating, est_rating_confidence, est_rating_robustness
            FROM players WHERE player_id = %s
        """, (player_id,))

        row = cursor.fetchone()
        conn.close()

        if row:
            rating, confidence, robustness = row
            # Handle None values
            rating = rating or 500.0  # Default rating
            confidence = confidence or self.confidence_base
            robustness = robustness or 0
            return rating, confidence, robustness

        return None, self.confidence_base, 0

    def get_player_fargo(self, player_id: str) -> Optional[float]:
        """Get player's Fargo score from players table (for EST floor)."""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT fargo_score FROM players WHERE player_id = %s", (player_id,))
        row = cursor.fetchone()
        conn.close()
        if row and row[0] is not None:
            return float(row[0])
        return None

    def _apply_fargo_floor(self, rating: float, player_id: str) -> float:
        """Ensure EST is not unreasonably below Fargo when both exist."""
        fargo = self.get_player_fargo(player_id)
        if fargo is not None:
            floor = fargo - self.FARGO_FLOOR_SLACK
            return max(rating, floor)
        return rating

    def update_player_rating(self, transition: RatingTransition) -> bool:
        """Update player's rating in database and set est_rating_trend (1=up, -1=down, 0=stable)."""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        prev = transition.previous_rating
        new = transition.new_rating
        if prev is not None and new is not None:
            trend = 1 if new > prev else (-1 if new < prev else 0)
        else:
            trend = 0
        try:
            cursor.execute("""
                UPDATE players SET
                    est_rating = %s,
                    est_rating_confidence = %s,
                    est_rating_robustness = %s,
                    est_rating_last_updated = CURRENT_TIMESTAMP,
                    est_rating_formula_version = %s,
                    est_rating_trend = %s
                WHERE player_id = %s
            """, (
                transition.new_rating,
                transition.confidence,
                transition.robustness,
                transition.formula_version,
                trend,
                transition.player_id
            ))

            success = cursor.rowcount > 0
            conn.commit()
            return success

        except Exception as e:
            logger.error(f"Failed to update player rating: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def record_rating_transition(self, game_context: GameContext,
                               transition: RatingTransition) -> bool:
        """Record rating transition in audit table."""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        try:
            import json
            cursor.execute("""
                INSERT INTO est_rating_transitions (
                    player_id, player_name, match_id, game_id,
                    previous_est_rating, new_est_rating, formula_version,
                    confidence, robustness, rating_change,
                    opponent_id, opponent_name, opponent_rating,
                    game_outcome, game_context, tournament_id
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                transition.player_id,
                transition.player_name,
                game_context.match_id,
                game_context.game_id,
                transition.previous_rating,
                transition.new_rating,
                transition.formula_version,
                transition.confidence,
                transition.robustness,
                transition.change_amount,
                game_context.opponent_id,
                game_context.opponent_name,
                game_context.opponent_rating,
                game_context.outcome,
                json.dumps(game_context.game_metadata),
                game_context.tournament_id
            ))

            conn.commit()
            return True

        except Exception as e:
            logger.error(f"Failed to record rating transition: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def process_game_completion(self, game_context: GameContext) -> Optional[RatingTransition]:
        """
        Process a completed game and update player's rating.

        Args:
            game_context: Context about the completed game

        Returns:
            RatingTransition if successful, None if failed
        """
        try:
            # Get current player rating
            current_rating, current_confidence, current_robustness = self.get_player_current_rating(
                game_context.player_id
            )

            # Get opponent rating (needed for seeding if player has no rating, and for Elo update)
            opponent_rating, _, _ = self.get_player_current_rating(game_context.opponent_id)

            # If player has no rating yet, seed from this game: who they beat/lost to
            if current_rating is None:
                if opponent_rating is not None:
                    bump = self.k_factor_base
                    actual_score = 1.0 if game_context.outcome == 'win' else 0.0
                    current_rating = opponent_rating + (bump if actual_score == 1.0 else -bump)
                    current_rating = max(self.MIN_RATING, min(self.MAX_RATING, current_rating))
                    current_rating = self._apply_fargo_floor(current_rating, game_context.player_id)
                    current_confidence = self.confidence_base
                    current_robustness = 0
                    logger.info(
                        "Seeded EST for player %s from opponent %s (outcome=%s): initial_rating=%.1f",
                        game_context.player_id, game_context.opponent_id, game_context.outcome, current_rating
                    )
                else:
                    logger.warning(
                        "No rating for player %s and opponent %s has no EST; cannot seed",
                        game_context.player_id, game_context.opponent_id
                    )
                    return None

            if opponent_rating is None:
                opponent_rating = current_rating  # Default to same rating if opponent unknown

            # Calculate rating update
            actual_score = 1.0 if game_context.outcome == 'win' else 0.0
            rating_change = self.calculate_rating_update(
                current_rating, opponent_rating, actual_score, current_confidence
            )

            # Apply rating change with bounds checking
            new_rating = max(self.MIN_RATING, min(self.MAX_RATING, current_rating + rating_change))
            new_rating = self._apply_fargo_floor(new_rating, game_context.player_id)

            # Update robustness and confidence
            new_robustness = current_robustness + 1
            new_confidence = self.calculate_confidence(new_robustness)

            # Create transition record
            transition = RatingTransition(
                player_id=game_context.player_id,
                player_name=game_context.player_name,
                previous_rating=current_rating,
                new_rating=new_rating,
                confidence=new_confidence,
                robustness=new_robustness,
                change_amount=rating_change,
                formula_version=self.formula_version,
            )

            # Update player rating
            if not self.update_player_rating(transition):
                logger.error(f"Failed to update rating for player {game_context.player_id}")
                return None

            # Record transition in audit table
            if not self.record_rating_transition(game_context, transition):
                logger.warning(f"Failed to record rating transition audit for player {game_context.player_id}")

            logger.info(
                "EST update player=%s %.1f -> %.1f (change=%.1f) confidence=%.2f",
                game_context.player_id, current_rating, new_rating, rating_change, new_confidence
            )

            return transition

        except Exception as e:
            logger.error(f"Error processing game completion: {e}")
            return None

    def get_player_rating_history(self, player_id: str, limit: int = 50) -> list:
        """Get recent rating transitions for a player."""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                created_at,
                previous_est_rating,
                new_est_rating,
                rating_change,
                confidence,
                robustness,
                opponent_name,
                game_outcome,
                tournament_id
            FROM est_rating_transitions
            WHERE player_id = %s
            ORDER BY created_at DESC
            LIMIT %s
        """, (player_id, limit))

        transitions = []
        for row in cursor.fetchall():
            transitions.append({
                'timestamp': row[0],
                'previous_rating': row[1],
                'new_rating': row[2],
                'change': row[3],
                'confidence': row[4],
                'robustness': row[5],
                'opponent': row[6],
                'outcome': row[7],
                'tournament_id': row[8]
            })

        conn.close()
        return transitions

    def seed_est_from_tournament_placement(self, player_id: str) -> Optional[float]:
        """
        Seed EST for a player with no rating using their rank in tournaments (rankings table).
        Uses field Fargo ratings: implied rating = percentile of field corresponding to finish position.
        Returns the seeded rating if successful, else None.
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT first_name, last_name FROM players WHERE player_id = %s",
                (player_id,),
            )
            row = cursor.fetchone()
            if not row:
                conn.close()
                return None
            first, last = (row[0] or "").strip(), (row[1] or "").strip()
            name_first_last = f"{first} {last}".strip()
            name_last_first = f"{last}, {first}".strip() if (last and first) else name_first_last

            # Rows where this player appears (any system/snapshot)
            cursor.execute(
                """
                SELECT ranking_system, snapshot_date, position, fargo_rating
                FROM rankings
                WHERE (player_name = %s OR player_name = %s)
                ORDER BY snapshot_date DESC
                """,
                (name_first_last, name_last_first),
            )
            player_rows = cursor.fetchall()
            if not player_rows:
                conn.close()
                return None

            implied_ratings = []
            seen = set()
            for system, snapshot, position, _ in player_rows:
                key = (system, str(snapshot))
                if key in seen:
                    continue
                seen.add(key)
                if position is None or position < 1:
                    continue
                # Field ratings for this snapshot (descending)
                cursor.execute(
                    """
                    SELECT fargo_rating FROM rankings
                    WHERE ranking_system = %s AND snapshot_date = %s AND fargo_rating IS NOT NULL
                    ORDER BY fargo_rating DESC NULLS LAST
                    """,
                    (system, snapshot),
                )
                field_ratings = [float(r[0]) for r in cursor.fetchall() if r[0] is not None]
                if not field_ratings:
                    continue
                # Position 1 = best -> index 0; position P -> index P-1 (capped)
                idx = min(position - 1, len(field_ratings) - 1)
                implied_ratings.append(field_ratings[idx])

            if not implied_ratings:
                conn.close()
                return None

            initial_rating = sum(implied_ratings) / len(implied_ratings)
            initial_rating = max(self.MIN_RATING, min(self.MAX_RATING, initial_rating))
            initial_rating = self._apply_fargo_floor(initial_rating, player_id)

            cursor.execute(
                """
                UPDATE players SET
                    est_rating = %s,
                    est_rating_confidence = %s,
                    est_rating_robustness = 0,
                    est_rating_last_updated = CURRENT_TIMESTAMP,
                    est_rating_formula_version = 'placement_seed_v1',
                    est_rating_trend = 0
                WHERE player_id = %s
                """,
                (initial_rating, self.CONFIDENCE_BASE, player_id),
            )
            conn.commit()
            logger.info(
                "Seeded EST for player %s from tournament placement: %.1f (from %d snapshots)",
                player_id, initial_rating, len(implied_ratings),
            )
            conn.close()
            return initial_rating
        except Exception as e:
            logger.exception("seed_est_from_tournament_placement failed for %s: %s", player_id, e)
            try:
                conn.rollback()
            except Exception as e:
                logger.debug("Cleanup error: %s", e)
            try:
                conn.close()
            except Exception as e:
                logger.debug("Cleanup error: %s", e)
            return None