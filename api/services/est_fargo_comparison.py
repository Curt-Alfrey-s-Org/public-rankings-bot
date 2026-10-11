"""
EST vs published Fargo comparison (Roadmap Phase 4).

Pairs players.est_rating with players.fargo_score into player_rating_accuracy
and refreshes rating_accuracy_metrics for rating_type='est'.

Doc refs (AI / maintainers): docs/ROADMAP.md § Phase 4
"""

from __future__ import annotations

import logging
import math
from datetime import date
from typing import Any, Optional

from api.services.rating_accuracy_engine import RatingAccuracyEngine

logger = logging.getLogger(__name__)


def run_est_fargo_comparison(db_manager: Any) -> dict[str, Any]:
    """
    Compare EST to Fargo for all players with both values.

    Returns summary: compared, recorded, mae, rmse, segments.
    """
    engine = RatingAccuracyEngine(db_manager)
    conn = db_manager.get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT player_id,
                   COALESCE(NULLIF(TRIM(first_name || ' ' || last_name), ''), player_id) AS player_name,
                   est_rating,
                   fargo_score,
                   COALESCE(est_rating_robustness, 0) AS robustness
            FROM players
            WHERE est_rating IS NOT NULL
              AND fargo_score IS NOT NULL
              AND est_rating > 0
              AND fargo_score > 0
            """
        )
        rows = cur.fetchall()
    finally:
        conn.close()

    recorded = 0
    errors: list[float] = []
    segments: dict[str, list[float]] = {
        "robust_0_5": [],
        "robust_6_20": [],
        "robust_21_plus": [],
        "rating_lt_500": [],
        "rating_500_650": [],
        "rating_gt_650": [],
    }

    for row in rows:
        player_id, player_name, est, fargo, robustness = row
        est_f = float(est)
        fargo_f = float(fargo)
        ok = engine.record_rating_accuracy(
            str(player_id),
            str(player_name or player_id),
            "est",
            est_f,
            fargo_f,
            data_source="players.fargo_score",
        )
        if ok:
            recorded += 1
            err = abs(est_f - fargo_f)
            errors.append(err)
            rob = int(robustness or 0)
            if rob <= 5:
                segments["robust_0_5"].append(err)
            elif rob <= 20:
                segments["robust_6_20"].append(err)
            else:
                segments["robust_21_plus"].append(err)
            if est_f < 500:
                segments["rating_lt_500"].append(err)
            elif est_f <= 650:
                segments["rating_500_650"].append(err)
            else:
                segments["rating_gt_650"].append(err)

    mae = sum(errors) / len(errors) if errors else None
    rmse = math.sqrt(sum(e * e for e in errors) / len(errors)) if errors else None

    metrics_updated = engine.update_accuracy_metrics("est")

    # Best-effort RMSE write if column exists
    if mae is not None and rmse is not None:
        try:
            conn2 = db_manager.get_connection()
            cur2 = conn2.cursor()
            cur2.execute(
                """
                UPDATE rating_accuracy_metrics
                SET root_mean_squared_error = %s, last_updated = CURRENT_TIMESTAMP
                WHERE rating_type = 'est' AND calculation_date = %s
                """,
                (rmse, date.today()),
            )
            conn2.commit()
            conn2.close()
        except Exception as e:
            logger.debug("RMSE column update skipped: %s", e)

    def _seg_mae(vals: list[float]) -> Optional[float]:
        return round(sum(vals) / len(vals), 3) if vals else None

    segment_mae = {k: _seg_mae(v) for k, v in segments.items()}
    segment_n = {k: len(v) for k, v in segments.items()}

    # Optional improvement log
    try:
        conn3 = db_manager.get_connection()
        cur3 = conn3.cursor()
        cur3.execute(
            """
            INSERT INTO system_accuracy_improvement (
                improvement_date, rating_type, previous_accuracy, new_accuracy,
                improvement_amount, calibration_changes, sample_size, notes
            ) VALUES (
                %s, 'est', NULL, NULL, NULL, %s::jsonb, %s, %s
            )
            """,
            (
                date.today(),
                __import__("json").dumps(
                    {"mae": mae, "rmse": rmse, "segment_mae": segment_mae}
                ),
                recorded,
                "est_fargo_comparison snapshot",
            ),
        )
        conn3.commit()
        conn3.close()
    except Exception as e:
        logger.debug("system_accuracy_improvement insert skipped: %s", e)

    return {
        "ok": True,
        "candidates": len(rows),
        "recorded": recorded,
        "mae": round(mae, 3) if mae is not None else None,
        "rmse": round(rmse, 3) if rmse is not None else None,
        "metrics_updated": metrics_updated,
        "segment_mae": segment_mae,
        "segment_n": segment_n,
        "calculation_date": date.today().isoformat(),
    }
