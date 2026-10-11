"""
Rating Archive Service - Historical Rating Preservation

This service automatically archives old rating values before they are updated,
enabling comprehensive historical tracking and accuracy analysis over time.

Archives Fargo, ALFA, and EST ratings with full metadata for:
- Historical chart generation
- Accuracy comparison analysis
- Self-calibration improvements
- Audit trail maintenance
"""

import logging
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RatingArchiveRecord:
    """Represents a rating change that needs to be archived."""
    player_id: str
    player_name: str
    rating_type: str  # 'fargo', 'alfa', 'est'
    old_rating: Optional[float]
    new_rating: float
    ranking_system: Optional[str] = None
    source: str = 'system_update'
    confidence_score: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None


class RatingArchiveService:
    """Service for archiving rating changes before updates."""

    def __init__(self, db_manager):
        """Initialize with database manager."""
        self.db = db_manager

    def archive_fargo_rating(self, record: RatingArchiveRecord) -> bool:
        """
        Archive a Fargo rating change.
        """
        # Input validation
        if not record or record.rating_type != 'fargo':
            logger.error(f"Invalid record or wrong rating type for Fargo archive: {record.rating_type if record else 'None'}")
            return False

        if not record.player_id or not record.player_name:
            logger.error("Missing required player data for Fargo rating archive")
            return False

        if record.new_rating is None:
            logger.error(f"Missing new rating for Fargo archive of player {record.player_name}")
            return False

        conn = None
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()

            # Validate database connection
            if not conn or conn.closed:
                logger.error("Database connection is not available")
                return False

            cursor.execute("""
                INSERT INTO fargo_rating_history (
                    player_id, player_name, ranking_system,
                    old_fargo_rating, new_fargo_rating, fargo_source,
                    snapshot_date, confidence_score, data_quality
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                record.player_id,
                record.player_name,
                record.ranking_system,
                record.old_rating,
                record.new_rating,
                record.source or 'system_update',
                date.today(),
                max(0.0, min(1.0, record.confidence_score or 0.8)),  # Clamp confidence to [0,1]
                record.metadata.get('data_quality', 'verified') if record.metadata else 'verified'
            ))

            conn.commit()
            logger.debug("Archived Fargo rating %.2f for %s", record.new_rating, record.player_name)
            return True

        except Exception as e:
            logger.error(f"Error archiving Fargo rating for {record.player_name}: {e}")
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

    def archive_alfa_rating(self, record: RatingArchiveRecord) -> bool:
        """
        Archive an ALFA rating change.
        """
        # Input validation
        if not record or record.rating_type != 'alfa':
            logger.error(f"Invalid record or wrong rating type for ALFA archive: {record.rating_type if record else 'None'}")
            return False

        if not record.player_id or not record.player_name:
            logger.error("Missing required player data for ALFA rating archive")
            return False

        if record.new_rating is None:
            logger.error(f"Missing new rating for ALFA archive of player {record.player_name}")
            return False

        conn = None
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()

            # Validate database connection
            if not conn or conn.closed:
                logger.error("Database connection is not available")
                return False

            cursor.execute("""
                INSERT INTO alfa_rating_history (
                    player_id, player_name, ranking_system,
                    old_alfa_rating, new_alfa_rating, alfa_model_version,
                    snapshot_date, confidence_score, prediction_uncertainty
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                record.player_id,
                record.player_name,
                record.ranking_system,
                record.old_rating,
                record.new_rating,
                record.metadata.get('model_version', 'unknown') if record.metadata else 'unknown',
                date.today(),
                max(0.0, min(1.0, record.confidence_score or 0.7)),  # Clamp confidence to [0,1]
                record.metadata.get('uncertainty') if record.metadata else None
            ))

            conn.commit()
            logger.debug(".2f")
            return True

        except Exception as e:
            logger.error(f"Error archiving ALFA rating for {record.player_name}: {e}")
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

    def archive_est_rating_transition(self, player_id: str, player_name: str,
                                    old_rating: Optional[float], new_rating: float,
                                    confidence: float, game_context: Dict[str, Any]) -> bool:
        """
        Archive an EST rating transition (uses existing est_rating_transitions table).
        This is a special case since EST transitions are already tracked.
        """
        # For EST ratings, we rely on the existing transition tracking
        # in the LiveRatingEngine. This method is here for consistency.
        logger.debug(".2f")
        return True  # EST transitions are handled by LiveRatingEngine

    def archive_rating_change(self, record: RatingArchiveRecord) -> bool:
        """
        Archive a rating change based on its type.
        """
        if record.rating_type == 'fargo':
            return self.archive_fargo_rating(record)
        elif record.rating_type == 'alfa':
            return self.archive_alfa_rating(record)
        elif record.rating_type == 'est':
            # EST ratings use the existing transition system
            return self.archive_est_rating_transition(
                record.player_id, record.player_name,
                record.old_rating, record.new_rating,
                record.confidence_score or 0.8,
                record.metadata or {}
            )
        else:
            logger.error(f"Unknown rating type: {record.rating_type}")
            return False

    def batch_archive_rating_changes(self, records: List[RatingArchiveRecord]) -> Tuple[int, int]:
        """
        Archive multiple rating changes efficiently.

        Returns: (successful_archives, total_records)
        """
        successful = 0

        for record in records:
            if self.archive_rating_change(record):
                successful += 1

        logger.info(f"Batch archived {successful}/{len(records)} rating changes")
        return successful, len(records)

    def get_player_rating_history(self, player_id: str, rating_type: Optional[str] = None,
                                limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get historical rating data for a player across all rating types.

        Args:
            player_id: Player identifier
            rating_type: Optional filter for specific rating type ('fargo', 'alfa', 'est')
            limit: Maximum number of records to return (1-500)

        Returns:
            List of historical rating records
        """
        # Input validation
        if not player_id or not isinstance(player_id, str):
            logger.error("Invalid player_id provided to get_player_rating_history")
            return []

        if limit < 1 or limit > 500:
            logger.warning(f"Invalid limit {limit}, clamping to range 1-500")
            limit = max(1, min(500, limit))

        if rating_type and rating_type not in ['fargo', 'alfa', 'est']:
            logger.error(f"Invalid rating_type: {rating_type}")
            return []

        conn = None
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()

            # Validate database connection
            if not conn or conn.closed:
                logger.error("Database connection is not available")
                return []

            # Build query based on rating type filter
            if rating_type == 'fargo':
                query = """
                    SELECT 'fargo' as rating_type, new_fargo_rating as rating_value,
                           snapshot_date, archived_at, confidence_score, fargo_source as source
                    FROM fargo_rating_history
                    WHERE player_id = %s
                    ORDER BY snapshot_date DESC
                    LIMIT %s
                """
            elif rating_type == 'alfa':
                query = """
                    SELECT 'alfa' as rating_type, new_alfa_rating as rating_value,
                           snapshot_date, archived_at, confidence_score, alfa_model_version as source
                    FROM alfa_rating_history
                    WHERE player_id = %s
                    ORDER BY snapshot_date DESC
                    LIMIT %s
                """
            elif rating_type == 'est':
                query = """
                    SELECT 'est' as rating_type, new_est_rating as rating_value,
                           created_at::date as snapshot_date, created_at as archived_at,
                           confidence, formula_version as source
                    FROM est_rating_transitions
                    WHERE player_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                """
            else:
                # All rating types combined
                query = """
                    SELECT * FROM (
                        SELECT 'fargo' as rating_type, new_fargo_rating as rating_value,
                               snapshot_date, archived_at, confidence_score, fargo_source as source,
                               snapshot_date as sort_date
                        FROM fargo_rating_history
                        WHERE player_id = %s

                        UNION ALL

                        SELECT 'alfa' as rating_type, new_alfa_rating as rating_value,
                               snapshot_date, archived_at, confidence_score, alfa_model_version as source,
                               snapshot_date as sort_date
                        FROM alfa_rating_history
                        WHERE player_id = %s

                        UNION ALL

                        SELECT 'est' as rating_type, new_est_rating as rating_value,
                               created_at::date as snapshot_date, created_at as archived_at,
                               confidence, formula_version as source,
                               created_at::date as sort_date
                        FROM est_rating_transitions
                        WHERE player_id = %s
                    ) combined
                    ORDER BY sort_date DESC
                    LIMIT %s
                """

            if rating_type in ['fargo', 'alfa', 'est']:
                cursor.execute(query, (player_id, limit))
            else:
                cursor.execute(query, (player_id, player_id, player_id, limit))

            results = []
            for row in cursor.fetchall():
                try:
                    # Handle potential None values and date formatting
                    snapshot_date = row[2]
                    archived_at = row[3]

                    results.append({
                        'rating_type': row[0],
                        'rating_value': row[1],
                        'snapshot_date': snapshot_date.isoformat() if hasattr(snapshot_date, 'isoformat') else str(snapshot_date) if snapshot_date else None,
                        'archived_at': archived_at.isoformat() if hasattr(archived_at, 'isoformat') else str(archived_at) if archived_at else None,
                        'confidence_score': row[4] if row[4] is not None else 0.5,
                        'source': row[5] or 'unknown'
                    })
                except (IndexError, AttributeError) as e:
                    logger.warning(f"Error processing rating history row: {e}")
                    continue

            logger.debug(f"Retrieved {len(results)} historical rating records for player {player_id}")
            return results

        except Exception as e:
            logger.error(f"Error retrieving rating history for player {player_id}: {e}")
            return []
        finally:
            if conn:
                try:
                    conn.close()
                except Exception as close_error:
                    logger.warning(f"Error closing database connection: {close_error}")

    def get_rating_accuracy_trends(self, player_id: str, rating_type: str,
                                  days_back: int = 90) -> List[Dict[str, Any]]:
        """
        Get accuracy trends for a player's rating predictions over time.
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT prediction_date, accuracy_score, absolute_error, confidence_level
                FROM player_rating_accuracy
                WHERE player_id = %s AND rating_type = %s
                  AND prediction_date >= CURRENT_DATE - INTERVAL '%s days'
                ORDER BY prediction_date DESC
            """, (player_id, rating_type, days_back))

            trends = []
            for row in cursor.fetchall():
                trends.append({
                    'date': row[0].isoformat(),
                    'accuracy_score': row[1],
                    'absolute_error': row[2],
                    'confidence_level': row[3]
                })

            return trends

        except Exception as e:
            logger.error(f"Error retrieving accuracy trends for player {player_id}: {e}")
            return []
        finally:
            conn.close()