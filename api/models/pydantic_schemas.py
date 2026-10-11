"""
Pydantic request/response models for Alfa Rating prediction endpoints.

Comprehensive validation for:
- Prediction requests (POST /api/alfa/predict)
- Explanation requests (POST /api/alfa/explain)
- Player lookups (GET /api/alfa/player/{player_id})
- Player comparisons (GET /api/alfa/comparison/{operator_id}/{player2_id})
"""

from typing import Optional, List
from pydantic import BaseModel, Field, validator, root_validator
from datetime import datetime


# ============================================================================
# REQUEST MODELS
# ============================================================================


class AlfaPredictRequest(BaseModel):
    """Request model for POST /api/alfa/predict endpoint."""

    operator_id: int = Field(..., description="Player 1 ID", gt=0)
    player2_id: int = Field(..., description="Player 2 ID", gt=0)
    race_to: int = Field(..., description="Race-to value (2-15)", ge=2, le=15)
    table_size: str = Field(..., description="Table size", pattern="^(7ft|8ft|9ft|10ft|8.5ft)$")
    format: str = Field(..., description="Game format", pattern="^(9-ball|10-ball|8-ball|mixed)$")
    location: str = Field(..., description="Venue location code")
    match_id: Optional[str] = Field(None, description="Optional match identifier for tracking")

    @validator("operator_id", "player2_id", pre=True)
    def validate_player_ids_differ(cls, v, values):
        """Ensure player IDs are different."""
        if "operator_id" in values and v == values["operator_id"]:
            raise ValueError("operator_id and player2_id must be different")
        return v

    class Config:
        example = {
            "operator_id": 123,
            "player2_id": 456,
            "race_to": 11,
            "table_size": "9ft",
            "format": "9-ball",
            "location": "silk_city_billiards",
            "match_id": "match_20260216_001",
        }


class AlfaExplainRequest(BaseModel):
    """Request model for POST /api/alfa/explain endpoint."""

    match_id: str = Field(..., description="Match ID to explain", min_length=1, max_length=255)

    class Config:
        example = {
            "match_id": "match_20260216_001",
        }


# ============================================================================
# RESPONSE MODELS
# ============================================================================


class PredictionFactor(BaseModel):
    """Single factor contributing to prediction."""

    name: str = Field(..., description="Factor name (e.g., 'rating_gap', 'table_size')")
    contribution: float = Field(..., description="Contribution to probability (-1 to 1)")
    weight: float = Field(..., description="Factor importance (0-1)")
    direction: Optional[str] = Field(None, description="favors_p1 or favors_p2")

    class Config:
        example = {
            "name": "rating_gap",
            "contribution": 0.15,
            "weight": 0.8,
            "direction": "favors_p1",
        }


class AlfaPredictResponse(BaseModel):
    """Response model for POST /api/alfa/predict endpoint."""

    match_id: Optional[str] = Field(None, description="Match identifier")
    predicted_win_prob_p1: float = Field(
        ..., description="Player 1 win probability (0-1)", ge=0, le=1
    )
    predicted_win_prob_p2: float = Field(
        ..., description="Player 2 win probability (0-1)", ge=0, le=1
    )
    factors: List[PredictionFactor] = Field(
        ..., description="Factors contributing to prediction"
    )
    confidence: float = Field(
        ..., description="Model confidence (0-1)", ge=0, le=1
    )
    predicted_race_length: Optional[float] = Field(
        None, description="Estimated game length in minutes"
    )
    prediction_brier_score: Optional[float] = Field(
        None, description="Expected calibration metric"
    )
    model_version: str = Field(
        ..., description="Model version used (e.g., 'alfa_logistic_v1')"
    )
    timestamp: datetime = Field(..., description="Prediction timestamp")

    class Config:
        example = {
            "match_id": "match_20260216_001",
            "predicted_win_prob_p1": 0.65,
            "predicted_win_prob_p2": 0.35,
            "factors": [
                {
                    "name": "rating_gap",
                    "contribution": 0.15,
                    "weight": 0.8,
                    "direction": "favors_p1",
                },
                {
                    "name": "table_size_comfort",
                    "contribution": 0.08,
                    "weight": 0.5,
                    "direction": "favors_p1",
                },
            ],
            "confidence": 0.82,
            "predicted_race_length": 45.2,
            "model_version": "alfa_logistic_v1",
            "timestamp": "2026-02-16T10:30:00Z",
        }


class AnomalyFlag(BaseModel):
    """Single anomaly flag."""

    flag_name: str = Field(..., description="Flag type")
    description: Optional[str] = Field(None, description="Flag description")
    severity: str = Field(..., description="low, medium, or high")
    severity_score: float = Field(..., description="Numeric severity (0-1)", ge=0, le=1)
    explanation: Optional[str] = Field(None, description="Human-readable explanation")

    class Config:
        example = {
            "flag_name": "winning_weak_only",
            "description": "Player wins primarily against weaker opponents",
            "severity": "medium",
            "severity_score": 0.65,
            "explanation": "Player's win rate drops 45% against rated players",
        }


class AlfaExplainResponse(BaseModel):
    """Response model for POST /api/alfa/explain endpoint."""

    match_id: str = Field(..., description="Match ID")
    match_details: dict = Field(..., description="Match metadata")
    predicted_prob_p1: float = Field(
        ..., description="Predicted win probability for player 1"
    )
    predicted_prob_p2: float = Field(
        ..., description="Predicted win probability for player 2"
    )
    actual_winner_id: Optional[int] = Field(None, description="Actual winner (if played)")
    actual_result: Optional[str] = Field(
        None, description="Win/loss for player 1 (or 'not_played')"
    )
    prediction_error: Optional[float] = Field(
        None, description="Brier score if match was played"
    )
    factors_breakdown: List[PredictionFactor] = Field(
        ..., description="Factor contributions"
    )
    anomaly_flags: List[AnomalyFlag] = Field(..., description="Detected anomalies")
    confidence: float = Field(..., description="Model confidence (0-1)")

    class Config:
        example = {
            "match_id": "match_20260216_001",
            "match_details": {
                "operator_id": 123,
                "player2_id": 456,
                "table_size": "9ft",
                "format": "9-ball",
                "race_to": 11,
            },
            "predicted_prob_p1": 0.65,
            "predicted_prob_p2": 0.35,
            "actual_winner_id": 123,
            "actual_result": "win",
            "prediction_error": 0.1225,
            "factors_breakdown": [],
            "anomaly_flags": [],
            "confidence": 0.82,
        }


class RatingHistory(BaseModel):
    """Historical rating data point."""

    date: str = Field(..., description="Date (ISO format)")
    rating: float = Field(..., description="Alfa rating on that date")
    confidence: float = Field(..., description="Confidence in rating (0-1)")

    class Config:
        example = {
            "date": "2026-02-16",
            "rating": 675.5,
            "confidence": 0.92,
        }


class ColdStartProgress(BaseModel):
    """Cold start progress for new players."""

    games_played: int = Field(..., description="Games since registration")
    confidence_estimate: float = Field(..., description="Confidence in rating (0-1)")
    target_confidence: float = Field(
        default=0.85, description="Target confidence for convergence"
    )
    games_to_convergence: int = Field(
        ..., description="Estimated games to reach target confidence"
    )

    class Config:
        example = {
            "games_played": 8,
            "confidence_estimate": 0.62,
            "target_confidence": 0.85,
            "games_to_convergence": 12,
        }


class AlfaPlayerResponse(BaseModel):
    """Response model for GET /api/alfa/player/{player_id}."""

    player_id: int = Field(..., description="Player ID")
    player_name: Optional[str] = Field(None, description="Player name")
    current_rating: float = Field(..., description="Current Alfa rating")
    rating_confidence: float = Field(..., description="Confidence in rating (0-1)")
    games_played: int = Field(..., description="Total games played")
    anomaly_score: float = Field(..., description="Anomaly score (0-1)")
    rating_history: List[RatingHistory] = Field(
        ..., description="Last 30 days of ratings"
    )
    cold_start_progress: Optional[ColdStartProgress] = Field(
        None, description="Cold start info (if new player)"
    )
    last_update: datetime = Field(..., description="Last rating update timestamp")
    robustness: int = Field(..., description="Number of validated games")

    class Config:
        example = {
            "player_id": 123,
            "player_name": "John Doe",
            "current_rating": 675.5,
            "rating_confidence": 0.92,
            "games_played": 45,
            "anomaly_score": 0.15,
            "rating_history": [
                {"date": "2026-02-16", "rating": 675.5, "confidence": 0.92},
                {"date": "2026-02-15", "rating": 672.1, "confidence": 0.91},
            ],
            "cold_start_progress": None,
            "last_update": "2026-02-16T10:30:00Z",
            "robustness": 45,
        }


class HeadToHeadStats(BaseModel):
    """Head-to-head history between 2 players."""

    total_matches: int = Field(..., description="Total matches between players")
    operator_wins: int = Field(..., description="Player 1 match wins")
    player2_wins: int = Field(..., description="Player 2 match wins")
    win_rate_p1: float = Field(..., description="Player 1 win rate in H2H")

    class Config:
        example = {
            "total_matches": 12,
            "operator_wins": 7,
            "player2_wins": 5,
            "win_rate_p1": 0.583,
        }


class PlayerComparison(BaseModel):
    """Comparison data for two players."""

    operator_id: int = Field(..., description="Player 1 ID")
    player2_id: int = Field(..., description="Player 2 ID")
    operator_name: Optional[str] = Field(None, description="Player 1 name")
    player2_name: Optional[str] = Field(None, description="Player 2 name")
    fargo_diff: Optional[float] = Field(None, description="Fargo rating difference")
    alfa_diff: float = Field(..., description="Alfa rating difference")
    head_to_head: HeadToHeadStats = Field(
        ..., description="Head-to-head history"
    )
    tournament_history: dict = Field(
        ..., description="Tournament results summary"
    )
    predicted_matchup_prob_p1: Optional[float] = Field(
        None, description="Predicted matchup probability for player 1"
    )

    class Config:
        example = {
            "operator_id": 123,
            "player2_id": 456,
            "operator_name": "John Doe",
            "player2_name": "Jane Smith",
            "fargo_diff": 25.0,
            "alfa_diff": 45.5,
            "head_to_head": {
                "total_matches": 12,
                "operator_wins": 7,
                "player2_wins": 5,
                "win_rate_p1": 0.583,
            },
            "tournament_history": {
                "tournaments_together": 3,
                "operator_avg_placement": 2.5,
                "player2_avg_placement": 5.2,
            },
        }


class AlfaComparisonResponse(BaseModel):
    """Response model for GET /api/alfa/comparison/{operator_id}/{player2_id}."""

    comparison: PlayerComparison = Field(..., description="Comparison data")
    timestamp: datetime = Field(..., description="Comparison timestamp")
    narrative: Optional[str] = Field(None, description="LLM-generated matchup narrative")

    class Config:
        example = {
            "comparison": {
                "operator_id": 123,
                "player2_id": 456,
                "operator_name": "John Doe",
                "player2_name": "Jane Smith",
                "fargo_diff": 25.0,
                "alfa_diff": 45.5,
                "head_to_head": {
                    "total_matches": 12,
                    "operator_wins": 7,
                    "player2_wins": 5,
                    "win_rate_p1": 0.583,
                },
                "tournament_history": {},
            },
            "timestamp": "2026-02-16T10:30:00Z",
        }


# ============================================================================
# ERROR RESPONSE MODELS
# ============================================================================


class ErrorDetail(BaseModel):
    """Error response detail."""

    status_code: int = Field(..., description="HTTP status code")
    detail: str = Field(..., description="Error message")
    error_type: Optional[str] = Field(None, description="Error type")
    timestamp: datetime = Field(..., description="Error timestamp")
    validation_errors: Optional[List[dict]] = Field(
        None, description="Pydantic validation errors"
    )

    class Config:
        example = {
            "status_code": 400,
            "detail": "Invalid input: race_to must be between 2 and 15",
            "error_type": "validation_error",
            "timestamp": "2026-02-16T10:30:00Z",
        }


# ============================================================================
# VIDEO ANALYSIS INTEGRATION MODELS
# ============================================================================

class AlfaVideoAnalysisUpdate(BaseModel):
    """Request model for POST /api/alfa/video-analysis-update endpoint."""

    analysis_id: str = Field(..., description="AI coach analysis ID")
    user_id: str = Field(..., description="User ID who owns the analysis")
    player_name: str = Field(..., description="Player name to update rating for")
    association: str = Field(..., description="Association (WPBA, WPA_Women, WPA_Men)")

    class Config:
        example = {
            "analysis_id": "123e4567-e89b-12d3-a456-426614174000",
            "user_id": "user_123",
            "player_name": "John Doe",
            "association": "WPBA"
        }
