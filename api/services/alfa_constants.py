"""
Alfa Rating System Constants - Model A (Conservative)

The Alfa rating adjusts Fargo based on sustained tournament performance
patterns while avoiding overreaction to normal variance in elite play.

Key Principle for WPA/WPBA:
    Professionals compete without handicaps. Variance in tournament finish
    position is normal competitive variance, NOT sandbagging. A high Fargo
    player finishing poorly in a single tournament is just having a bad day.

Design Philosophy:
    - Fargo is the most reliable skill indicator (primary weight)
    - Only adjust for SUSTAINED patterns across multiple tournaments
    - Do not penalize single-tournament variance
    - Tournament strength matters (elite wins > weak field wins)
    - Constrain adjustments to prevent rating instability
"""

# ============================================================================
# MODEL A: CONSERVATIVE WEIGHTING (Recommended for WPA/WPBA)
# ============================================================================
# Best for professional/elite play where Fargo accurately reflects skill.
# Prioritizes rating stability over responsiveness to variance.

# Weighting Distribution
ALFA_BASE_WEIGHT = 0.85  # 85% - Fargo rating (most reliable)
ALFA_PATTERN_WEIGHT = 0.12  # 12% - Sustained pattern (10+ tournaments)
ALFA_CURRENT_WEIGHT = 0.03  # 3% - Current tournament (minimal variance impact)

# Deviation Constraints
ALFA_MAX_DEVIATION = 15.0  # Maximum ±15 points from Fargo rating
ALFA_MIN_DEVIATION = -15.0  # Minimum deviation (symmetric constraint)

# ============================================================================
# PATTERN ANALYSIS CONFIGURATION
# ============================================================================

# Minimum data requirements before adjusting from pure Fargo
MIN_TOURNAMENTS_FOR_PATTERN = 3  # Require at least 3 tournaments

# Pattern analysis window (use whichever provides more data)
PATTERN_WINDOW_TOURNAMENTS = 10  # Analyze most recent 10 tournaments
PATTERN_WINDOW_MONTHS = 6  # OR tournaments within last 6 months

# Expected performance percentile (0.5 = 50th percentile expected)
# For a field of 20 players, 50th percentile = 10th place finish
EXPECTED_FINISH_PERCENTILE = 0.5

# ============================================================================
# TOURNAMENT STRENGTH MULTIPLIERS
# ============================================================================
# Tournament strength amplifies pattern adjustments (not single-tournament).
# Elite field performances indicate higher true skill than regional events.

TOURNAMENT_STRENGTH = {
    "regional": 0.8,  # Local/regional events
    "national": 1.0,  # Standard national tournaments (baseline)
    "major": 1.3,  # US Open, World Championships
    "elite_invitational": 1.5,  # Derby City, Mosconi Cup, etc.
}

# Default strength when tournament type is unknown
DEFAULT_TOURNAMENT_STRENGTH = 1.0

# ============================================================================
# ADJUSTMENT SCALING
# ============================================================================
# These scales control how much pattern/current performance can shift Alfa.

# Pattern adjustment: sustained deviation from expected across many tournaments
# Example: Consistently finishing top 25% → +10 points max
PATTERN_ADJUSTMENT_SCALE = 20.0  # Max ±10 points from sustained pattern

# Current tournament adjustment: single event performance
# Example: Winning a tournament → +5 points max (minimal single-event impact)
CURRENT_ADJUSTMENT_SCALE = 10.0  # Max ±5 points from current tournament

# ============================================================================
# TIME DECAY (Optional)
# ============================================================================
# Weight recent tournaments more heavily than older ones in pattern analysis.
# Set to 0.0 to disable time decay (all tournaments weighted equally).

TIME_DECAY_RATE = 0.0  # 0.0 = no decay, 0.1 = 10% less weight per tournament back

# ============================================================================
# DATABASE UPDATE CONFIGURATION
# ============================================================================

# When to recalculate Alfa ratings
ALFA_RECALC_TRIGGER = "after_tournament"  # Options: "after_tournament", "batch_nightly"

# Cache TTL for computed Alfa ratings (seconds)
ALFA_CACHE_TTL = 300  # 5 minutes

# ============================================================================
# RATING BOUNDS (Validation)
# ============================================================================
# Sanity checks to prevent invalid ratings from calculations errors

MIN_VALID_ALFA_RATING = 200.0  # Below this is likely calculation error
MAX_VALID_ALFA_RATING = 900.0  # Above this is likely calculation error
MIN_VALID_FARGO_RATING = 200.0  # Minimum expected Fargo
MAX_VALID_FARGO_RATING = 850.0  # Maximum expected Fargo (world-class)

# ============================================================================
# FIELD STRENGTH CALCULATION
# ============================================================================
# Used to determine tournament strength when not explicitly provided

# Field strength calculated from average opponent Fargo
WEAK_FIELD_AVG_FARGO = 450.0  # Below this = weak field (0.8x multiplier)
STRONG_FIELD_AVG_FARGO = 650.0  # Above this = elite field (1.3x+ multiplier)

# ============================================================================
# EXPLAINABILITY THRESHOLDS
# ============================================================================
# For UI display of why Alfa differs from Fargo

SIGNIFICANT_DEVIATION_THRESHOLD = 5.0  # Show explanation if Alfa differs by ±5+
PATTERN_SIGNIFICANCE_THRESHOLD = 0.15  # 15%+ deviation from expected is significant

# ============================================================================
# PHASE 3: ADVANCED CONTEXT ADJUSTMENTS
# ============================================================================
# Enhanced tournament and player context for more accurate ratings

# Player Experience Weighting (based on tournament history)
EXPERIENCE_LEVELS = {
    "rookie": {"min_tournaments": 0, "max_tournaments": 5, "weight_multiplier": 0.9},     # Less stable ratings
    "developing": {"min_tournaments": 6, "max_tournaments": 15, "weight_multiplier": 1.0}, # Standard weighting
    "experienced": {"min_tournaments": 16, "max_tournaments": 50, "weight_multiplier": 1.1}, # More confident in patterns
    "veteran": {"min_tournaments": 51, "max_tournaments": float('inf'), "weight_multiplier": 1.2}, # High confidence
}

# Tournament Field Quality Indicators
FIELD_QUALITY_THRESHOLDS = {
    "weak": {"avg_fargo_threshold": 450.0, "multiplier": 0.8},      # Regional/local events
    "standard": {"avg_fargo_threshold": 550.0, "multiplier": 1.0},  # Normal tournaments
    "strong": {"avg_fargo_threshold": 650.0, "multiplier": 1.2},    # National/major events
    "elite": {"avg_fargo_threshold": 700.0, "multiplier": 1.4},     # World-class/elite events
}

# Video Analysis Integration Weights
VIDEO_ANALYSIS_WEIGHTS = {
    "technique_confidence": 0.25,    # Weight for technique assessment
    "strategy_confidence": 0.25,     # Weight for strategy assessment
    "overall_performance": 0.3,      # Weight for overall performance score
    "frame_quality": 0.2,            # Weight for video/analysis quality
    "max_video_adjustment": 12.0,    # Maximum rating points from video (±12)
    "min_frames_required": 10,       # Minimum frames for reliable analysis
    "video_freshness_days": 90,      # Video analysis considered fresh for N days
}

# Anomaly Detection Thresholds
ANOMALY_THRESHOLDS = {
    "sudden_rating_drop": -25.0,     # Flag if rating drops more than this in one update
    "unusual_performance": 3.0,      # Standard deviations from expected performance
    "inconsistent_results": 0.4,     # High variance in recent tournament finishes
    "rapid_improvement": 15.0,       # Flag suspiciously fast improvement
    "minimum_tournaments": 3,        # Minimum tournaments before anomaly detection
}

# Confidence Scoring Parameters
CONFIDENCE_SCORING = {
    "base_confidence": 0.7,          # Base confidence level
    "tournament_volume_bonus": 0.05, # Bonus per tournament (max +0.3)
    "recency_bonus": 0.1,            # Bonus for recent tournaments
    "consistency_bonus": 0.15,       # Bonus for consistent performance
    "video_evidence_bonus": 0.2,     # Bonus when video analysis available
    "field_quality_bonus": 0.1,      # Bonus for playing in strong fields
    "max_confidence": 0.95,          # Maximum possible confidence score
    "min_confidence": 0.3,           # Minimum possible confidence score
}

# Performance Convergence Optimization
CONVERGENCE_OPTIMIZATION = {
    "damping_factor": 0.8,           # Dampen rapid changes (0.8 = 80% of calculated change)
    "minimum_change_threshold": 0.5, # Don't update if change is less than 0.5 points
    "maximum_change_per_update": 5.0, # Cap single update changes to prevent volatility
    "history_smoothing_window": 5,   # Use last N tournaments for smoothing
    "trend_analysis_periods": 3,     # Number of periods to analyze trends
}

# ============================================================================
# HISTORICAL CONSTANTS (Documentation Only)
# ============================================================================
# Previous sandbagging detection logic has been removed as of 2026-02-17.
# Rationale: WPA/WPBA tournaments have no handicapping. Variance in finish
# position is normal competitive variance, not sandbagging.
#
# For future reference: Sandbagging detection is ONLY applicable to:
# - Handicapped league play (APA, BCA, etc.)
# - Amateur tournaments with handicap-based brackets
# - NOT applicable to professional straight-up competition (WPA/WPBA)
