"""
Self-Calibration Engine - Autonomous Rating System Improvement

This engine continuously analyzes historical rating data to improve the accuracy
of Fargo, ALFA, and EST rating calculations. The goal is to make the app
increasingly independent of FargoRate data by self-tuning rating algorithms.

Key Features:
- Historical trend analysis for accuracy improvement
- Automatic parameter adjustment based on performance data
- Tournament validation of rating calculations
- Confidence-based learning from verified results
- Progressive reduction of FargoRate dependency
"""

import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import statistics
import json

logger = logging.getLogger(__name__)


@dataclass
class CalibrationParameter:
    """A parameter that can be calibrated."""
    name: str
    current_value: float
    min_value: float
    max_value: float
    step_size: float
    description: str


@dataclass
class CalibrationResult:
    """Result of a calibration adjustment."""
    parameter_name: str
    old_value: float
    new_value: float
    expected_improvement: float
    confidence_level: float
    reasoning: str


class SelfCalibrationEngine:
    """
    Engine for self-calibrating rating calculations based on historical performance.
    """

    # Default calibration parameters for each rating type
    DEFAULT_PARAMETERS = {
        'est': {
            'k_factor_base': CalibrationParameter(
                name='k_factor_base',
                current_value=32.0,
                min_value=16.0,
                max_value=64.0,
                step_size=4.0,
                description='Base K-factor for Elo-style rating updates'
            ),
            'confidence_base': CalibrationParameter(
                name='confidence_base',
                current_value=0.5,
                min_value=0.3,
                max_value=0.8,
                step_size=0.05,
                description='Base confidence level for new players'
            ),
            'confidence_growth_rate': CalibrationParameter(
                name='confidence_growth_rate',
                current_value=0.1,
                min_value=0.05,
                max_value=0.2,
                step_size=0.02,
                description='Rate at which confidence grows with games played'
            )
        },
        'alfa': {
            'model_confidence_threshold': CalibrationParameter(
                name='model_confidence_threshold',
                current_value=0.7,
                min_value=0.5,
                max_value=0.9,
                step_size=0.05,
                description='Minimum confidence threshold for ALFA predictions'
            ),
            'prediction_weight_recent': CalibrationParameter(
                name='prediction_weight_recent',
                current_value=0.6,
                min_value=0.3,
                max_value=0.8,
                step_size=0.1,
                description='Weight given to recent tournament performance vs historical'
            )
        },
        'fargo': {
            'api_reliability_score': CalibrationParameter(
                name='api_reliability_score',
                current_value=0.9,
                min_value=0.7,
                max_value=0.95,
                step_size=0.02,
                description='Assumed reliability of FargoRate API data'
            ),
            'scraper_success_rate': CalibrationParameter(
                name='scraper_success_rate',
                current_value=0.85,
                min_value=0.7,
                max_value=0.95,
                step_size=0.02,
                description='Expected success rate of Fargo scraping operations'
            )
        }
    }

    def __init__(self, db_manager, accuracy_engine):
        """Initialize with database and accuracy engines."""
        self.db = db_manager
        self.accuracy_engine = accuracy_engine
        self.parameters = self._load_current_parameters()

    def _load_current_parameters(self) -> Dict[str, Dict[str, CalibrationParameter]]:
        """
        Load current calibration parameters from the database.
        """
        parameters = {}

        for rating_type, param_defs in self.DEFAULT_PARAMETERS.items():
            parameters[rating_type] = {}
            for param_name, default_param in param_defs.items():
                # Try to load from database, fall back to defaults
                db_value = self._get_parameter_from_db(rating_type, param_name)
                if db_value is not None:
                    param_copy = CalibrationParameter(
                        name=param_name,
                        current_value=db_value,
                        min_value=default_param.min_value,
                        max_value=default_param.max_value,
                        step_size=default_param.step_size,
                        description=default_param.description
                    )
                    parameters[rating_type][param_name] = param_copy
                else:
                    parameters[rating_type][param_name] = default_param

        return parameters

    def _get_parameter_from_db(self, rating_type: str, parameter_name: str) -> Optional[float]:
        """
        Get the current value of a calibration parameter from the database.
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT parameter_value
                FROM rating_calibration_params
                WHERE rating_type = %s AND parameter_name = %s
                ORDER BY effective_date DESC
                LIMIT 1
            """, (rating_type, parameter_name))

            row = cursor.fetchone()
            return float(row[0]) if row else None

        except Exception as e:
            logger.warning(f"Could not load parameter {parameter_name} for {rating_type}: {e}")
            return None
        finally:
            conn.close()

    def analyze_accuracy_trends(self, rating_type: str, days_back: int = 90) -> Dict[str, Any]:
        """
        Analyze accuracy trends to identify improvement opportunities.
        """
        # Get accuracy data over time periods
        periods = [
            (30, "last_30_days"),
            (60, "last_60_days"),
            (90, "last_90_days")
        ]

        trend_data = {}
        accuracy_scores = []

        for days, period_name in periods:
            end_date = date.today()
            start_date = end_date - timedelta(days=days)

            metrics = self.accuracy_engine.calculate_accuracy_metrics(
                rating_type, start_date, end_date
            )

            if metrics:
                trend_data[period_name] = {
                    'accuracy': metrics.accuracy_percentage,
                    'mae': metrics.mean_absolute_error,
                    'sample_size': metrics.sample_size
                }
                accuracy_scores.append(metrics.accuracy_percentage)

        # Analyze trends
        analysis = {
            'trend_data': trend_data,
            'overall_trend': self._calculate_trend(accuracy_scores),
            'recommendations': []
        }

        # Generate recommendations based on analysis
        if len(accuracy_scores) >= 2:
            recent_accuracy = accuracy_scores[-1]  # Most recent
            previous_accuracy = accuracy_scores[-2]  # Previous period

            if recent_accuracy < 75.0:  # Below acceptable threshold
                analysis['recommendations'].append({
                    'type': 'accuracy_improvement',
                    'priority': 'high',
                    'description': f'{rating_type.upper()} accuracy ({recent_accuracy:.1f}%) below acceptable threshold'
                })

            accuracy_change = recent_accuracy - previous_accuracy
            if accuracy_change < -5.0:  # Declining accuracy
                analysis['recommendations'].append({
                    'type': 'trend_reversal',
                    'priority': 'high',
                    'description': f'{rating_type.upper()} accuracy declining ({accuracy_change:.1f}% change)'
                })

        return analysis

    def _calculate_trend(self, values: List[float]) -> str:
        """
        Calculate trend direction from a series of values.
        """
        if len(values) < 2:
            return 'insufficient_data'

        # Simple linear trend
        if len(values) >= 3:
            # Check if generally increasing or decreasing
            increases = sum(1 for i in range(1, len(values)) if values[i] > values[i-1])
            decreases = sum(1 for i in range(1, len(values)) if values[i] < values[i-1])

            if increases > decreases:
                return 'improving'
            elif decreases > increases:
                return 'declining'
            else:
                return 'stable'
        else:
            # Simple comparison of last two values
            return 'improving' if values[-1] > values[0] else 'declining' if values[-1] < values[0] else 'stable'

    def generate_parameter_adjustments(self, rating_type: str) -> List[CalibrationResult]:
        """
        Generate recommended parameter adjustments based on accuracy analysis.
        """
        adjustments = []
        analysis = self.analyze_accuracy_trends(rating_type)

        if not analysis['trend_data']:
            return adjustments

        most_recent = list(analysis['trend_data'].values())[-1]
        current_accuracy = most_recent['accuracy']

        # Get current parameters for this rating type
        current_params = self.parameters.get(rating_type, {})

        if rating_type == 'est':
            # EST rating calibration logic
            if current_accuracy < 75.0:
                # Low accuracy - try increasing K-factor for more responsive ratings
                k_factor_param = current_params.get('k_factor_base')
                if k_factor_param and k_factor_param.current_value < k_factor_param.max_value:
                    new_value = min(k_factor_param.current_value + k_factor_param.step_size,
                                  k_factor_param.max_value)
                    adjustments.append(CalibrationResult(
                        parameter_name='k_factor_base',
                        old_value=k_factor_param.current_value,
                        new_value=new_value,
                        expected_improvement=2.0,  # Expected 2% accuracy improvement
                        confidence_level=0.7,
                        reasoning='Increasing K-factor to make ratings more responsive to recent performance'
                    ))

            if analysis['overall_trend'] == 'declining':
                # Declining trend - try adjusting confidence growth
                conf_growth_param = current_params.get('confidence_growth_rate')
                if conf_growth_param:
                    # Slow down confidence growth to stabilize ratings
                    new_value = max(conf_growth_param.current_value - conf_growth_param.step_size,
                                  conf_growth_param.min_value)
                    adjustments.append(CalibrationResult(
                        parameter_name='confidence_growth_rate',
                        old_value=conf_growth_param.current_value,
                        new_value=new_value,
                        expected_improvement=1.5,
                        confidence_level=0.6,
                        reasoning='Reducing confidence growth rate to stabilize declining accuracy trend'
                    ))

        elif rating_type == 'alfa':
            # ALFA rating calibration logic
            if current_accuracy < 70.0:
                # Low accuracy - try increasing weight on recent performance
                weight_param = current_params.get('prediction_weight_recent')
                if weight_param and weight_param.current_value < weight_param.max_value:
                    new_value = min(weight_param.current_value + weight_param.step_size,
                                  weight_param.max_value)
                    adjustments.append(CalibrationResult(
                        parameter_name='prediction_weight_recent',
                        old_value=weight_param.current_value,
                        new_value=new_value,
                        expected_improvement=3.0,
                        confidence_level=0.75,
                        reasoning='Increasing weight on recent performance to improve ALFA accuracy'
                    ))

        elif rating_type == 'fargo':
            # Fargo rating calibration (mostly about data quality)
            if current_accuracy < 80.0:
                reliability_param = current_params.get('api_reliability_score')
                if reliability_param:
                    # Reduce assumed reliability to make system more conservative
                    new_value = max(reliability_param.current_value - reliability_param.step_size,
                                  reliability_param.min_value)
                    adjustments.append(CalibrationResult(
                        parameter_name='api_reliability_score',
                        old_value=reliability_param.current_value,
                        new_value=new_value,
                        expected_improvement=1.0,
                        confidence_level=0.8,
                        reasoning='Reducing assumed API reliability to improve error handling'
                    ))

        return adjustments

    def apply_parameter_adjustments(self, adjustments: List[CalibrationResult]) -> bool:
        """
        Apply the recommended parameter adjustments to the database.

        Args:
            adjustments: List of calibration adjustments to apply

        Returns:
            True if all adjustments applied successfully, False otherwise
        """
        # Input validation
        if not adjustments:
            logger.info("No parameter adjustments to apply")
            return True

        if not isinstance(adjustments, list):
            logger.error("Invalid adjustments parameter: must be a list")
            return False

        # Validate each adjustment
        for i, adjustment in enumerate(adjustments):
            if not isinstance(adjustment, CalibrationResult):
                logger.error(f"Invalid adjustment at index {i}: not a CalibrationResult")
                return False

            # Validate parameter values are within bounds
            rating_type = adjustment.parameter_name.split('_')[0]
            if rating_type in self.parameters and adjustment.parameter_name in self.parameters[rating_type]:
                param_def = self.parameters[rating_type][adjustment.parameter_name]
                if not (param_def.min_value <= adjustment.new_value <= param_def.max_value):
                    logger.error(f"Parameter {adjustment.parameter_name} value {adjustment.new_value} out of bounds [{param_def.min_value}, {param_def.max_value}]")
                    return False

        conn = None
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()

            # Validate database connection
            if not conn or conn.closed:
                logger.error("Database connection is not available")
                return False

            adjustment_details = []

            for adjustment in adjustments:
                # Extract rating type from parameter name (e.g., 'est_k_factor_base' -> 'est')
                rating_type = adjustment.parameter_name.split('_')[0]

                # Validate rating type
                if rating_type not in ['est', 'alfa', 'fargo']:
                    logger.warning(f"Unknown rating type '{rating_type}' for parameter {adjustment.parameter_name}, skipping")
                    continue

                # Update parameter in database
                cursor.execute("""
                    INSERT INTO rating_calibration_params (
                        rating_type, parameter_name, parameter_value, effective_date,
                        calibration_method, sample_size, confidence_interval
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    rating_type,
                    adjustment.parameter_name,
                    adjustment.new_value,
                    date.today(),
                    'automated_self_calibration',
                    100,  # Placeholder sample size
                    adjustment.confidence_level
                ))

                # Update in-memory parameters
                if rating_type in self.parameters and adjustment.parameter_name in self.parameters[rating_type]:
                    self.parameters[rating_type][adjustment.parameter_name].current_value = adjustment.new_value

                adjustment_details.append({
                    'parameter': adjustment.parameter_name,
                    'old_value': adjustment.old_value,
                    'new_value': adjustment.new_value,
                    'reasoning': adjustment.reasoning
                })

            # Record the calibration event
            total_improvement = sum(adj.expected_improvement for adj in adjustments)

            cursor.execute("""
                INSERT INTO system_accuracy_improvement (
                    improvement_date, rating_type, previous_accuracy,
                    new_accuracy, improvement_amount, calibration_changes,
                    sample_size, statistical_significance, notes
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                date.today(),
                'system_wide',  # Apply to all rating types
                0.0,  # Would need to calculate from recent metrics
                0.0,  # Would need to calculate new accuracy
                total_improvement,
                json.dumps(adjustment_details),
                len(adjustments) * 100,  # Rough sample size estimate
                0.8,  # Default statistical significance
                f"Self-calibration applied {len(adjustments)} parameter adjustments with expected {total_improvement:.1f}% improvement"
            ))

            conn.commit()
            logger.info(f"Successfully applied {len(adjustments)} parameter adjustments with expected {total_improvement:.1f}% accuracy improvement")
            return True

        except Exception as e:
            logger.error(f"Error applying parameter adjustments: {e}")
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

    def run_self_calibration_cycle(self) -> Dict[str, Any]:
        """
        Run a complete self-calibration cycle for all rating types.
        """
        results = {
            'timestamp': datetime.now().isoformat(),
            'rating_types_processed': [],
            'adjustments_applied': [],
            'accuracy_improvements': {},
            'errors': []
        }

        rating_types = ['fargo', 'alfa', 'est']

        for rating_type in rating_types:
            try:
                # Analyze current accuracy
                analysis = self.analyze_accuracy_trends(rating_type)

                # Generate adjustments
                adjustments = self.generate_parameter_adjustments(rating_type)

                # Apply adjustments if any
                if adjustments:
                    success = self.apply_parameter_adjustments(adjustments)
                    if success:
                        results['adjustments_applied'].extend([
                            {
                                'rating_type': rating_type,
                                'parameter': adj.parameter_name,
                                'old_value': adj.old_value,
                                'new_value': adj.new_value,
                                'reasoning': adj.reasoning
                            }
                            for adj in adjustments
                        ])

                results['rating_types_processed'].append(rating_type)
                results['accuracy_improvements'][rating_type] = {
                    'current_accuracy': list(analysis['trend_data'].values())[-1]['accuracy'] if analysis['trend_data'] else None,
                    'trend': analysis['overall_trend'],
                    'recommendations_count': len(analysis.get('recommendations', []))
                }

            except Exception as e:
                error_msg = f"Error calibrating {rating_type}: {str(e)}"
                logger.error(error_msg)
                results['errors'].append(error_msg)

        return results

    def get_independence_progress(self) -> Dict[str, Any]:
        """
        Calculate how independent the system is from FargoRate data.
        """
        progress = {
            'overall_independence': 0.0,
            'rating_type_independence': {},
            'fargorate_reduction_trend': [],
            'estimated_full_independence_date': None
        }

        rating_types = ['fargo', 'alfa', 'est']

        for rating_type in rating_types:
            # Get accuracy metrics
            metrics = self.accuracy_engine.calculate_accuracy_metrics(rating_type)
            if metrics:
                # Calculate independence based on accuracy and sample size
                # Higher accuracy + larger sample size = more independence
                accuracy_factor = min(metrics.accuracy_percentage / 100.0, 1.0)
                sample_factor = min(metrics.sample_size / 1000.0, 1.0)  # Scale by sample size

                independence_score = (accuracy_factor * 0.7) + (sample_factor * 0.3)
                progress['rating_type_independence'][rating_type] = {
                    'independence_score': independence_score,
                    'accuracy_contribution': accuracy_factor,
                    'sample_size_contribution': sample_factor,
                    'accuracy_percentage': metrics.accuracy_percentage
                }

        # Calculate overall independence
        if progress['rating_type_independence']:
            avg_independence = statistics.mean([
                data['independence_score']
                for data in progress['rating_type_independence'].values()
            ])
            progress['overall_independence'] = avg_independence

            # Estimate full independence date (when all types reach 95% accuracy)
            if avg_independence > 0.8:
                # Project based on current improvement rate
                remaining_progress = 0.95 - avg_independence
                estimated_months = max(1, int(remaining_progress * 12))  # Rough estimate
                progress['estimated_full_independence_date'] = (
                    date.today() + timedelta(days=estimated_months * 30)
                ).isoformat()

        return progress