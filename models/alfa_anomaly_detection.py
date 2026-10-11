"""
ALFa Anomaly Detection System.

Detects suspicious player patterns indicating possible cheating, skill misrepresentation,
or rating system issues. Computes 6 anomaly flags and combines into severity score.

Flags:
1. winning_weak_only: Evidence of only beating much weaker players
2. losing_strong_only: Evidence of only losing to much stronger players
3. rating_league_mismatch: Declared rating doesn't match league division
4. sudden_jump: Unexplained rapid rating increase
5. high_variance: Inconsistent win rate (high variance)
6. break_dominance_outlier: Unusual break-winning pattern
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Tuple
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class AnomalyFlags:
    """Set of anomaly flags for a single player."""
    
    player_id: str
    games_played: int
    rating: float
    
    # The 6 flags
    winning_weak_only: bool = False
    losing_strong_only: bool = False
    rating_league_mismatch: bool = False
    sudden_jump: bool = False
    high_variance: bool = False
    break_dominance_outlier: bool = False
    
    # Summary metrics
    anomaly_score: float = 0.0
    severity_level: str = "none"  # none, low (0-0.3), medium (0.3-0.7), high (0.7-1.0)
    flagged_count: int = 0
    
    def as_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "player_id": self.player_id,
            "games_played": self.games_played,
            "rating": self.rating,
            "winning_weak_only": self.winning_weak_only,
            "losing_strong_only": self.losing_strong_only,
            "rating_league_mismatch": self.rating_league_mismatch,
            "sudden_jump": self.sudden_jump,
            "high_variance": self.high_variance,
            "break_dominance_outlier": self.break_dominance_outlier,
            "anomaly_score": self.anomaly_score,
            "severity_level": self.severity_level,
            "flagged_count": self.flagged_count,
        }


@dataclass
class PlayerMatchHistory:
    """Match history for anomaly detection."""
    
    player_id: str
    rating: float
    games: List[Dict] = field(default_factory=list)
    # Each game dict must have: opponent_rating, won (bool), is_break (bool)


class AnomalyDetector:
    """
    Detects anomalies in player behavior and rating progression.
    
    Uses 6 flags weighted by relevance to combine into 0-1 anomaly score.
    """
    
    # Threshold differences for opponent comparisons (points)
    WEAK_THRESHOLD = -50      # Opponent is 50+ points below
    STRONG_THRESHOLD = 50     # Opponent is 50+ points above
    
    # Thresholds for suspicious patterns
    WEAK_ONLY_WINRATE_THRESHOLD = 0.80     # 80%+ wins vs weak only
    STRONG_ONLY_LOSSRATE_THRESHOLD = 0.80  # 80%+ losses vs strong only
    SUDDEN_JUMP_THRESHOLD = 40              # +40 points in period
    SUDDEN_JUMP_WINDOW = 5                  # 5 games
    HIGH_VARIANCE_THRESHOLD = 0.35          # Std dev of win%
    BREAK_DOMINANCE_THRESHOLD = 0.75        # 75%+ break win rate
    
    # Flag weights for anomaly score (must sum to 1.0)
    FLAG_WEIGHTS = {
        "winning_weak_only": 0.20,
        "losing_strong_only": 0.20,
        "rating_league_mismatch": 0.15,
        "sudden_jump": 0.25,
        "high_variance": 0.15,
        "break_dominance_outlier": 0.05,
    }
    
    def detect_anomalies(
        self,
        player_history: PlayerMatchHistory,
        league_division: Optional[str] = None,
        expected_rating_range: Optional[Tuple[float, float]] = None,
    ) -> AnomalyFlags:
        """
        Detect anomalies in player history.
        
        Args:
            player_history: PlayerMatchHistory with games
            league_division: Optional league division (e.g., "A", "B") for mismatch check
            expected_rating_range: Optional (low, high) rating range for division
            
        Returns:
            AnomalyFlags with flags and anomaly_score
        """
        flags = AnomalyFlags(
            player_id=player_history.player_id,
            games_played=len(player_history.games),
            rating=player_history.rating,
        )
        
        if flags.games_played < 3:
            # Not enough data for reliable anomaly detection
            return flags
        
        # Check each anomaly flag
        if self._check_winning_weak_only(player_history):
            flags.winning_weak_only = True
            flags.flagged_count += 1
        
        if self._check_losing_strong_only(player_history):
            flags.losing_strong_only = True
            flags.flagged_count += 1
        
        if league_division and expected_rating_range:
            if self._check_rating_league_mismatch(
                player_history.rating, expected_rating_range
            ):
                flags.rating_league_mismatch = True
                flags.flagged_count += 1
        
        if self._check_sudden_jump(player_history):
            flags.sudden_jump = True
            flags.flagged_count += 1
        
        if self._check_high_variance(player_history):
            flags.high_variance = True
            flags.flagged_count += 1
        
        if self._check_break_dominance_outlier(player_history):
            flags.break_dominance_outlier = True
            flags.flagged_count += 1
        
        # Compute anomaly score
        flags.anomaly_score = self._compute_anomaly_score(flags)
        flags.severity_level = self._severity_level(flags.anomaly_score)
        
        return flags
    
    def _check_winning_weak_only(self, history: PlayerMatchHistory) -> bool:
        """Flag if player wins 80%+ vs opponents 50+ pts below."""
        games_vs_weak = [
            g for g in history.games
            if g["opponent_rating"] < history.rating - self.WEAK_THRESHOLD
        ]
        
        if len(games_vs_weak) == 0:
            return False
        
        win_rate = sum(1 for g in games_vs_weak if g["won"]) / len(games_vs_weak)
        return win_rate >= self.WEAK_ONLY_WINRATE_THRESHOLD and len(games_vs_weak) >= 5
    
    def _check_losing_strong_only(self, history: PlayerMatchHistory) -> bool:
        """Flag if player loses 80%+ vs opponents 50+ pts above."""
        games_vs_strong = [
            g for g in history.games
            if g["opponent_rating"] > history.rating + self.STRONG_THRESHOLD
        ]
        
        if len(games_vs_strong) == 0:
            return False
        
        loss_rate = sum(1 for g in games_vs_strong if not g["won"]) / len(games_vs_strong)
        return loss_rate >= self.STRONG_ONLY_LOSSRATE_THRESHOLD and len(games_vs_strong) >= 5
    
    def _check_rating_league_mismatch(
        self, player_rating: float, expected_range: Tuple[float, float]
    ) -> bool:
        """Flag if player rating is far outside league division expectations."""
        low, high = expected_range
        # Flag if outside range by >100 points
        threshold = 100
        return player_rating < low - threshold or player_rating > high + threshold
    
    def _check_sudden_jump(self, history: PlayerMatchHistory) -> bool:
        """Flag if rating jumped +40 pts in 5-game window."""
        if len(history.games) < self.SUDDEN_JUMP_WINDOW:
            return False
        
        # Simulate rating progression (simplified; real system would track frame-by-frame)
        window = self.SUDDEN_JUMP_WINDOW
        for i in range(len(history.games) - window):
            # Estimate rating change from win/loss pattern
            window_wins = sum(1 for g in history.games[i:i+window] if g["won"])
            # Rough heuristic: each 5 wins ~ +20 pts
            rating_change = window_wins * 8
            
            if rating_change >= self.SUDDEN_JUMP_THRESHOLD:
                return True
        
        return False
    
    def _check_high_variance(self, history: PlayerMatchHistory) -> bool:
        """Flag if win percentage has high variance (>0.35 std dev)."""
        if len(history.games) < 10:
            return False
        
        # Compute rolling win% with 5-game window
        window = 5
        win_pcts = []
        for i in range(len(history.games) - window + 1):
            window_wins = sum(1 for g in history.games[i:i+window] if g["won"])
            win_pct = window_wins / window
            win_pcts.append(win_pct)
        
        variance = np.std(win_pcts) if win_pcts else 0.0
        return variance > self.HIGH_VARIANCE_THRESHOLD
    
    def _check_break_dominance_outlier(self, history: PlayerMatchHistory) -> bool:
        """Flag if break win rate is unusually high (>75%)."""
        break_games = [g for g in history.games if g.get("is_break", False)]
        
        if len(break_games) < 5:
            return False
        
        break_win_rate = sum(1 for g in break_games if g["won"]) / len(break_games)
        overall_win_rate = sum(1 for g in history.games if g["won"]) / len(history.games)
        
        # Flag if break win rate is 75%+ AND significantly higher than overall
        return (
            break_win_rate >= self.BREAK_DOMINANCE_THRESHOLD
            and (break_win_rate - overall_win_rate) > 0.15
        )
    
    def _compute_anomaly_score(self, flags: AnomalyFlags) -> float:
        """
        Compute weighted anomaly score (0-1) from flags.
        
        Combines flags using weights; score clusters around discrete values
        unless high-variance is present.
        """
        score = 0.0
        
        if flags.winning_weak_only:
            score += self.FLAG_WEIGHTS["winning_weak_only"]
        if flags.losing_strong_only:
            score += self.FLAG_WEIGHTS["losing_strong_only"]
        if flags.rating_league_mismatch:
            score += self.FLAG_WEIGHTS["rating_league_mismatch"]
        if flags.sudden_jump:
            score += self.FLAG_WEIGHTS["sudden_jump"]
        if flags.high_variance:
            score += self.FLAG_WEIGHTS["high_variance"]
        if flags.break_dominance_outlier:
            score += self.FLAG_WEIGHTS["break_dominance_outlier"]
        
        return min(1.0, score)
    
    def _severity_level(self, score: float) -> str:
        """Classify anomaly severity based on score."""
        if score < 0.3:
            return "low"
        elif score < 0.7:
            return "medium"
        else:
            return "high"


def analyze_anomalies_batch(
    player_histories: List[PlayerMatchHistory],
    detector: Optional[AnomalyDetector] = None,
) -> Tuple[List[AnomalyFlags], Dict[str, int]]:
    """
    Detect anomalies for batch of players.
    
    Args:
        player_histories: List of PlayerMatchHistory
        detector: Optional AnomalyDetector (creates new if None)
        
    Returns:
        Tuple of (anomaly_flags_list, statistics)
    """
    if detector is None:
        detector = AnomalyDetector()
    
    flags_list = []
    stats = {
        "total_players": len(player_histories),
        "flagged_players": 0,
        "low_severity": 0,
        "medium_severity": 0,
        "high_severity": 0,
        "avg_flags_per_player": 0.0,
    }
    
    total_flags = 0
    for history in player_histories:
        flags = detector.detect_anomalies(history)
        flags_list.append(flags)
        
        if flags.flagged_count > 0:
            stats["flagged_players"] += 1
        
        if flags.severity_level == "low":
            stats["low_severity"] += 1
        elif flags.severity_level == "medium":
            stats["medium_severity"] += 1
        elif flags.severity_level == "high":
            stats["high_severity"] += 1
        
        total_flags += flags.flagged_count
    
    stats["avg_flags_per_player"] = (
        total_flags / len(player_histories) if player_histories else 0.0
    )
    
    return flags_list, stats
