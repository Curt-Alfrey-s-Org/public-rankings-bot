"""
Rating Accuracy API Routes

Provides accuracy metrics and historical analysis for the rating systems.
Used by admin dashboard to display confidence levels and self-calibration status.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional, Dict, Any
from datetime import date, timedelta
import logging

from api.services.rating_accuracy_engine import RatingAccuracyEngine
from database import get_database_manager

router = APIRouter(prefix="/api/rating-accuracy", tags=["rating-accuracy"])
logger = logging.getLogger(__name__)


@router.get("/dashboard")
async def get_accuracy_dashboard():
    """
    Get comprehensive accuracy dashboard data for all rating systems.
    """
    try:
        db = get_database_manager()
        accuracy_engine = RatingAccuracyEngine(db)

        dashboard_data = accuracy_engine.get_accuracy_dashboard_data()

        return {
            "success": True,
            "data": dashboard_data
        }

    except Exception as e:
        logger.error(f"Error fetching accuracy dashboard: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics/{rating_type}")
async def get_rating_metrics(
    rating_type: str,
    days: int = Query(30, ge=1, le=365)
):
    """
    Get detailed accuracy metrics for a specific rating type.
    """
    try:
        if rating_type not in ['fargo', 'alfa', 'est']:
            raise HTTPException(status_code=400, detail="Invalid rating type")

        db = get_database_manager()
        accuracy_engine = RatingAccuracyEngine(db)

        metrics = accuracy_engine.calculate_accuracy_metrics(rating_type)
        if not metrics:
            return {
                "success": True,
                "data": None,
                "message": f"No accuracy data available for {rating_type}"
            }

        return {
            "success": True,
            "data": {
                "rating_type": metrics.rating_type,
                "total_predictions": metrics.total_predictions,
                "accurate_predictions": metrics.accurate_predictions,
                "accuracy_percentage": round(metrics.accuracy_percentage, 2),
                "mean_absolute_error": round(metrics.mean_absolute_error, 2),
                "confidence_interval": round(metrics.confidence_interval, 2),
                "sample_size": metrics.sample_size,
                "calculation_date": metrics.calculation_date.isoformat()
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching metrics for {rating_type}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/update-metrics")
async def update_accuracy_metrics():
    """
    Manually trigger accuracy metrics calculation for all rating types.
    Admin only - used to refresh dashboard data.
    """
    try:
        db = get_database_manager()
        accuracy_engine = RatingAccuracyEngine(db)

        updated_types = []
        for rating_type in ['fargo', 'alfa', 'est']:
            if accuracy_engine.update_accuracy_metrics(rating_type):
                updated_types.append(rating_type)

        return {
            "success": True,
            "message": f"Updated accuracy metrics for: {', '.join(updated_types)}",
            "updated_types": updated_types
        }

    except Exception as e:
        logger.error(f"Error updating accuracy metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compare-est-fargo")
async def compare_est_fargo():
    """
    Snapshot EST vs published Fargo for all players with both values.
    Populates player_rating_accuracy and refreshes est metrics (Phase 4).
    """
    try:
        from api.services.est_fargo_comparison import run_est_fargo_comparison

        db = get_database_manager()
        result = run_est_fargo_comparison(db)
        return {"success": True, **result}
    except Exception as e:
        logger.error(f"Error comparing est vs fargo: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/calibration-recommendations/{rating_type}")
async def get_calibration_recommendations(rating_type: str):
    """
    Get AI-generated recommendations for improving rating accuracy.
    """
    try:
        if rating_type not in ['fargo', 'alfa', 'est']:
            raise HTTPException(status_code=400, detail="Invalid rating type")

        db = get_database_manager()
        accuracy_engine = RatingAccuracyEngine(db)

        recommendations = accuracy_engine.generate_calibration_recommendations(rating_type)

        return {
            "success": True,
            "rating_type": rating_type,
            "recommendations": [
                {
                    "parameter_name": rec.parameter_name,
                    "current_value": rec.current_value,
                    "recommended_value": rec.recommended_value,
                    "expected_improvement": rec.expected_improvement,
                    "confidence_level": rec.confidence_level,
                    "reasoning": rec.reasoning
                }
                for rec in recommendations
            ]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating calibration recommendations for {rating_type}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/apply-calibration/{rating_type}")
async def apply_calibration_recommendations(rating_type: str):
    """
    Apply AI-generated calibration recommendations to improve accuracy.
    Admin only - automatically adjusts rating calculation parameters.
    """
    try:
        if rating_type not in ['fargo', 'alfa', 'est']:
            raise HTTPException(status_code=400, detail="Invalid rating type")

        db = get_database_manager()
        accuracy_engine = RatingAccuracyEngine(db)

        recommendations = accuracy_engine.generate_calibration_recommendations(rating_type)
        if not recommendations:
            return {
                "success": True,
                "message": f"No calibration recommendations available for {rating_type}",
                "applied_count": 0
            }

        success = accuracy_engine.apply_calibration_recommendations(recommendations)

        if success:
            return {
                "success": True,
                "message": f"Applied {len(recommendations)} calibration adjustments for {rating_type}",
                "applied_count": len(recommendations)
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to apply calibration recommendations")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error applying calibration for {rating_type}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/historical-comparison")
async def get_historical_comparison(days: int = Query(90, ge=30, le=365)):
    """
    Get historical comparison between app ratings and FargoRate data.
    Shows how accuracy has improved over time.
    """
    try:
        db = get_database_manager()
        accuracy_engine = RatingAccuracyEngine(db)

        comparison_data = {}

        for rating_type in ['fargo', 'alfa', 'est']:
            # Get accuracy over different time periods
            periods = [
                (30, "last_30_days"),
                (60, "last_60_days"),
                (90, "last_90_days")
            ]

            comparison_data[rating_type] = {}

            for days_back, period_name in periods:
                metrics = accuracy_engine.calculate_accuracy_metrics(
                    rating_type,
                    date.today() - timedelta(days=days_back),
                    date.today()
                )

                if metrics:
                    comparison_data[rating_type][period_name] = {
                        "accuracy_percentage": round(metrics.accuracy_percentage, 2),
                        "sample_size": metrics.sample_size,
                        "mean_absolute_error": round(metrics.mean_absolute_error, 2)
                    }

        return {
            "success": True,
            "data": comparison_data,
            "analysis_period_days": days
        }

    except Exception as e:
        logger.error(f"Error fetching historical comparison: {e}")
        raise HTTPException(status_code=500, detail=str(e))