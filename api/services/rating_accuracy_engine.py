"""
Rating Accuracy Engine - Self-Calibrating Rating System

This engine compares app-calculated ratings with FargoRate data to:
1. Calculate accuracy percentages for each rating type
2. Self-calibrate rating algorithms to improve accuracy over time
3. Track confidence scores and prediction uncertainty
4. Provide accuracy metrics for admin dashboard

The goal is to make the app increasingly independent of FargoRate data
by continuously improving its own rating calculations.
"""

import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import statistics
import json

logger = logging.getLogger(__name__)


@dataclass
class AccuracyMetrics:
    """Accuracy metrics for a rating system."""
    rating_type: str
    total_predictions: int
    accurate_predictions: int
    mean_absolute_error: float
    accuracy_percentage: float
    confidence_interval: float
    sample_size: int
    calculation_date: date


@dataclass
class CalibrationRecommendation:
    """Recommendation for adjusting rating calculation parameters."""
    parameter_name: str
    current_value: float
    recommended_value: float
    expected_improvement: float
    confidence_level: float
    reasoning: str


class RatingAccuracyEngine:
    """Engine for calculating rating accuracy and self-calibration."""

    # Accuracy thresholds for different confidence levels
    HIGH_ACCURACY_THRESHOLD = 0.95  # 95% considered "accurate"
    MEDIUM_ACCURACY_THRESHOLD = 0.85  # 85% considered "good"
    LOW_ACCURACY_THRESHOLD = 0.70  # 70% considered "needs improvement"

    # Minimum sample size for reliable accuracy calculations
    MIN_SAMPLE_SIZE = 50

    def __init__(self, db_manager):
        """Initialize with database manager."""
        self.db = db_manager

    def calculate_accuracy_metrics(self, rating_type: str,
                                 start_date: date = None,
                                 end_date: date = None) -> Optional[AccuracyMetrics]:
        """
        Calculate comprehensive accuracy metrics for a rating type.

        Compares app predictions with verified FargoRate data.
        """
        if start_date is None:
            start_date = date.today() - timedelta(days=30)
        if end_date is None:
            end_date = date.today()

        conn = self.db.get_connection()
        cursor = conn.cursor()

        try:
            # Get accuracy data for the specified period
            cursor.execute("""
                SELECT
                    COUNT(*) as total_predictions,
                    COUNT(CASE WHEN accuracy_score >= %s THEN 1 END) as accurate_predictions,
                    AVG(absolute_error) as mae,
                    AVG(accuracy_score) * 100.0 as accuracy_percentage,
                    STDDEV(accuracy_score) as std_dev
                FROM player_rating_accuracy
                WHERE rating_type = %s
                  AND prediction_date BETWEEN %s AND %s
                  AND actual_rating IS NOT NULL
            """, (self.HIGH_ACCURACY_THRESHOLD, rating_type, start_date, end_date))

            row = cursor.fetchone()
            if not row or row[0] == 0:  # No data
                return None

            total_predictions, accurate_predictions, mae, accuracy_pct, std_dev = row

            # Calculate 95% confidence interval
            if std_dev and total_predictions > 1:
                confidence_interval = 1.96 * (std_dev / (total_predictions ** 0.5))
            else:
                confidence_interval = 0.0

            return AccuracyMetrics(
                rating_type=rating_type,
                total_predictions=total_predictions,
                accurate_predictions=accurate_predictions,
                mean_absolute_error=mae or 0.0,
                accuracy_percentage=accuracy_pct or 0.0,
                confidence_interval=confidence_interval,
                sample_size=total_predictions,
                calculation_date=end_date
            )

        except Exception as e:
            logger.error(f"Error calculating accuracy metrics for {rating_type}: {e}")
            return None
        finally:
            conn.close()

    def update_accuracy_metrics(self, rating_type: str) -> bool:
        """
        Update the accuracy metrics table with latest calculations.
        """
        metrics = self.calculate_accuracy_metrics(rating_type)
        if not metrics:
            logger.warning(f"No accuracy data available for {rating_type}")
            return False

        conn = self.db.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO rating_accuracy_metrics (
                    rating_type, calculation_date, total_predictions,
                    accurate_predictions, mean_absolute_error,
                    accuracy_percentage, confidence_interval_lower,
                    confidence_interval_upper, sample_size
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (rating_type, calculation_date)
                DO UPDATE SET
                    total_predictions = EXCLUDED.total_predictions,
                    accurate_predictions = EXCLUDED.accurate_predictions,
                    mean_absolute_error = EXCLUDED.mean_absolute_error,
                    accuracy_percentage = EXCLUDED.accuracy_percentage,
                    confidence_interval_lower = EXCLUDED.confidence_interval_lower,
                    confidence_interval_upper = EXCLUDED.confidence_interval_upper,
                    sample_size = EXCLUDED.sample_size,
                    last_updated = CURRENT_TIMESTAMP
            """, (
                metrics.rating_type, metrics.calculation_date, metrics.total_predictions,
                metrics.accurate_predictions, metrics.mean_absolute_error,
                metrics.accuracy_percentage,
                metrics.accuracy_percentage - metrics.confidence_interval,  # lower bound
                metrics.accuracy_percentage + metrics.confidence_interval,  # upper bound
                metrics.sample_size
            ))

            conn.commit()
            logger.info(f"Updated accuracy metrics for {rating_type}: {metrics.accuracy_percentage:.1f}%")
            return True

        except Exception as e:
            logger.error(f"Error updating accuracy metrics for {rating_type}: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def record_rating_accuracy(self, player_id: str, player_name: str,
                             rating_type: str, predicted_rating: float,
                             actual_rating: float, data_source: str = "fargorate_api") -> bool:
        """
        Record an individual rating prediction for accuracy tracking.

        This is called whenever we have both a predicted rating and a verified actual rating.

        Args:
            player_id: Unique player identifier
            player_name: Player display name
            rating_type: Type of rating ('fargo', 'alfa', 'est')
            predicted_rating: Rating predicted by the system
            actual_rating: Verified actual rating from FargoRate or other source
            data_source: Source of the actual rating data

        Returns:
            True if successfully recorded, False otherwise
        """
        # Input validation
        if not player_id or not isinstance(player_id, str):
            logger.error("Invalid player_id provided to record_rating_accuracy")
            return False

        if not player_name or not isinstance(player_name, str):
            logger.error("Invalid player_name provided to record_rating_accuracy")
            return False

        if rating_type not in ['fargo', 'alfa', 'est']:
            logger.error(f"Invalid rating_type: {rating_type}")
            return False

        if not isinstance(predicted_rating, (int, float)) or predicted_rating < 0 or predicted_rating > 1000:
            logger.error(f"Invalid predicted_rating: {predicted_rating}")
            return False

        if not isinstance(actual_rating, (int, float)) or actual_rating < 0 or actual_rating > 1000:
            logger.error(f"Invalid actual_rating: {actual_rating}")
            return False

        if not data_source or not isinstance(data_source, str):
            logger.warning(f"Invalid data_source: {data_source}, using default")
            data_source = "unknown"

        # Calculate metrics
        absolute_error = abs(predicted_rating - actual_rating)
        max_rating = max(predicted_rating, actual_rating)

        # Calculate accuracy score (0.0 to 1.0, where 1.0 is perfect)
        if max_rating > 0:
            # Normalize error by rating magnitude
            accuracy_score = max(0.0, min(1.0, 1.0 - (absolute_error / max_rating)))
        else:
            accuracy_score = 0.0

        # Calculate confidence level based on various factors
        confidence_level = self._calculate_prediction_confidence(
            rating_type, predicted_rating, absolute_error
        )

        conn = None
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()

            # Validate database connection
            if not conn or conn.closed:
                logger.error("Database connection is not available")
                return False

            cursor.execute("""
                INSERT INTO player_rating_accuracy (
                    player_id, player_name, rating_type, predicted_rating,
                    actual_rating, absolute_error, accuracy_score,
                    confidence_level, prediction_date, data_source
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                player_id, player_name, rating_type, predicted_rating,
                actual_rating, absolute_error, accuracy_score,
                confidence_level, date.today(), data_source
            ))

            conn.commit()
            logger.debug(".2f")
            return True

        except Exception as e:
            logger.error(f"Error recording rating accuracy for {player_name}: {e}")
            if conn:
                try:
                    conn.rollback()
                except Exception as rollback_error:
                    logger.error(f"Error rolling back transaction: {rollback_error}")
            return False
        finally:
            if conn:
                try:
                    conn.close()
                except Exception as close_error:
                    logger.warning(f"Error closing database connection: {close_error}")

    def _calculate_prediction_confidence(self, rating_type: str,
                                       predicted_rating: float,
                                       absolute_error: float) -> float:
        """
        Calculate confidence level for a prediction based on various factors.
        """
        base_confidence = 0.5  # Start with moderate confidence

        # Adjust based on rating type reliability
        type_multipliers = {
            'fargo': 0.9,  # Fargo ratings are generally reliable
            'est': 0.8,    # EST ratings have some uncertainty
            'alfa': 0.7    # ALFA ratings have more uncertainty
        }

        base_confidence *= type_multipliers.get(rating_type, 0.5)

        # Adjust based on error magnitude
        if predicted_rating > 0:
            error_ratio = absolute_error / predicted_rating
            if error_ratio < 0.05:  # Very small error
                base_confidence *= 1.2
            elif error_ratio < 0.15:  # Moderate error
                base_confidence *= 1.0
            else:  # Large error
                base_confidence *= 0.8

        return min(0.95, max(0.1, base_confidence))

    def generate_calibration_recommendations(self, rating_type: str) -> List[CalibrationRecommendation]:
        """
        Analyze accuracy data and generate recommendations for parameter adjustments.
        """
        recommendations = []

        # Get recent accuracy trends
        recent_metrics = []
        for days_back in [7, 14, 30]:
            end_date = date.today()
            start_date = end_date - timedelta(days=days_back)
            metrics = self.calculate_accuracy_metrics(rating_type, start_date, end_date)
            if metrics:
                recent_metrics.append((days_back, metrics))

        if len(recent_metrics) < 2:
            return recommendations  # Need more data

        # Analyze trends
        accuracy_trend = recent_metrics[-1][1].accuracy_percentage - recent_metrics[0][1].accuracy_percentage

        if rating_type == 'est':
            # EST rating calibration recommendations
            if accuracy_trend < -5.0:  # Accuracy decreasing
                recommendations.append(CalibrationRecommendation(
                    parameter_name="k_factor_base",
                    current_value=32.0,
                    recommended_value=28.0,  # Reduce K-factor to make ratings more stable
                    expected_improvement=3.0,
                    confidence_level=0.75,
                    reasoning="Accuracy trending downward, reducing K-factor may stabilize ratings"
                ))

            if recent_metrics[-1][1].mean_absolute_error > 50:
                recommendations.append(CalibrationRecommendation(
                    parameter_name="confidence_base",
                    current_value=0.5,
                    recommended_value=0.6,  # Increase base confidence
                    expected_improvement=2.0,
                    confidence_level=0.8,
                    reasoning="High error rates suggest over-conservative confidence scoring"
                ))

        elif rating_type == 'alfa':
            # ALFA rating calibration recommendations
            if accuracy_trend < -3.0:
                recommendations.append(CalibrationRecommendation(
                    parameter_name="model_confidence_threshold",
                    current_value=0.7,
                    recommended_value=0.75,
                    expected_improvement=2.5,
                    confidence_level=0.7,
                    reasoning="ALFA accuracy declining, increasing confidence threshold may help"
                ))

        return recommendations

    def apply_calibration_recommendations(self, recommendations: List[CalibrationRecommendation]) -> bool:
        """
        Apply approved calibration recommendations to the system.
        """
        if not recommendations:
            return True

        conn = self.db.get_connection()
        cursor = conn.cursor()

        try:
            calibration_changes = []

            for rec in recommendations:
                # Record the calibration change
                cursor.execute("""
                    INSERT INTO rating_calibration_params (
                        rating_type, parameter_name, parameter_value, effective_date,
                        calibration_method, sample_size, confidence_interval
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    rec.parameter_name.split('_')[0],  # Extract rating type from param name
                    rec.parameter_name,
                    rec.recommended_value,
                    date.today(),
                    'automated_calibration',
                    100,  # Placeholder sample size
                    rec.confidence_level
                ))

                calibration_changes.append({
                    'parameter': rec.parameter_name,
                    'old_value': rec.current_value,
                    'new_value': rec.recommended_value,
                    'reasoning': rec.reasoning
                })

            # Record the system improvement
            cursor.execute("""
                INSERT INTO system_accuracy_improvement (
                    improvement_date, rating_type, previous_accuracy,
                    new_accuracy, improvement_amount, calibration_changes,
                    sample_size, statistical_significance, notes
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                date.today(),
                recommendations[0].parameter_name.split('_')[0],
                0.0,  # Would need to calculate from recent metrics
                0.0,  # Would need to calculate new accuracy
                sum(r.expected_improvement for r in recommendations),
                json.dumps(calibration_changes),
                100,
                0.8,
                f"Applied {len(recommendations)} automated calibration adjustments"
            ))

            conn.commit()
            logger.info(f"Applied {len(recommendations)} calibration recommendations")
            return True

        except Exception as e:
            logger.error(f"Error applying calibration recommendations: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def get_accuracy_dashboard_data(self) -> Dict[str, Any]:
        """
        Get accuracy data for the admin dashboard.
        """
        dashboard_data = {
            'overall_accuracy': {},
            'rating_type_breakdown': {},
            'recent_trends': {},
            'calibration_status': {}
        }

        rating_types = ['fargo', 'alfa', 'est']

        for rating_type in rating_types:
            # Current accuracy metrics
            metrics = self.calculate_accuracy_metrics(rating_type)
            if metrics:
                dashboard_data['rating_type_breakdown'][rating_type] = {
                    'accuracy_percentage': metrics.accuracy_percentage,
                    'total_predictions': metrics.total_predictions,
                    'mean_absolute_error': metrics.mean_absolute_error,
                    'confidence_interval': metrics.confidence_interval
                }

            # Recent trends (last 30 days vs previous 30 days)
            current_metrics = self.calculate_accuracy_metrics(
                rating_type,
                date.today() - timedelta(days=30),
                date.today()
            )
            previous_metrics = self.calculate_accuracy_metrics(
                rating_type,
                date.today() - timedelta(days=60),
                date.today() - timedelta(days=30)
            )

            if current_metrics and previous_metrics:
                trend = current_metrics.accuracy_percentage - previous_metrics.accuracy_percentage
                dashboard_data['recent_trends'][rating_type] = {
                    'current_accuracy': current_metrics.accuracy_percentage,
                    'previous_accuracy': previous_metrics.accuracy_percentage,
                    'trend': trend,
                    'trend_direction': 'improving' if trend > 0 else 'declining' if trend < 0 else 'stable'
                }

        # Overall system accuracy (weighted average)
        total_accuracy = 0.0
        total_weight = 0.0
        weights = {'fargo': 0.4, 'alfa': 0.3, 'est': 0.3}  # Weight by reliability

        for rating_type, weight in weights.items():
            if rating_type in dashboard_data['rating_type_breakdown']:
                accuracy = dashboard_data['rating_type_breakdown'][rating_type]['accuracy_percentage']
                total_accuracy += accuracy * weight
                total_weight += weight

        if total_weight > 0:
            dashboard_data['overall_accuracy'] = {
                'system_accuracy_percentage': total_accuracy / total_weight,
                'last_updated': datetime.now().isoformat(),
                'data_freshness': 'current'
            }

        return dashboard_data