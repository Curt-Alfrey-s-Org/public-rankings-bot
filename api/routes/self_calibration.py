"""
Self-Calibration API Routes

Endpoints for autonomous system improvement and FargoRate independence tracking.
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any
import logging

from api.auth import require_admin
from api.services.live_log import (
    register_job,
    start_background_action,
    stream_log_response,
)
from api.services.live_topics import Topic
from api.services.live_updates import notify_data_changed
from api.services.self_calibration_engine import SelfCalibrationEngine
from api.services.rating_accuracy_engine import RatingAccuracyEngine
from database import get_database_manager

router = APIRouter(prefix="/api/self-calibration", tags=["self-calibration"])
logger = logging.getLogger(__name__)

register_job("calibration_cycle", "Self-calibration cycle")
for _rating_type in ("fargo", "alfa", "est"):
    register_job(
        f"apply_recommendations_{_rating_type}",
        f"Apply AI recommendations ({_rating_type.upper()})",
    )


@router.get("/independence-progress")
async def get_independence_progress():
    """
    Get current FargoRate independence progress and metrics.
    """
    try:
        db = get_database_manager()
        accuracy_engine = RatingAccuracyEngine(db)
        calibration_engine = SelfCalibrationEngine(db, accuracy_engine)

        progress = calibration_engine.get_independence_progress()

        return {
            "success": True,
            "data": progress
        }

    except Exception as e:
        logger.error(f"Error fetching independence progress: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/calibration-analysis/{rating_type}")
async def get_calibration_analysis(rating_type: str):
    """
    Get detailed calibration analysis for a specific rating type.
    """
    try:
        if rating_type not in ['fargo', 'alfa', 'est']:
            raise HTTPException(status_code=400, detail="Invalid rating type")

        db = get_database_manager()
        accuracy_engine = RatingAccuracyEngine(db)
        calibration_engine = SelfCalibrationEngine(db, accuracy_engine)

        analysis = calibration_engine.analyze_accuracy_trends(rating_type)
        adjustments = calibration_engine.generate_parameter_adjustments(rating_type)

        return {
            "success": True,
            "rating_type": rating_type,
            "analysis": analysis,
            "recommended_adjustments": [
                {
                    "parameter_name": adj.parameter_name,
                    "old_value": adj.old_value,
                    "new_value": adj.new_value,
                    "expected_improvement": adj.expected_improvement,
                    "confidence_level": adj.confidence_level,
                    "reasoning": adj.reasoning
                }
                for adj in adjustments
            ]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing calibration for {rating_type}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/run-calibration-cycle")
async def run_calibration_cycle(_admin: dict = Depends(require_admin)):
    """
    Trigger a self-calibration cycle for all rating systems.
    Fire-and-forget: returns immediately and runs in a background thread.
    Watch progress at GET /api/self-calibration/run-calibration-cycle/log.
    """

    def _runner() -> None:
        db = get_database_manager()
        accuracy_engine = RatingAccuracyEngine(db)
        calibration_engine = SelfCalibrationEngine(db, accuracy_engine)
        logger.info("Starting self-calibration cycle for all rating types")
        result = calibration_engine.run_self_calibration_cycle()
        logger.info("Self-calibration cycle complete: %s", result)
        try:
            notify_data_changed(
                Topic.CALIBRATION.value,
                message="Self-calibration cycle completed",
            )
        except Exception as e:
            logger.warning("notify_data_changed failed (calibration cycle): %s", e)

    started = start_background_action("calibration_cycle", _runner)
    return {
        "success": True,
        "status": started["status"],
        "message": started["message"],
        "log_file": started.get("log_file"),
        "estimated_duration": "30-60 seconds",
    }


@router.get("/run-calibration-cycle/log")
async def stream_calibration_cycle_log(_admin: dict = Depends(require_admin)):
    """Stream the live log for the most recent Self-calibration cycle run."""
    return stream_log_response("calibration_cycle")


@router.post("/apply-recommendations/{rating_type}")
async def apply_calibration_recommendations(
    rating_type: str,
    _admin: dict = Depends(require_admin),
):
    """
    Apply AI-generated calibration recommendations for a specific rating type.
    Fire-and-forget; watch progress at GET .../apply-recommendations/{rating_type}/log.
    """
    if rating_type not in ("fargo", "alfa", "est"):
        raise HTTPException(status_code=400, detail="Invalid rating type")

    job_id = f"apply_recommendations_{rating_type}"

    def _runner() -> None:
        db = get_database_manager()
        accuracy_engine = RatingAccuracyEngine(db)
        calibration_engine = SelfCalibrationEngine(db, accuracy_engine)
        adjustments = calibration_engine.generate_parameter_adjustments(rating_type)
        if not adjustments:
            logger.info("No calibration recommendations available for %s", rating_type)
            return
        logger.info(
            "Applying %d calibration adjustments for %s", len(adjustments), rating_type
        )
        success = calibration_engine.apply_parameter_adjustments(adjustments)
        if not success:
            raise RuntimeError(f"apply_parameter_adjustments returned False for {rating_type}")
        for adj in adjustments:
            logger.info(
                "  %s: %s -> %s (%s)",
                adj.parameter_name,
                adj.old_value,
                adj.new_value,
                adj.reasoning,
            )
        try:
            notify_data_changed(
                Topic.CALIBRATION.value,
                rows_updated=len(adjustments),
                message=f"Applied {len(adjustments)} {rating_type} calibration adjustments",
            )
            notify_data_changed(
                Topic.RANKINGS.value,
                rows_updated=len(adjustments),
                message=f"{rating_type} calibration applied",
            )
        except Exception as e:
            logger.warning("notify_data_changed failed (apply calibration %s): %s", rating_type, e)

    started = start_background_action(job_id, _runner)
    return {
        "success": True,
        "status": started["status"],
        "rating_type": rating_type,
        "message": started["message"],
        "log_file": started.get("log_file"),
    }


@router.get("/apply-recommendations/{rating_type}/log")
async def stream_apply_recommendations_log(
    rating_type: str,
    _admin: dict = Depends(require_admin),
):
    """Stream the live log for the most recent Apply AI recommendations run."""
    if rating_type not in ("fargo", "alfa", "est"):
        raise HTTPException(status_code=400, detail="Invalid rating type")
    return stream_log_response(f"apply_recommendations_{rating_type}")


@router.get("/calibration-history")
async def get_calibration_history(limit: int = 20):
    """
    Get history of calibration adjustments and their effectiveness.
    """
    try:
        db = get_database_manager()
        conn = db.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                improvement_date,
                rating_type,
                previous_accuracy,
                new_accuracy,
                improvement_amount,
                calibration_changes,
                sample_size,
                statistical_significance,
                notes,
                created_at
            FROM system_accuracy_improvement
            ORDER BY improvement_date DESC
            LIMIT %s
        """, (limit,))

        history = []
        for row in cursor.fetchall():
            history.append({
                "improvement_date": row[0].isoformat() if row[0] else None,
                "rating_type": row[1],
                "previous_accuracy": row[2],
                "new_accuracy": row[3],
                "improvement_amount": row[4],
                "calibration_changes": row[5],
                "sample_size": row[6],
                "statistical_significance": row[7],
                "notes": row[8],
                "created_at": row[9].isoformat() if row[9] else None
            })

        conn.close()

        return {
            "success": True,
            "history": history
        }

    except Exception as e:
        logger.error(f"Error fetching calibration history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/current-parameters/{rating_type}")
async def get_current_parameters(rating_type: str):
    """
    Get current calibration parameters for a rating type.
    """
    try:
        if rating_type not in ['fargo', 'alfa', 'est']:
            raise HTTPException(status_code=400, detail="Invalid rating type")

        db = get_database_manager()
        conn = db.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                parameter_name,
                parameter_value,
                effective_date,
                calibration_method,
                sample_size,
                confidence_interval
            FROM rating_calibration_params
            WHERE rating_type = %s
            ORDER BY effective_date DESC
        """, (rating_type,))

        parameters = {}
        for row in cursor.fetchall():
            param_name = row[0]
            if param_name not in parameters:  # Keep only the most recent value
                parameters[param_name] = {
                    "value": row[1],
                    "effective_date": row[2].isoformat() if row[2] else None,
                    "calibration_method": row[3],
                    "sample_size": row[4],
                    "confidence_interval": row[5]
                }

        conn.close()

        return {
            "success": True,
            "rating_type": rating_type,
            "parameters": parameters
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching parameters for {rating_type}: {e}")
        raise HTTPException(status_code=500, detail=str(e))