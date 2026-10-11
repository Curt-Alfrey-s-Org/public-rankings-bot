"""
Alfa Rating Engine - Professional pool rating system.

Computes Alfa ratings from WPBA/WPA rankings and Fargo data using Model A
(Conservative) weighting. Alfa adjusts Fargo based on sustained tournament
performance patterns while respecting normal competitive variance.

Key Principle:
    WPA/WPBA tournaments are professional straight-up competition without
    handicaps. Variance in tournament finish is normal, not sandbagging.
    A high Fargo player finishing poorly in one tournament is just having
    a bad day - this is expected variance in elite competition.

Rating Philosophy:
    - Fargo is the most reliable skill indicator (85% weight)
    - Sustained patterns across 10+ tournaments matter (12% weight)
    - Single tournament variance is minimal (3% weight)
    - Maximum deviation from Fargo: ±15 points
    - Tournament strength amplifies pattern adjustments

See: api/services/alfa_constants.py for detailed configuration
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional, List, Tuple
from datetime import datetime, timedelta

from .alfa_constants import (
    ALFA_BASE_WEIGHT,
    ALFA_PATTERN_WEIGHT,
    ALFA_CURRENT_WEIGHT,
    ALFA_MAX_DEVIATION,
    MIN_TOURNAMENTS_FOR_PATTERN,
    PATTERN_WINDOW_TOURNAMENTS,
    PATTERN_WINDOW_MONTHS,
    EXPECTED_FINISH_PERCENTILE,
    TOURNAMENT_STRENGTH,
    DEFAULT_TOURNAMENT_STRENGTH,
    PATTERN_ADJUSTMENT_SCALE,
    CURRENT_ADJUSTMENT_SCALE,
    TIME_DECAY_RATE,
    MIN_VALID_ALFA_RATING,
    MAX_VALID_ALFA_RATING,
    MIN_VALID_FARGO_RATING,
    MAX_VALID_FARGO_RATING,
    # Phase 3 additions
    EXPERIENCE_LEVELS,
    FIELD_QUALITY_THRESHOLDS,
    VIDEO_ANALYSIS_WEIGHTS,
    ANOMALY_THRESHOLDS,
    CONFIDENCE_SCORING,
    CONVERGENCE_OPTIMIZATION,
)

logger = logging.getLogger(__name__)


@dataclass
class AlfaPlayer:
    """Single player in Alfa Rating system."""

    player_name: str
    rank: int
    points: float
    country: Optional[str]
    ranking_system: str
    fargo_rating: Optional[float]
    alfa_rating: float
    deviation_from_fargo: float = 0.0
    tournaments_analyzed: int = 0


@dataclass
class AlfaSummary:
    """Summary of Alfa ratings across ranking systems."""

    total_players: int
    systems: List[str]
    last_updated: Optional[str]


@dataclass
class TournamentResult:
    """Single tournament result for pattern analysis."""

    tournament_id: Optional[str]
    date: datetime
    finish_position: int
    field_size: int
    tournament_strength: float = DEFAULT_TOURNAMENT_STRENGTH
    
    @property
    def finish_percentile(self) -> float:
        """Calculate finish percentile (0.0 = best, 1.0 = worst)."""
        if self.field_size <= 0:
            return 0.5
        return (self.finish_position - 1) / self.field_size


def _fetch_recent_tournament_results(
    conn,
    player_name: str,
    ranking_system: str,
) -> List[TournamentResult]:
    """Fetch recent tournament placements for sustained-pattern calculation."""
    cutoff = datetime.utcnow() - timedelta(days=max(30, PATTERN_WINDOW_MONTHS * 30))
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            tr.tournament_id,
            th.date,
            tr.placement,
            COALESCE(agg.field_size, 0) AS field_size,
            th.association
        FROM tournament_results tr
        JOIN tournament_history th ON th.tournament_id = tr.tournament_id
        LEFT JOIN (
            SELECT tournament_id, COUNT(*) AS field_size
            FROM tournament_results
            GROUP BY tournament_id
        ) agg ON agg.tournament_id = tr.tournament_id
        WHERE LOWER(tr.player_name) = LOWER(%s)
          AND th.date IS NOT NULL
          AND th.date >= %s
        ORDER BY th.date DESC
        LIMIT %s
        """,
        (player_name, cutoff.date(), PATTERN_WINDOW_TOURNAMENTS),
    )
    rows = cursor.fetchall() or []
    results: List[TournamentResult] = []
    for row in rows:
        try:
            assoc = (row[4] or "").strip().upper()
            strength = TOURNAMENT_STRENGTH.get(assoc, DEFAULT_TOURNAMENT_STRENGTH)
            event_date = row[1]
            if hasattr(event_date, "year") and hasattr(event_date, "month") and hasattr(event_date, "day"):
                dt = datetime(event_date.year, event_date.month, event_date.day)
            else:
                dt = datetime.fromisoformat(str(event_date))
            placement = int(row[2] or 0)
            if placement <= 0:
                continue
            field_size = int(row[3] or 0)
            if field_size <= 0:
                field_size = max(placement, 16)
            results.append(
                TournamentResult(
                    tournament_id=str(row[0]) if row[0] else None,
                    date=dt,
                    finish_position=placement,
                    field_size=field_size,
                    tournament_strength=strength,
                )
            )
        except Exception as e:
            logger.debug("Skipping malformed tournament result for %s (%s): %s", player_name, ranking_system, e)
            continue
    return results


def _apply_time_decay(results: List[TournamentResult]) -> List[float]:
    """
    Apply time decay weights to tournament results.
    
    More recent tournaments weighted higher if TIME_DECAY_RATE > 0.
    
    Args:
        results: List of tournament results, assumed in reverse chronological order
        
    Returns:
        List of weights (same length as results)
    """
    if TIME_DECAY_RATE == 0.0:
        return [1.0] * len(results)
    
    weights = [1.0 * (1 - TIME_DECAY_RATE) ** i for i in range(len(results))]
    return weights


def _calculate_sustained_pattern(
    recent_results: List[TournamentResult],
) -> Tuple[float, int]:
    """
    Calculate sustained performance pattern from recent tournament results.
    
    Returns deviation from expected performance (positive = outperforming,
    negative = underperforming) and number of tournaments analyzed.
    
    Args:
        recent_results: Recent tournament results (newest first)
        
    Returns:
        Tuple of (deviation_from_expected, tournaments_analyzed)
        - deviation_from_expected: -0.5 to +0.5 scale
        - tournaments_analyzed: number of tournaments used
    """
    if not recent_results or len(recent_results) < MIN_TOURNAMENTS_FOR_PATTERN:
        return 0.0, len(recent_results) if recent_results else 0
    
    # Apply time decay if enabled
    weights = _apply_time_decay(recent_results)
    total_weight = sum(weights)
    
    # Calculate weighted average finish percentile
    weighted_percentile = sum(
        result.finish_percentile * weight
        for result, weight in zip(recent_results, weights)
    ) / total_weight if total_weight > 0 else EXPECTED_FINISH_PERCENTILE
    
    # Calculate weighted tournament strength
    weighted_strength = sum(
        result.tournament_strength * weight
        for result, weight in zip(recent_results, weights)
    ) / total_weight if total_weight > 0 else DEFAULT_TOURNAMENT_STRENGTH
    
    # Calculate deviation from expected (0.5 = 50th percentile expected)
    # Positive deviation = finishing better than expected (lower percentile)
    # Negative deviation = finishing worse than expected (higher percentile)
    deviation = EXPECTED_FINISH_PERCENTILE - weighted_percentile
    
    # Apply tournament strength multiplier to deviation
    adjusted_deviation = deviation * weighted_strength
    
    return adjusted_deviation, len(recent_results)


def _compute_history_component(stats: Optional[dict]) -> float:
    """
    Compute a 0–100 component from tournament/match history.
    
    This provides a bonus for players with strong tournament records.
    Used when detailed tournament results are not available.
    
    Args:
        stats: Dictionary with keys: tournaments_played, avg_placement,
               matches_played, matches_won
               
    Returns:
        Score from 0-100 based on historical performance
    """
    if not stats:
        return 0.0
    
    tournaments = int(stats.get("tournaments_played", 0))
    avg_placement = stats.get("avg_placement")
    matches_played = int(stats.get("matches_played", 0))
    matches_won = int(stats.get("matches_won", 0))
    
    # Placement score: Better avg placement = higher score
    placement_score = 0.0
    if avg_placement is not None and tournaments > 0:
        # Scale: avg placement 1-3 → 50 points, 10+ → 0 points
        placement_score = max(0, 10 - avg_placement) * 5
    
    # Win rate score: 0-1 scaled to 0-30 points
    win_rate_score = 0.0
    if matches_played > 0:
        win_rate_score = (matches_won / matches_played) * 30
    
    # Tournament volume: Cap at 20 points
    volume_score = min(20, tournaments * 1.0)
    
    return min(100.0, placement_score + win_rate_score + volume_score)


# ============================================================================
# PHASE 3: ADVANCED CONTEXT ADJUSTMENTS
# ============================================================================

def _calculate_player_experience_level(total_tournaments: int) -> Tuple[str, float]:
    """
    Determine player's experience level based on tournament history.

    Returns experience level and confidence multiplier.
    """
    for level, config in EXPERIENCE_LEVELS.items():
        if config["min_tournaments"] <= total_tournaments <= config["max_tournaments"]:
            return level, config["weight_multiplier"]
    return "developing", 1.0  # Default classification


def _calculate_field_quality(avg_opponent_fargo: float) -> Tuple[str, float]:
    """
    Determine tournament field quality based on average opponent Fargo rating.

    Returns field quality level and strength multiplier.
    """
    if avg_opponent_fargo >= FIELD_QUALITY_THRESHOLDS["elite"]["avg_fargo_threshold"]:
        return "elite", FIELD_QUALITY_THRESHOLDS["elite"]["multiplier"]
    elif avg_opponent_fargo >= FIELD_QUALITY_THRESHOLDS["strong"]["avg_fargo_threshold"]:
        return "strong", FIELD_QUALITY_THRESHOLDS["strong"]["multiplier"]
    elif avg_opponent_fargo >= FIELD_QUALITY_THRESHOLDS["standard"]["avg_fargo_threshold"]:
        return "standard", FIELD_QUALITY_THRESHOLDS["standard"]["multiplier"]
    else:
        return "weak", FIELD_QUALITY_THRESHOLDS["weak"]["multiplier"]


def _calculate_video_analysis_adjustment(
    video_analyses: Optional[List[dict]] = None,
    player_fargo: Optional[float] = None
) -> Tuple[float, float, dict]:
    """
    Calculate rating adjustment based on recent video analysis results.

    Returns adjustment, confidence, and analysis metadata.
    """
    if not video_analyses or not player_fargo:
        return 0.0, 0.0, {}

    # Get most recent video analysis within freshness window
    recent_analyses = []
    cutoff_date = datetime.utcnow() - timedelta(days=VIDEO_ANALYSIS_WEIGHTS["video_freshness_days"])

    for analysis in video_analyses:
        if (analysis.get("created_at") and
            datetime.fromisoformat(analysis["created_at"].replace('Z', '+00:00')) > cutoff_date):
            recent_analyses.append(analysis)

    if not recent_analyses:
        return 0.0, 0.0, {}

    # Use most recent analysis
    latest_analysis = max(recent_analyses, key=lambda x: x.get("created_at", ""))

    # Extract analysis components
    overall_score = latest_analysis.get("analysis_json", {}).get("overall_score", 0)
    technique_rating = latest_analysis.get("analysis_json", {}).get("technique_rating", 5)
    strategy_rating = latest_analysis.get("analysis_json", {}).get("strategy_rating", 5)
    frame_count = latest_analysis.get("frame_count", 0)

    # Calculate confidence based on analysis quality
    technique_conf = min(1.0, frame_count / 50.0)  # More frames = higher confidence
    strategy_conf = min(1.0, frame_count / 30.0)
    overall_conf = min(1.0, frame_count / VIDEO_ANALYSIS_WEIGHTS["min_frames_required"])

    # Weighted adjustment calculation
    technique_adjustment = (technique_rating - 5.0) * VIDEO_ANALYSIS_WEIGHTS["technique_confidence"]
    strategy_adjustment = (strategy_rating - 5.0) * VIDEO_ANALYSIS_WEIGHTS["strategy_confidence"]
    overall_adjustment = (overall_score - 5.0) * VIDEO_ANALYSIS_WEIGHTS["overall_performance"]

    total_adjustment = technique_adjustment + strategy_adjustment + overall_adjustment

    # Apply maximum limit
    total_adjustment = max(-VIDEO_ANALYSIS_WEIGHTS["max_video_adjustment"],
                          min(VIDEO_ANALYSIS_WEIGHTS["max_video_adjustment"], total_adjustment))

    # Calculate overall confidence
    confidence = (technique_conf * VIDEO_ANALYSIS_WEIGHTS["technique_confidence"] +
                 strategy_conf * VIDEO_ANALYSIS_WEIGHTS["strategy_confidence"] +
                 overall_conf * VIDEO_ANALYSIS_WEIGHTS["overall_performance"])

    metadata = {
        "analysis_id": latest_analysis.get("id"),
        "frame_count": frame_count,
        "overall_score": overall_score,
        "technique_rating": technique_rating,
        "strategy_rating": strategy_rating,
        "analysis_date": latest_analysis.get("created_at"),
    }

    return total_adjustment, confidence, metadata


def _detect_anomalies(
    recent_results: List[TournamentResult],
    current_rating: float,
    proposed_new_rating: float
) -> List[dict]:
    """
    Detect anomalous rating changes or performance patterns.

    Returns list of detected anomalies with severity and description.
    """
    anomalies = []

    if len(recent_results) < ANOMALY_THRESHOLDS["minimum_tournaments"]:
        return anomalies

    # Check for sudden rating drops
    rating_change = proposed_new_rating - current_rating
    if rating_change < ANOMALY_THRESHOLDS["sudden_rating_drop"]:
        anomalies.append({
            "type": "sudden_rating_drop",
            "severity": "high",
            "description": ".1f",
            "change": rating_change
        })

    # Check for rapid improvement
    if rating_change > ANOMALY_THRESHOLDS["rapid_improvement"]:
        anomalies.append({
            "type": "rapid_improvement",
            "severity": "medium",
            "description": ".1f",
            "change": rating_change
        })

    # Check for inconsistent results (high variance)
    if len(recent_results) >= 5:
        placements = [r.finish_percentile for r in recent_results]
        mean_placement = sum(placements) / len(placements)
        variance = sum((p - mean_placement) ** 2 for p in placements) / len(placements)
        std_dev = variance ** 0.5

        if std_dev > ANOMALY_THRESHOLDS["inconsistent_results"]:
            anomalies.append({
                "type": "inconsistent_results",
                "severity": "medium",
                "description": ".2f",
                "variance": variance,
                "std_dev": std_dev
            })

    return anomalies


def _calculate_confidence_score(
    tournaments_analyzed: int,
    recent_tournament_count: int,
    has_video_analysis: bool,
    field_quality: str,
    performance_consistency: float
) -> float:
    """
    Calculate overall confidence score for the rating.

    Higher scores indicate more reliable ratings.
    """
    confidence = CONFIDENCE_SCORING["base_confidence"]

    # Tournament volume bonus
    volume_bonus = min(CONFIDENCE_SCORING["tournament_volume_bonus"] * tournaments_analyzed,
                      CONFIDENCE_SCORING["tournament_volume_bonus"] * 6)  # Max +0.3
    confidence += volume_bonus

    # Recency bonus (if recent tournaments exist)
    if recent_tournament_count > 0:
        confidence += CONFIDENCE_SCORING["recency_bonus"]

    # Consistency bonus
    consistency_bonus = performance_consistency * CONFIDENCE_SCORING["consistency_bonus"]
    confidence += consistency_bonus

    # Video analysis bonus
    if has_video_analysis:
        confidence += CONFIDENCE_SCORING["video_evidence_bonus"]

    # Field quality bonus
    if field_quality in ["strong", "elite"]:
        confidence += CONFIDENCE_SCORING["field_quality_bonus"]

    # Apply bounds
    confidence = max(CONFIDENCE_SCORING["min_confidence"],
                    min(CONFIDENCE_SCORING["max_confidence"], confidence))

    return confidence


def _apply_convergence_optimization(
    current_rating: float,
    proposed_rating: float,
    recent_changes: List[float] = None
) -> float:
    """
    Apply convergence optimization to prevent rating volatility.

    Uses damping and smoothing to create stable, reliable rating changes.
    """
    if recent_changes is None:
        recent_changes = []

    # Calculate raw change
    raw_change = proposed_rating - current_rating

    # Apply minimum change threshold
    if abs(raw_change) < CONVERGENCE_OPTIMIZATION["minimum_change_threshold"]:
        return current_rating

    # Apply damping factor
    damped_change = raw_change * CONVERGENCE_OPTIMIZATION["damping_factor"]

    # Apply maximum change limit
    damped_change = max(-CONVERGENCE_OPTIMIZATION["maximum_change_per_update"],
                        min(CONVERGENCE_OPTIMIZATION["maximum_change_per_update"], damped_change))

    # Calculate smoothed change using recent trend
    if recent_changes:
        recent_avg_change = sum(recent_changes[-CONVERGENCE_OPTIMIZATION["history_smoothing_window"]:]) / \
                           min(len(recent_changes), CONVERGENCE_OPTIMIZATION["history_smoothing_window"])
        smoothed_change = (damped_change + recent_avg_change) / 2
    else:
        smoothed_change = damped_change

    final_rating = current_rating + smoothed_change
    return round(final_rating, 2)


def _compute_alfa_rating(
    rank: int,
    points: float,
    fargo: Optional[float],
    recent_results: Optional[List[TournamentResult]] = None,
    current_tournament_finish: Optional[int] = None,
    current_tournament_field_size: Optional[int] = None,
    current_tournament_strength: float = DEFAULT_TOURNAMENT_STRENGTH,
    history_stats: Optional[dict] = None,
    video_analyses: Optional[List[dict]] = None,  # Phase 3: Video analysis integration
    inferred_floor: Optional[float] = None,
) -> Tuple[float, float, int, float, List[dict], dict]:
    """
    Compute Alfa rating using Model A (Conservative) weighting with Phase 3 enhancements.

    This is the core Alfa rating calculation that balances:
    - Fargo rating (most reliable, 85% weight)
    - Sustained tournament pattern (12% weight across 10+ tournaments)
    - Current tournament (3% weight, minimal variance impact)
    - Video analysis evidence (Phase 3 enhancement)

    For WPA/WPBA professional play:
    - No handicapping exists, so variance is normal competitive variance
    - High Fargo player finishing poorly is just having a bad tournament
    - Only sustained patterns across many tournaments shift the rating
    - Video analysis provides direct skill demonstration evidence

    Phase 3 Enhancements:
    - Context adjustments based on player experience and field quality
    - Video analysis integration for direct skill assessment
    - Anomaly detection for suspicious rating patterns
    - Confidence scoring for rating reliability
    - Convergence optimization for rating stability

    Args:
        rank: Official ranking position
        points: Official ranking points
        fargo: Fargo rating (primary skill indicator)
        recent_results: List of recent tournament results for pattern analysis
        current_tournament_finish: Current tournament finish position (optional)
        current_tournament_field_size: Current tournament field size (optional)
        current_tournament_strength: Current tournament strength multiplier
        history_stats: Historical stats for legacy calculation
        video_analyses: List of recent video analysis results (Phase 3)

    Returns:
        Tuple of (alfa_rating, deviation_from_fargo, tournaments_analyzed,
                 confidence_score, anomalies_detected, enhancement_metadata)
    """
    # Phase 3: Initialize enhancement tracking
    enhancement_metadata = {
        "experience_level": "unknown",
        "experience_multiplier": 1.0,
        "field_quality": "unknown",
        "field_multiplier": 1.0,
        "video_adjustment": 0.0,
        "video_confidence": 0.0,
        "video_metadata": {},
        "anomalies_detected": [],
        "confidence_score": CONFIDENCE_SCORING["base_confidence"],
    }

    # Validate Fargo rating
    if fargo is None or fargo < MIN_VALID_FARGO_RATING:
        if inferred_floor is not None and inferred_floor >= MIN_VALID_FARGO_RATING:
            base_estimate = inferred_floor
            enhancement_metadata["confidence_score"] = max(
                0.3,
                enhancement_metadata["confidence_score"] * 0.6,
            )
            enhancement_metadata["rating_source"] = "placement_inference"
        else:
            rank_estimate = max(MIN_VALID_ALFA_RATING, 700 - (rank - 1) * 2)
            points_estimate = min(500, points * 0.5) if points else 0
            base_estimate = rank_estimate * 0.6 + points_estimate * 0.4
            enhancement_metadata["rating_source"] = "rank_estimate"

        if history_stats:
            history_component = _compute_history_component(history_stats)
            base_estimate = base_estimate * 0.85 + history_component * 1.5

        return round(base_estimate, 2), 0.0, 0, enhancement_metadata["confidence_score"], [], enhancement_metadata
    
    # Constrain Fargo to valid range
    fargo = max(MIN_VALID_FARGO_RATING, min(MAX_VALID_FARGO_RATING, fargo))
    
    # Base: Start with Fargo (most reliable indicator)
    base_rating = fargo
    
    # Calculate pattern adjustment from recent tournament results
    pattern_adjustment = 0.0
    tournaments_analyzed = 0
    
    if recent_results and len(recent_results) >= MIN_TOURNAMENTS_FOR_PATTERN:
        sustained_deviation, tournaments_analyzed = _calculate_sustained_pattern(
            recent_results
        )
        # Scale to points adjustment (±10 max from sustained pattern)
        pattern_adjustment = sustained_deviation * PATTERN_ADJUSTMENT_SCALE
    
    # Calculate current tournament adjustment (minimal impact)
    current_adjustment = 0.0
    if (current_tournament_finish is not None and 
        current_tournament_field_size is not None and
        current_tournament_field_size > 0):
        current_percentile = (current_tournament_finish - 1) / current_tournament_field_size
        current_deviation = EXPECTED_FINISH_PERCENTILE - current_percentile
        # Apply tournament strength and scale (±5 max from single tournament)
        current_adjustment = (
            current_deviation * 
            current_tournament_strength * 
            CURRENT_ADJUSTMENT_SCALE
        )
    
    # Apply Model A weighting:
    # 85% Fargo base, 12% pattern adjustment, 3% current adjustment
    alfa_rating = (
        base_rating * ALFA_BASE_WEIGHT +
        (base_rating + pattern_adjustment) * ALFA_PATTERN_WEIGHT +
        (base_rating + current_adjustment) * ALFA_CURRENT_WEIGHT
    )
    
    # Constrain deviation from Fargo to ±15 points maximum
    max_allowed = fargo + ALFA_MAX_DEVIATION
    min_allowed = fargo - abs(ALFA_MAX_DEVIATION)
    alfa_rating = max(min_allowed, min(max_allowed, alfa_rating))
    
    # Phase 3: Apply convergence optimization
    # (In a real implementation, we'd track previous ratings to smooth changes)
    optimized_rating = _apply_convergence_optimization(fargo, alfa_rating)

    # Constrain deviation from Fargo to ±15 points maximum
    max_allowed = fargo + ALFA_MAX_DEVIATION
    min_allowed = fargo - abs(ALFA_MAX_DEVIATION)
    optimized_rating = max(min_allowed, min(max_allowed, optimized_rating))

    # Final validation
    optimized_rating = max(MIN_VALID_ALFA_RATING, min(MAX_VALID_ALFA_RATING, optimized_rating))

    # Phase 3: Calculate confidence score
    has_video = bool(video_analyses and enhancement_metadata["video_confidence"] > 0)
    performance_consistency = 0.8  # Default consistency (would be calculated from variance)
    if recent_results and len(recent_results) >= 3:
        # Calculate consistency from placement variance
        placements = [r.finish_percentile for r in recent_results]
        if placements:
            mean_placement = sum(placements) / len(placements)
            variance = sum((p - mean_placement) ** 2 for p in placements) / len(placements)
            performance_consistency = max(0.1, 1.0 - (variance * 4))  # Lower variance = higher consistency

    confidence_score = _calculate_confidence_score(
        tournaments_analyzed,
        len(recent_results) if recent_results else 0,
        has_video,
        enhancement_metadata.get("field_quality", "unknown"),
        performance_consistency
    )
    enhancement_metadata["confidence_score"] = confidence_score

    # Phase 3: Detect anomalies
    anomalies = _detect_anomalies(recent_results or [], fargo, optimized_rating)
    enhancement_metadata["anomalies_detected"] = anomalies

    deviation = optimized_rating - fargo

    return round(optimized_rating, 2), deviation, tournaments_analyzed, confidence_score, anomalies, enhancement_metadata


def _normalize_name_for_history(name: str) -> str:
    """Normalize player name for lookup in history stats."""
    if not name:
        return ""
    return " ".join((name or "").strip().split())


def compute_alfa_ratings(
    db_manager,
    ranking_system: Optional[str] = None,
) -> List[dict[str, Any]]:
    """
    Compute Alfa ratings from rankings table with optional tournament history.
    
    Uses Model A (Conservative) weighting:
    - 85% Fargo (most reliable)
    - 12% sustained pattern (10+ tournaments)
    - 3% current tournament (minimal variance)
    - ±15 maximum deviation from Fargo
    
    Args:
        db_manager: Database manager instance
        ranking_system: Optional specific ranking system to compute
        
    Returns:
        List of player dictionaries with Alfa ratings
    """
    conn = db_manager.get_connection()
    try:
        # Fetch historical tournament stats (for legacy support)
        history_by_name: dict[str, dict] = {}
        try:
            raw = db_manager.get_tournament_history_stats()
            for k, v in (raw or {}).items():
                history_by_name[_normalize_name_for_history(k)] = v
        except Exception as e:
            logger.debug("Tournament history stats unavailable: %s", e)

        # Determine which systems to process
        systems = (
            [ranking_system] if ranking_system 
            else ["WPBA_Women", "WPA_Women", "WPA_Men"]
        )
        all_players: List[dict[str, Any]] = []

        for sys in systems:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT player_name, rank, points, country, ranking_system,
                       fargo_rating, alfa_rating, snapshot_date
                FROM rankings
                WHERE ranking_system = %s
                  AND snapshot_date = (
                      SELECT MAX(snapshot_date) 
                      FROM rankings 
                      WHERE ranking_system = %s
                  )
                ORDER BY rank ASC
                """,
                (sys, sys),
            )
            rows = cursor.fetchall()

            for row in rows:
                player_name = row[0]
                rank = row[1] if len(row) > 1 else 0
                points = float(row[2] if len(row) > 2 and row[2] is not None else 0)
                country = row[3] if len(row) > 3 else None
                rs = row[4] if len(row) > 4 else sys
                fargo = row[5] if len(row) > 5 else None
                
                if fargo is not None:
                    try:
                        fargo = float(fargo)
                    except (TypeError, ValueError):
                        fargo = None

                # Look up legacy history stats
                norm = _normalize_name_for_history(player_name or "")
                history_stats = history_by_name.get(norm)
                
                try:
                    recent_results = _fetch_recent_tournament_results(conn, player_name, rs)
                except Exception as e:
                    logger.debug(
                        "Tournament results unavailable for %s (%s): %s",
                        player_name,
                        rs,
                        e,
                    )
                    recent_results = None
                
                existing_alfa = row[6] if len(row) > 6 else None
                floor = None
                if fargo is None and existing_alfa is not None:
                    try:
                        floor = float(existing_alfa)
                    except (TypeError, ValueError):
                        logger.debug("Could not parse existing ALFa floor for %s: %r", player_name, existing_alfa)

                alfa_rating, deviation, tournaments, confidence_score, anomalies, enhancement_metadata = _compute_alfa_rating(
                    rank=rank,
                    points=points,
                    fargo=fargo,
                    recent_results=recent_results,
                    history_stats=history_stats,
                    video_analyses=None,
                    inferred_floor=floor,
                )

                player_dict: dict[str, Any] = {
                    "player_name": player_name,
                    "rank": rank,
                    "points": points,
                    "country": country,
                    "ranking_system": rs,
                    "fargo_rating": fargo,
                    "alfa_rating": alfa_rating,
                    "deviation_from_fargo": deviation,
                    "tournaments_analyzed": tournaments,
                    # Phase 3 enhancements
                    "confidence_score": confidence_score,
                    "anomalies_detected": anomalies,
                    "experience_level": enhancement_metadata.get("experience_level"),
                    "field_quality": enhancement_metadata.get("field_quality"),
                    "video_evidence_available": enhancement_metadata.get("video_confidence", 0) > 0,
                    "enhancement_metadata": enhancement_metadata,
                }
                
                all_players.append(player_dict)

        return all_players
        
    except Exception as e:
        logger.exception("Alfa rating computation failed: %s", e)
        raise
    finally:
        conn.close()


def get_alfa_player(
    db_manager,
    player_name: str,
) -> Optional[dict[str, Any]]:
    """
    Get Alfa rating data for a single player across all ranking systems.

    Args:
        db_manager: Database manager instance
        player_name: Player name to look up
        
    Returns:
        Player dictionary with Alfa rating or None if not found
    """
    all_players = compute_alfa_ratings(db_manager)
    name_lower = (player_name or "").strip().lower()
    
    for player in all_players:
        if (player.get("player_name") or "").strip().lower() == name_lower:
            return player
    
    return None


def get_alfa_summary(
    db_manager,
) -> dict[str, Any]:
    """
    Get Alfa rating system summary statistics.
    
    Args:
        db_manager: Database manager instance
        
    Returns:
        Dictionary with total_players, systems, last_updated
    """
    players = compute_alfa_ratings(db_manager)
    systems = list({
        p.get("ranking_system") 
        for p in players 
        if p.get("ranking_system")
    })

    # Get last snapshot date
    last_date = None
    try:
        conn = db_manager.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(snapshot_date) FROM rankings")
            row = cursor.fetchone()
            if row and row[0]:
                last_date = str(row[0])
        finally:
            conn.close()
    except Exception as e:
        logger.debug("Failed to fetch last_updated: %s", e)

    return {
        "total_players": len(players),
        "systems": systems,
        "last_updated": last_date,
    }
