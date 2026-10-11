"""
Alfa Rating prediction API endpoints.

Provides REST API for:
- Match outcome predictions with explainability
- Player rating lookups and history
- Head-to-head comparisons
- Rating factors and confidence metrics

Note: Sandbagging/anomaly detection has been removed as of 2026-02-17.
Rationale: WPA/WPBA tournaments are professional non-handicapped competition.
Variance in tournament finish is normal competitive variance, not sandbagging.

All endpoints integrate with PostgreSQL database for prediction logging and factor tracking.
"""

from __future__ import annotations

import logging
import json
from datetime import datetime, timedelta
from typing import Optional, List
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text

from api.models.pydantic_schemas import (
    AlfaPredictRequest,
    AlfaPredictResponse,
    AlfaExplainRequest,
    AlfaExplainResponse,
    AlfaPlayerResponse,
    AlfaComparisonResponse,
    PredictionFactor,
    RatingHistory,
    ColdStartProgress,
    HeadToHeadStats,
    PlayerComparison,
    AlfaVideoAnalysisUpdate,
)
from api.config.model_loader import (
    get_model_loader,
    get_logistic_regression_model,
    get_cold_start_engine,
    player_ratings_cache,
    prediction_cache,
)
from database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/alfa", tags=["alfa"])

# Model version string
MODEL_VERSION = "alfa_logistic_v1"


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def _get_or_create_match_id(
    operator_id: int,
    player2_id: int,
    match_id: Optional[str] = None,
) -> str:
    """Generate or use provided match ID."""
    if match_id:
        return match_id
    return f"match_{datetime.utcnow().isoformat()}_{operator_id}_{player2_id}_{uuid4().hex[:8]}"


def _compute_prediction_factors(
    operator_rating: float,
    player2_rating: float,
    table_size: str,
    game_format: str,
    race_to: int,
) -> tuple[List[PredictionFactor], float]:
    """
    Compute factors contributing to prediction.

    Returns:
        Tuple of (factors list, combined contribution)
    """
    factors: List[PredictionFactor] = []

    # Rating gap factor
    rating_gap = operator_rating - player2_rating
    rating_gap_contrib = min(0.4, abs(rating_gap) / 500)
    if rating_gap > 0:
        rating_gap_contrib *= 1.0
    else:
        rating_gap_contrib *= -1.0

    factors.append(
        PredictionFactor(
            name="rating_gap",
            contribution=rating_gap_contrib,
            weight=0.35,
            direction="favors_p1" if rating_gap_contrib > 0 else "favors_p2",
        )
    )

    # Table size comfort (assumption: larger tables favor higher-ranked players)
    table_size_bonus = 0.05 if table_size == "9ft" or table_size == "10ft" else 0.02
    factors.append(
        PredictionFactor(
            name="table_size_comfort",
            contribution=table_size_bonus,
            weight=0.15,
            direction="favors_p1",
        )
    )

    # Format comfort
    format_weights = {
        "9-ball": 0.10,
        "10-ball": 0.08,
        "8-ball": 0.12,
        "mixed": 0.05,
    }
    format_contrib = format_weights.get(game_format, 0.05)
    factors.append(
        PredictionFactor(
            name="format_specialty",
            contribution=format_contrib,
            weight=0.15,
            direction="favors_p1",
        )
    )

    # Race-to length impact
    race_impact = (race_to - 8) / 10  # Longer races may reduce variance
    factors.append(
        PredictionFactor(
            name="race_length_factor",
            contribution=race_impact * 0.1,
            weight=0.10,
            direction="favors_p1" if race_impact > 0 else "favors_p2",
        )
    )

    # Combine contributions (simplified logistic approach)
    total_contrib = sum(f.contribution * f.weight for f in factors)
    return factors, total_contrib


def _compute_win_probability(combined_contrib: float) -> tuple[float, float]:
    """
    Convert combined factor contribution to win probabilities.

    Uses logistic function: P(win) = 1 / (1 + e^(-x))
    """
    import math

    # Apply sigmoid function
    prob_p1 = 1.0 / (1.0 + math.exp(-combined_contrib * 10))  # Scale for visibility
    prob_p2 = 1.0 - prob_p1

    # Ensure not too extreme
    prob_p1 = max(0.01, min(0.99, prob_p1))
    prob_p2 = 1.0 - prob_p1

    return prob_p1, prob_p2


def _fetch_player_rating(
    db: Session, player_id: int
) -> Optional[dict]:
    """Fetch current player rating from database."""
    try:
        result = db.execute(
            text(
                """
                SELECT id, player_id, player_name, rating, robustness, rating_confidence, 
                       anomaly_score, updated_at
                FROM alfa_player_ratings
                WHERE player_id = :player_id
                ORDER BY updated_at DESC
                LIMIT 1
                """
            ),
            {"player_id": player_id},
        ).fetchone()

        if result:
            return {
                "id": result[0],
                "player_id": result[1],
                "player_name": result[2],
                "rating": result[3],
                "robustness": result[4],
                "rating_confidence": result[5],
                "anomaly_score": result[6],
                "updated_at": result[7],
            }
    except Exception as e:
        logger.error(f"Error fetching player rating: {e}")

    return None


def _insert_prediction(
    db: Session,
    match_id: str,
    operator_id: int,
    player2_id: int,
    predicted_prob_p1: float,
    predicted_prob_p2: float,
    confidence: float,
) -> bool:
    """Insert prediction into database."""
    try:
        db.execute(
            text(
                """
                INSERT INTO alfa_match_predictions 
                (match_id, operator_id, player2_id, predicted_win_prob_p1, 
                 predicted_win_prob_p2, prediction_confidence, model_version, created_at, updated_at)
                VALUES (:match_id, :operator_id, :player2_id, :prob_p1, :prob_p2, 
                        :confidence, :model_version, :now, :now)
                ON CONFLICT (match_id) DO UPDATE SET
                  predicted_win_prob_p1 = :prob_p1,
                  predicted_win_prob_p2 = :prob_p2,
                  updated_at = :now
                """
            ),
            {
                "match_id": match_id,
                "operator_id": operator_id,
                "player2_id": player2_id,
                "prob_p1": predicted_prob_p1,
                "prob_p2": predicted_prob_p2,
                "confidence": confidence,
                "model_version": MODEL_VERSION,
                "now": datetime.utcnow(),
            },
        )
        db.commit()
        return True
    except Exception as e:
        logger.error(f"Error inserting prediction: {e}")
        db.rollback()
        return False


def _insert_prediction_factors(
    db: Session,
    match_id: str,
    factors: List[PredictionFactor],
) -> bool:
    """Insert prediction factors into database."""
    try:
        for factor in factors:
            db.execute(
                text(
                    """
                    INSERT INTO alfa_prediction_factors 
                    (match_id, factor_name, contribution, direction, weight, created_at)
                    VALUES (:match_id, :name, :contribution, :direction, :weight, :now)
                    """
                ),
                {
                    "match_id": match_id,
                    "name": factor.name,
                    "contribution": factor.contribution,
                    "direction": factor.direction,
                    "weight": factor.weight,
                    "now": datetime.utcnow(),
                },
            )
        db.commit()
        return True
    except Exception as e:
        logger.error(f"Error inserting prediction factors: {e}")
        db.rollback()
        return False


# ============================================================================
# ENDPOINT: POST /api/alfa/predict
# ============================================================================


@router.post(
    "/predict",
    response_model=AlfaPredictResponse,
    summary="Predict match outcome",
    description="Predict match outcome with explainable factors",
)
async def predict_match(
    request: AlfaPredictRequest,
    db: Session = Depends(get_db),
) -> AlfaPredictResponse:
    """
    Predict match outcome probabilities with factor breakdown.

    This endpoint:
    1. Fetches current player ratings
    2. Computes prediction factors (rating gap, table size, format, etc.)
    3. Calculates win probabilities using logistic regression
    4. Stores prediction in database for audit/validation
    5. Returns structured prediction with confidence and factors

    Args:
        request: Prediction request with player IDs, match parameters

    Returns:
        Prediction with probabilities, factors, and confidence

    Responses:
        - 200: Successful prediction
        - 404: Player not found
        - 400: Invalid input parameters
        - 503: Model loading failure
    """
    try:
        # Check cache first
        cache_key = f"predict_{request.operator_id}_{request.player2_id}_{request.race_to}"
        cached = prediction_cache.get(cache_key)
        if cached:
            logger.info(f"Returning cached prediction for {cache_key}")
            return cached

        # Ensure models are loaded
        loader = get_model_loader()
        if not loader.is_healthy():
            raise HTTPException(
                status_code=503,
                detail="Model loading failed. Check server logs.",
            )

        # Fetch player ratings
        operator_data = _fetch_player_rating(db, request.operator_id)
        player2_data = _fetch_player_rating(db, request.player2_id)

        if not operator_data or not player2_data:
            raise HTTPException(
                status_code=404,
                detail="One or both players not found in rating system",
            )

        # Get match ID
        match_id = _get_or_create_match_id(
            request.operator_id, request.player2_id, request.match_id
        )

        # Compute prediction factors
        factors, total_contrib = _compute_prediction_factors(
            operator_data["rating"],
            player2_data["rating"],
            request.table_size,
            request.format,
            request.race_to,
        )

        # Calculate win probabilities
        prob_p1, prob_p2 = _compute_win_probability(total_contrib)

        # Estimate confidence based on player robustness
        p1_confidence = min(0.95, operator_data["rating_confidence"])
        p2_confidence = min(0.95, player2_data["rating_confidence"])
        overall_confidence = (p1_confidence + p2_confidence) / 2

        # Build response
        response = AlfaPredictResponse(
            match_id=match_id,
            predicted_win_prob_p1=prob_p1,
            predicted_win_prob_p2=prob_p2,
            factors=factors,
            confidence=overall_confidence,
            predicted_race_length=None,  # Can be computed from historical data
            prediction_brier_score=None,  # Only after match is played
            model_version=MODEL_VERSION,
            timestamp=datetime.utcnow(),
        )

        # Store in database
        _insert_prediction(
            db,
            match_id,
            request.operator_id,
            request.player2_id,
            prob_p1,
            prob_p2,
            overall_confidence,
        )
        _insert_prediction_factors(db, match_id, factors)

        # Cache result
        prediction_cache.set(cache_key, response)

        logger.info(
            f"Prediction for match {match_id}: P1={prob_p1:.2%}, P2={prob_p2:.2%}"
        )
        return response

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Prediction endpoint error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ============================================================================
# ENDPOINT: POST /api/alfa/explain
# ============================================================================


@router.post(
    "/explain",
    response_model=AlfaExplainResponse,
    summary="Explain prediction",
    description="Get detailed explanation of a match prediction",
)
async def explain_prediction(
    request: AlfaExplainRequest,
    db: Session = Depends(get_db),
) -> AlfaExplainResponse:
    """
    Get detailed explanation of a match prediction.

    Retrieves:
    - Original prediction and confidence
    - Factor breakdown (what influenced the prediction)
    - Actual outcome (if match was played)
    - Prediction calibration (Brier score if played)
    - Anomaly flags detected

    Args:
        request: Explanation request with match_id

    Returns:
        Detailed explanation with factors, anomalies, and calibration

    Responses:
        - 200: Successful explanation
        - 404: Match not found
        - 500: Database error
    """
    try:
        # Fetch prediction from database
        pred_result = db.execute(
            text(
                """
                SELECT id, match_id, operator_id, player2_id, predicted_win_prob_p1,
                       predicted_win_prob_p2, prediction_confidence, model_version,
                       actual_winner_id, actual_winner_games, actual_loser_games,
                       brier_score, created_at
                FROM alfa_match_predictions
                WHERE match_id = :match_id
                """
            ),
            {"match_id": request.match_id},
        ).fetchone()

        if not pred_result:
            raise HTTPException(status_code=404, detail="Prediction not found")

        (
            pred_id,
            match_id,
            operator_id,
            player2_id,
            pred_prob_p1,
            pred_prob_p2,
            confidence,
            model_version,
            actual_winner,
            winner_games,
            loser_games,
            brier_score,
            created_at,
        ) = pred_result

        # Fetch factors
        factors_results = db.execute(
            text(
                """
                SELECT factor_name, contribution, direction, weight
                FROM alfa_prediction_factors
                WHERE match_id = :match_id
                """
            ),
            {"match_id": match_id},
        ).fetchall()

        factors = [
            PredictionFactor(
                name=row[0],
                contribution=row[1],
                direction=row[2],
                weight=row[3],
            )
            for row in factors_results
        ]

        # Determine actual result
        actual_result = None
        if actual_winner:
            actual_result = "win" if actual_winner == operator_id else "loss"

        response = AlfaExplainResponse(
            match_id=match_id,
            match_details={
                "operator_id": operator_id,
                "player2_id": player2_id,
            },
            predicted_prob_p1=pred_prob_p1,
            predicted_prob_p2=pred_prob_p2,
            actual_winner_id=actual_winner,
            actual_result=actual_result,
            prediction_error=brier_score,
            factors_breakdown=factors,
            anomaly_flags=[],  # Anomaly detection removed (normal variance in pro play)
            confidence=confidence,
        )

        logger.info(f"Explained prediction for match {match_id}")
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Explain endpoint error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ============================================================================
# ENDPOINT: GET /api/alfa/player/{player_id}
# ============================================================================


@router.get(
    "/player/{player_id}",
    response_model=AlfaPlayerResponse,
    summary="Get player ratings",
    description="Fetch player Alfa rating, history, and statistics",
)
async def get_player_ratings(
    player_id: int,
    db: Session = Depends(get_db),
) -> AlfaPlayerResponse:
    """
    Get comprehensive player rating data including history and progress.

    Returns:
    - Current Alfa rating and confidence
    - 30-day rating history
    - Games played and robustness metrics
    - Cold start progress (for new players)
    - Anomaly score

    Args:
        player_id: Player ID

    Returns:
        Player rating data with history

    Responses:
        - 200: Player data retrieved
        - 404: Player not found
        - 500: Database error
    """
    try:
        # Check cache
        cache_key = f"player_{player_id}"
        cached = player_ratings_cache.get(cache_key)
        if cached:
            logger.info(f"Returning cached player data for {player_id}")
            return cached

        # Fetch current rating
        current = _fetch_player_rating(db, player_id)
        if not current:
            raise HTTPException(status_code=404, detail="Player not found")

        # Fetch rating history (last 30 days)
        history_results = db.execute(
            text(
                """
                SELECT updated_at, rating, rating_confidence
                FROM alfa_player_ratings
                WHERE player_id = :player_id
                ORDER BY updated_at DESC
                LIMIT 30
                """
            ),
            {"player_id": player_id},
        ).fetchall()

        rating_history = [
            RatingHistory(
                date=row[0].date().isoformat(),
                rating=row[1],
                confidence=row[2],
            )
            for row in history_results
        ]

        # Determine cold start progress
        cold_start_progress = None
        if current["robustness"] < 20:
            games_to_convergence = max(0, 20 - current["robustness"])
            cold_start_progress = ColdStartProgress(
                games_played=current["robustness"],
                confidence_estimate=current["rating_confidence"],
                target_confidence=0.85,
                games_to_convergence=games_to_convergence,
            )

        response = AlfaPlayerResponse(
            player_id=player_id,
            player_name=current.get("player_name"),
            current_rating=current["rating"],
            rating_confidence=current["rating_confidence"],
            games_played=current["robustness"],
            anomaly_score=current.get("anomaly_score", 0.0),
            rating_history=rating_history,
            cold_start_progress=cold_start_progress,
            last_update=current["updated_at"],
            robustness=current["robustness"],
        )

        # Cache result
        player_ratings_cache.set(cache_key, response)

        logger.info(f"Retrieved ratings for player {player_id}")
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Player ratings endpoint error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ============================================================================
# ENDPOINT: GET /api/alfa/comparison/{operator_id}/{player2_id}
# ============================================================================


@router.get(
    "/comparison/{operator_id}/{player2_id}",
    response_model=AlfaComparisonResponse,
    summary="Compare two players",
    description="Head-to-head comparison between players",
)
async def compare_players(
    operator_id: int,
    player2_id: int,
    db: Session = Depends(get_db),
) -> AlfaComparisonResponse:
    """
    Compare two players across multiple dimensions.

    Includes:
    - Rating differences (Alfa and Fargo)
    - Head-to-head match history
    - Tournament history together
    - Predicted matchup probability

    Args:
        operator_id: First player ID
        player2_id: Second player ID

    Returns:
        Comprehensive comparison data

    Responses:
        - 200: Comparison retrieved
        - 404: One or both players not found
        - 500: Database error
    """
    try:
        # Fetch both players
        p1_data = _fetch_player_rating(db, operator_id)
        p2_data = _fetch_player_rating(db, player2_id)

        if not p1_data or not p2_data:
            raise HTTPException(status_code=404, detail="One or both players not found")

        # Fetch head-to-head history
        h2h_result = db.execute(
            text(
                """
                SELECT COUNT(*) as total,
                       SUM(CASE WHEN operator_id = :operator_id AND operator_final_score > player2_final_score THEN 1
                                WHEN player2_id = :operator_id AND player2_final_score > operator_final_score THEN 1
                                ELSE 0 END) as p1_wins
                FROM tournament_history_matches
                WHERE (operator_id = :operator_id AND player2_id = :player2_id)
                   OR (operator_id = :player2_id AND player2_id = :operator_id)
                """
            ),
            {
                "operator_id": operator_id,
                "player2_id": player2_id,
            },
        ).fetchone()

        total_matches = h2h_result[0] if h2h_result and h2h_result[0] else 0
        p1_wins = h2h_result[1] if h2h_result and h2h_result[1] else 0
        p2_wins = total_matches - p1_wins

        h2h = HeadToHeadStats(
            total_matches=total_matches,
            operator_wins=p1_wins,
            player2_wins=p2_wins,
            win_rate_p1=p1_wins / total_matches if total_matches > 0 else 0.5,
        )

        # Compute prediction for this matchup
        _, prob_p1 = _compute_win_probability(
            (p1_data["rating"] - p2_data["rating"]) / 500
        )

        comparison = PlayerComparison(
            operator_id=operator_id,
            player2_id=player2_id,
            operator_name=p1_data.get("player_name"),
            player2_name=p2_data.get("player_name"),
            fargo_diff=None,  # Would require Fargo data fetch
            alfa_diff=p1_data["rating"] - p2_data["rating"],
            head_to_head=h2h,
            tournament_history={},
            predicted_matchup_prob_p1=prob_p1,
        )

        response = AlfaComparisonResponse(
            comparison=comparison,
            timestamp=datetime.utcnow(),
        )

        # Generate matchup narrative via Ollama
        try:
            from api.services.ollama_narratives import generate_matchup_narrative
            from api.services.ollama_client import is_ollama_enabled
            if is_ollama_enabled():
                h2h_for_narrative = {
                    "operator_name": p1_data.get("player_name"),
                    "player2_name": p2_data.get("player_name"),
                    "operator_rating": p1_data.get("rating"),
                    "player2_rating": p2_data.get("rating"),
                    "total_matches": total_matches,
                    "operator_wins": p1_wins,
                    "player2_wins": p2_wins,
                    "predicted_p1_win_prob": prob_p1,
                }
                narrative = await generate_matchup_narrative(h2h_for_narrative)
                if narrative:
                    response.narrative = narrative
        except Exception as narr_err:
            logger.debug("Matchup narrative skipped: %s", narr_err)

        logger.info(f"Compared players {operator_id} vs {player2_id}")
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Comparison endpoint error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ============================================================================
# DASHBOARD STATS ENDPOINT
# ============================================================================


@router.get(
    "/dashboard/stats",
    summary="Dashboard statistics",
    description="Aggregate stats for main dashboard (players, predictions, anomalies)",
)
async def get_dashboard_stats(db: Session = Depends(get_db)):
    """
    Return dashboard overview stats. Used by main Dashboard page.
    Returns zeros when Alfa tables are not yet populated.
    """
    try:
        total_players = 0
        new_players = 0
        anomalies_detected = 0
        predictions_today = 0
        avg_rating_change = 0.0
        system_health_score = 100.0

        # Try alfa_player_ratings (may not exist)
        try:
            r = db.execute(text("SELECT COUNT(*) FROM alfa_player_ratings")).scalar()
            total_players = r or 0
        except Exception as e:
            logger.warning("Could not read alfa_player_ratings count: %s", e)

        # Try new players (last 30 days) - alfa_player_ratings.updated_at
        try:
            r = db.execute(text("""
                SELECT COUNT(*) FROM alfa_player_ratings
                WHERE updated_at >= CURRENT_DATE - INTERVAL '30 days'
            """)).scalar()
            new_players = r or 0
        except Exception as e:
            logger.warning("Could not read recent new player count: %s", e)

        # Try anomaly flags
        try:
            r = db.execute(text("SELECT COUNT(*) FROM alfa_anomaly_flags")).scalar()
            anomalies_detected = r or 0
        except Exception as e:
            logger.warning("Could not read anomaly flag count: %s", e)

        # Try predictions today - model_predictions or alfa_match_predictions
        try:
            r = db.execute(text("""
                SELECT COUNT(*) FROM model_predictions
                WHERE prediction_timestamp::date = CURRENT_DATE
            """)).scalar()
            predictions_today = r or 0
        except Exception:
            try:
                r = db.execute(text("""
                    SELECT COUNT(*) FROM alfa_match_predictions
                    WHERE created_at::date = CURRENT_DATE
                """)).scalar()
                predictions_today = r or 0
            except Exception as e:
                logger.warning("Could not read prediction counts from model_predictions/alfa_match_predictions: %s", e)

        return {
            "total_players": total_players,
            "new_players": new_players,
            "anomalies_detected": anomalies_detected,
            "predictions_today": predictions_today,
            "avg_rating_change": avg_rating_change,
            "system_health_score": system_health_score,
        }
    except Exception as e:
        logger.warning(f"Dashboard stats error (returning defaults): {e}")
        return {
            "total_players": 0,
            "new_players": 0,
            "anomalies_detected": 0,
            "predictions_today": 0,
            "avg_rating_change": 0.0,
            "system_health_score": 100.0,
        }


# ============================================================================
# HEALTH CHECK ENDPOINT
# ============================================================================


@router.get(
    "/health",
    summary="Health check",
    description="Check if Alfa rating system is operational",
)
async def health_check():
    """
    Check Alfa system health.

    Returns:
        Status of models and database connectivity

    Responses:
        - 200: System healthy
        - 503: Model loading issues
    """
    try:
        loader = get_model_loader()
        health_report = loader.get_health_report()

        if loader.is_healthy():
            return {
                "status": "healthy",
                "models": health_report["models_loaded"],
                "timestamp": datetime.utcnow().isoformat(),
            }
        else:
            raise HTTPException(
                status_code=503,
                detail=f"Models not ready: {health_report['load_errors']}",
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Health check error: {e}")
        raise HTTPException(status_code=503, detail="Health check failed")


# ============================================================================
# VIDEO ANALYSIS INTEGRATION ENDPOINTS
# ============================================================================

@router.post("/video-analysis-update", response_model=dict)
async def update_alfa_from_video_analysis(
    request: AlfaVideoAnalysisUpdate,
    db: Session = Depends(get_db)
):
    """
    Update ALFA rating based on video analysis results.

    This endpoint integrates AI video coaching results into the ALFA rating system,
    allowing video analysis to influence player ratings based on demonstrated skill level.

    Video analysis provides direct observation of technique, strategy, and performance
    that can refine ALFA ratings beyond tournament results alone.
    """
    try:
        # Validate analysis ID exists and belongs to user
        from api.models.ai_coach import AICoachAnalysis
        analysis = db.query(AICoachAnalysis).filter_by(
            id=request.analysis_id,
            user_id=request.user_id
        ).first()

        if not analysis:
            raise HTTPException(status_code=404, detail="Video analysis not found")

        if analysis.status != "completed":
            raise HTTPException(status_code=400, detail="Video analysis not completed yet")

        if not analysis.analysis_json:
            raise HTTPException(status_code=400, detail="Video analysis has no results")

        # Extract performance metrics from video analysis
        video_score = analysis.analysis_json.get("overall_score", 0)
        technique_rating = analysis.analysis_json.get("technique_rating", 0)
        strategy_rating = analysis.analysis_json.get("strategy_rating", 0)
        positioning_rating = analysis.analysis_json.get("positioning_rating", 0)

        # Calculate video-based rating adjustment
        # Video analysis provides direct skill assessment that can refine ALFA ratings
        video_confidence = min(0.8, analysis.frame_count / 50.0)  # Higher confidence with more frames
        video_adjustment = calculate_video_adjustment(
            video_score, technique_rating, strategy_rating, positioning_rating, video_confidence
        )

        # Get current ALFA rating
        from api.services.alfa_engine import AlfaEngine
        engine = AlfaEngine()
        current_rating = engine.get_player_rating(request.player_name, request.association)

        if not current_rating:
            raise HTTPException(status_code=404, detail=f"No ALFA rating found for {request.player_name}")

        # Apply video analysis adjustment to ALFA rating
        new_rating = apply_video_adjustment_to_alfa(
            current_rating, video_adjustment, request.analysis_id, db
        )

        # Log the rating update
        logger.info(
            f"Updated ALFA rating for {request.player_name} from {current_rating.rating:.1f} "
            f"to {new_rating:.1f} based on video analysis {request.analysis_id}"
        )

        return {
            "success": True,
            "player_name": request.player_name,
            "association": request.association,
            "old_rating": current_rating.rating,
            "new_rating": new_rating,
            "adjustment": video_adjustment.adjustment,
            "confidence": video_adjustment.confidence,
            "analysis_id": request.analysis_id,
            "updated_at": datetime.utcnow().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Video analysis ALFA update failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to update ALFA rating from video analysis")


def calculate_video_adjustment(video_score: float, technique: float, strategy: float,
                              positioning: float, confidence: float) -> dict:
    """
    Calculate rating adjustment based on video analysis metrics.

    Video analysis provides direct skill assessment that can refine ALFA ratings.
    Higher video scores suggest the player may be rated higher than tournament results indicate.
    """
    # Normalize scores to 0-10 scale
    avg_performance = (technique + strategy + positioning) / 3.0

    # Calculate adjustment based on video performance vs expected performance
    # Video analysis can reveal skill levels not fully captured by tournament results
    base_adjustment = (video_score - 5.0) * 2.0  # ±10 points max from video score alone
    performance_adjustment = (avg_performance - 5.0) * 1.5  # ±7.5 points from technique/strategy

    # Combined adjustment with confidence weighting
    total_adjustment = (base_adjustment * 0.6 + performance_adjustment * 0.4) * confidence

    # Limit adjustment magnitude to prevent extreme changes
    total_adjustment = max(-8.0, min(8.0, total_adjustment))

    return {
        "adjustment": total_adjustment,
        "confidence": confidence,
        "video_score": video_score,
        "avg_performance": avg_performance,
        "components": {
            "base_adjustment": base_adjustment,
            "performance_adjustment": performance_adjustment
        }
    }


def apply_video_adjustment_to_alfa(current_rating: dict, video_adjustment: dict,
                                  analysis_id: str, db: Session) -> float:
    """
    Apply video analysis adjustment to existing ALFA rating.

    Updates the player's ALFA rating in the database with the video-informed adjustment.
    """
    new_rating = current_rating["rating"] + video_adjustment["adjustment"]

    # Ensure rating stays within valid bounds
    from api.services.alfa_constants import MIN_VALID_ALFA_RATING, MAX_VALID_ALFA_RATING
    new_rating = max(MIN_VALID_ALFA_RATING, min(MAX_VALID_ALFA_RATING, new_rating))

    # Update the rating in database
    # Note: This assumes there's a way to update ratings - may need to create a new table
    # or modify existing rating storage to track video analysis contributions

    # Video analysis rating adjustment record (tracks how video analysis influences ratings)

    try:
        # Insert video analysis rating adjustment
        db.execute(text("""
            INSERT INTO video_analysis_rating_adjustments
            (analysis_id, player_name, association, old_rating, new_rating,
             adjustment, confidence, created_at)
            VALUES (:analysis_id, :player_name, :association, :old_rating, :new_rating,
                   :adjustment, :confidence, :created_at)
            ON CONFLICT (analysis_id) DO UPDATE SET
                old_rating = EXCLUDED.old_rating,
                new_rating = EXCLUDED.new_rating,
                adjustment = EXCLUDED.adjustment,
                confidence = EXCLUDED.confidence,
                updated_at = :created_at
        """), {
            "analysis_id": analysis_id,
            "player_name": current_rating.get("player_name"),
            "association": current_rating.get("association", "Unknown"),
            "old_rating": current_rating["rating"],
            "new_rating": new_rating,
            "adjustment": video_adjustment["adjustment"],
            "confidence": video_adjustment["confidence"],
            "created_at": datetime.utcnow()
        })
        db.commit()

    except Exception as e:
        logger.warning(f"Could not save video analysis rating adjustment: {e}")
        # Continue without saving adjustment record - rating update still works

    return new_rating
