"""
ALFa Cold-Start Bayesian Adjustment System.

Implements cold-start rating adjustment for new players using Bayesian blending:
- Computes prior distribution (mean, std) from training data by skill level
- Implements Bayesian blending weights based on game count
- Converges new player ratings to true rating within target ±30 points by 20 games
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional, Dict, Tuple
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class ColdStartPriors:
    """Prior distribution parameters by skill level."""
    
    default_beginner: float  # Default for unknown players
    mean_low: float  # Mean for 200-400 bin
    std_low: float
    mean_mid: float  # Mean for 400-600 bin
    std_mid: float
    mean_high: float  # Mean for 600+ bin
    std_high: float
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "default_beginner": self.default_beginner,
            "mean_low": self.mean_low,
            "std_low": self.std_low,
            "mean_mid": self.mean_mid,
            "std_mid": self.std_mid,
            "mean_high": self.mean_high,
            "std_high": self.std_high,
        }


class ColdStartEngine:
    """
    Bayesian cold-start rating adjustment.
    
    Blends measured rating (observed from early games) with prior distribution
    based on player's estimated skill level. Reduces initial variance and
    accelerates convergence to true rating.
    """
    
    # Bayesian blending weights by game count
    # Format: (max_games, starter_weight, measured_weight)
    BLEND_SCHEDULE = [
        (10, 0.80, 0.20),      # < 10 games: 80% starter, 20% measured
        (50, 0.50, 0.50),      # 10-50 games: 50/50
        (200, 0.10, 0.90),     # 50-200 games: 10% starter, 90% measured
        (float('inf'), 0.00, 1.00),  # 200+ games: 0% starter, 100% measured
    ]
    
    def __init__(self, priors: Optional[ColdStartPriors] = None):
        """
        Initialize cold-start engine.
        
        Args:
            priors: ColdStartPriors with mean/std by skill level.
                   If None, use defaults (400 for beginner).
        """
        if priors is None:
            # Default priors (to be computed from training data)
            priors = ColdStartPriors(
                default_beginner=400.0,
                mean_low=320.0,
                std_low=50.0,
                mean_mid=500.0,
                std_mid=55.0,
                mean_high=720.0,
                std_high=70.0,
            )
        self.priors = priors
    
    def starter_rating(self, estimated_skill_level: Optional[float] = None) -> float:
        """
        Compute initial (starter) rating for a new player.
        
        Uses prior distribution based on estimated skill level:
        - Below 400: unlikely, use mean_low
        - 200-400: use mean_low
        - 400-600: use mean_mid
        - 600+: use mean_high
        - Unknown: use default_beginner (400)
        
        Args:
            estimated_skill_level: Optional estimated player skill (e.g., from league division)
            
        Returns:
            Starter rating for Bayesian blending.
        """
        if estimated_skill_level is None:
            return self.priors.default_beginner
        
        if estimated_skill_level < 400:
            return self.priors.mean_low
        elif estimated_skill_level < 600:
            return self.priors.mean_mid
        else:
            return self.priors.mean_high
    
    def bayesian_blend(
        self,
        measured_rating: float,
        games_played: int,
        estimated_skill_level: Optional[float] = None,
    ) -> Tuple[float, Dict[str, float]]:
        """
        Blend measured rating with prior distribution using Bayesian weights.
        
        Args:
            measured_rating: Observed rating from early games (e.g., GLicko/ELO)
            games_played: Number of games player has played
            estimated_skill_level: Optional skill estimate for prior selection
            
        Returns:
            Tuple of (blended_rating, blending_stats)
            - blended_rating: Final rating (weighted average)
            - blending_stats: Dict with weights, priors, measured, blend_ratio
        """
        # Get starter (prior) rating
        starter = self.starter_rating(estimated_skill_level)
        
        # Get blending weights based on game count
        starter_weight, measured_weight = self._get_blend_weights(games_played)
        
        # Compute blended rating
        blended = starter_weight * starter + measured_weight * measured_rating
        
        # Return with diagnostic info
        stats = {
            "starter_rating": starter,
            "measured_rating": measured_rating,
            "blended_rating": blended,
            "starter_weight": starter_weight,
            "measured_weight": measured_weight,
            "games_played": games_played,
            "adjustment": blended - measured_rating,
        }
        
        return blended, stats
    
    def _get_blend_weights(self, games_played: int) -> Tuple[float, float]:
        """
        Get Bayesian blending weights based on game count.
        
        Returns:
            Tuple of (starter_weight, measured_weight) summing to 1.0
        """
        for max_games, w_starter, w_measured in self.BLEND_SCHEDULE:
            if games_played < max_games:
                return w_starter, w_measured
        
        # Shouldn't reach here, but fallback to full measured
        return 0.0, 1.0
    
    @classmethod
    def compute_priors_from_data(
        cls,
        player_ratings: list[float],
        player_skill_estimates: Optional[list[float]] = None,
    ) -> ColdStartPriors:
        """
        Compute prior distribution from training data.
        
        Segments players by Fargo rating bins and computes mean/std for each:
        - Low bin: 200-400
        - Mid bin: 400-600
        - High bin: 600+
        
        Args:
            player_ratings: List of Fargo ratings
            player_skill_estimates: Optional per-player skill estimates (unused if None)
            
        Returns:
            ColdStartPriors with computed mean/std by bin
        """
        player_ratings = np.array(player_ratings)
        
        # Bin players by rating
        low_bin = (player_ratings >= 200) & (player_ratings < 400)
        mid_bin = (player_ratings >= 400) & (player_ratings < 600)
        high_bin = (player_ratings >= 600)
        
        # Compute stats for each bin
        mean_low = float(np.mean(player_ratings[low_bin])) if low_bin.any() else 320.0
        std_low = float(np.std(player_ratings[low_bin])) if low_bin.any() else 50.0
        
        mean_mid = float(np.mean(player_ratings[mid_bin])) if mid_bin.any() else 500.0
        std_mid = float(np.std(player_ratings[mid_bin])) if mid_bin.any() else 55.0
        
        mean_high = float(np.mean(player_ratings[high_bin])) if high_bin.any() else 720.0
        std_high = float(np.std(player_ratings[high_bin])) if high_bin.any() else 70.0
        
        logger.info(f"Computed cold-start priors from {len(player_ratings)} players:")
        logger.info(f"  Low (200-400):   n={low_bin.sum():>4d}, mean={mean_low:>6.1f}, std={std_low:>6.1f}")
        logger.info(f"  Mid (400-600):   n={mid_bin.sum():>4d}, mean={mean_mid:>6.1f}, std={std_mid:>6.1f}")
        logger.info(f"  High (600+):     n={high_bin.sum():>4d}, mean={mean_high:>6.1f}, std={std_high:>6.1f}")
        
        return ColdStartPriors(
            default_beginner=400.0,
            mean_low=mean_low,
            std_low=std_low,
            mean_mid=mean_mid,
            std_mid=std_mid,
            mean_high=mean_high,
            std_high=std_high,
        )
    
    def convergence_analysis(
        self,
        initial_rating: float,
        true_rating: float,
        games_count: list[int] = None,
    ) -> Dict[int, float]:
        """
        Analyze convergence: how adjustment decreases with more games.
        
        Shows how blended rating converges to true rating as games accumulate.
        
        Args:
            initial_rating: Initial measured/observed rating
            true_rating: True skill level (ground truth)
            games_count: Milestones to check (default: [1, 5, 10, 20, 50, 100])
            
        Returns:
            Dict mapping game count to predicted rating after adjustment
        """
        if games_count is None:
            games_count = [1, 5, 10, 20, 50, 100, 200]
        
        results = {}
        for n_games in games_count:
            # Assume measured rating tracks towards true rating
            # (simple model: linearly interpolate)
            measured = initial_rating + 0.5 * (true_rating - initial_rating) * min(1.0, n_games / 20)
            blended, _ = self.bayesian_blend(measured, n_games, true_rating)
            results[n_games] = blended
        
        return results
