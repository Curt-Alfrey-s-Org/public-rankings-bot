#!/usr/bin/env python3
"""
Simple enrichment implementation to replace the complex one.
"""

def simple_enrich_player_data(engine):
    """Simple cross-system enrichment implementation."""
    from sqlalchemy import text
    import time
    import logging

    logger = logging.getLogger(__name__)
    logger.info("Starting simple cross-system player data enrichment")
    start_time = time.time()

    stats = {
        'matched_players': 0,
        'fields_filled': 0,
        'conflicts_logged': 0
    }

    try:
        with engine.begin() as conn:
            # Find players who appear in multiple systems
            result = conn.execute(text("""
                SELECT DISTINCT player_name
                FROM rankings
                WHERE player_name IN (
                    SELECT player_name
                    FROM rankings
                    GROUP BY player_name
                    HAVING COUNT(DISTINCT ranking_system) > 1
                )
                ORDER BY player_name
            """))

            cross_system_players = [row[0] for row in result.fetchall()]
            stats['matched_players'] = len(cross_system_players)

            for player_name in cross_system_players:
                try:
                    # Get all records for this player
                    result = conn.execute(text("""
                        SELECT id, player_name, ranking_system, license_number, fargo_rating, country
                        FROM rankings
                        WHERE player_name = :name
                        ORDER BY snapshot_date DESC
                    """), {'name': player_name})

                    records = result.fetchall()
                    if len(records) < 2:
                        continue

                    # Find best values across all systems
                    best_license = None
                    best_fargo = None
                    best_country = None

                    for record in records:
                        record_id, name, system, license, fargo, country = record
                        if license and not best_license:
                            best_license = license
                        if fargo is not None and (best_fargo is None or fargo > best_fargo):
                            best_fargo = fargo
                        if country and not best_country:
                            best_country = country

                    # Update records that are missing data
                    for record in records:
                        record_id, name, system, license, fargo, country = record

                        updates = {}
                        if not license and best_license:
                            updates['license_number'] = best_license
                        if fargo is None and best_fargo is not None:
                            updates['fargo_rating'] = best_fargo
                        if not country and best_country:
                            updates['country'] = best_country

                        if updates:
                            # Build update query
                            set_parts = [f"{k} = :{k}" for k in updates.keys()]
                            set_clause = ", ".join(set_parts)
                            params = {'record_id': record_id, **updates}

                            conn.execute(text(f"""
                                UPDATE rankings
                                SET {set_clause}, updated_at = CURRENT_TIMESTAMP
                                WHERE id = :record_id
                            """), params)

                            stats['fields_filled'] += len(updates)

                except Exception as e:
                    logger.warning(f"Failed to enrich data for player {player_name}: {e}")
                    stats['conflicts_logged'] += 1

    except Exception as e:
        logger.error(f"Enrichment failed: {e}")
        stats['conflicts_logged'] += 1

    stats['duration_seconds'] = time.time() - start_time
    logger.info(f"Enrichment completed: {stats['matched_players']} players, "
               f"{stats['fields_filled']} fields filled")

    return stats