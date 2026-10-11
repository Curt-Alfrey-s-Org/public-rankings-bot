"""
ALFA Placement Inference Engine.

Infers a minimum skill rating (floor) for unrated players based on
tournament placements relative to Fargo-rated opponents.

Logic:
    If Player A (no Fargo) placed HIGHER than Player B (Fargo X)
    in the same tournament, Player A's inferred floor >= X.

    Across multiple tournaments, take the MAX of all such floors,
    apply a small confidence discount, and store as ALFA (not Fargo).

The result is a conservative floor estimate -- the player is *at least*
this good.  It is NOT an official Fargo rating.
"""

import logging
from typing import Dict, List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

CONFIDENCE_DISCOUNT = 25


def infer_alfa_from_placements(
    engine: Engine,
    *,
    discount: int = CONFIDENCE_DISCOUNT,
) -> Dict[str, dict]:
    """Infer ALFA floor ratings from tournament placement data.

    Returns:
        {player_name: {
            "inferred_rating": float,
            "raw_floor": float,
            "discount": int,
            "num_tournaments": int,
            "best_beaten_player": str,
            "best_beaten_fargo": float,
        }}
    """
    with engine.connect() as conn:
        rows = conn.execute(text("""
            WITH latest AS (
                SELECT ranking_system, MAX(snapshot_date) AS max_date
                FROM rankings GROUP BY ranking_system
            ),
            rated AS (
                SELECT DISTINCT r.player_name, MAX(r.fargo_rating) AS fargo
                FROM rankings r
                JOIN latest l
                  ON r.ranking_system = l.ranking_system
                  AND r.snapshot_date = l.max_date
                WHERE r.fargo_rating IS NOT NULL
                GROUP BY r.player_name
            ),
            unrated AS (
                SELECT DISTINCT r.player_name
                FROM rankings r
                JOIN latest l
                  ON r.ranking_system = l.ranking_system
                  AND r.snapshot_date = l.max_date
                WHERE r.fargo_rating IS NULL
                AND r.player_name NOT IN (SELECT player_name FROM rated)
            ),
            inferences AS (
                SELECT
                    tr_u.player_name AS unrated_name,
                    tr_r.player_name AS beaten_name,
                    rated.fargo AS beaten_fargo,
                    tr_u.tournament_id,
                    tr_u.placement AS unrated_placement,
                    tr_r.placement AS beaten_placement
                FROM tournament_results tr_u
                JOIN unrated u ON tr_u.player_name = u.player_name
                JOIN tournament_results tr_r
                  ON tr_u.tournament_id = tr_r.tournament_id
                  AND tr_u.placement < tr_r.placement
                JOIN rated ON tr_r.player_name = rated.player_name
            )
            SELECT
                unrated_name,
                MAX(beaten_fargo) AS raw_floor,
                COUNT(DISTINCT tournament_id) AS num_tournaments,
                -- best beaten player (the one with the highest Fargo)
                (ARRAY_AGG(beaten_name ORDER BY beaten_fargo DESC))[1] AS best_beaten_player,
                MAX(beaten_fargo) AS best_beaten_fargo
            FROM inferences
            GROUP BY unrated_name
            ORDER BY raw_floor DESC
        """)).fetchall()

    results: Dict[str, dict] = {}
    for row in rows:
        name = row[0]
        raw_floor = float(row[1])
        num_tournaments = int(row[2])
        best_beaten = row[3]
        best_beaten_fargo = float(row[4])

        inferred = max(0, raw_floor - discount)

        results[name] = {
            "inferred_rating": round(inferred, 1),
            "raw_floor": raw_floor,
            "discount": discount,
            "num_tournaments": num_tournaments,
            "best_beaten_player": best_beaten,
            "best_beaten_fargo": best_beaten_fargo,
        }

    logger.info(
        "Placement inference: %d players inferred (discount=%d)",
        len(results), discount,
    )
    return results


def apply_inferred_ratings(engine: Engine, results: Dict[str, dict]) -> int:
    """Write inferred ALFA ratings to rankings.alfa_rating for unrated players.

    Only updates rows where fargo_rating IS NULL (never overwrites official Fargo).
    Stores inference metadata in source_data under the ``alfa_source`` key.

    Returns:
        Total rows updated across all ranking systems.
    """
    if not results:
        return 0

    total = 0
    with engine.connect() as conn:
        for name, info in results.items():
            rating = info["inferred_rating"]
            meta = {
                "alfa_source": "placement_inference",
                "alfa_raw_floor": info["raw_floor"],
                "alfa_discount": info["discount"],
                "alfa_tournaments_used": info["num_tournaments"],
                "alfa_best_beaten": info["best_beaten_player"],
                "alfa_best_beaten_fargo": info["best_beaten_fargo"],
            }
            result = conn.execute(text("""
                UPDATE rankings
                SET alfa_rating = :rating,
                    source_data = COALESCE(source_data, '{}'::jsonb) || CAST(:meta AS jsonb)
                WHERE player_name = :name
                AND fargo_rating IS NULL
                AND (alfa_rating IS NULL OR alfa_rating < :rating)
            """), {
                "rating": rating,
                "meta": __import__("json").dumps(meta),
                "name": name,
            })
            total += result.rowcount
        conn.commit()

    logger.info("Applied inferred ALFA ratings: %d rows updated", total)
    return total


def get_inference_summary(results: Dict[str, dict]) -> str:
    """Human-readable summary of inference results."""
    if not results:
        return "No players could be inferred from placement data."
    ratings = [v["inferred_rating"] for v in results.values()]
    multi_tourn = [v for v in results.values() if v["num_tournaments"] >= 2]
    lines = [
        f"Inferred {len(results)} players from tournament placements:",
        f"  Rating range: {min(ratings):.0f} - {max(ratings):.0f}",
        f"  Players with 2+ tournament evidence: {len(multi_tourn)}",
        f"  Confidence discount applied: -{results[next(iter(results))]['discount']} pts",
    ]
    return "\n".join(lines)
