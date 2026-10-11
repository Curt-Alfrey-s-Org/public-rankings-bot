#!/usr/bin/env python3
"""
PostgreSQL database manager for Rankings Bot
Replacement for SQLite db_manager with PostgreSQL/SQLAlchemy
"""

# Doc refs (AI / maintainers): docs/RANKINGS_DATA_DOC_HOOKS.md; docs/RANKINGS_TABLE_DESIGN.md;
#   docs/WPA_RANKINGS_DATA_FLOW.md; docs/WPBA_DATA_FLOW.md; docs/RANKINGS_DATA_CONSOLIDATION.md

import hashlib
import json
import os
import re
import time
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Any, Union, Tuple
import logging
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError, OperationalError
from . import get_engine
from scrapers.wpba_pdf_columns import (
    WPBA_ROTATING_11TH_KEY,
    WPBA_ROTATING_11TH_LABEL,
)

logger = logging.getLogger(__name__)
DB_CONNECT_MAX_RETRIES = max(1, int(os.getenv("DB_CONNECT_MAX_RETRIES", "3")))
DB_CONNECT_BASE_BACKOFF_SEC = max(0.1, float(os.getenv("DB_CONNECT_BASE_BACKOFF_SEC", "0.5")))
RANKINGS_DROP_GUARD_ENABLED = os.getenv("RANKINGS_DROP_GUARD_ENABLED", "1") == "1"
RANKINGS_DROP_GUARD_MIN_PREV_COUNT = max(1, int(os.getenv("RANKINGS_DROP_GUARD_MIN_PREV_COUNT", "50")))
RANKINGS_DROP_GUARD_MIN_RATIO = max(0.01, min(1.0, float(os.getenv("RANKINGS_DROP_GUARD_MIN_RATIO", "0.70"))))
RANKINGS_DROP_GUARD_SYSTEMS = {"WPBA_Women", "WPA_Women", "WPA_Men", "WPBA", "WPA"}


class PostgresManager:
    """Manage rankings database operations with PostgreSQL"""

    # Rolling-window PDFs usually show 10 events; allow headroom for extra/dynamic columns.
    WPBA_WOMEN_EVENT_COLUMN_LIMIT = 15
    # WPA HTML tables expose a bounded set of event columns; cap split breadth for safety.
    WPA_MEN_WOMEN_EVENT_COLUMN_LIMIT = 25
    # Rankings page drill-down: the N most recent *active* event columns (≥1 player with points),
    # sorted newest-first (PDF/source column order, then base mapping order), then truncated
    # to N. Fewer than N entries only when fewer than N columns have points. See docs/10_TOURNAMENT_RULE.md.
    RANKINGS_MENU_RECENT_TOURNAMENT_LIMIT = 10
    # WPBA is a 10-rotating + 11th (rotating-out / out-of-window) system; the menu shows the 10
    # in-window events plus the rotating 11th so the event leaving the window stays visible until
    # a newer event pushes it off. See docs/10_TOURNAMENT_RULE.md.
    WPBA_MENU_RECENT_TOURNAMENT_LIMIT = 11

    _ASSOCIATION_PHYSICAL_TABLES = frozenset(
        {
            "wpba_rankings",
            "fargo_rankings",
            "wpa_men_rankings",
            "wpa_women_rankings",
            "heyball_men_rankings",
            "heyball_women_rankings",
            "artistic_rankings",
        }
    )

    def __init__(self, engine=None):
        """Initialize PostgreSQL manager.

        Args:
            engine: Optional SQLAlchemy engine. When omitted, uses the main ``DATABASE_URL`` engine.
        """
        self.engine = engine if engine is not None else get_engine()
    
    def get_connection(self):
        """Get raw database connection with retry/backoff on transient failures."""
        last_exc = None
        for attempt in range(1, DB_CONNECT_MAX_RETRIES + 1):
            try:
                return self.engine.raw_connection()
            except OperationalError as exc:
                last_exc = exc
                if attempt >= DB_CONNECT_MAX_RETRIES:
                    logger.error(
                        "Database connection failed after %s attempts: %s",
                        DB_CONNECT_MAX_RETRIES,
                        exc,
                    )
                    break
                delay = DB_CONNECT_BASE_BACKOFF_SEC * (2 ** (attempt - 1))
                logger.warning(
                    "Database connection failed (attempt %s/%s): %s; retrying in %.2fs",
                    attempt,
                    DB_CONNECT_MAX_RETRIES,
                    exc,
                    delay,
                )
                time.sleep(delay)

        if last_exc is not None:
            raise last_exc
        raise OperationalError("Failed to acquire database connection", None, None)
    
    def _generate_player_id_from_name(self, name: str, license_number: str = None) -> str:
        """Build deterministic player_id across name format variations."""
        import hashlib
        if license_number:
            cleaned = re.sub(r"[^A-Za-z0-9]+", "-", str(license_number).strip()).strip("-")
            return f"LIC-{cleaned[:28]}"
        canonical = self._canonical_player_name(name)
        digest = hashlib.sha1(canonical.encode("utf-8")).hexdigest()[:26]
        return f"RANK-{digest}"

    def _split_player_name(self, name: str) -> Tuple[str, str]:
        """
        Split display name into first/last for players table.
        Handles both "First Last" and "Last, First" forms.
        """
        raw = (name or "").strip()
        m = self._LICENSE_SUFFIX_RE.search(raw)
        if m:
            raw = raw[: m.start()].strip()
        if "," in raw:
            parts = [p.strip() for p in raw.split(",", 1)]
            if len(parts) == 2 and parts[0] and parts[1]:
                raw = f"{parts[1]} {parts[0]}"
        raw = re.sub(r"\s+", " ", raw).strip()
        if not raw:
            return ("Unknown", "Unknown")
        pieces = raw.split(" ")
        if len(pieces) == 1:
            return (pieces[0], "Unknown")
        return (pieces[0], " ".join(pieces[1:]))

    def _normalize_license_number(self, license_number: Any) -> Optional[str]:
        """Normalize license format for consistent matching/storage."""
        raw = str(license_number or "").strip().upper()
        if not raw:
            return None
        raw = re.sub(r"\s+", " ", raw)

        # Prefer canonical license token when extra trailing text appears
        # (e.g. "ACBS - 644 PHI" -> "ACBS - 644").
        m = re.search(r"([A-Z]{2,5}\s*-\s*\d{2,5})", raw)
        if m:
            raw = m.group(1)
        else:
            # Reject shifted/non-license values (country codes, plain numeric IDs).
            if self._COUNTRY_CODE_RE.fullmatch(raw) or self._NUMERIC_CODE_RE.fullmatch(raw):
                return None

        raw = re.sub(r"\s*-\s*", " - ", raw)
        return raw

    def _normalize_country_value(self, country: Any) -> Optional[str]:
        """Normalize country values and reject shifted/non-country artifacts."""
        raw = str(country or "").strip()
        if not raw:
            return None
        raw = re.sub(r"\s+", " ", raw)
        upper = raw.upper()

        # Country should never look like a license token or synthetic placeholder.
        if re.search(r"[A-Z]{2,5}\s*-\s*\d{2,5}", upper):
            return None
        if upper.startswith("RANK-"):
            return None
        if self._NUMERIC_CODE_RE.fullmatch(raw):
            return None

        # Normalize common forms.
        if self._COUNTRY_CODE_RE.fullmatch(upper):
            return upper

        low = raw.lower()
        if low in {"united states", "united states of america", "u.s.a", "u.s.a.", "usa"}:
            return "USA"

        return raw

    def _is_wpa_authoritative_system(self, system: str) -> bool:
        """WPA systems are the authoritative source for license numbers."""
        s = str(system or "").strip()
        return s == "WPA" or s.startswith("WPA_")

    def _ensure_license_locks_table(self, conn) -> None:
        """Create immutable-license lock table if it does not exist."""
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS player_license_locks (
                canonical_name TEXT PRIMARY KEY,
                license_number VARCHAR(255) NOT NULL,
                source_system VARCHAR(64) NOT NULL,
                locked_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_player_license_locks_license
            ON player_license_locks (license_number)
        """))

    def _ensure_country_locks_table(self, conn) -> None:
        """Create immutable-country lock table if it does not exist."""
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS player_country_locks (
                canonical_name TEXT PRIMARY KEY,
                country VARCHAR(255) NOT NULL,
                source_system VARCHAR(64) NOT NULL,
                locked_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_player_country_locks_country
            ON player_country_locks (country)
        """))

    def _load_license_locks(self, conn) -> Dict[str, str]:
        rows = conn.execute(text("""
            SELECT canonical_name, license_number
            FROM player_license_locks
        """)).fetchall()
        locks: Dict[str, str] = {}
        for r in rows:
            canonical = str(r[0] or "").strip()
            normalized = self._normalize_license_number(r[1])
            if canonical and normalized:
                locks[canonical] = normalized
        return locks

    def _load_country_locks(self, conn) -> Dict[str, str]:
        rows = conn.execute(text("""
            SELECT canonical_name, country
            FROM player_country_locks
        """)).fetchall()
        locks: Dict[str, str] = {}
        for r in rows:
            canonical = str(r[0] or "").strip()
            normalized = self._normalize_country_value(r[1])
            if canonical and normalized:
                locks[canonical] = normalized
        return locks

    def _apply_license_lock_policy(
        self,
        conn,
        rows_for_upsert: List[Dict[str, Any]],
        system: str,
    ) -> Dict[str, int]:
        """
        Enforce immutable license policy:
        - WPA systems seed lock values when no lock exists.
        - Once locked, incoming writes cannot change license_number.
        - Ambiguous WPA candidates (same canonical name, multiple licenses) are skipped.
        """
        self._ensure_license_locks_table(conn)
        locks = self._load_license_locks(conn)
        is_authoritative = self._is_wpa_authoritative_system(system)

        # Pre-detect ambiguous canonical names inside the incoming authoritative batch.
        candidate_licenses: Dict[str, set] = {}
        if is_authoritative:
            for row in rows_for_upsert:
                canonical = str(row.get("canonical_name") or "").strip()
                incoming = self._normalize_license_number(row.get("license_number"))
                if canonical and incoming:
                    candidate_licenses.setdefault(canonical, set()).add(incoming)
        ambiguous_candidates = {k for k, vals in candidate_licenses.items() if len(vals) > 1}

        created_locks = 0
        overridden_rows = 0
        filled_rows = 0
        conflict_rows = 0
        ambiguous_rows = 0
        dropped_non_authoritative = 0

        for row in rows_for_upsert:
            canonical = str(row.get("canonical_name") or "").strip()
            incoming = self._normalize_license_number(row.get("license_number"))
            row["license_number"] = incoming
            if not canonical:
                continue

            locked = locks.get(canonical)

            # Seed locks from authoritative WPA feeds.
            if is_authoritative and incoming and locked is None:
                if canonical in ambiguous_candidates:
                    ambiguous_rows += 1
                else:
                    conn.execute(text("""
                        INSERT INTO player_license_locks (canonical_name, license_number, source_system)
                        VALUES (:canonical_name, :license_number, :source_system)
                        ON CONFLICT (canonical_name) DO NOTHING
                    """), {
                        "canonical_name": canonical,
                        "license_number": incoming,
                        "source_system": system,
                    })
                    locks[canonical] = incoming
                    locked = incoming
                    created_locks += 1

            # Immutable once locked.
            if locked:
                if incoming and incoming != locked:
                    conflict_rows += 1
                    overridden_rows += 1
                elif not incoming:
                    filled_rows += 1
                row["license_number"] = locked
            elif not is_authoritative and incoming:
                # Non-WPA writes cannot establish/overwrite license identity.
                row["license_number"] = None
                dropped_non_authoritative += 1

        return {
            "created_locks": created_locks,
            "overridden_rows": overridden_rows,
            "filled_rows": filled_rows,
            "conflict_rows": conflict_rows,
            "ambiguous_rows": ambiguous_rows,
            "dropped_non_authoritative": dropped_non_authoritative,
        }

    def _apply_country_lock_policy(
        self,
        conn,
        rows_for_upsert: List[Dict[str, Any]],
        system: str,
    ) -> Dict[str, int]:
        """
        Enforce immutable country policy:
        - WPA systems seed lock values when no lock exists.
        - Once locked, incoming writes cannot change country.
        - Ambiguous WPA candidates (same canonical name, multiple countries) are skipped.
        """
        self._ensure_country_locks_table(conn)
        locks = self._load_country_locks(conn)
        is_authoritative = self._is_wpa_authoritative_system(system)

        candidate_countries: Dict[str, set] = {}
        if is_authoritative:
            for row in rows_for_upsert:
                canonical = str(row.get("canonical_name") or "").strip()
                incoming = self._normalize_country_value(row.get("country"))
                if canonical and incoming:
                    candidate_countries.setdefault(canonical, set()).add(incoming)
        ambiguous_candidates = {k for k, vals in candidate_countries.items() if len(vals) > 1}

        created_locks = 0
        overridden_rows = 0
        filled_rows = 0
        conflict_rows = 0
        ambiguous_rows = 0
        dropped_non_authoritative = 0

        for row in rows_for_upsert:
            canonical = str(row.get("canonical_name") or "").strip()
            incoming = self._normalize_country_value(row.get("country"))
            row["country"] = incoming
            if not canonical:
                continue

            locked = locks.get(canonical)

            if is_authoritative and incoming and locked is None:
                if canonical in ambiguous_candidates:
                    ambiguous_rows += 1
                else:
                    conn.execute(text("""
                        INSERT INTO player_country_locks (canonical_name, country, source_system)
                        VALUES (:canonical_name, :country, :source_system)
                        ON CONFLICT (canonical_name) DO NOTHING
                    """), {
                        "canonical_name": canonical,
                        "country": incoming,
                        "source_system": system,
                    })
                    locks[canonical] = incoming
                    locked = incoming
                    created_locks += 1

            if locked:
                if incoming and incoming != locked:
                    conflict_rows += 1
                    overridden_rows += 1
                elif not incoming:
                    filled_rows += 1
                row["country"] = locked
            elif not is_authoritative and incoming:
                # Non-WPA writes cannot establish/overwrite country identity.
                row["country"] = None
                dropped_non_authoritative += 1

        return {
            "created_locks": created_locks,
            "overridden_rows": overridden_rows,
            "filled_rows": filled_rows,
            "conflict_rows": conflict_rows,
            "ambiguous_rows": ambiguous_rows,
            "dropped_non_authoritative": dropped_non_authoritative,
        }

    def enforce_wpa_license_lockdown(self) -> Dict[str, Any]:
        """
        Backfill and apply immutable license locks from latest WPA snapshots.
        This is safe to run repeatedly.
        """
        with self.engine.begin() as conn:
            self._ensure_license_locks_table(conn)

            latest_rows = conn.execute(text("""
                WITH latest_per_system AS (
                    SELECT ranking_system, MAX(snapshot_date) AS snapshot_date
                    FROM rankings
                    WHERE ranking_system LIKE 'WPA_%'
                    GROUP BY ranking_system
                )
                SELECT r.player_name, r.license_number, r.ranking_system
                FROM rankings r
                JOIN latest_per_system l
                  ON l.ranking_system = r.ranking_system
                 AND l.snapshot_date = r.snapshot_date
                WHERE r.license_number IS NOT NULL
                  AND TRIM(r.license_number) <> ''
            """)).fetchall()

            grouped: Dict[str, set] = {}
            for player_name, license_number, _system in latest_rows:
                canonical = self._canonical_player_name(player_name or "")
                normalized = self._normalize_license_number(license_number)
                if not canonical or not normalized:
                    continue
                grouped.setdefault(canonical, set()).add(normalized)

            existing_locks = self._load_license_locks(conn)
            inserted_locks = 0
            ambiguous_names = 0
            for canonical, licenses in grouped.items():
                if len(licenses) != 1:
                    ambiguous_names += 1
                    continue
                if canonical in existing_locks:
                    continue
                only_license = next(iter(licenses))
                conn.execute(text("""
                    INSERT INTO player_license_locks (canonical_name, license_number, source_system)
                    VALUES (:canonical_name, :license_number, :source_system)
                    ON CONFLICT (canonical_name) DO NOTHING
                """), {
                    "canonical_name": canonical,
                    "license_number": only_license,
                    "source_system": "WPA_LOCKDOWN_BACKFILL",
                })
                inserted_locks += 1

            players_updated = conn.execute(text("""
                UPDATE players p
                SET license_number = pll.license_number
                FROM player_license_locks pll
                WHERE LOWER(TRIM(COALESCE(p.first_name, '') || ' ' || COALESCE(p.last_name, ''))) = pll.canonical_name
                  AND COALESCE(TRIM(p.license_number), '') <> COALESCE(TRIM(pll.license_number), '')
            """)).rowcount

            rankings_updated = conn.execute(text("""
                UPDATE rankings r
                SET license_number = pll.license_number
                FROM player_license_locks pll
                WHERE pll.canonical_name = LOWER(
                    TRIM(
                        REGEXP_REPLACE(
                            CASE
                                WHEN POSITION(',' IN r.player_name) > 0 THEN
                                    TRIM(SPLIT_PART(r.player_name, ',', 2)) || ' ' || TRIM(SPLIT_PART(r.player_name, ',', 1))
                                ELSE r.player_name
                            END,
                            '\\s+[A-Z]{2,5}\\s*-\\s*\\d{2,5}\\s*$',
                            ''
                        )
                    )
                )
                  AND COALESCE(TRIM(r.license_number), '') <> COALESCE(TRIM(pll.license_number), '')
            """)).rowcount

        return {
            "latest_wpa_rows_considered": len(latest_rows),
            "candidate_names": len(grouped),
            "inserted_locks": int(inserted_locks or 0),
            "ambiguous_names_skipped": int(ambiguous_names or 0),
            "players_updated": int(players_updated or 0),
            "rankings_updated": int(rankings_updated or 0),
        }

    def enforce_wpa_country_lockdown(self) -> Dict[str, Any]:
        """
        Backfill and apply immutable country locks from latest WPA snapshots.
        This is safe to run repeatedly.
        """
        with self.engine.begin() as conn:
            self._ensure_country_locks_table(conn)

            latest_rows = conn.execute(text("""
                WITH latest_per_system AS (
                    SELECT ranking_system, MAX(snapshot_date) AS snapshot_date
                    FROM rankings
                    WHERE ranking_system LIKE 'WPA_%'
                    GROUP BY ranking_system
                )
                SELECT r.player_name, r.country, r.ranking_system
                FROM rankings r
                JOIN latest_per_system l
                  ON l.ranking_system = r.ranking_system
                 AND l.snapshot_date = r.snapshot_date
                WHERE r.country IS NOT NULL
                  AND TRIM(r.country) <> ''
            """)).fetchall()

            grouped: Dict[str, set] = {}
            for player_name, country, _system in latest_rows:
                canonical = self._canonical_player_name(player_name or "")
                normalized = self._normalize_country_value(country)
                if not canonical or not normalized:
                    continue
                grouped.setdefault(canonical, set()).add(normalized)

            existing_locks = self._load_country_locks(conn)
            inserted_locks = 0
            ambiguous_names = 0
            for canonical, countries in grouped.items():
                if len(countries) != 1:
                    ambiguous_names += 1
                    continue
                if canonical in existing_locks:
                    continue
                only_country = next(iter(countries))
                conn.execute(text("""
                    INSERT INTO player_country_locks (canonical_name, country, source_system)
                    VALUES (:canonical_name, :country, :source_system)
                    ON CONFLICT (canonical_name) DO NOTHING
                """), {
                    "canonical_name": canonical,
                    "country": only_country,
                    "source_system": "WPA_LOCKDOWN_BACKFILL",
                })
                inserted_locks += 1

            players_updated = conn.execute(text("""
                UPDATE players p
                SET nationality = pcl.country
                FROM player_country_locks pcl
                WHERE LOWER(TRIM(COALESCE(p.first_name, '') || ' ' || COALESCE(p.last_name, ''))) = pcl.canonical_name
                  AND COALESCE(TRIM(p.nationality), '') <> COALESCE(TRIM(pcl.country), '')
            """)).rowcount

            rankings_updated = conn.execute(text("""
                UPDATE rankings r
                SET country = pcl.country
                FROM player_country_locks pcl
                WHERE pcl.canonical_name = LOWER(
                    TRIM(
                        REGEXP_REPLACE(
                            CASE
                                WHEN POSITION(',' IN r.player_name) > 0 THEN
                                    TRIM(SPLIT_PART(r.player_name, ',', 2)) || ' ' || TRIM(SPLIT_PART(r.player_name, ',', 1))
                                ELSE r.player_name
                            END,
                            '\\s+[A-Z]{2,5}\\s*-\\s*\\d{2,5}\\s*$',
                            ''
                        )
                    )
                )
                  AND COALESCE(TRIM(r.country), '') <> COALESCE(TRIM(pcl.country), '')
            """)).rowcount

        return {
            "latest_wpa_rows_considered": len(latest_rows),
            "candidate_names": len(grouped),
            "inserted_locks": int(inserted_locks or 0),
            "ambiguous_names_skipped": int(ambiguous_names or 0),
            "players_updated": int(players_updated or 0),
            "rankings_updated": int(rankings_updated or 0),
        }

    def unlock_identity_locks(self, player_name: str, lock_type: str = "both") -> Dict[str, Any]:
        """
        Remove immutable lock rows for a player.
        lock_type: license | country | both
        """
        canonical = self._canonical_player_name(player_name or "")
        if not canonical:
            raise ValueError("player_name is required")
        lock_type = (lock_type or "both").strip().lower()
        if lock_type not in {"license", "country", "both"}:
            raise ValueError("lock_type must be one of: license, country, both")

        with self.engine.begin() as conn:
            self._ensure_license_locks_table(conn)
            self._ensure_country_locks_table(conn)
            removed_license = 0
            removed_country = 0

            if lock_type in {"license", "both"}:
                removed_license = conn.execute(text("""
                    DELETE FROM player_license_locks
                    WHERE canonical_name = :canonical_name
                """), {"canonical_name": canonical}).rowcount
            if lock_type in {"country", "both"}:
                removed_country = conn.execute(text("""
                    DELETE FROM player_country_locks
                    WHERE canonical_name = :canonical_name
                """), {"canonical_name": canonical}).rowcount

        return {
            "player_name": player_name,
            "canonical_name": canonical,
            "lock_type": lock_type,
            "removed_license_locks": int(removed_license or 0),
            "removed_country_locks": int(removed_country or 0),
        }

    def relock_identity_fields(
        self,
        player_name: str,
        lock_type: str = "both",
        *,
        license_number: Optional[str] = None,
        country: Optional[str] = None,
        source_system: str = "ADMIN_MANUAL",
    ) -> Dict[str, Any]:
        """
        Set/re-set immutable lock rows for a player and immediately apply to players/rankings.
        If license_number/country is omitted, derive from latest WPA snapshots.
        """
        canonical = self._canonical_player_name(player_name or "")
        if not canonical:
            raise ValueError("player_name is required")

        lock_type = (lock_type or "both").strip().lower()
        if lock_type not in {"license", "country", "both"}:
            raise ValueError("lock_type must be one of: license, country, both")

        normalized_license = self._normalize_license_number(license_number)
        normalized_country = self._normalize_country_value(country)

        with self.engine.begin() as conn:
            self._ensure_license_locks_table(conn)
            self._ensure_country_locks_table(conn)

            # Derive missing values from latest WPA snapshots.
            if lock_type in {"license", "both"} and not normalized_license:
                rows = conn.execute(text("""
                    WITH latest_per_system AS (
                        SELECT ranking_system, MAX(snapshot_date) AS snapshot_date
                        FROM rankings
                        WHERE ranking_system LIKE 'WPA_%'
                        GROUP BY ranking_system
                    )
                    SELECT r.license_number
                    FROM rankings r
                    JOIN latest_per_system l
                      ON l.ranking_system = r.ranking_system
                     AND l.snapshot_date = r.snapshot_date
                    WHERE LOWER(
                        TRIM(
                            REGEXP_REPLACE(
                                CASE
                                    WHEN POSITION(',' IN r.player_name) > 0 THEN
                                        TRIM(SPLIT_PART(r.player_name, ',', 2)) || ' ' || TRIM(SPLIT_PART(r.player_name, ',', 1))
                                    ELSE r.player_name
                                END,
                                '\\s+[A-Z]{2,5}\\s*-\\s*\\d{2,5}\\s*$',
                                ''
                            )
                        )
                    ) = :canonical_name
                """), {"canonical_name": canonical}).fetchall()
                candidates = {
                    self._normalize_license_number(r[0])
                    for r in rows
                    if self._normalize_license_number(r[0]) is not None
                }
                if len(candidates) == 1:
                    normalized_license = next(iter(candidates))
                elif len(candidates) > 1:
                    raise ValueError(f"Ambiguous license candidates for {player_name}: {sorted(candidates)}")

            if lock_type in {"country", "both"} and not normalized_country:
                rows = conn.execute(text("""
                    WITH latest_per_system AS (
                        SELECT ranking_system, MAX(snapshot_date) AS snapshot_date
                        FROM rankings
                        WHERE ranking_system LIKE 'WPA_%'
                        GROUP BY ranking_system
                    )
                    SELECT r.country
                    FROM rankings r
                    JOIN latest_per_system l
                      ON l.ranking_system = r.ranking_system
                     AND l.snapshot_date = r.snapshot_date
                    WHERE LOWER(
                        TRIM(
                            REGEXP_REPLACE(
                                CASE
                                    WHEN POSITION(',' IN r.player_name) > 0 THEN
                                        TRIM(SPLIT_PART(r.player_name, ',', 2)) || ' ' || TRIM(SPLIT_PART(r.player_name, ',', 1))
                                    ELSE r.player_name
                                END,
                                '\\s+[A-Z]{2,5}\\s*-\\s*\\d{2,5}\\s*$',
                                ''
                            )
                        )
                    ) = :canonical_name
                """), {"canonical_name": canonical}).fetchall()
                candidates = {
                    self._normalize_country_value(r[0])
                    for r in rows
                    if self._normalize_country_value(r[0]) is not None
                }
                if len(candidates) == 1:
                    normalized_country = next(iter(candidates))
                elif len(candidates) > 1:
                    raise ValueError(f"Ambiguous country candidates for {player_name}: {sorted(candidates)}")

            if lock_type in {"license", "both"} and not normalized_license:
                raise ValueError("No license value available to relock")
            if lock_type in {"country", "both"} and not normalized_country:
                raise ValueError("No country value available to relock")

            if lock_type in {"license", "both"}:
                conn.execute(text("""
                    INSERT INTO player_license_locks (canonical_name, license_number, source_system)
                    VALUES (:canonical_name, :license_number, :source_system)
                    ON CONFLICT (canonical_name)
                    DO UPDATE SET
                        license_number = EXCLUDED.license_number,
                        source_system = EXCLUDED.source_system,
                        updated_at = CURRENT_TIMESTAMP
                """), {
                    "canonical_name": canonical,
                    "license_number": normalized_license,
                    "source_system": source_system,
                })
                conn.execute(text("""
                    UPDATE players
                    SET license_number = :license_number
                    WHERE LOWER(TRIM(COALESCE(first_name, '') || ' ' || COALESCE(last_name, ''))) = :canonical_name
                """), {"canonical_name": canonical, "license_number": normalized_license})
                conn.execute(text("""
                    UPDATE rankings
                    SET license_number = :license_number
                    WHERE LOWER(
                        TRIM(
                            REGEXP_REPLACE(
                                CASE
                                    WHEN POSITION(',' IN player_name) > 0 THEN
                                        TRIM(SPLIT_PART(player_name, ',', 2)) || ' ' || TRIM(SPLIT_PART(player_name, ',', 1))
                                    ELSE player_name
                                END,
                                '\\s+[A-Z]{2,5}\\s*-\\s*\\d{2,5}\\s*$',
                                ''
                            )
                        )
                    ) = :canonical_name
                """), {"canonical_name": canonical, "license_number": normalized_license})

            if lock_type in {"country", "both"}:
                conn.execute(text("""
                    INSERT INTO player_country_locks (canonical_name, country, source_system)
                    VALUES (:canonical_name, :country, :source_system)
                    ON CONFLICT (canonical_name)
                    DO UPDATE SET
                        country = EXCLUDED.country,
                        source_system = EXCLUDED.source_system,
                        updated_at = CURRENT_TIMESTAMP
                """), {
                    "canonical_name": canonical,
                    "country": normalized_country,
                    "source_system": source_system,
                })
                conn.execute(text("""
                    UPDATE players
                    SET nationality = :country
                    WHERE LOWER(TRIM(COALESCE(first_name, '') || ' ' || COALESCE(last_name, ''))) = :canonical_name
                """), {"canonical_name": canonical, "country": normalized_country})
                conn.execute(text("""
                    UPDATE rankings
                    SET country = :country
                    WHERE LOWER(
                        TRIM(
                            REGEXP_REPLACE(
                                CASE
                                    WHEN POSITION(',' IN player_name) > 0 THEN
                                        TRIM(SPLIT_PART(player_name, ',', 2)) || ' ' || TRIM(SPLIT_PART(player_name, ',', 1))
                                    ELSE player_name
                                END,
                                '\\s+[A-Z]{2,5}\\s*-\\s*\\d{2,5}\\s*$',
                                ''
                            )
                        )
                    ) = :canonical_name
                """), {"canonical_name": canonical, "country": normalized_country})

        return {
            "player_name": player_name,
            "canonical_name": canonical,
            "lock_type": lock_type,
            "license_number": normalized_license,
            "country": normalized_country,
            "source_system": source_system,
        }

    def save_rankings(self, rankings: List[Dict], system: str, snapshot_date: date = None) -> int:
        """
        Save rankings snapshot to PostgreSQL with comprehensive error handling

        Args:
            rankings: List of ranking dicts
            system: 'WPBA', 'WPA', 'WPBA_Women', 'WPA_Men', 'WPA_Women', etc.
            snapshot_date: Date of snapshot (default: today)

        Returns:
            Number of rankings saved

        Raises:
            OperationalError: If database connection fails
            IntegrityError: If data integrity constraints are violated
            Exception: For other database errors
        """
        if snapshot_date is None:
            snapshot_date = date.today()

        if not rankings:
            logger.warning(f"No rankings provided for {system}")
            return 0

        saved_count = 0
        failed_count = 0
        rows_for_upsert: List[Dict[str, Any]] = []

        for i, ranking in enumerate(rankings):
            try:
                # Validate required fields
                if not ranking.get('name'):
                    logger.warning("Skipping ranking %s: missing name", i)
                    failed_count += 1
                    continue

                rank_value = ranking.get('rank')
                if not isinstance(rank_value, (int, float)) or rank_value <= 0:
                    logger.warning("Skipping ranking %s for %s: invalid rank %s", i, ranking.get('name'), rank_value)
                    failed_count += 1
                    continue

                # First-class columns stored in dedicated columns; rest in source_data (JSONB)
                first_class = {'name', 'rank', 'points', 'country', 'license_number', 'stops_played'}
                source_data = {
                    k: v for k, v in ranking.items()
                    if k not in first_class and v is not None and not (isinstance(k, str) and k.startswith('_'))
                }
                # WPBA_Women: compute overall from rolling-10 (sum of most recent 10 tournaments) when we have per-tournament columns.
                # Only override PDF total when the rolling-10 sum agrees (within tolerance) to guard against
                # blank-cell shifting in the text parser that can inflate the computed sum.
                if system == "WPBA_Women" and source_data:
                    tournament_cols = ranking.get("_wpba_tournament_columns")
                    if tournament_cols:
                        # Persist the PDF column order (left-to-right == newest-first) so the
                        # menu/split/history recency ordering is driven by the source PDF itself
                        # (single source of truth), not the hand-maintained WPBA_WOMEN_COLUMN_MAPPING.
                        source_data["_wpba_tournament_columns"] = list(tournament_cols)
                        combined = {**ranking, **source_data}
                        rolling_total = self._sum_rolling_10_wpba_event_points(combined, tournament_cols)
                        original_points = float(ranking.get('points', 0) or 0)
                        if rolling_total > 0 and (
                            original_points == 0
                            or abs(rolling_total - original_points) < 1.0
                        ):
                            ranking = dict(ranking)
                            ranking["points"] = rolling_total
                # WPA overall rows: keep points aligned with per-event source columns.
                if system in {"WPA_Men", "WPA_Women"} and source_data:
                    combined = {**ranking, **source_data}
                    total_from_events = self._sum_all_event_points(combined)
                    if total_from_events > 0:
                        ranking = dict(ranking)
                        ranking["points"] = total_from_events
                source_data_json = json.dumps(source_data) if source_data else None
                # Pass valid JSON when empty so CAST works (empty object)
                source_data_for_db = source_data_json if source_data_json else '{}'

                # One row per (ranking_system, snapshot_date, position). Rank can tie (51, 51, 53).
                # Same path used for imports and for future live scorekeeper updates.
                # player_id resolved later in save_rankings after lock policy (identity resolution)
                rows_for_upsert.append({
                    'player_id': self._generate_player_id_from_name(ranking['name'], ranking.get('license_number')),
                    'name': str(ranking['name']).strip(),
                    'canonical_name': self._canonical_player_name(str(ranking['name'])),
                    'system': system,
                    'rank': int(rank_value),
                    'points': float(ranking.get('points', 0) or 0),
                    'country': ranking.get('country'),
                    'license_number': ranking.get('license_number'),
                    'stops_played': ranking.get('stops_played'),
                    'date': snapshot_date,
                    'source_data': source_data_for_db,
                    'position': i + 1,
                })
            except (KeyError, ValueError, TypeError) as e:
                logger.error("Data validation error for ranking %s in %s: %s", i, system, e)
                failed_count += 1
                continue

        if not rows_for_upsert:
            logger.warning("No valid %s rankings rows to save for %s", system, snapshot_date)
            return 0

        if (
            RANKINGS_DROP_GUARD_ENABLED
            and system in RANKINGS_DROP_GUARD_SYSTEMS
            and os.getenv("ALLOW_RANKINGS_DROP", "0") != "1"
        ):
            incoming_count = len(rows_for_upsert)
            with self.engine.connect() as conn:
                prev = conn.execute(
                    text(
                        """
                        SELECT snapshot_date, COUNT(*) AS cnt
                        FROM rankings
                        WHERE ranking_system = :system
                          AND snapshot_date <> :snapshot_date
                        GROUP BY snapshot_date
                        ORDER BY snapshot_date DESC
                        LIMIT 1
                        """
                    ),
                    {"system": system, "snapshot_date": snapshot_date},
                ).fetchone()
            if prev:
                prev_date, prev_count = prev[0], int(prev[1] or 0)
                if prev_count >= RANKINGS_DROP_GUARD_MIN_PREV_COUNT:
                    ratio = incoming_count / float(prev_count)
                    if ratio < RANKINGS_DROP_GUARD_MIN_RATIO:
                        raise ValueError(
                            f"Blocked rankings write for {system}: incoming rows={incoming_count} is "
                            f"{ratio:.2%} of previous snapshot ({prev_count} rows on {prev_date}). "
                            "Set ALLOW_RANKINGS_DROP=1 to override intentionally."
                        )

        # Ensure archive table exists
        self.ensure_archive_table_exists()

        try:
            # Archive existing data before replacing (data persistence requirement)
            archived_count = self.archive_existing_rankings(system, snapshot_date)

            # Atomic snapshot replace: prevents stale rows and partial writes for a system/date.
            with self.engine.begin() as conn:
                # Detect minimal players schema (name only) vs full (player_id, first_name, last_name)
                has_player_id = conn.execute(text("""
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'players' AND column_name = 'player_id'
                    LIMIT 1
                """)).fetchone() is not None
                use_minimal_players = not has_player_id

                lock_stats = self._apply_license_lock_policy(conn, rows_for_upsert, system)
                if any(lock_stats.values()):
                    logger.info(
                        "License lock policy (%s): created=%s overridden=%s filled=%s conflicts=%s ambiguous=%s dropped_non_authoritative=%s",
                        system,
                        lock_stats["created_locks"],
                        lock_stats["overridden_rows"],
                        lock_stats["filled_rows"],
                        lock_stats["conflict_rows"],
                        lock_stats["ambiguous_rows"],
                        lock_stats["dropped_non_authoritative"],
                    )
                country_lock_stats = self._apply_country_lock_policy(conn, rows_for_upsert, system)
                if any(country_lock_stats.values()):
                    logger.info(
                        "Country lock policy (%s): created=%s overridden=%s filled=%s conflicts=%s ambiguous=%s dropped_non_authoritative=%s",
                        system,
                        country_lock_stats["created_locks"],
                        country_lock_stats["overridden_rows"],
                        country_lock_stats["filled_rows"],
                        country_lock_stats["conflict_rows"],
                        country_lock_stats["ambiguous_rows"],
                        country_lock_stats["dropped_non_authoritative"],
                    )

                # Identity resolution: resolve player_id by license or canonical name variants
                # to prevent duplicates (e.g. "Kazakis Alexander" vs "Alexander Kazakis")
                for row in rows_for_upsert:
                    resolved_id, resolved_first, resolved_last = self._resolve_player_id(
                        conn,
                        row['name'],
                        row.get('license_number'),
                        row.get('canonical_name', ''),
                        row.get('system'),
                    )
                    row['player_id'] = resolved_id
                    row['_resolved_first'] = resolved_first
                    row['_resolved_last'] = resolved_last

                # Upsert into players table to ensure they exist and identity data is updated
                # Use resolved first/last when available for consistency; never fabricate license
                player_rows = []
                for row in rows_for_upsert:
                    if row.get('_resolved_first') is not None and row.get('_resolved_last') is not None:
                        first_name, last_name = row['_resolved_first'], row['_resolved_last']
                    else:
                        first_name, last_name = self._split_player_name(row['name'])
                    player_rows.append({
                        'player_id': row['player_id'],
                        'first_name': first_name,
                        'last_name': last_name,
                        'nationality': row.get('country'),
                        'license_number': row.get('license_number'),  # None if missing; never fabricated
                    })
                
                if player_rows:
                    if use_minimal_players:
                        # Minimal schema: players has (id, name, nationality, fargo_rating, ...)
                        unique_by_name = {row['name']: row.get('country') for row in rows_for_upsert if row.get('name')}
                        for full_name, nationality in unique_by_name.items():
                            conn.execute(text("""
                                INSERT INTO players (name, nationality)
                                VALUES (:name, :nationality)
                                ON CONFLICT (name)
                                DO UPDATE SET nationality = COALESCE(EXCLUDED.nationality, players.nationality)
                            """), {"name": full_name.strip(), "nationality": nationality})
                    else:
                        # Full schema: player_id, first_name, last_name, ...
                        unique_players = list({p['player_id']: p for p in player_rows}.values())
                        conn.execute(text("""
                            INSERT INTO players (player_id, first_name, last_name, nationality, license_number)
                            VALUES (:player_id, :first_name, :last_name, :nationality, :license_number)
                            ON CONFLICT (player_id)
                            DO UPDATE SET
                                nationality = COALESCE(EXCLUDED.nationality, players.nationality),
                                license_number = COALESCE(EXCLUDED.license_number, players.license_number)
                        """), unique_players)

                conn.execute(
                    text("""
                        DELETE FROM rankings
                        WHERE ranking_system = :system
                          AND snapshot_date = :date
                    """),
                    {'system': system, 'date': snapshot_date},
                )
                if use_minimal_players:
                    conn.execute(text("""
                        INSERT INTO rankings
                        (player_name, ranking_system, rank, points, country, license_number, stops_played, snapshot_date, source_data, position, fargo_rating, alfa_rating, fargo_robustness)
                        VALUES (
                            :name, :system, :rank, :points, :country, :license_number, :stops_played, :date, CAST(:source_data AS jsonb), :position,
                            (SELECT MAX(fargo_rating) FROM players WHERE LOWER(TRIM(name)) = :canonical_name),
                            NULL,
                            NULL
                        )
                        ON CONFLICT (player_name, ranking_system, snapshot_date)
                        DO UPDATE SET
                            rank = EXCLUDED.rank,
                            points = EXCLUDED.points,
                            country = EXCLUDED.country,
                            license_number = COALESCE(EXCLUDED.license_number, rankings.license_number),
                            stops_played = COALESCE(EXCLUDED.stops_played, rankings.stops_played),
                            source_data = COALESCE(EXCLUDED.source_data, rankings.source_data),
                            position = EXCLUDED.position,
                            fargo_rating = EXCLUDED.fargo_rating,
                            alfa_rating = EXCLUDED.alfa_rating,
                            fargo_robustness = EXCLUDED.fargo_robustness
                    """), rows_for_upsert)
                else:
                    conn.execute(text("""
                        INSERT INTO rankings
                        (player_name, ranking_system, rank, points, country, license_number, stops_played, snapshot_date, source_data, position, fargo_rating, alfa_rating, fargo_robustness)
                        VALUES (
                            :name, :system, :rank, :points, :country, :license_number, :stops_played, :date, CAST(:source_data AS jsonb), :position,
                            (SELECT MAX(fargo_score) FROM players WHERE LOWER(TRIM(first_name || ' ' || last_name)) = :canonical_name),
                            (SELECT MAX(alfa_rating) FROM players WHERE LOWER(TRIM(first_name || ' ' || last_name)) = :canonical_name),
                            (SELECT MAX(fargo_robustness) FROM players WHERE LOWER(TRIM(first_name || ' ' || last_name)) = :canonical_name)
                        )
                        ON CONFLICT (ranking_system, snapshot_date, position)
                        DO UPDATE SET
                            player_name = EXCLUDED.player_name,
                            rank = EXCLUDED.rank,
                            points = EXCLUDED.points,
                            country = EXCLUDED.country,
                            license_number = COALESCE(EXCLUDED.license_number, rankings.license_number),
                            stops_played = COALESCE(EXCLUDED.stops_played, rankings.stops_played),
                            source_data = COALESCE(EXCLUDED.source_data, rankings.source_data),
                            fargo_rating = COALESCE(EXCLUDED.fargo_rating, rankings.fargo_rating),
                            alfa_rating = COALESCE(EXCLUDED.alfa_rating, rankings.alfa_rating),
                            fargo_robustness = COALESCE(EXCLUDED.fargo_robustness, rankings.fargo_robustness)
                    """), rows_for_upsert)
            saved_count = len(rows_for_upsert)

        except OperationalError as e:
            logger.error(f"Database connection error while saving {system} rankings: {e}")
            raise
        except IntegrityError as e:
            logger.error("Integrity constraint violation while saving %s rankings: %s", system, e)
            raise
        except Exception as e:
            logger.error(f"Database error while saving {system} rankings: {e}")
            raise

        if failed_count > 0:
            logger.warning(f"Saved {saved_count} {system} rankings, {failed_count} failed for {snapshot_date}")

        logger.info(f"Successfully saved {saved_count} {system} rankings for {snapshot_date} (archived {archived_count} previous records)")

        try:
            self._mirror_rankings_to_association_table(system, snapshot_date)
        except Exception as mirror_exc:
            logger.warning("Association mirror post-save failed for %s: %s", system, mirror_exc)

        # Detect and save ranking changes
        try:
            self._detect_and_save_changes(system, snapshot_date)
        except Exception as e:
            logger.error(f"Failed to detect ranking changes for {system}: {e}")

        # Broadcast cache invalidation for real-time UI updates
        try:
            import asyncio
            from api.notifications import broadcast_cache_invalidation
            payload = {
                "system": system,
                "records_saved": saved_count,
                "snapshot_date": str(snapshot_date)
            }
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(broadcast_cache_invalidation("rankings_saved", payload))
            except RuntimeError:
                logger.debug("No running event loop; skipping cache invalidation broadcast for %s", system)
        except Exception as e:
            logger.debug(f"Cache invalidation broadcast failed: {e}")

        return saved_count
    
    def _detect_and_save_changes(self, system: str, snapshot_date: date) -> int:
        """Compare current snapshot to previous and insert into ranking_changes"""
        with self.engine.connect() as conn:
            # Find previous snapshot date
            result = conn.execute(text("""
                SELECT snapshot_date FROM rankings
                WHERE ranking_system = :system AND snapshot_date < :date
                ORDER BY snapshot_date DESC LIMIT 1
            """), {'system': system, 'date': snapshot_date})
            prev_row = result.fetchone()
            
            if not prev_row:
                conn.commit()
                return 0
            
            prev_date = prev_row[0]
            
            # Get previous snapshot
            prev_result = conn.execute(text("""
                SELECT player_name, rank, points FROM rankings
                WHERE ranking_system = :system AND snapshot_date = :date
            """), {'system': system, 'date': prev_date})
            prev_by_name = {r[0]: (r[1], r[2]) for r in prev_result.fetchall()}
            
            # Get current snapshot
            curr_result = conn.execute(text("""
                SELECT player_name, rank, points FROM rankings
                WHERE ranking_system = :system AND snapshot_date = :date
            """), {'system': system, 'date': snapshot_date})
            current = curr_result.fetchall()
            
            change_count = 0
            for (player_name, new_rank, new_points) in current:
                prev = prev_by_name.get(player_name)
                
                if prev is None:
                    change_type = "new_player"
                    old_rank, old_points = None, None
                else:
                    old_rank, old_points = prev
                    if old_rank != new_rank and old_points != new_points:
                        change_type = "rank_up" if new_rank < old_rank else "rank_down"
                    elif old_rank != new_rank:
                        change_type = "rank_up" if new_rank < old_rank else "rank_down"
                    elif old_points != new_points:
                        change_type = "points_change"
                    else:
                        continue
                
                conn.execute(text("""
                    INSERT INTO ranking_changes
                    (player_name, ranking_system, old_rank, new_rank, old_points, new_points, change_date, change_type)
                    VALUES (:name, :system, :old_rank, :new_rank, :old_points, :new_points, :date, :type)
                """), {
                    'name': player_name,
                    'system': system,
                    'old_rank': old_rank,
                    'new_rank': new_rank,
                    'old_points': old_points,
                    'new_points': new_points,
                    'date': snapshot_date,
                    'type': change_type
                })
                change_count += 1
            
            conn.commit()
            
            if change_count:
                logger.info(f"Recorded {change_count} ranking changes for {system} ({prev_date} -> {snapshot_date})")
            return change_count
    
    def get_movement(self, system: str, limit: int = 50) -> List[Dict]:
        """Get recent ranking changes for a system (newest first)"""
        with self.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT player_name, ranking_system, old_rank, new_rank, old_points, new_points, change_date, change_type
                FROM ranking_changes
                WHERE ranking_system = :system
                ORDER BY change_date DESC, id DESC
                LIMIT :limit
            """), {'system': system, 'limit': limit})
            
            return [
                {
                    "player_name": r[0],
                    "ranking_system": r[1],
                    "old_rank": r[2],
                    "new_rank": r[3],
                    "old_points": r[4],
                    "new_points": r[5],
                    "change_date": str(r[6]),
                    "change_type": r[7],
                }
                for r in result.fetchall()
            ]
    
    def save_wpba_rankings(self, rankings: List[Dict], snapshot_date: date = None, ranking_type: str = 'WPBA_Women') -> int:
        """Save WPBA rankings snapshot.

        Persists ``stops_played``. The WPBA ranking PDF lists per-event point columns only for
        the top ~18 players, so tournament_history / per-event results cannot supply a complete
        tournaments-played count for the ~150 remaining ranked players. The PDF's own
        ``stops_played`` column is authoritative and present for every ranked player, so it is
        the single source of truth for the Leaderboard's "tournaments played".
        (Previously this stripped stops_played on the assumption tournament_history would cover
        everyone — invalid because the source only details the top 18. See docs/WPBA_TOURNAMENT_SSOT.md.)
        """
        return self.save_rankings(rankings, ranking_type, snapshot_date)
    
    def save_wpa_rankings(self, rankings: List[Dict], snapshot_date: date = None, ranking_type: str = 'WPA_Women') -> int:
        """Save WPA rankings snapshot"""
        return self.save_rankings(rankings, ranking_type, snapshot_date)

    def save_cp_rankings(self, rankings: List[Dict], snapshot_date: date = None, ranking_type: str = 'Competitors_Pool_9Ball') -> int:
        """Save CP rankings snapshot"""
        return self.save_rankings(rankings, ranking_type, snapshot_date)

    def get_latest_snapshot_as_rankings(
        self, source_system: str, snapshot_date: Optional[date] = None
    ) -> Tuple[Optional[date], List[Dict]]:
        """Get a snapshot for a system as a list of ranking dicts (for copy). Returns (snapshot_date, rows).
        If snapshot_date is None, uses the latest snapshot."""
        with self.engine.connect() as conn:
            if snapshot_date is not None:
                result = conn.execute(text("""
                    SELECT snapshot_date, player_name, rank, points, country, license_number, stops_played, source_data
                    FROM rankings
                    WHERE ranking_system = :system AND snapshot_date = :dt
                    ORDER BY position ASC NULLS LAST, rank ASC, id ASC
                """), {'system': source_system, 'dt': snapshot_date})
            else:
                result = conn.execute(text("""
                    SELECT snapshot_date, player_name, rank, points, country, license_number, stops_played, source_data
                    FROM rankings
                    WHERE ranking_system = :system
                    AND snapshot_date = (SELECT MAX(snapshot_date) FROM rankings WHERE ranking_system = :system)
                    ORDER BY position ASC NULLS LAST, rank ASC, id ASC
                """), {'system': source_system})
            rows = result.fetchall()
        if not rows:
            return None, []
        snap = rows[0][0]
        rankings = []
        for r in rows:
            rec = {
                'name': r[1],
                'rank': r[2],
                'points': float(r[3]) if r[3] is not None else 0,
                'country': r[4],
                'license_number': r[5],
                'stops_played': r[6],
            }
            if r[7]:
                try:
                    extra = r[7] if isinstance(r[7], dict) else json.loads(r[7])
                    rec.update({k: v for k, v in extra.items() if k not in rec})
                except (TypeError, ValueError) as e:
                    logger.debug("Could not parse source_data for %s in %s: %s", r[1], source_system, e)
            rankings.append(rec)
        return snap, rankings

    def copy_rankings_from_source_to_targets(
        self, source_system: str, target_systems: List[str]
    ) -> Dict[str, int]:
        """Copy the latest snapshot from source_system to each target_system. Returns {target: count}."""
        snapshot_date, rankings = self.get_latest_snapshot_as_rankings(source_system)
        if not snapshot_date or not rankings:
            logger.warning(f"No data to copy from {source_system}")
            return {t: 0 for t in target_systems}
        result = {}
        for target in target_systems:
            count = self.save_rankings(rankings, target, snapshot_date)
            result[target] = count
            logger.info(f"Copied {count} rankings from {source_system} to {target}")
        return result

    def _points_from_event_columns(self, rec: Dict, key_predicate) -> float:
        """Sum numeric values from keys in rec that match key_predicate(k)."""
        total = 0.0
        first_class = {"name", "rank", "points", "country", "license_number", "stops_played"}
        for k, v in rec.items():
            if k in first_class or not key_predicate(k):
                continue
            try:
                if v is None or v == "":
                    continue
                total += float(str(v).replace(",", "").strip())
            except (ValueError, TypeError) as e:
                logger.debug("Non-numeric event points in key '%s' with value '%s': %s", k, v, e)
        return total

    def _points_from_8ball_columns(self, rec: Dict) -> float:
        """Sum numeric values from keys that look like 8-ball event columns."""
        return self._points_from_event_columns(rec, lambda k: "8" in k and "ball" in k.lower())

    def _points_from_10ball_columns(self, rec: Dict) -> float:
        """Sum numeric values from keys that look like 10-ball event columns."""
        return self._points_from_event_columns(rec, lambda k: "10" in k and "ball" in k.lower())

    def _points_from_9ball_columns(self, rec: Dict) -> float:
        """Sum numeric values from keys that look like 9-ball (not 10-ball) event columns."""
        return self._points_from_event_columns(
            rec, lambda k: "9" in k and "ball" in k.lower() and "10" not in k
        )

    def get_latest_snapshot_with_8ball_data(self, system: str = "WPA_Men") -> Tuple[Optional[date], List[Dict]]:
        """Get the latest snapshot that has 8-ball columns in source_data (for WPA Men → CP 8-Ball)."""
        with self.engine.connect() as conn:
            # Find latest snapshot where at least one row has an 8-ball key in source_data
            row = conn.execute(text("""
                SELECT r.snapshot_date
                FROM rankings r
                WHERE r.ranking_system = :system
                AND r.source_data IS NOT NULL AND r.source_data != '{}'::jsonb
                AND EXISTS (
                    SELECT 1 FROM jsonb_object_keys(r.source_data) k
                    WHERE k::text LIKE '%8%' AND k::text LIKE '%ball%'
                )
                ORDER BY r.snapshot_date DESC
                LIMIT 1
            """), {"system": system}).fetchone()
            if not row:
                return None, []
            snapshot_date = row[0]
        return self.get_latest_snapshot_as_rankings(system, snapshot_date)

    def get_latest_snapshot_with_data(self, system: str) -> Tuple[Optional[date], List[Dict]]:
        """Get the latest snapshot that has source_data (for WPA Women column splitting)."""
        with self.engine.connect() as conn:
            # Find latest snapshot where at least one row has source_data
            row = conn.execute(text("""
                SELECT r.snapshot_date
                FROM rankings r
                WHERE r.ranking_system = :system
                AND r.source_data IS NOT NULL AND r.source_data != '{}'::jsonb
                ORDER BY r.snapshot_date DESC
                LIMIT 1
            """), {"system": system}).fetchone()
            if not row:
                return None, []
            snapshot_date = row[0]
        return self.get_latest_snapshot_as_rankings(system, snapshot_date)

    def copy_wpa_men_to_cp_8ball_using_8ball_points(self) -> int:
        """Copy WPA Men snapshot (with 8-ball columns) to Competitors_Pool_8Ball, using 8-ball points from source_data."""
        result = self.split_wpa_men_to_column_buttons()
        return result.get("WPA_Men_Yalin_8Ball", 0)

    # One button per WPA Men event column: (source_data key, ranking_system, display label)
    WPA_MEN_COLUMN_MAPPING: List[Tuple[str, str, str]] = [
        ("jax_mens_international_open_2025", "WPA_Men_10B_Polish", "Jax Men's International Open 2025"),
        ("little_monster_international_open_2025", "WPA_Men_Maldives", "Little Monster International Open 2025"),
        ("58th_all_japan_open_2025", "WPA_Men_HCM", "58th All Japan Open 2025"),
        ("international_9ball_open_2025", "WPA_Men_9B_IntlOpen", "International 9-Ball Open 2025"),
        ("qatar_world_cup_10ball_2025", "WPA_Men_10B_Qatar", "Qatar World Cup 10-Ball 2025"),
        ("yalin_wpa_8ball_world_championship_2025", "WPA_Men_Yalin_8Ball", "Yalin 8-Ball World Championship 2025"),
        ("predator_wpa_10ball_world_championship_2025", "WPA_Men_Predator_10B", "Predator 10-Ball World Championship 2025"),
        ("38th_jpba_japan_open_2025", "WPA_Men_JPBA_JapanOpen", "38th JPBA Japan Open 2025"),
        ("pudong_tangcheng_wpa_9ball_china_open_2025", "WPA_Men_9B_ChinaOpen", "Pudong 9-Ball China Open 2025"),
        ("9ball_world_championship_2025", "WPA_Men_9B_WorldChamp", "9-Ball World Championship 2025"),
        ("indonesia_international_10ball_open_2025", "WPA_Men_10B_Indonesia", "Indonesia 10-Ball Open 2025"),
        ("kamui_las_vegas_open_2025", "WPA_Men_Kamui_LasVegas", "Kamui Las Vegas Open 2025"),
    ]

    # One button per WPA Women event column: (source_data key, ranking_system, display label)
    WPA_WOMEN_COLUMN_MAPPING: List[Tuple[str, str, str]] = [
        ("wpa_9ball_world_championship_2025", "WPA_Women_9B_WorldChamp", "WPA 9-Ball World Championship 2025"),
        ("little_monster_international_open_2025", "WPA_Women_LittleMonster", "Little Monster International Open 2025"),
        ("57th_all_japan_championship_2025", "WPA_Women_AllJapan57", "57th All Japan Championship 2025"),
        ("wpba_dr_pool_tour_championship_2025", "WPA_Women_DRPoolTour", "WPBA DR Pool Tour Championship 2025"),
        ("predator_wpa_10ball_world_championship_2025", "WPA_Women_10B_Predator", "Predator WPA 10-Ball World Championship 2025"),
        ("poison_saigon_9ball_open_2025", "WPA_Women_9Ball", "Poison Saigon 9-Ball Open 2025"),
        ("japan_open_2025", "WPA_Women_JapanOpen", "Japan Open 2025"),
        ("china_open_2025", "WPA_Women_ChinaOpen", "China Open 2025"),
        ("wpba_olhausen_colorado_classic_2025", "WPA_Women_WPBA_Colorado", "WPBA Olhausen Colorado Classic 2025"),
        ("indonesia_10ball_open_2025", "WPA_Women_10B_Indonesia", "Indonesia 10-Ball Open 2025"),
        ("wpa_8ball_world_championship_2025", "WPA_Women_8Ball", "WPA 8-Ball World Championship 2025"),
        ("wpba_se_masters_2025", "WPA_Women_WPBA_SEMasters", "WPBA SE Masters 2025"),
        ("wpba_raxx_mezz_2025", "WPA_Women_WPBA_RaxxMezz", "WPBA Raxx Mezz 2025"),
        ("kamui_las_vegas_open_2025", "WPA_Women_Kamui_LasVegas", "Kamui Las Vegas Open 2025"),
        ("pbs_las_vegas_open_2026", "WPA_Women_PBS_LasVegasOpen2026", "PBS Las Vegas Open 2026"),
        ("wpba_olhausen_ironcity_2025", "WPA_Women_WPBA_IronCity", "WPBA Olhausen IronCity 2025"),
    ]

    # One button per Heyball Men event column: (source_data key, ranking_system, display label)
    WPA_HEYBALL_MEN_COLUMN_MAPPING: List[Tuple[str, str, str]] = [
        ("heyball_world_championship_2025", "WPA_Heyball_Men_WorldChamp", "Heyball World Championship 2025"),
        ("10ball_wc_2024", "WPA_Heyball_Men_10Ball", "10-Ball World Championship 2024"),
        ("asian_heyball_open_2025", "WPA_Heyball_Men_Asian", "Asian Heyball Open 2025"),
        ("european_heyball_open_2025", "WPA_Heyball_Men_European", "European Heyball Open 2025"),
        ("north_american_heyball_open_2025", "WPA_Heyball_Men_NorthAmerican", "North American Heyball Open 2025"),
        ("oceania_heyball_open_2025", "WPA_Heyball_Men_Oceania", "Oceania Heyball Open 2025"),
        ("pan_american_heyball_open_2025", "WPA_Heyball_Men_PanAmerican", "Pan American Heyball Open 2025"),
        ("heyball_champion_of_champions_2025", "WPA_Heyball_Men_Champions", "Heyball Champion of Champions 2025"),
    ]

    # One button per Heyball Women event column: (source_data key, ranking_system, display label)
    WPA_HEYBALL_WOMEN_COLUMN_MAPPING: List[Tuple[str, str, str]] = [
        ("heyball_world_championship_2025", "WPA_Heyball_Women_WorldChamp", "Heyball World Championship 2025"),
        ("asian_heyball_open_2025", "WPA_Heyball_Women_Asian", "Asian Heyball Open 2025"),
        ("european_heyball_open_2025", "WPA_Heyball_Women_European", "European Heyball Open 2025"),
        ("north_american_heyball_open_2025", "WPA_Heyball_Women_NorthAmerican", "North American Heyball Open 2025"),
        ("oceania_heyball_open_2025", "WPA_Heyball_Women_Oceania", "Oceania Heyball Open 2025"),
        ("pan_american_heyball_open_2025", "WPA_Heyball_Women_PanAmerican", "Pan American Heyball Open 2025"),
        ("heyball_champion_of_champions_2025", "WPA_Heyball_Women_Champions", "Heyball Champion of Champions 2025"),
    ]

    # One button per Artistic Pool event: (source_data key for final pts, ranking_system, display label)
    # Only systems already allowed by rankings_ranking_system_check.
    # 2023 WC and 2024 WC points stay on the WPA_Artistic row source_data.
    WPA_ARTISTIC_COLUMN_MAPPING: List[Tuple[str, str, str]] = [
        ("2022_wc_pts", "WPA_Artistic_2022_WC", "2022 World Championship"),
    ]

    # One button per WPBA Women event column: (source_data key, ranking_system, display label)
    WPBA_WOMEN_COLUMN_MAPPING: List[Tuple[str, str, str]] = [
        ("2026_wpba_classic_billiards_championship", "WPBA_Women_ClassicBilliards2026", "2026 Classic Billiards Championship"),
        ("2026_wpba_olhausen_iron_city_invitational_vi", "WPBA_Women_IronCityVI", "2026 Iron City Invitational VI"),
        ("2025_wpba_dr_pool_jacoby_tour_championship", "WPBA_Women_Jacoby2025", "2025 Jacoby Tour Championship"),
        ("2025_wpba_olhausen_colorado_classic", "WPBA_Women_Colorado2025", "2025 Colorado Classic"),
        ("2025_wpba_soaring_eagle_masters", "WPBA_Women_SoaringEagle2025", "2025 Soaring Eagle Masters"),
        ("2025_wpba_olhausen_raxx_mezz_invitational", "WPBA_Women_RaxxMezz2025", "2025 Raxx Mezz Invitational"),
        ("2025_wpba_olhausen_iron_city_invitational_v", "WPBA_Women_IronCityV", "2025 Iron City Invitational V"),
        ("2024_wpba_dr_pool_jacoby_tour_championship", "WPBA_Women_Jacoby2024", "2024 Jacoby Tour Championship"),
        ("2024_wpba_capital_city_billiards_invitational", "WPBA_Women_CapitalCity2024", "2024 Capital City Invitational"),
        ("2024_wpba_cuespeed_napa_invitational", "WPBA_Women_NAPA2024", "2024 Cuespeed NAPA Invitational"),
        ("2024_wpba_olhausen_colorado_classic", "WPBA_Women_Colorado2024", "2024 Colorado Classic"),
        (WPBA_ROTATING_11TH_KEY, "WPBA_Women_Rotating11th", WPBA_ROTATING_11TH_LABEL),
        ("wpba_palmetto_billiards_invitational", "WPBA_Women_Palmetto", "Palmetto Billiards Invitational"),
    ]

    def _points_from_single_column(self, rec: Dict, column_key: str) -> float:
        """Extract numeric points from a single source_data column key."""
        val = rec.get(column_key)
        if val is None or val == "":
            return 0.0
        try:
            return float(str(val).replace(",", "").strip())
        except (ValueError, TypeError):
            return 0.0

    # Keys we never treat as event points (first-class or metadata)
    _NON_EVENT_KEYS = frozenset({
        "name", "rank", "points", "country", "license_number", "stops_played",
        "player", "date", "ranking_system", "id", "fargo_rating", "alfa_rating",
        "fargo_last_updated", "fargo_robustness", "total", "position",
        "wpba_column_labels",  # PDF header display names (dict), not a point column
        "wpa_column_labels",  # HTML header display names (dict), not a point column
    })

    # Artistic Pool sub-breakdown keys (position/score/discipline per event) --
    # must not be counted in _sum_all_event_points since the *_pts key already
    # contains the combined value.
    _ARTISTIC_BREAKDOWN_SUFFIXES = ("_position_pts", "_score_pts", "_discipline_pts", "_raw_total", "_pct_applied")
    _LICENSE_SUFFIX_RE = re.compile(r"\s+([A-Z]{2,5}\s*-\s*\d{2,5})\s*$")
    _COUNTRY_CODE_RE = re.compile(r"^[A-Z]{2,5}$")
    _NUMERIC_CODE_RE = re.compile(r"^\d{4,}$")

    _ASSOCIATION_DB_MAP: Dict[str, str] = {
        "wpba": "WPBA",
        "wpa": "WPA",
        "wpa women": "WPA",
        "wpa men": "WPA",
        "wpa heyball men": "WPA",
        "wpa heyball women": "WPA",
        "wpa artistic": "WPA",
    }

    def _canonical_player_name(self, name: str) -> str:
        raw = (name or "").strip()
        m = self._LICENSE_SUFFIX_RE.search(raw)
        if m:
            raw = raw[: m.start()].strip()
        if "," in raw:
            parts = [p.strip() for p in raw.split(",", 1)]
            if len(parts) == 2 and parts[0] and parts[1]:
                raw = f"{parts[1]} {parts[0]}"
        return re.sub(r"\s+", " ", raw).lower().strip()

    def _generate_name_variants_for_lookup(self, canonical: str) -> List[str]:
        """
        Generate name variants for identity resolution (e.g. "alexander kazakis" <-> "kazakis alexander").
        Used to match existing players and prevent duplicates from name-order differences.
        """
        variants: List[str] = []
        raw = (canonical or "").strip().lower()
        raw = re.sub(r"\s+", " ", raw)
        if not raw:
            return variants
        variants.append(raw)
        parts = raw.split()
        if len(parts) >= 2:
            reversed_order = " ".join(reversed(parts))
            if reversed_order not in variants:
                variants.append(reversed_order)
        return variants

    def _resolve_player_id(
        self,
        conn,
        name: str,
        license_number: Optional[str],
        canonical_name: str,
        system: Optional[str] = None,
    ) -> Tuple[str, Optional[str], Optional[str]]:
        """
        Resolve to existing player_id by license or canonical name variants.
        Prevents duplicates when same person appears with different name formats or licenses.

        Returns:
            (player_id, first_name, last_name)
            If existing player found: (existing_id, existing_first, existing_last)
            Else: (generated_id, None, None) - caller uses _split_player_name for first/last
        """
        variants = self._generate_name_variants_for_lookup(canonical_name)
        if not variants:
            return (
                self._generate_player_id_from_name(name, license_number),
                None,
                None,
            )

        # 0. Optional: expand variants from player_name_aliases (scraped_name -> canonical_name)
        if system:
            try:
                alias_rows = conn.execute(
                    text("""
                        SELECT canonical_name FROM player_name_aliases
                        WHERE LOWER(TRIM(scraped_name)) = :name AND ranking_system = :system
                    """),
                    {"name": (name or "").strip().lower(), "system": system},
                ).fetchall()
                for r in alias_rows:
                    c = (r[0] or "").strip().lower()
                    if c and c not in variants:
                        variants.append(c)
                        variants.extend(self._generate_name_variants_for_lookup(c))
            except Exception as e:
                logger.debug("player_name_aliases lookup failed: %s", e)

        # 1. License lookup: if we have this license in locks, get canonical and find player
        normalized_lic = self._normalize_license_number(license_number) if license_number else None
        if normalized_lic:
            try:
                row = conn.execute(
                    text("""
                        SELECT pll.canonical_name
                        FROM player_license_locks pll
                        WHERE pll.license_number = :lic
                    """),
                    {"lic": normalized_lic},
                ).fetchone()
                if row:
                    locked_canonical = (row[0] or "").strip().lower()
                    if locked_canonical:
                        variants = list(set(variants + [locked_canonical]))
            except Exception as e:
                logger.debug("License lock lookup failed: %s", e)

        # 2. Find existing player by canonical name or variants (first_name || ' ' || last_name)
        try:
            for v in variants:
                result = conn.execute(
                    text("""
                        SELECT player_id, first_name, last_name
                        FROM players
                        WHERE LOWER(TRIM(first_name || ' ' || last_name)) = :v
                           OR LOWER(TRIM(last_name || ' ' || first_name)) = :v
                        LIMIT 1
                    """),
                    {"v": v},
                ).fetchone()
                if result:
                    return (str(result[0]), str(result[1] or ""), str(result[2] or ""))
        except Exception as e:
            logger.debug("Player lookup by name variants failed: %s", e)

        return (
            self._generate_player_id_from_name(name, license_number),
            None,
            None,
        )

    def _swap_last_token_name(self, name: str) -> str:
        """
        Swap last token to front: "First Middle Last" -> "Last First Middle".
        Helps match systems that alternate between "First Last" and "Last First".
        """
        canonical = re.sub(r"\s+", " ", (name or "").strip())
        if not canonical:
            return ""
        parts = canonical.split(" ")
        if len(parts) < 2:
            return canonical
        return " ".join([parts[-1], *parts[:-1]])

    def _normalize_display_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize row fields for UI display when source imports used shifted columns.
        - Strip trailing license token from name (e.g. "Foo ACBS - 108") for display
        - If country is numeric and license is country-code-like, swap (column shift fix)
        - Never fabricate license or country: if not in scraped data, leave blank.
        """
        out = dict(row)
        name = str(out.get("name") or "").strip()
        country = str(out.get("country") or "").strip()
        license_number = str(out.get("license_number") or "").strip()

        suffix_match = self._LICENSE_SUFFIX_RE.search(name)
        if suffix_match:
            name = name[: suffix_match.start()].strip()

        country_is_numeric = bool(self._NUMERIC_CODE_RE.fullmatch(country))
        license_is_country_code = bool(self._COUNTRY_CODE_RE.fullmatch(license_number))

        if country_is_numeric and license_is_country_code:
            country = license_number
            license_number = ""

        out["name"] = name or out.get("name")
        out["player_name"] = out.get("name")  # API contract for mobile (RankingItem expects player_name)
        out["country"] = country or None
        out["license_number"] = license_number or None
        return out

    def _sum_rolling_10_wpba_event_points(self, rec: Dict, tournament_cols: List[str]) -> float:
        """Sum points from the most recent 10 tournament columns (rolling-10 rule for WPBA/WPA/Heyball)."""
        if not tournament_cols:
            return 0.0
        # Take last 10 (most recent tournaments)
        cols_to_sum = tournament_cols[-10:]
        total = 0.0
        for k in cols_to_sum:
            val = rec.get(k)
            if val is None or val == "":
                continue
            try:
                n = float(str(val).replace(",", "").strip())
                if n >= 0:
                    total += n
            except (ValueError, TypeError):
                pass
        return total

    def _sum_all_event_points(self, rec: Dict) -> float:
        """Sum all numeric values in rec that look like event/tournament point columns.
        Excludes first-class/metadata keys, any key that looks like a total
        (so we don't double-count), and Artistic Pool sub-breakdown keys
        (position/score/discipline) since the ``*_pts`` key already has the
        combined value."""
        total = 0.0
        for k, v in rec.items():
            if k in self._NON_EVENT_KEYS or v is None or v == "":
                continue
            if "total" in k.lower():
                continue
            if any(k.endswith(sfx) for sfx in self._ARTISTIC_BREAKDOWN_SUFFIXES):
                continue
            try:
                n = float(str(v).replace(",", "").strip())
                if n >= 0:
                    total += n
            except (ValueError, TypeError) as e:
                logger.debug("Skipping non-numeric source_data value for key '%s': %s", k, e)
        return total

    def verify_wpa_men_totals(self, tolerance: float = 0.01) -> List[Dict[str, Any]]:
        """Verify that for WPA Men, stored points = sum of all event columns. Returns list of mismatches."""
        snapshot_date, rankings = self.get_latest_snapshot_with_8ball_data("WPA_Men")
        if not snapshot_date or not rankings:
            return []
        mismatches = []
        for rec in rankings:
            stored = float(rec.get("points") or 0)
            computed = self._sum_all_event_points(rec)
            if abs(computed - stored) > tolerance:
                mismatches.append({
                    "player_name": rec.get("name"),
                    "stored_points": round(stored, 2),
                    "computed_total": round(computed, 2),
                    "diff": round(computed - stored, 2),
                })
        return mismatches

    def recalculate_wpa_men_totals_from_source_data(self, tolerance: float = 0.01) -> int:
        """For WPA Men latest snapshot, set points = sum of all event columns for each row where they differ. Returns count updated."""
        snapshot_date, rankings = self.get_latest_snapshot_with_8ball_data("WPA_Men")
        if not snapshot_date or not rankings:
            return 0
        with self.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT id, player_name, points, source_data
                FROM rankings
                WHERE ranking_system = 'WPA_Men' AND snapshot_date = :dt
                ORDER BY position ASC NULLS LAST, rank ASC, id ASC
            """), {"dt": snapshot_date})
            rows = result.fetchall()
        updated = 0
        for r in rows:
            row_id, name, stored_pts, source_data = r[0], r[1], float(r[2] or 0), r[3]
            rec = {"name": name, "points": stored_pts}
            if source_data:
                try:
                    extra = source_data if isinstance(source_data, dict) else json.loads(source_data)
                    rec.update({k: v for k, v in extra.items() if k not in rec})
                except (TypeError, ValueError) as e:
                    logger.debug("Could not parse WPA_Men source_data for row id %s (%s): %s", row_id, name, e)
            computed = self._sum_all_event_points(rec)
            if abs(computed - stored_pts) > tolerance:
                with self.engine.connect() as conn:
                    conn.execute(text("UPDATE rankings SET points = :pts WHERE id = :id"), {"pts": computed, "id": row_id})
                    conn.commit()
                updated += 1
                logger.info("WPA Men recalc: %s stored=%.2f computed=%.2f", name, stored_pts, computed)
        return updated

    def split_wpa_men_to_column_buttons(self) -> Dict[str, int]:
        """Split WPA Men snapshot so each event column has its own ranking_system (one button per column).
        Include ALL players from main WPA_Men rankings in each tournament with 0 points for missing/null data.
        Uses hardcoded mapping plus HTML-discovered columns; skips columns with no non-zero points
        (preserves existing per-event snapshots). Returns {ranking_system: count}."""
        snapshot_date, rankings = self.get_latest_snapshot_with_8ball_data("WPA_Men")
        if not snapshot_date or not rankings:
            logger.warning("No WPA_Men snapshot with event columns to split")
            return {}
        column_mapping = self._get_wpa_recent_column_mapping(
            rankings,
            self.WPA_MEN_COLUMN_MAPPING,
            "WPA_Men",
            self.WPA_MEN_WOMEN_EVENT_COLUMN_LIMIT,
        )
        result: Dict[str, int] = {}
        for column_key, target_system, _label in column_mapping:
            rows = []
            for rec in rankings:
                pts = self._points_from_single_column(rec, column_key)
                rows.append({
                    "name": rec.get("name"),
                    "rank": 0,
                    "points": pts,
                    "country": rec.get("country"),
                    "license_number": rec.get("license_number"),
                })
            rows.sort(key=lambda r: (-float(r["points"]), (r["name"] or "")))
            for i, r in enumerate(rows):
                r["rank"] = i + 1
            if rows:
                with self.engine.connect() as conn:
                    conn.execute(
                        text("DELETE FROM rankings WHERE ranking_system = :sys AND snapshot_date = :dt"),
                        {"sys": target_system, "dt": snapshot_date},
                    )
                    conn.commit()
                count = self.save_rankings(rows, target_system, snapshot_date)
                result[target_system] = count
                logger.info("Split WPA Men -> %s: %d players (column %s with 0s for missing data)", target_system, count, column_key)
        self.copy_fargo_from_wpa_men_to_cp_systems(snapshot_date)
        return result

    def split_wpa_women_to_column_buttons(self) -> Dict[str, int]:
        """Split WPA Women snapshot so each event column has its own ranking_system (one button per column).
        Include ALL players from main WPA_Women rankings in each tournament with 0 points for missing/null data.
        Uses hardcoded mapping plus HTML-discovered columns; skips columns with no non-zero points
        (preserves existing per-event snapshots). Returns {ranking_system: count}."""
        snapshot_date, rankings = self.get_latest_snapshot_with_data("WPA_Women")
        if not snapshot_date or not rankings:
            logger.warning("No WPA_Women snapshot with event columns to split")
            return {}
        column_mapping = self._get_wpa_recent_column_mapping(
            rankings,
            self.WPA_WOMEN_COLUMN_MAPPING,
            "WPA_Women",
            self.WPA_MEN_WOMEN_EVENT_COLUMN_LIMIT,
        )
        result: Dict[str, int] = {}
        for column_key, target_system, _label in column_mapping:
            rows = []
            for rec in rankings:
                pts = self._points_from_single_column(rec, column_key)
                ranking = {
                    'name': rec.get('name', rec.get('player', '')),
                    'rank': None,
                    'points': pts,
                    'country': rec.get('country'),
                    'license_number': rec.get('license_number') or rec.get('wpa_license_number'),
                    'fargo_rating': rec.get('fargo_rating'),
                    'alfa_rating': rec.get('alfa_rating'),
                    'stops_played': rec.get('stops_played'),
                }
                rows.append(ranking)
            if not rows:
                continue
            rows.sort(key=lambda x: (-x['points'], x['name']))
            for i, r in enumerate(rows, 1):
                r['rank'] = i
            with self.engine.connect() as conn:
                conn.execute(
                    text("DELETE FROM rankings WHERE ranking_system = :sys AND snapshot_date = :dt"),
                    {"sys": target_system, "dt": snapshot_date},
                )
                conn.commit()
            count = self.save_rankings(rows, target_system, snapshot_date)
            result[target_system] = count
            logger.info("Split WPA Women -> %s: %d players (column %s with 0s for missing data)", target_system, count, column_key)
        self.copy_fargo_from_wpa_women_to_cp_systems(snapshot_date)
        return result

    def copy_fargo_from_wpa_women_to_cp_systems(self, snapshot_date: Optional[date] = None) -> int:
        """Copy fargo_rating and fargo_last_updated from WPA_Women into CP and WPA_Women_* column systems
        by matching player_name. Uses same snapshot_date when given; otherwise uses latest WPA_Women snapshot."""
        targets: List[str] = []
        with self.engine.connect() as conn:
            wpa_women_column_systems = list(
                dict.fromkeys(
                    [t[1] for t in self.WPA_WOMEN_COLUMN_MAPPING]
                    + self._distinct_child_ranking_systems(conn, "WPA_Women")
                )
            )
            targets = [
                "Competitors_Pool_8Ball", "Competitors_Pool_10Ball", "Competitors_Pool_9Ball", "Competitors_Pool_Women_9Ball"
            ] + wpa_women_column_systems
            total_updated = 0
            if snapshot_date is not None:
                # Same snapshot: copy from WPA_Women that snapshot
                for target in targets:
                    result = conn.execute(text("""
                        UPDATE rankings r
                        SET fargo_rating = w.fargo_rating,
                            fargo_last_updated = w.fargo_last_updated
                        FROM rankings w
                        WHERE w.ranking_system = 'WPA_Women'
                          AND w.snapshot_date = :dt
                          AND r.ranking_system = :target
                          AND r.snapshot_date = :dt
                          AND r.player_name = w.player_name
                          AND w.fargo_rating IS NOT NULL
                    """), {"dt": snapshot_date, "target": target})
                    total_updated += result.rowcount
            else:
                # No snapshot: copy Fargo from latest WPA_Women row per player (match by normalized name)
                for target in targets:
                    result = conn.execute(text("""
                        UPDATE rankings r
                        SET fargo_rating = w.fargo_rating,
                            fargo_last_updated = w.fargo_last_updated
                        FROM (
                            SELECT DISTINCT ON (player_name) player_name, fargo_rating, fargo_last_updated
                            FROM rankings
                            WHERE ranking_system = 'WPA_Women' AND fargo_rating IS NOT NULL
                            ORDER BY player_name, snapshot_date DESC
                        ) w
                        WHERE r.ranking_system = :target
                          AND r.player_name = w.player_name
                          AND w.fargo_rating IS NOT NULL
                    """), {"target": target})
                    total_updated += result.rowcount
            conn.commit()
        logger.info("Copied Fargo ratings from WPA_Women to %d target systems: %d total updates", len(targets), total_updated)
        return total_updated

    def split_wpa_heyball_men_to_column_buttons(self) -> Dict[str, int]:
        """Split WPA Heyball Men snapshot so each event column has its own ranking_system (one button per column).
        Include ALL players from main WPA_Heyball_Men rankings in each tournament with 0 points for missing/null data.
        This ensures proper total calculations. Returns {ranking_system: count}."""
        snapshot_date, rankings = self.get_latest_snapshot_with_data("WPA_Heyball_Men")
        if not snapshot_date or not rankings:
            logger.warning("No WPA_Heyball_Men snapshot with event columns to split")
            return {}
        result: Dict[str, int] = {}
        for column_key, target_system, _label in self.WPA_HEYBALL_MEN_COLUMN_MAPPING:
            rows = []
            for rec in rankings:
                # Always include players from main rankings, use 0 for missing/null tournament data
                pts = self._points_from_single_column(rec, column_key)
                # Create ranking dict for this player in this specific tournament
                ranking = {
                    'name': rec.get('name', rec.get('player', rec.get('athlete', ''))),
                    'rank': None,  # Will be set after sorting
                    'points': pts,  # Can be 0 for players who didn't participate
                    'country': rec.get('country'),
                    'license_number': rec.get('license_number') or rec.get('wpa_license_number'),
                    'fargo_rating': rec.get('fargo_rating'),
                    'alfa_rating': rec.get('alfa_rating'),
                    'stops_played': rec.get('stops_played'),
                }
                rows.append(ranking)
            if not rows:
                continue
            # Sort by points descending and assign ranks
            rows.sort(key=lambda x: (-x['points'], x['name']))
            for i, r in enumerate(rows, 1):
                r['rank'] = i
            with self.engine.connect() as conn:
                # Delete existing data for this system and date
                conn.execute(
                    text("DELETE FROM rankings WHERE ranking_system = :sys AND snapshot_date = :dt"),
                    {"sys": target_system, "dt": snapshot_date},
                )
                conn.commit()
            count = self.save_rankings(rows, target_system, snapshot_date)
            result[target_system] = count
            logger.info("Split WPA Heyball Men -> %s: %d players (column %s with 0s for missing data)", target_system, count, column_key)
        self.copy_fargo_from_wpa_heyball_men_to_cp_systems(snapshot_date)
        return result

    def split_wpa_heyball_women_to_column_buttons(self) -> Dict[str, int]:
        """Split WPA Heyball Women snapshot so each event column has its own ranking_system (one button per column).
        Include ALL players from main WPA_Heyball_Women rankings in each tournament with 0 points for missing/null data.
        This ensures proper total calculations. Returns {ranking_system: count}."""
        snapshot_date, rankings = self.get_latest_snapshot_with_data("WPA_Heyball_Women")
        if not snapshot_date or not rankings:
            logger.warning("No WPA_Heyball_Women snapshot with event columns to split")
            return {}
        result: Dict[str, int] = {}
        for column_key, target_system, _label in self.WPA_HEYBALL_WOMEN_COLUMN_MAPPING:
            rows = []
            for rec in rankings:
                # Always include players from main rankings, use 0 for missing/null tournament data
                pts = self._points_from_single_column(rec, column_key)
                # Create ranking dict for this player in this specific tournament
                ranking = {
                    'name': rec.get('name', rec.get('player', rec.get('athlete', ''))),
                    'rank': None,  # Will be set after sorting
                    'points': pts,  # Can be 0 for players who didn't participate
                    'country': rec.get('country'),
                    'license_number': rec.get('license_number') or rec.get('wpa_license_number'),
                    'fargo_rating': rec.get('fargo_rating'),
                    'alfa_rating': rec.get('alfa_rating'),
                    'stops_played': rec.get('stops_played'),
                }
                rows.append(ranking)
            if not rows:
                continue
            # Sort by points descending and assign ranks
            rows.sort(key=lambda x: (-x['points'], x['name']))
            for i, r in enumerate(rows, 1):
                r['rank'] = i
            with self.engine.connect() as conn:
                # Delete existing data for this system and date
                conn.execute(
                    text("DELETE FROM rankings WHERE ranking_system = :sys AND snapshot_date = :dt"),
                    {"sys": target_system, "dt": snapshot_date},
                )
                conn.commit()
            count = self.save_rankings(rows, target_system, snapshot_date)
            result[target_system] = count
            logger.info("Split WPA Heyball Women -> %s: %d players (column %s with 0s for missing data)", target_system, count, column_key)
        self.copy_fargo_from_wpa_heyball_women_to_cp_systems(snapshot_date)
        return result

    def split_wpa_artistic_to_column_buttons(self) -> Dict[str, int]:
        """Split WPA Artistic Pool snapshot so each event has its own ranking_system
        (one button per tournament). Include ALL players from main WPA_Artistic rankings in each tournament
        with 0 points for missing/null data. Each per-event record stores the position/score/
        discipline breakdown in source_data for display. Returns {ranking_system: count}."""
        snapshot_date, rankings = self.get_latest_snapshot_with_data("WPA_Artistic")
        if not snapshot_date or not rankings:
            logger.warning("No WPA_Artistic snapshot with event columns to split")
            return {}
        result: Dict[str, int] = {}
        for column_key, target_system, _label in self.WPA_ARTISTIC_COLUMN_MAPPING:
            event_prefix = column_key.replace("_pts", "")
            rows = []
            for rec in rankings:
                # Always include players from main rankings, use 0 for missing/null tournament data
                pts = self._points_from_single_column(rec, column_key)
                ranking: Dict[str, Any] = {
                    "name": rec.get("name"),
                    "rank": 0,
                    "points": pts,  # Can be 0 for players who didn't participate
                    "country": rec.get("country"),
                    "position_pts": rec.get(f"{event_prefix}_position_pts"),
                    "score_pts": rec.get(f"{event_prefix}_score_pts"),
                    "discipline_pts": rec.get(f"{event_prefix}_discipline_pts"),
                    "raw_total": rec.get(f"{event_prefix}_raw_total"),
                    "pct_applied": rec.get(f"{event_prefix}_pct_applied"),
                }
                rows.append(ranking)
            rows.sort(key=lambda r: (-float(r["points"]), (r["name"] or "")))
            for i, r in enumerate(rows):
                r["rank"] = i + 1
            if rows:
                with self.engine.connect() as conn:
                    conn.execute(
                        text("DELETE FROM rankings WHERE ranking_system = :sys AND snapshot_date = :dt"),
                        {"sys": target_system, "dt": snapshot_date},
                    )
                    conn.commit()
                count = self.save_rankings(rows, target_system, snapshot_date)
                result[target_system] = count
                logger.info("Split WPA Artistic -> %s: %d players (column %s with 0s for missing data)", target_system, count, column_key)
        return result

    def _extract_year_from_text(self, text_value: Optional[str]) -> int:
        """Extract a 4-digit year (20xx) from text, or 0 when missing."""
        text_value = (text_value or "").strip()
        m = re.search(r"(20\d{2})", text_value)
        if not m:
            return 0
        try:
            return int(m.group(1))
        except (TypeError, ValueError):
            return 0

    def _get_wpba_column_mapping_with_discovered(self, rankings: List[Dict]) -> List[Tuple[str, str, str]]:
        """Merge hardcoded WPBA column mapping with dynamically discovered columns from latest WPBA rows."""
        mapping = list(self.WPBA_WOMEN_COLUMN_MAPPING)
        known_keys = {m[0] for m in mapping}
        if not rankings:
            return mapping

        discovered_keys = set()
        for rec in rankings:
            if not isinstance(rec, dict):
                continue
            for k, v in rec.items():
                if k in known_keys or k in self._NON_EVENT_KEYS:
                    continue
                if isinstance(k, str) and k.startswith("col_"):
                    continue
                if "total" in k.lower() or "rank" in k.lower() or "name" in k.lower():
                    continue
                try:
                    float(str(v or "0").replace(",", "").strip())
                except (ValueError, TypeError):
                    continue
                discovered_keys.add(k)

        used_targets = {m[1] for m in mapping}
        for k in sorted(discovered_keys):
            # New tournament column: derive system name and label (max 32 chars for ranking_system)
            safe = re.sub(r"[^\w]", "_", k).strip("_")
            parts = [p.capitalize() for p in safe.split("_") if p and not p.isdigit()]
            label = " ".join(parts) if parts else k
            base = "".join(p for p in parts[:6] if p) or safe[:15]
            target = "WPBA_Women_" + re.sub(r"[^A-Za-z0-9_]", "", base)
            if len(target) > 32:
                target = "WPBA_Women_" + re.sub(r"[^A-Za-z0-9_]", "", safe)[:20]
            target = target[:32]
            # Two different PDF columns must not share the same ranking_system (would overwrite split data).
            if target in used_targets:
                h = hashlib.sha256(k.encode("utf-8")).hexdigest()[:8]
                target = ("WPBA_W_" + h)[:32]
                if target in used_targets:
                    target = ("WPBA_W_" + h + k[:4])[:32]
            used_targets.add(target)
            mapping.append((k, target, label))
            known_keys.add(k)
        return mapping

    def _get_wpba_recent_column_mapping(self, rankings: List[Dict], limit: int = 10) -> List[Tuple[str, str, str]]:
        """Return the ``limit`` most recent active WPBA tournaments, ordered newest-first.

        Recency is driven by the PDF column order the scraper preserves on each row as
        ``_wpba_tournament_columns`` (left-to-right == newest-first; it excludes the rotating
        11th). This is the authoritative single-source-of-truth ordering, so when a new event
        enters the rolling window it rolls in at the top and the oldest in-window event falls
        off automatically — without depending on the hand-maintained ``WPBA_WOMEN_COLUMN_MAPPING``.
        The rotating-11th (out-of-window) column always sorts last so it stays visible as the
        event leaving the window. Columns absent from the PDF order list fall back to
        year-descending, then hardcoded mapping position.
        """
        mapping = self._get_wpba_column_mapping_with_discovered(rankings)
        if not mapping:
            return []

        active: List[Tuple[str, str, str]] = []
        for column_key, target_system, label in mapping:
            if any(self._points_from_single_column(rec, column_key) > 0 for rec in rankings):
                active.append((column_key, target_system, label))

        if not active:
            return []

        # Authoritative recency: position in the scraper-preserved PDF column order
        # (first row that carries the list wins; all rows share the same order).
        pdf_order: Dict[str, int] = {}
        for rec in rankings:
            cols = rec.get("_wpba_tournament_columns") if isinstance(rec, dict) else None
            if isinstance(cols, list) and cols:
                for i, k in enumerate(cols):
                    if k not in pdf_order:
                        pdf_order[k] = i
                break

        known_order = {k: i for i, (k, _sys, _label) in enumerate(self.WPBA_WOMEN_COLUMN_MAPPING)}

        def _sort_key(item: Tuple[str, str, str]) -> Tuple[int, int, int, str]:
            column_key, _target, label = item
            # Rotating 11th (out-of-window) always last.
            if column_key == WPBA_ROTATING_11TH_KEY:
                return (2, 0, 0, label.lower())
            # In-window events follow the PDF's newest-first column order.
            if column_key in pdf_order:
                return (0, pdf_order[column_key], 0, label.lower())
            # Fallback (columns missing from PDF order list): year desc, then hardcoded position.
            year = self._extract_year_from_text(column_key) or self._extract_year_from_text(label)
            known_idx = known_order.get(column_key, 10_000)
            return (1, -year, known_idx, label.lower())

        active.sort(key=_sort_key)
        return active[: max(1, int(limit or 10))]

    def _wpa_column_label_from_rankings(self, rankings: List[Dict], column_key: str) -> Optional[str]:
        """Prefer HTML header text from wpa_column_labels when present."""
        for rec in rankings:
            if not isinstance(rec, dict):
                continue
            labels = rec.get("wpa_column_labels")
            if isinstance(labels, dict) and column_key in labels:
                lab = labels.get(column_key)
                if lab and str(lab).strip():
                    return str(lab).strip()
        return None

    def _get_wpa_column_mapping_with_discovered(
        self,
        rankings: List[Dict],
        base_mapping: List[Tuple[str, str, str]],
        ranking_parent: str,
    ) -> List[Tuple[str, str, str]]:
        """Merge hardcoded WPA mapping with numeric event columns present in snapshot rows."""
        mapping = list(base_mapping)
        known_keys = {m[0] for m in mapping}
        if not rankings:
            return mapping

        discovered_keys = set()
        for rec in rankings:
            if not isinstance(rec, dict):
                continue
            for k, v in rec.items():
                if k in known_keys or k in self._NON_EVENT_KEYS:
                    continue
                if isinstance(k, str) and k.startswith("col_"):
                    continue
                if "total" in k.lower() or "rank" in k.lower() or "name" in k.lower():
                    continue
                if any(k.endswith(sfx) for sfx in self._ARTISTIC_BREAKDOWN_SUFFIXES):
                    continue
                try:
                    float(str(v or "0").replace(",", "").strip())
                except (ValueError, TypeError):
                    continue
                discovered_keys.add(k)

        prefix_with_us = ranking_parent + "_"
        used_targets = {m[1] for m in mapping}
        prefix_len = len(prefix_with_us)
        max_slug = max(1, 32 - prefix_len)

        for k in sorted(discovered_keys):
            label = self._wpa_column_label_from_rankings(rankings, k)
            if not label:
                safe = re.sub(r"[^\w]", "_", k).strip("_")
                parts = [p.capitalize() for p in safe.split("_") if p and not p.isdigit()]
                label = " ".join(parts) if parts else k

            safe = re.sub(r"[^\w]", "_", k).strip("_")
            slug = re.sub(r"[^A-Za-z0-9_]", "", safe) or "evt"
            slug = slug[:max_slug]
            target = (prefix_with_us + slug)[:32]

            if target in used_targets:
                h = hashlib.sha256(k.encode("utf-8")).hexdigest()[:8]
                target = (prefix_with_us + h)[:32]
                if target in used_targets:
                    target = (prefix_with_us + h + re.sub(r"[^A-Za-z0-9]", "", k)[:4])[:32]
            used_targets.add(target)
            mapping.append((k, target, label))
            known_keys.add(k)
        return mapping

    def _get_wpa_recent_column_mapping(
        self,
        rankings: List[Dict],
        base_mapping: List[Tuple[str, str, str]],
        ranking_parent: str,
        limit: int,
    ) -> List[Tuple[str, str, str]]:
        """Active event columns (≥1 player with points > 0), sorted newest-first, then first ``limit`` kept.

        Order: descending year parsed from column key or label (20xx), then position in ``base_mapping``,
        then label (stable). Columns with no extractable year sort after dated columns (year 0).
        """
        full_mapping = self._get_wpa_column_mapping_with_discovered(rankings, base_mapping, ranking_parent)
        if not full_mapping:
            return []

        active: List[Tuple[str, str, str]] = []
        for column_key, target_system, label in full_mapping:
            if any(self._points_from_single_column(rec, column_key) > 0 for rec in rankings):
                active.append((column_key, target_system, label))

        if not active:
            return []

        known_order = {k: i for i, (k, _sys, _label) in enumerate(base_mapping)}

        def _sort_key(item: Tuple[str, str, str]) -> Tuple[int, int, str]:
            column_key, _target, lbl = item
            year = self._extract_year_from_text(column_key) or self._extract_year_from_text(lbl)
            known_idx = known_order.get(column_key, 10_000)
            return (-year, known_idx, lbl.lower())

        active.sort(key=_sort_key)
        return active[: max(1, int(limit or self.WPA_MEN_WOMEN_EVENT_COLUMN_LIMIT))]

    def _distinct_child_ranking_systems(self, conn, ranking_parent: str) -> List[str]:
        """Distinct per-event systems under WPA_Men or WPA_Women (not the overall row)."""
        if ranking_parent == "WPA_Men":
            like_pat = r"WPA\_Men\_%"
        elif ranking_parent == "WPA_Women":
            like_pat = r"WPA\_Women\_%"
        else:
            return []
        rows = conn.execute(
            text(
                "SELECT DISTINCT ranking_system FROM rankings "
                "WHERE ranking_system LIKE :pat ESCAPE '\\' ORDER BY ranking_system"
            ),
            {"pat": like_pat},
        ).fetchall()
        return [str(r[0]) for r in rows if r and r[0]]

    def get_wpa_men_tournament_systems(self) -> List[Dict[str, str]]:
        """WPA Men per-event buttons: ``RANKINGS_MENU_RECENT_TOURNAMENT_LIMIT`` most recent active events, newest-first."""
        _sd, rankings = self.get_latest_snapshot_with_8ball_data("WPA_Men")
        if not rankings:
            return []
        mapping = self._get_wpa_recent_column_mapping(
            rankings,
            self.WPA_MEN_COLUMN_MAPPING,
            "WPA_Men",
            self.RANKINGS_MENU_RECENT_TOURNAMENT_LIMIT,
        )
        return [{"ranking_system": target, "label": label} for _k, target, label in mapping]

    def get_wpa_women_tournament_systems(self) -> List[Dict[str, str]]:
        """WPA Women per-event buttons: ``RANKINGS_MENU_RECENT_TOURNAMENT_LIMIT`` most recent active events, newest-first."""
        _sd, rankings = self.get_latest_snapshot_with_data("WPA_Women")
        if not rankings:
            return []
        mapping = self._get_wpa_recent_column_mapping(
            rankings,
            self.WPA_WOMEN_COLUMN_MAPPING,
            "WPA_Women",
            self.RANKINGS_MENU_RECENT_TOURNAMENT_LIMIT,
        )
        return [{"ranking_system": target, "label": label} for _k, target, label in mapping]

    def get_wpba_tournament_systems(self) -> List[Dict[str, str]]:
        """Return list of {ranking_system, label} for WPBA tournament buttons (overall + per-tournament).

        Uses active tournament columns from latest WPBA_Women snapshot (hardcoded + discovered),
        sorted by recency (PDF column order), and returns the 10 in-window tournaments plus the
        rotating 11th (out-of-window) event — newest-first, rotating-11th last.
        If no WPBA_Women data, falls back to distinct WPBA_Women_* systems in DB with derived labels.
        Excludes overall WPBA_Women.
        """
        # Read directly from snapshot with source_data merged (not the paginated API
        # response which strips tournament columns for the overall view).
        rankings = self._get_wpba_women_rankings_for_snapshot(date.today())
        if not rankings:
            with self.engine.connect() as conn:
                row = conn.execute(
                    text("SELECT MAX(snapshot_date) FROM rankings WHERE ranking_system = 'WPBA_Women'")
                ).fetchone()
            if row and row[0]:
                rankings = self._get_wpba_women_rankings_for_snapshot(row[0])
        mapping = self._get_wpba_recent_column_mapping(
            rankings, limit=self.WPBA_MENU_RECENT_TOURNAMENT_LIMIT
        )
        return [{"ranking_system": target, "label": label} for _k, target, label in mapping]

    def split_wpba_women_to_column_buttons(self) -> Dict[str, int]:
        """Split WPBA Women overall rankings into individual tournament systems.

        Uses active tournament columns from the latest WPBA snapshot and keeps only
        the most recent 10 tournaments for WPBA tournament buttons.
        Include ALL players from main rankings in each tournament with 0 points for missing/null data.
        This ensures proper total calculations when summing component systems.

        Returns:
            Dict with tournament names and player counts
        """
        # Read directly from snapshot with source_data merged (not the paginated API
        # response which strips tournament columns for the overall view).
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT MAX(snapshot_date) FROM rankings WHERE ranking_system = 'WPBA_Women'")
            ).fetchone()
        snap_date = row[0] if row and row[0] else date.today()
        rankings = self._get_wpba_women_rankings_for_snapshot(snap_date)
        if not rankings:
            return {}

        raw_date = rankings[0].get("snapshot_date") or rankings[0].get("date")
        if isinstance(raw_date, str):
            snapshot_date = datetime.strptime(raw_date[:10], "%Y-%m-%d").date()
        else:
            snapshot_date = raw_date or date.today()
        result = {}
        column_mapping = self._get_wpba_recent_column_mapping(
            rankings, limit=self.WPBA_WOMEN_EVENT_COLUMN_LIMIT
        )

        for column_key, target_system, label in column_mapping:
            rows = []
            has_nonzero = False
            for rec in rankings:
                pts = self._points_from_single_column(rec, column_key)
                if pts > 0:
                    has_nonzero = True
                ranking = {
                    'name': rec.get('name', rec.get('player', '')),
                    'rank': None,
                    'points': pts,
                    'country': rec.get('country'),
                    'license_number': rec.get('license_number') or rec.get('wpa_license_number'),
                    'fargo_rating': rec.get('fargo_rating'),
                    'alfa_rating': rec.get('alfa_rating'),
                }
                rows.append(ranking)

            if not rows:
                continue

            if not has_nonzero:
                logger.info(
                    "Skipping %s (%s): no non-zero points in source data — preserving existing snapshot",
                    target_system, label,
                )
                continue

            rows.sort(key=lambda x: (-x['points'], x['name']))
            for i, r in enumerate(rows):
                r["rank"] = i + 1

            count = self.save_rankings(rows, target_system, snapshot_date)
            result[label] = count

        return result

    def copy_fargo_from_wpa_heyball_men_to_cp_systems(self, snapshot_date: Optional[date] = None) -> int:
        """Copy fargo_rating and fargo_last_updated from WPA_Heyball_Men into CP and WPA_Heyball_Men_* column systems
        by matching player_name. Uses same snapshot_date when given; otherwise uses latest WPA_Heyball_Men snapshot."""
        heyball_men_column_systems = [t[1] for t in self.WPA_HEYBALL_MEN_COLUMN_MAPPING]
        targets = [
            "Competitors_Pool_8Ball", "Competitors_Pool_10Ball", "Competitors_Pool_9Ball", "Competitors_Pool_Men_9Ball"
        ] + heyball_men_column_systems
        total_updated = 0
        with self.engine.connect() as conn:
            if snapshot_date is not None:
                # Same snapshot: copy from WPA_Heyball_Men that snapshot
                for target in targets:
                    result = conn.execute(text("""
                        UPDATE rankings r
                        SET fargo_rating = w.fargo_rating,
                            fargo_last_updated = w.fargo_last_updated
                        FROM rankings w
                        WHERE w.ranking_system = 'WPA_Heyball_Men'
                          AND w.snapshot_date = :dt
                          AND r.ranking_system = :target
                          AND r.snapshot_date = :dt
                          AND r.player_name = w.player_name
                          AND w.fargo_rating IS NOT NULL
                    """), {"dt": snapshot_date, "target": target})
                    total_updated += result.rowcount
            else:
                # No snapshot: copy Fargo from latest WPA_Heyball_Men row per player
                for target in targets:
                    result = conn.execute(text("""
                        UPDATE rankings r
                        SET fargo_rating = w.fargo_rating,
                            fargo_last_updated = w.fargo_last_updated
                        FROM (
                            SELECT DISTINCT ON (player_name) player_name, fargo_rating, fargo_last_updated
                            FROM rankings
                            WHERE ranking_system = 'WPA_Heyball_Men' AND fargo_rating IS NOT NULL
                            ORDER BY player_name, snapshot_date DESC
                        ) w
                        WHERE r.ranking_system = :target
                          AND r.player_name = w.player_name
                          AND w.fargo_rating IS NOT NULL
                    """), {"target": target})
                    total_updated += result.rowcount
        logger.info("Copied Fargo from WPA_Heyball_Men to %d target systems: %d total updates", len(targets), total_updated)
        return total_updated

    def copy_fargo_from_wpa_heyball_women_to_cp_systems(self, snapshot_date: Optional[date] = None) -> int:
        """Copy fargo_rating and fargo_last_updated from WPA_Heyball_Women into CP and WPA_Heyball_Women_* column systems
        by matching player_name. Uses same snapshot_date when given; otherwise uses latest WPA_Heyball_Women snapshot."""
        heyball_women_column_systems = [t[1] for t in self.WPA_HEYBALL_WOMEN_COLUMN_MAPPING]
        targets = [
            "Competitors_Pool_8Ball", "Competitors_Pool_10Ball", "Competitors_Pool_9Ball", "Competitors_Pool_Women_9Ball"
        ] + heyball_women_column_systems
        total_updated = 0
        with self.engine.connect() as conn:
            if snapshot_date is not None:
                # Same snapshot: copy from WPA_Heyball_Women that snapshot
                for target in targets:
                    result = conn.execute(text("""
                        UPDATE rankings r
                        SET fargo_rating = w.fargo_rating,
                            fargo_last_updated = w.fargo_last_updated
                        FROM rankings w
                        WHERE w.ranking_system = 'WPA_Heyball_Women'
                          AND w.snapshot_date = :dt
                          AND r.ranking_system = :target
                          AND r.snapshot_date = :dt
                          AND r.player_name = w.player_name
                          AND w.fargo_rating IS NOT NULL
                    """), {"dt": snapshot_date, "target": target})
                    total_updated += result.rowcount
            else:
                # No snapshot: copy Fargo from latest WPA_Heyball_Women row per player
                for target in targets:
                    result = conn.execute(text("""
                        UPDATE rankings r
                        SET fargo_rating = w.fargo_rating,
                            fargo_last_updated = w.fargo_last_updated
                        FROM (
                            SELECT DISTINCT ON (player_name) player_name, fargo_rating, fargo_last_updated
                            FROM rankings
                            WHERE ranking_system = 'WPA_Heyball_Women' AND fargo_rating IS NOT NULL
                            ORDER BY player_name, snapshot_date DESC
                        ) w
                        WHERE r.ranking_system = :target
                          AND r.player_name = w.player_name
                          AND w.fargo_rating IS NOT NULL
                    """), {"target": target})
                    total_updated += result.rowcount
        logger.info("Copied Fargo from WPA_Heyball_Women to %d target systems: %d total updates", len(targets), total_updated)
        return total_updated

    # Game-type mapping: (extractor_fn, target(s)). Kept for backward compatibility if needed.
    _WPA_MEN_GAME_TYPE_TARGETS = [
        ("_points_from_8ball_columns", "Competitors_Pool_8Ball"),
        ("_points_from_10ball_columns", "Competitors_Pool_10Ball"),
        ("_points_from_9ball_columns", ["Competitors_Pool_9Ball", "Competitors_Pool_Men_9Ball"]),
    ]

    def split_wpa_men_to_game_type_buttons(self) -> Dict[str, int]:
        """Legacy: split by game type (combined columns). Prefer split_wpa_men_to_column_buttons for one button per column."""
        return self.split_wpa_men_to_column_buttons()

    def copy_fargo_from_wpa_men_to_cp_systems(self, snapshot_date: Optional[date] = None) -> int:
        """Copy fargo_rating and fargo_last_updated from WPA_Men into CP and WPA_Men_* column systems
        by matching player_name. Uses same snapshot_date when given; otherwise uses latest WPA_Men snapshot."""
        total_updated = 0
        targets: List[str] = []
        with self.engine.connect() as conn:
            wpa_men_column_systems = list(
                dict.fromkeys(
                    [t[1] for t in self.WPA_MEN_COLUMN_MAPPING]
                    + self._distinct_child_ranking_systems(conn, "WPA_Men")
                )
            )
            targets = [
                "Competitors_Pool_8Ball", "Competitors_Pool_10Ball", "Competitors_Pool_9Ball", "Competitors_Pool_Men_9Ball"
            ] + wpa_men_column_systems
            if snapshot_date is not None:
                # Same snapshot: copy from WPA_Men that snapshot
                for target in targets:
                    result = conn.execute(text("""
                        UPDATE rankings r
                        SET fargo_rating = w.fargo_rating,
                            fargo_last_updated = w.fargo_last_updated
                        FROM rankings w
                        WHERE w.ranking_system = 'WPA_Men'
                          AND w.snapshot_date = :dt
                          AND r.ranking_system = :target
                          AND r.snapshot_date = :dt
                          AND r.player_name = w.player_name
                          AND w.fargo_rating IS NOT NULL
                    """), {"dt": snapshot_date, "target": target})
                    total_updated += result.rowcount
            else:
                # No snapshot: copy Fargo from latest WPA_Men row per player (match by normalized name:
                # WPA_Men may be "Surname, First" while CP is "Surname First")
                for target in targets:
                    result = conn.execute(text("""
                        WITH wpa_fargo AS (
                            SELECT DISTINCT ON (TRIM(REGEXP_REPLACE(REPLACE(player_name, ',', ' '), '\\s+', ' ', 'g')))
                                player_name,
                                TRIM(REGEXP_REPLACE(REPLACE(player_name, ',', ' '), '\\s+', ' ', 'g')) AS norm_name,
                                fargo_rating,
                                fargo_last_updated
                            FROM rankings
                            WHERE ranking_system = 'WPA_Men' AND fargo_rating IS NOT NULL
                            ORDER BY TRIM(REGEXP_REPLACE(REPLACE(player_name, ',', ' '), '\\s+', ' ', 'g')), snapshot_date DESC
                        )
                        UPDATE rankings r
                        SET fargo_rating = w.fargo_rating,
                            fargo_last_updated = w.fargo_last_updated
                        FROM wpa_fargo w
                        WHERE r.ranking_system = :target
                          AND r.fargo_rating IS NULL
                          AND TRIM(REGEXP_REPLACE(REPLACE(r.player_name, ',', ' '), '\\s+', ' ', 'g')) = w.norm_name
                    """), {"target": target})
                    total_updated += result.rowcount
            conn.commit()
        if total_updated:
            logger.info("Copied Fargo from WPA_Men to %d target systems: %d rows updated", len(targets), total_updated)
        return total_updated

    def get_latest_rankings(self, system: str) -> List[Dict]:
        """Get most recent rankings for a system"""
        with self.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT player_name, rank, points, country, snapshot_date
                FROM rankings
                WHERE ranking_system = :system
                AND snapshot_date = (
                    SELECT MAX(snapshot_date) 
                    FROM rankings 
                    WHERE ranking_system = :system
                )
                ORDER BY position ASC NULLS LAST, rank ASC, id ASC
            """), {'system': system})
            
            return [
                {
                    'name': r[0],
                    'rank': r[1],
                    'points': r[2],
                    'country': r[3],
                    'date': str(r[4])
                }
                for r in result.fetchall()
            ]
    
    def get_ranking_history(self, player_name: str, association: str) -> List[Dict]:
        """Get ranking history for a player in a specific association"""
        with self.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT snapshot_date, rank, points
                FROM rankings
                WHERE player_name = :name
                  AND UPPER(ranking_system) = UPPER(:system)
                ORDER BY snapshot_date DESC
            """), {'name': player_name, 'system': association})
            
            return [
                {
                    'date': str(r[0]),
                    'rank': r[1],
                    'points': r[2]
                }
                for r in result.fetchall()
            ]

    def _association_table_for_system(self, system: str) -> Optional[str]:
        """Map legacy ranking_system code to dedicated association table name."""
        if not system:
            return None
        if system == "WPBA_Women" or system.startswith("WPBA_Women_"):
            return "wpba_rankings"
        if system == "WPA_Men" or system.startswith("WPA_Men_"):
            return "wpa_men_rankings"
        if system == "WPA_Women" or system.startswith("WPA_Women_"):
            return "wpa_women_rankings"
        if system == "WPA_Heyball_Men" or system.startswith("WPA_Heyball_Men_"):
            return "heyball_men_rankings"
        if system == "WPA_Heyball_Women" or system.startswith("WPA_Heyball_Women_"):
            return "heyball_women_rankings"
        if system == "WPA_Artistic" or system.startswith("WPA_Artistic_"):
            return "artistic_rankings"
        if system in ("FARGO_GLOBAL", "FARGO", "fargo_global"):
            return "fargo_rankings"
        return None

    def _resolve_physical_rankings_read(self, conn, system: str) -> Tuple[str, str]:
        """Prefer association table reads when populated; else legacy `rankings`."""
        assoc = self._association_table_for_system(system)
        default: Tuple[str, str] = ("rankings", "ranking_system")
        if not assoc or assoc not in self._ASSOCIATION_PHYSICAL_TABLES:
            return default
        exists = conn.execute(
            text(
                """
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = :t
                """
            ),
            {"t": assoc},
        ).fetchone()
        if not exists:
            return default
        has = conn.execute(
            text(f"SELECT 1 FROM {assoc} WHERE ranking_variant = :s LIMIT 1"),
            {"s": system},
        ).fetchone()
        if has:
            return assoc, "ranking_variant"
        return default

    def _mirror_rankings_to_association_table(self, system: str, snapshot_date: date) -> None:
        """Copy snapshot rows from `rankings` into the association-specific physical table."""
        tbl = self._association_table_for_system(system)
        if not tbl or tbl not in self._ASSOCIATION_PHYSICAL_TABLES:
            return
        try:
            with self.engine.begin() as conn:
                conn.execute(
                    text(f"DELETE FROM {tbl} WHERE ranking_variant = :s AND snapshot_date = :d"),
                    {"s": system, "d": snapshot_date},
                )
                conn.execute(
                    text(
                        f"""
                INSERT INTO {tbl} (
                    player_name, ranking_variant, rank, points, country, license_number,
                    stops_played, snapshot_date, source_data, position, fargo_rating, alfa_rating, fargo_robustness
                )
                SELECT
                    player_name, ranking_system, rank, points, country, license_number,
                    stops_played, snapshot_date, source_data, position, fargo_rating, alfa_rating, fargo_robustness
                FROM rankings
                WHERE ranking_system = :s AND snapshot_date = :d
                        """
                    ),
                    {"s": system, "d": snapshot_date},
                )
        except Exception as exc:
            logger.warning("Association table mirror failed for %s: %s", system, exc)

    def refresh_fargo_rankings_table(self, snapshot_date: Optional[date] = None) -> int:
        """Populate `fargo_rankings` from `players` Fargo scores (global leaderboard snapshot)."""
        snapshot_date = snapshot_date or date.today()
        tbl = "fargo_rankings"
        if tbl not in self._ASSOCIATION_PHYSICAL_TABLES:
            return 0
        try:
            with self.engine.begin() as conn:
                exists = conn.execute(
                    text(
                        """
                        SELECT 1 FROM information_schema.tables
                        WHERE table_schema = 'public' AND table_name = 'fargo_rankings'
                        """
                    ),
                ).fetchone()
                if not exists:
                    return 0
                has_score = conn.execute(
                    text(
                        """
                        SELECT 1 FROM information_schema.columns
                        WHERE table_schema = 'public' AND table_name = 'players'
                          AND column_name = 'fargo_score'
                        LIMIT 1
                        """
                    ),
                ).fetchone()
                if not has_score:
                    return 0
                conn.execute(
                    text("DELETE FROM fargo_rankings WHERE snapshot_date = :d"),
                    {"d": snapshot_date},
                )
                result = conn.execute(
                    text(
                        """
                INSERT INTO fargo_rankings (
                    player_name, ranking_variant, rank, points, country, license_number,
                    stops_played, snapshot_date, source_data, position, fargo_rating, alfa_rating, fargo_robustness
                )
                SELECT
                    player_name,
                    'FARGO_GLOBAL' AS ranking_variant,
                    ROW_NUMBER() OVER (ORDER BY fargo_score DESC NULLS LAST) AS rank,
                    COALESCE(fargo_score, 0)::double precision AS points,
                    country,
                    license_number,
                    NULL::integer AS stops_played,
                    :snap AS snapshot_date,
                    '{}'::jsonb AS source_data,
                    ROW_NUMBER() OVER (ORDER BY fargo_score DESC NULLS LAST) AS position,
                    fargo_score::double precision AS fargo_rating,
                    NULL::double precision AS alfa_rating,
                    fargo_robustness::integer AS fargo_robustness
                FROM (
                    SELECT DISTINCT ON (LOWER(TRIM(COALESCE(first_name, '') || ' ' || COALESCE(last_name, ''))))
                        TRIM(COALESCE(first_name, '') || ' ' || COALESCE(last_name, '')) AS player_name,
                        nationality AS country,
                        license_number,
                        fargo_score,
                        fargo_robustness
                    FROM players
                    WHERE TRIM(COALESCE(first_name, '') || ' ' || COALESCE(last_name, '')) != ''
                      AND fargo_score IS NOT NULL
                    ORDER BY LOWER(TRIM(COALESCE(first_name, '') || ' ' || COALESCE(last_name, ''))),
                             fargo_score DESC NULLS LAST
                ) deduped
                        """
                    ),
                    {"snap": snapshot_date},
                )
                return int(result.rowcount or 0)
        except Exception as exc:
            logger.warning("refresh_fargo_rankings_table failed: %s", exc)
            return 0
    
    def get_rankings_paginated(
        self,
        system: str,
        limit: int = 100,
        offset: int = 0,
        search: Optional[str] = None,
    ) -> Dict:
        """Get paginated rankings for a system with proper database-level pagination.

        Optional ``search`` filters rows by case-insensitive substring match on player_name.
        """
        with self.engine.connect() as conn:
            tbl, sys_col = self._resolve_physical_rankings_read(conn, system)
            query_system = system
            # For WPA systems, prioritize snapshots with detailed event data over newer summary snapshots
            target_date = None
            if system == "WPA_Men":
                # Find the most recent snapshot with detailed event data (8-ball columns)
                detailed_snapshot = conn.execute(text(f"""
                    SELECT r.snapshot_date
                    FROM {tbl} r
                    WHERE r.{sys_col} = :system
                    AND r.source_data IS NOT NULL AND r.source_data != '{{}}'::jsonb
                    AND EXISTS (
                        SELECT 1 FROM jsonb_object_keys(r.source_data) k
                        WHERE k::text LIKE '%8%' AND k::text LIKE '%ball%'
                    )
                    ORDER BY r.snapshot_date DESC
                    LIMIT 1
                """), {"system": system}).fetchone()
                target_date = detailed_snapshot[0] if detailed_snapshot else None
            elif system in ("WPA_Women", "WPA_Heyball_Men", "WPA_Heyball_Women"):
                # Find the most recent snapshot with any source_data
                detailed_snapshot = conn.execute(text(f"""
                    SELECT r.snapshot_date
                    FROM {tbl} r
                    WHERE r.{sys_col} = :system
                    AND r.source_data IS NOT NULL AND r.source_data != '{{}}'::jsonb
                    ORDER BY r.snapshot_date DESC
                    LIMIT 1
                """), {"system": system}).fetchone()
                target_date = detailed_snapshot[0] if detailed_snapshot else None
            elif system.startswith("WPBA_Women_"):
                # Per-tournament sub-systems: the split writes the current PDF snapshot for every
                # active event, so the single source of truth is the LATEST populated snapshot.
                # Pick the most recent snapshot that has any non-zero rows (skips fully-empty
                # placeholder snapshots). Do NOT rank by row count — an older, more-populated
                # snapshot would otherwise mask the fresh scrape and show stale event data.
                detailed_snapshot = conn.execute(text(f"""
                    SELECT snapshot_date
                    FROM (
                        SELECT
                            snapshot_date,
                            SUM(CASE WHEN points > 0 THEN 1 ELSE 0 END) AS nonzero_rows
                        FROM {tbl}
                        WHERE {sys_col} = :system
                        GROUP BY snapshot_date
                    ) s
                    WHERE nonzero_rows >= 1
                    ORDER BY snapshot_date DESC
                    LIMIT 1
                """), {"system": system}).fetchone()
                target_date = detailed_snapshot[0] if detailed_snapshot else None
            if target_date:
                # Use selected snapshot (detailed/metadata-rich) for this system.
                snapshot_condition = "AND snapshot_date = :target_date"
                params = {'system': query_system, 'limit': limit, 'offset': offset, 'target_date': target_date}
            else:
                # Use latest snapshot for selected system
                snapshot_condition = f"AND snapshot_date = (SELECT MAX(snapshot_date) FROM {tbl} WHERE {sys_col} = :system)"
                params = {'system': query_system, 'limit': limit, 'offset': offset}

            search_term = (search or "").strip()
            search_condition = ""
            row_search_condition = ""
            if search_term:
                params["search"] = f"%{search_term}%"
                search_condition = "AND player_name ILIKE :search"
                row_search_condition = "AND r.player_name ILIKE :search"

            # Total/count must match the same snapshot condition used for returned rows.
            count_result = conn.execute(
                text(
                    f"""
                    SELECT COUNT(*) as total
                    FROM {tbl}
                    WHERE {sys_col} = :system
                    {snapshot_condition}
                    {search_condition}
                    """
                ),
                {k: v for k, v in params.items() if k in ("system", "target_date", "search")},
            )
            total = int(count_result.fetchone()[0] or 0)

            # Get paginated results (include id for edit, source_data for full source columns in UI)
            # players table uses first_name+last_name (tournament schema) or name (minimal schema)
            result = conn.execute(text(f"""
                WITH players_by_name AS (
                    SELECT
                        LOWER(TRIM(COALESCE(first_name, '') || ' ' || COALESCE(last_name, ''))) AS full_name,
                        MAX(
                            CASE
                                WHEN TRIM(COALESCE(nationality, '')) ~ '^[A-Z]{{2,5}}$'
                                    THEN TRIM(nationality)
                                ELSE NULL
                            END
                        ) AS nationality,
                        MAX(license_number) AS license_number,
                        MAX(fargo_score)::DOUBLE PRECISION AS fargo_score,
                        NULL::DOUBLE PRECISION AS alfa_rating,
                        NULL::INTEGER AS fargo_robustness,
                        NULL::DOUBLE PRECISION AS est_rating,
                        NULL::DOUBLE PRECISION AS est_rating_confidence,
                        NULL::INTEGER AS est_rating_robustness,
                        NULL::VARCHAR AS est_rating_trend
                    FROM players
                    WHERE TRIM(COALESCE(first_name, '') || ' ' || COALESCE(last_name, '')) != ''
                    GROUP BY LOWER(TRIM(COALESCE(first_name, '') || ' ' || COALESCE(last_name, '')))
                )
                SELECT
                    r.id,
                    r.player_name as name,
                    r.rank,
                    r.points,
                    COALESCE(
                        p_direct.nationality,
                        p_swapped.nationality,
                        CASE
                            WHEN TRIM(COALESCE(r.country, '')) ~ '^[A-Z]{{2,5}}$'
                                THEN TRIM(r.country)
                            ELSE NULL
                        END
                    ) as country,
                    COALESCE(
                        p_direct.license_number,
                        p_swapped.license_number,
                        CASE
                            WHEN TRIM(COALESCE(r.license_number, '')) ~ '^[A-Z]{{2,5}}\\s*-\\s*\\d{{2,5}}$'
                                THEN TRIM(r.license_number)
                            ELSE NULL
                        END
                    ) as license_number,
                    COALESCE(p_direct.fargo_score, p_swapped.fargo_score, r.fargo_rating) as fargo_rating,
                    r.stops_played,
                    COALESCE(p_direct.alfa_rating, p_swapped.alfa_rating, r.alfa_rating) as alfa_rating,
                    r.snapshot_date as date,
                    r.{sys_col} as ranking_system,
                    r.source_data,
                    COALESCE(p_direct.fargo_robustness, p_swapped.fargo_robustness, r.fargo_robustness) as fargo_robustness,
                    COALESCE(p_direct.est_rating, p_swapped.est_rating) as est_rating,
                    COALESCE(p_direct.est_rating_confidence, p_swapped.est_rating_confidence) as est_rating_confidence,
                    COALESCE(p_direct.est_rating_robustness, p_swapped.est_rating_robustness) as est_rating_robustness,
                    COALESCE(p_direct.est_rating_trend, p_swapped.est_rating_trend) as est_rating_trend
                FROM {tbl} r
                LEFT JOIN players_by_name p_direct
                  ON p_direct.full_name = LOWER(
                        TRIM(
                            REGEXP_REPLACE(
                                CASE
                                    WHEN POSITION(',' IN r.player_name) > 0 THEN
                                        TRIM(SPLIT_PART(r.player_name, ',', 2)) || ' ' || TRIM(SPLIT_PART(r.player_name, ',', 1))
                                    ELSE r.player_name
                                END,
                                '\\s+[A-Z]{{2,5}}\\s*-\\s*\\d{{2,5}}\\s*$',
                                ''
                            )
                        )
                    )
                LEFT JOIN players_by_name p_swapped
                  ON p_swapped.full_name = LOWER(
                        TRIM(
                            REGEXP_REPLACE(
                                REGEXP_REPLACE(
                                    CASE
                                        WHEN POSITION(',' IN r.player_name) > 0 THEN
                                            TRIM(SPLIT_PART(r.player_name, ',', 2)) || ' ' || TRIM(SPLIT_PART(r.player_name, ',', 1))
                                        ELSE r.player_name
                                    END,
                                    '\\s+[A-Z]{{2,5}}\\s*-\\s*\\d{{2,5}}\\s*$',
                                    ''
                                ),
                                '^(.*)\\s+([^\\s]+)$',
                                '\\2 \\1'
                            )
                        )
                    )
                WHERE r.{sys_col} = :system
                {snapshot_condition}
                {row_search_condition}
                ORDER BY r.position ASC NULLS LAST, r.rank ASC, r.id ASC
                LIMIT :limit OFFSET :offset
            """), params)

            rows = result.fetchall()
            rankings = []
            is_wpa_men = system == "WPA_Men"
            is_wpa_women = system == "WPA_Women"
            is_heyball_men = system == "WPA_Heyball_Men"
            is_heyball_women = system == "WPA_Heyball_Women"
            is_artistic = system == "WPA_Artistic"
            is_wpba_women = system == "WPBA_Women"
            is_overall = is_wpa_men or is_wpa_women or is_heyball_men or is_heyball_women or is_artistic or is_wpba_women

            for r in rows:
                base = {
                    'id': r[0],
                    'name': r[1],
                    'rank': r[2],
                    'points': r[3],
                    'country': r[4],
                    'license_number': r[5],
                    'fargo_rating': r[6],
                    'stops_played': r[7],
                    'alfa_rating': r[8],
                    'date': str(r[9]),
                    'ranking_system': r[10],
                    'fargo_robustness': r[12],
                    'est_rating': r[13],
                    'est_rating_confidence': r[14],
                    'est_rating_robustness': r[15],
                    'est_rating_trend': r[16] if len(r) > 16 else None,
                }
                sd = r[11]
                if isinstance(sd, str):
                    try:
                        sd = json.loads(sd) if sd else None
                    except (TypeError, ValueError):
                        sd = None
                # Non-overall systems: merge source_data columns into the API response
                if sd and not is_overall:
                    for k, v in sd.items():
                        if k not in base:
                            base[k] = v
                # Overall systems: merge source_data for WPA_Men, WPA_Women, Artistic only.
                # WPBA_Women and Heyball overall: tournament columns are on their own buttons.
                if is_overall and sd:
                    if not (is_heyball_men or is_heyball_women or is_wpba_women):
                        for k, v in sd.items():
                            if k not in base:
                                base[k] = v
                        if is_artistic:
                            for col_key, _sys, _label in self.WPA_ARTISTIC_COLUMN_MAPPING:
                                val = sd.get(col_key)
                                if val is not None:
                                    base[col_key] = val
                base = self._normalize_display_row(base)
                rankings.append(base)

            return {
                'total': total,
                'rankings': rankings,
                'limit': limit,
                'offset': offset,
                'count': len(rankings)
            }

    # Systems shown on Leaderboard (same tours as Rankings page). LOCAL = director-run tournaments.
    LEADERBOARD_SYSTEMS = ("WPBA_Women", "WPA_Women", "WPA_Men", "WPA_Heyball_Men", "WPA_Heyball_Women", "WPA_Artistic", "LOCAL")

    @staticmethod
    def _ranking_system_to_association(ranking_system: Optional[str]) -> Optional[str]:
        """Map a ranking_system to its tournament_history.association (None = all/combined)."""
        if not ranking_system:
            return None
        if ranking_system.startswith("WPBA"):
            return "WPBA"
        if ranking_system.startswith("WPA_Heyball"):
            return "HEYBALL"
        if ranking_system.startswith("WPA"):
            return "WPA"
        return None

    def _tournament_stats_by_player(self, association: Optional[str] = None) -> Dict[str, Dict[str, int]]:
        """Per-player completed-tournament stats from ``tournament_results`` (single source of truth).

        Returns ``{canonical_name: {tournaments_played, first/second/third_place_finishes}}``.

        Counts only real completed tournaments — excludes snapshot-pseudo rows
        (``rankings_snapshot*`` / ``"... Rankings (date)"``) which are ranking snapshots, not events.
        ``tournaments_played`` counts distinct tournaments where the player scored (>0 points),
        since ``tournament_results`` only stores scoring participants.

        When ``association`` is given, restricts to that association. WPBA history is the canonical
        ``wpba_evt_*`` set (docs/WPBA_TOURNAMENT_SSOT.md); WPA/HEYBALL history is the digitalpool
        archive event set with snapshot-pseudo rows removed (docs/WPA_TOURNAMENT_SSOT.md). The
        snapshot-pseudo exclusion above is belt-and-suspenders: those rows are also deleted from
        the table, but the filter keeps stats correct even if a stray one reappears.
        """
        where = [
            "th.status = 'completed'",
            "th.tournament_id NOT LIKE 'rankings_snapshot%'",
            "th.name NOT ILIKE '% Rankings (%'",
        ]
        params: Dict[str, Any] = {}
        if association:
            where.append("th.association = :assoc")
            params["assoc"] = association
        sql = f"""
            SELECT tr.player_name,
                   COUNT(DISTINCT tr.tournament_id) FILTER (WHERE tr.points > 0) AS tp,
                   COUNT(*) FILTER (WHERE tr.placement = 1) AS f1,
                   COUNT(*) FILTER (WHERE tr.placement = 2) AS f2,
                   COUNT(*) FILTER (WHERE tr.placement = 3) AS f3
            FROM tournament_results tr
            JOIN tournament_history th ON th.tournament_id = tr.tournament_id
            WHERE {' AND '.join(where)}
            GROUP BY tr.player_name
        """
        out: Dict[str, Dict[str, int]] = {}
        with self.engine.connect() as conn:
            for r in conn.execute(text(sql), params).fetchall():
                canon = self._canonical_player_name(r[0] or "").lower()
                if not canon:
                    continue
                agg = out.setdefault(
                    canon,
                    {"tournaments_played": 0, "first_place_finishes": 0,
                     "second_place_finishes": 0, "third_place_finishes": 0},
                )
                agg["tournaments_played"] += int(r[1] or 0)
                agg["first_place_finishes"] += int(r[2] or 0)
                agg["second_place_finishes"] += int(r[3] or 0)
                agg["third_place_finishes"] += int(r[4] or 0)
        return out

    def get_leaderboard_from_rankings(self, limit: Optional[int] = None, ranking_system: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get leaderboard data from rankings table (SINGLE SOURCE OF TRUTH for leaderboard/menu points).
        Merges latest snapshots from WPBA_Women, WPA_Women, WPA_Men, WPA_Heyball_Men, WPA_Heyball_Women, WPA_Artistic, LOCAL.
        Dedupes by license_number or normalized name; keeps best rank per player.
        Joins with players for avatar_url, hall_of_fame, hot_streak_count.
        Returns list in CurrentRankingResponse shape for Leaderboard UI.

        Args:
            limit: Maximum number of results to return
            ranking_system: If provided, filter to only this system (e.g. 'WPBA_Women'). 
                          When filtering by system, points are NOT summed across systems.

        NOTE: This is the ONLY source for leaderboard and menu points/rank data.
        DO NOT use players.total_points/players.current_rank or v_current_rankings for leaderboard displays.
        """
        with self.engine.connect() as conn:
            # If filtering by a specific system, use only that system
            systems_to_query = [ranking_system] if ranking_system else list(self.LEADERBOARD_SYSTEMS)
            placeholders = ", ".join(f"'{s}'" for s in systems_to_query)
            result = conn.execute(text(f"""
                WITH latest_per_system AS (
                    SELECT ranking_system, MAX(snapshot_date) AS snapshot_date
                    FROM rankings
                    WHERE ranking_system IN ({placeholders})
                    GROUP BY ranking_system
                ),
                combined AS (
                    SELECT
                        r.player_name,
                        r.rank,
                        r.points,
                        COALESCE(r.stops_played, 0)::int AS stops_played,
                        r.license_number,
                        r.fargo_rating::int AS fargo_rating,
                        r.country,
                        r.ranking_system
                    FROM rankings r
                    JOIN latest_per_system l
                      ON l.ranking_system = r.ranking_system AND l.snapshot_date = r.snapshot_date
                    WHERE r.ranking_system IN ({placeholders})
                ),
                players_extra AS (
                    SELECT
                        LOWER(TRIM(first_name || ' ' || last_name)) AS full_name,
                        LOWER(TRIM(last_name || ', ' || first_name)) AS alt_name,
                        array_agg(DISTINCT LOWER(TRIM(COALESCE(license_number, '')))) AS lic_array,
                        (array_agg(player_id ORDER BY player_id))[1] AS player_id,
                        (array_agg(avatar_url ORDER BY player_id))[1] AS avatar_url,
                        bool_or(COALESCE(hall_of_fame::boolean, false)) AS hall_of_fame,
                        MAX(COALESCE(hot_streak_count, 0))::int AS hot_streak_count
                    FROM players
                    WHERE (membership_status = 'active' OR membership_status = 'lifetime')
                      AND TRIM(COALESCE(first_name, '') || ' ' || COALESCE(last_name, '')) != ''
                    GROUP BY full_name, alt_name
                )
                SELECT
                    c.player_name,
                    c.rank,
                    c.points,
                    c.stops_played,
                    c.license_number,
                    c.fargo_rating,
                    c.country,
                    p.player_id,
                    p.avatar_url,
                    p.hall_of_fame,
                    p.hot_streak_count
                FROM combined c
                LEFT JOIN players_extra p
                  ON (
                    (TRIM(COALESCE(c.license_number, '')) != '' AND LOWER(TRIM(c.license_number)) = ANY(p.lic_array))
                    OR (TRIM(COALESCE(c.license_number, '')) = '' AND (
                        LOWER(TRIM(
                            CASE WHEN POSITION(',' IN c.player_name) > 0
                                THEN TRIM(SPLIT_PART(c.player_name, ',', 2)) || ' ' || TRIM(SPLIT_PART(c.player_name, ',', 1))
                                ELSE c.player_name
                            END
                        )) IN (p.full_name, p.alt_name)
                    ))
                  )
                ORDER BY c.rank ASC NULLS LAST, c.points DESC NULLS LAST
            """))
            rows = result.fetchall()

        # Merge: one row per player (by license or name). SUM points across systems (e.g. WPBA + LOCAL).
        seen_by_license: Dict[str, Dict] = {}
        seen_by_name: Dict[str, Dict] = {}
        for r in rows:
            player_name, rank, points, stops_played, license_number, fargo_rating, country = r[:7]
            player_id, avatar_url, hall_of_fame, hot_streak_count = r[7:11]
            lic = (license_number or "").strip()
            canonical = self._canonical_player_name(player_name)
            name_key = canonical.lower() if canonical else ""

            row_dict = {
                "player_name": player_name,
                "rank": rank,
                "points": float(points or 0),
                "stops_played": int(stops_played or 0),
                "license_number": lic or None,
                "fargo_rating": int(fargo_rating) if fargo_rating is not None else None,
                "country": (country or "").strip() or None,
                "player_id": str(player_id) if player_id is not None else None,
                "avatar_url": str(avatar_url) if avatar_url is not None else None,
                "hall_of_fame": bool(hall_of_fame),
                "hot_streak_count": int(hot_streak_count or 0),
            }

            def _merge_into(target: Dict[str, Dict], key: str):
                ex = target.get(key)
                if not ex:
                    target[key] = row_dict.copy()
                    return
                # When filtering by a single system, don't sum points - just keep the first entry
                # When querying all systems, sum points across systems (no data loss)
                if ranking_system:
                    # Single system: keep first entry (should only be one anyway)
                    target[key] = ex
                else:
                    # Multiple systems: sum points across systems
                    combined_pts = (ex.get("points") or 0) + (row_dict.get("points") or 0)
                    # Keep best (lowest) rank from primary systems
                    ex_rank = ex.get("rank") or 999999
                    new_rank = row_dict.get("rank") or 999999
                    best_rank = min(ex_rank, new_rank) if (ex_rank < 999999 or new_rank < 999999) else ex_rank
                    target[key] = {
                        **ex,
                        "points": combined_pts,
                        "rank": best_rank if best_rank < 999999 else ex.get("rank"),
                        "stops_played": max(ex.get("stops_played") or 0, row_dict.get("stops_played") or 0),
                        "player_id": ex.get("player_id") or row_dict.get("player_id"),
                        "avatar_url": ex.get("avatar_url") or row_dict.get("avatar_url"),
                        "hall_of_fame": ex.get("hall_of_fame") or row_dict.get("hall_of_fame"),
                        "hot_streak_count": max(ex.get("hot_streak_count") or 0, row_dict.get("hot_streak_count") or 0),
                    }

            if lic:
                _merge_into(seen_by_license, lic)
            elif name_key:
                _merge_into(seen_by_name, name_key)

        # Merge: license entries first, then name-only (skip if already in license)
        merged: List[Dict] = []
        seen_names = set()
        for d in seen_by_license.values():
            merged.append(d)
            cn = self._canonical_player_name(d["player_name"]).lower()
            if cn:
                seen_names.add(cn)
        for d in seen_by_name.values():
            cn = self._canonical_player_name(d["player_name"]).lower()
            if cn and cn not in seen_names:
                merged.append(d)
                seen_names.add(cn)

        # Sort by total points desc, then rank asc
        merged.sort(key=lambda x: (-(x.get("points") or 0), (x.get("rank") or 999999)))

        # Podium finishes (1st/2nd/3rd) and tournaments-played come from tournament_results
        # (the cleaned single source of truth — snapshot-pseudo rows excluded). Enabled per
        # association that has a canonical, pseudo-free event set:
        #   - WPBA: wpba_evt_* (PDF per-event). The PDF only details results for full-schedule
        #     players, so finishes cover the top ~18; tournaments-played uses the authoritative
        #     PDF stops_played column below (complete for all players). See docs/WPBA_TOURNAMENT_SSOT.md.
        #   - WPA / HEYBALL: digitalpool archive events. No stops column, so tournaments-played is
        #     derived from distinct completed events with results. See docs/WPA_TOURNAMENT_SSOT.md.
        # The combined view (no system) stays 0 to avoid mixing associations.
        _stat_assoc = self._ranking_system_to_association(ranking_system)
        _STATS_ASSOCS = {"WPBA", "WPA", "HEYBALL"}
        tourney_stats = self._tournament_stats_by_player(_stat_assoc) if _stat_assoc in _STATS_ASSOCS else {}

        # Assign global rank and convert to CurrentRankingResponse shape
        out: List[Dict[str, Any]] = []
        for i, d in enumerate(merged):
            if limit and len(out) >= limit:
                break
            first_name, last_name = self._split_player_name(d["player_name"])
            pid = d.get("player_id")
            if not pid:
                pid = self._generate_player_id_from_name(d["player_name"], d.get("license_number"))
            _lic = d.get("license_number")
            _av = d.get("avatar_url")
            _nat = d.get("country")
            _pts = d.get("points", 0)
            _fargo = d.get("fargo_rating")
            _stats = tourney_stats.get(self._canonical_player_name(d["player_name"]).lower(), {})
            # WPBA has an authoritative PDF stops_played column (complete for all players);
            # WPA/HEYBALL do not, so derive tournaments-played from distinct completed events.
            if _stat_assoc == "WPBA":
                _played = int(d.get("stops_played") or 0)
            else:
                _played = int(_stats.get("tournaments_played", 0))
            out.append({
                "player_id": str(pid),
                "first_name": first_name,
                "last_name": last_name,
                "nickname": None,
                "license_number": str(_lic) if _lic is not None else None,
                "avatar_url": str(_av) if _av is not None else None,
                "total_points": float(_pts) if _pts is not None else 0.0,
                "current_rank": i + 1,
                "total_tournaments_played": _played,
                "hall_of_fame": bool(d.get("hall_of_fame", False)),
                "hot_streak_count": int(d.get("hot_streak_count") or 0),
                "fargo_score": int(_fargo) if _fargo is not None else None,
                "nationality": str(_nat) if _nat is not None else None,
                "membership_status": "active",
                "win_percentage_matches": None,
                "win_percentage_games": None,
                "first_place_finishes": int(_stats.get("first_place_finishes", 0)),
                "second_place_finishes": int(_stats.get("second_place_finishes", 0)),
                "third_place_finishes": int(_stats.get("third_place_finishes", 0)),
            })
        return out

    def get_hot_streak_players(
        self,
        lookback: int = 3,
        min_tournaments: int = 3,
        limit: Optional[int] = None,
        association: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get players who jumped the most within the past N tournaments.
        Includes players with overall improvement across the window
        (newest placement better than oldest), even if an intermediate
        tournament placement dips.
        Placements returned oldest-first for chart (left=oldest, right=newest).
        Resilience (1yr / career) uses all real events in-window for that player
        in the same association (calendar year vs full history).
        Filter by association if provided.
        """
        with self.engine.connect() as conn:
            rows = self._fetch_hot_streak_event_rows(conn, association=association)

        # Group by player_name, take last N placements per player (most recent first)
        by_player: Dict[str, List[Tuple[int, date, int]]] = {}
        for player_name, placement, tdate, _tournament_name, _fargo_at_scrape, field_size in rows:
            name = (player_name or "").strip()
            if not name:
                continue
            if name not in by_player:
                by_player[name] = []
            if len(by_player[name]) < lookback:
                by_player[name].append((int(placement), tdate, int(field_size or 0)))

        # Overall improvement across window: newest must be better than oldest.
        hot_players: List[Dict[str, Any]] = []
        for player_name, placements in by_player.items():
            if len(placements) < min_tournaments:
                continue
            placements_oldest_first = [p[0] for p in reversed(placements)]
            field_sizes_oldest_first = [p[2] for p in reversed(placements)]
            oldest_placement = placements_oldest_first[0]
            newest_placement = placements_oldest_first[-1]
            if newest_placement >= oldest_placement:
                continue
            jump = oldest_placement - newest_placement
            hot_players.append({
                "player_name": player_name,
                "last_placements": placements_oldest_first,
                "recent_tournaments_count": len(placements),
                "trend_score": float(jump),
            })

        hot_players.sort(key=lambda x: -x["trend_score"])
        if limit:
            hot_players = hot_players[:limit]

        unique_names = list({hp["player_name"] for hp in hot_players})
        cutoff_1yr = date.today() - timedelta(days=365)
        hist_by_player: Dict[str, List[Tuple[date, int, int]]] = {}
        if unique_names:
            with self.engine.connect() as conn:
                hist_by_player = self._fetch_hot_streak_placement_history_for_players(
                    conn, unique_names, association
                )
        for hp in hot_players:
            rows_asc = hist_by_player.get(hp["player_name"], [])
            placements_career = [r[1] for r in rows_asc]
            field_career = [r[2] for r in rows_asc]
            rows_1yr = [r for r in rows_asc if r[0] >= cutoff_1yr]
            placements_1yr = [r[1] for r in rows_1yr]
            field_1yr = [r[2] for r in rows_1yr]
            hp["resilience_1yr"] = self._compute_resilience_score_optional(placements_1yr, field_1yr)
            hp["resilience_career"] = self._compute_resilience_score_optional(
                placements_career, field_career
            )

        out: List[Dict[str, Any]] = []
        with self.engine.connect() as conn:
            for i, row in enumerate(hot_players):
                player_name = row["player_name"]
                canonical = self._canonical_player_name(player_name)
                pid, first_name, last_name = self._resolve_player_id(
                    conn, player_name, None, canonical, system=None
                )
                if not first_name and not last_name:
                    first_name, last_name = self._split_player_name(player_name)
                if not pid:
                    pid = self._generate_player_id_from_name(player_name, None)
                avatar_url = None
                fargo_score = None
                if pid:
                    try:
                        r = conn.execute(
                            text("SELECT avatar_url, fargo_rating FROM players WHERE player_id = :pid"),
                            {"pid": pid},
                        ).fetchone()
                        if r:
                            avatar_url = str(r[0]) if r[0] is not None else None
                            fargo_score = int(r[1]) if r[1] is not None else None
                    except Exception:
                        pass

                out.append({
                    "player_id": str(pid),
                    "first_name": first_name or "Unknown",
                    "last_name": last_name or "Unknown",
                    "nickname": None,
                    "license_number": None,
                    "avatar_url": avatar_url,
                    "total_points": 0.0,
                    "current_rank": i + 1,
                    "total_tournaments_played": row["recent_tournaments_count"],
                    "hall_of_fame": False,
                    "hot_streak_count": 0,
                    "fargo_score": fargo_score,
                    "resilience_1yr": row.get("resilience_1yr"),
                    "resilience_career": row.get("resilience_career"),
                    "fargo_history": [],
                    "fargo_trend_score": 0.0,
                    "nationality": None,
                    "membership_status": "active",
                    "win_percentage_matches": None,
                    "win_percentage_games": None,
                    "first_place_finishes": 0,
                    "second_place_finishes": 0,
                    "third_place_finishes": 0,
                    "last_placements": row["last_placements"],
                    "trend_score": row["trend_score"],
                    "recent_tournaments_count": row["recent_tournaments_count"],
                })
        return out

    def _compute_resilience_score_optional(
        self, placements: List[int], field_sizes: List[int]
    ) -> Optional[float]:
        """Resilience for a window; requires at least two tournaments."""
        if len(placements) < 2:
            return None
        return self._compute_resilience_score(placements, field_sizes)

    def _compute_resilience_score(self, placements: List[int], field_sizes: List[int]) -> float:
        """
        Resilience indicator (0-100) from tournament ranking behavior:
        - bounce-back: latest placement vs worst in the window
        - consistency across events (normalized placement stability)
        - finish strength in latest event
        - overall normalized improvement (first vs last)
        """
        if not placements:
            return 0.0
        if len(placements) < 2:
            return 0.0

        n = len(placements)
        perf: List[float] = []
        max_place = max(placements) if placements else 1
        denom_fallback = max(1.0, float(max_place - 1))
        for i, place in enumerate(placements):
            fs = field_sizes[i] if i < len(field_sizes) else 0
            if fs and fs > 1:
                score = 1.0 - (float(place - 1) / float(fs - 1))
            else:
                score = 1.0 - (float(place - 1) / denom_fallback)
            perf.append(max(0.0, min(1.0, score)))

        deltas = [abs(perf[i + 1] - perf[i]) for i in range(n - 1)]
        avg_delta = (sum(deltas) / len(deltas)) if deltas else 0.0
        consistency = max(0.0, min(1.0, 1.0 - avg_delta))

        worst_p = max(placements)
        best_p = min(placements)
        spread = float(worst_p - best_p)
        if spread <= 0:
            bounce_back = 1.0
        else:
            bounce_back = max(0.0, min(1.0, float(worst_p - placements[-1]) / spread))

        finish_strength = perf[-1]
        improvement_strength = max(0.0, perf[-1] - perf[0])
        score = 100.0 * (
            0.35 * bounce_back +
            0.25 * consistency +
            0.25 * finish_strength +
            0.15 * improvement_strength
        )
        return round(max(0.0, min(100.0, score)), 1)

    def _hot_streak_association_clauses(
        self, association: Optional[str],
    ) -> Tuple[str, Dict[str, Any]]:
        """SQL clauses and params for hot-streak association filtering.

        Maps UI tab values (e.g. ``WPA Women``) to stored
        ``tournament_history.association`` values (``WPA`` / ``WPBA``),
        then adds sub-category filters (player present in matching ranking
        system, tournament-name keyword for Heyball) where needed.
        """
        if not association or not association.strip():
            return "", {}

        assoc_lower = association.strip().lower()
        db_assoc = self._ASSOCIATION_DB_MAP.get(assoc_lower, association.strip())

        clause = " AND COALESCE(NULLIF(TRIM(th.association), ''), 'WPA') ILIKE :hs_assoc"
        params: Dict[str, Any] = {"hs_assoc": db_assoc}

        ranking_like = self._association_rankings_like(association)
        if ranking_like and assoc_lower != db_assoc.lower():
            clause += (
                " AND EXISTS ("
                "   SELECT 1 FROM rankings r"
                "   WHERE r.player_name = tr.player_name"
                "     AND r.ranking_system LIKE :hs_ranking_like"
                " )"
            )
            params["hs_ranking_like"] = ranking_like

        if "heyball" in assoc_lower:
            clause += " AND th.name ILIKE :hs_name_kw"
            params["hs_name_kw"] = "%heyball%"

        return clause, params

    def _fetch_hot_streak_placement_history_for_players(
        self,
        conn,
        player_names: List[str],
        association: Optional[str],
    ) -> Dict[str, List[Tuple[date, int, int]]]:
        """Per player: (event_date, placement, field_size), oldest-first."""
        if not player_names:
            return {}
        real_tournaments_filter = """
            AND (th.tournament_id IS NULL OR th.tournament_id NOT LIKE 'rankings_snapshot%')
            AND EXISTS (SELECT 1 FROM tournament_results WHERE tournament_results.tournament_id = th.tournament_id)
            AND (th.name IS NULL OR (
                th.name NOT LIKE '% Rankings (%'
                AND th.name NOT ILIKE '% News%'
                AND th.name NOT ILIKE '% Events'
                AND LOWER(TRIM(th.name)) NOT IN ('wpba events', 'latest wpa news', 'wpa news', 'wpba news')
            ))
        """
        query = """
            SELECT tr.player_name, th.date, tr.placement,
                   COUNT(*) OVER (PARTITION BY tr.tournament_id) AS field_size
            FROM tournament_results tr
            JOIN tournament_history th ON tr.tournament_id = th.tournament_id
            WHERE tr.placement IS NOT NULL AND tr.placement > 0
              AND th.date IS NOT NULL
              AND tr.player_name = ANY(:names)
        """ + real_tournaments_filter
        params: Dict[str, Any] = {"names": list(player_names)}
        assoc_clause, assoc_params = self._hot_streak_association_clauses(association)
        query += assoc_clause
        params.update(assoc_params)
        query += " ORDER BY tr.player_name, th.date ASC, th.tournament_id ASC, tr.id ASC"
        rows = conn.execute(text(query), params).fetchall()
        by_player: Dict[str, List[Tuple[date, int, int]]] = {}
        for player_name, tdate, placement, field_size in rows:
            name = (player_name or "").strip()
            if not name:
                continue
            if name not in by_player:
                by_player[name] = []
            by_player[name].append((tdate, int(placement), int(field_size or 0)))
        return by_player

    def _fetch_hot_streak_event_rows(
        self,
        conn,
        *,
        association: Optional[str] = None,
    ) -> List[Tuple[str, int, date, Optional[str], Optional[float], int]]:
        # Keep in sync with api/routes/tournament_history.py REAL_TOURNAMENTS_WHERE_TH.
        real_tournaments_filter = """
            AND (th.tournament_id IS NULL OR th.tournament_id NOT LIKE 'rankings_snapshot%')
            AND EXISTS (SELECT 1 FROM tournament_results WHERE tournament_results.tournament_id = th.tournament_id)
            AND (th.name IS NULL OR (
                th.name NOT LIKE '% Rankings (%'
                AND th.name NOT ILIKE '% News%'
                AND th.name NOT ILIKE '% Events'
                AND LOWER(TRIM(th.name)) NOT IN ('wpba events', 'latest wpa news', 'wpa news', 'wpba news')
            ))
        """
        query = """
            SELECT tr.player_name, tr.placement, th.date, th.name, tr.fargo_rating_at_scrape,
                   COUNT(*) OVER (PARTITION BY tr.tournament_id) AS field_size
            FROM tournament_results tr
            JOIN tournament_history th ON tr.tournament_id = th.tournament_id
            WHERE tr.placement IS NOT NULL AND tr.placement > 0
              AND th.date IS NOT NULL
        """ + real_tournaments_filter
        params: Dict[str, Any] = {}
        assoc_clause, assoc_params = self._hot_streak_association_clauses(association)
        query += assoc_clause
        params.update(assoc_params)
        query += " ORDER BY tr.player_name, th.date DESC, th.tournament_id DESC, tr.id DESC"
        return conn.execute(text(query), params).fetchall()

    def _association_rankings_like(self, association: Optional[str]) -> Optional[str]:
        assoc = (association or "").strip().lower()
        if assoc == "wpba":
            return "WPBA%"
        if assoc == "wpa women":
            return "WPA_Women%"
        if assoc == "wpa men":
            return "WPA_Men%"
        if assoc == "wpa heyball men":
            return "WPA_Heyball_Men%"
        if assoc == "wpa heyball women":
            return "WPA_Heyball_Women%"
        if assoc == "wpa artistic":
            return "WPA_Artistic%"
        return None

    def _resolve_fargo_for_event(
        self,
        conn,
        *,
        player_name: str,
        tournament_date: date,
        association: Optional[str],
        fargo_at_scrape: Optional[float],
    ) -> Optional[float]:
        if fargo_at_scrape is not None:
            try:
                return float(fargo_at_scrape)
            except (TypeError, ValueError):
                pass

        first_name, last_name = self._split_player_name(player_name)
        name_variants = [player_name.strip()]
        if first_name and last_name:
            name_variants.append(f"{last_name}, {first_name}")
        ranking_like = self._association_rankings_like(association)

        rankings_query = """
            SELECT fargo_rating
            FROM rankings
            WHERE fargo_rating IS NOT NULL
              AND player_name = ANY(:names)
              AND snapshot_date <= :snapshot_date
        """
        params: Dict[str, Any] = {
            "names": list(dict.fromkeys([n for n in name_variants if n])),
            "snapshot_date": tournament_date,
        }
        if ranking_like:
            rankings_query += " AND ranking_system LIKE :ranking_like"
            params["ranking_like"] = ranking_like
        rankings_query += " ORDER BY snapshot_date DESC, id DESC LIMIT 1"
        r = conn.execute(text(rankings_query), params).fetchone()
        if r and r[0] is not None:
            try:
                return float(r[0])
            except (TypeError, ValueError):
                pass

        history_query = """
            SELECT new_fargo_rating
            FROM fargo_rating_history
            WHERE new_fargo_rating IS NOT NULL
              AND player_name = ANY(:names)
              AND snapshot_date <= :snapshot_date
            ORDER BY snapshot_date DESC, id DESC
            LIMIT 1
        """
        h = conn.execute(text(history_query), params).fetchone()
        if h and h[0] is not None:
            try:
                return float(h[0])
            except (TypeError, ValueError):
                pass
        return None

    def get_fargo_hot_streak_players(
        self,
        lookback: int = 3,
        min_tournaments: int = 3,
        limit: Optional[int] = None,
        association: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get players whose Fargo improved across their last N Fargo ratings."""
        with self.engine.connect() as conn:
            ranking_like = self._association_rankings_like(association)
            names_query = """
                SELECT DISTINCT player_name
                FROM (
                    SELECT player_name
                    FROM rankings
                    WHERE fargo_rating IS NOT NULL
                      AND player_name IS NOT NULL
                      AND TRIM(player_name) <> ''
                    UNION
                    SELECT player_name
                    FROM fargo_rating_history
                    WHERE new_fargo_rating IS NOT NULL
                      AND player_name IS NOT NULL
                      AND TRIM(player_name) <> ''
                ) src
                WHERE 1=1
            """
            params: Dict[str, Any] = {}
            if ranking_like:
                names_query += """
                    AND (
                        EXISTS (
                            SELECT 1
                            FROM rankings r
                            WHERE r.player_name = src.player_name
                              AND r.fargo_rating IS NOT NULL
                              AND r.ranking_system LIKE :ranking_like
                        )
                        OR EXISTS (
                            SELECT 1
                            FROM fargo_rating_history h
                            WHERE h.player_name = src.player_name
                              AND h.new_fargo_rating IS NOT NULL
                              AND h.ranking_system LIKE :ranking_like
                        )
                    )
                """
                params["ranking_like"] = ranking_like
            names_query += " ORDER BY player_name"
            candidate_names = [r[0] for r in conn.execute(text(names_query), params).fetchall()]

            fargo_hot_players: List[Dict[str, Any]] = []
            for player_name in candidate_names:
                first_name, last_name = self._split_player_name(player_name)
                name_variants = [player_name.strip()]
                if first_name and last_name:
                    name_variants.append(f"{last_name}, {first_name}")
                name_variants = list(dict.fromkeys([n for n in name_variants if n]))

                max_points = max(lookback * 4, lookback + 5)
                fargo_history: List[Dict[str, Any]] = []
                by_date: Dict[str, float] = {}
                rankings_query = """
                    SELECT DISTINCT ON (snapshot_date) snapshot_date, fargo_rating
                    FROM rankings
                    WHERE player_name = ANY(:names)
                      AND fargo_rating IS NOT NULL
                """
                shared_params: Dict[str, Any] = {"names": name_variants, "max_points": max_points}
                if ranking_like:
                    rankings_query += " AND ranking_system LIKE :ranking_like"
                    shared_params["ranking_like"] = ranking_like
                rankings_query += " ORDER BY snapshot_date DESC, id DESC LIMIT :max_points"
                rankings_rows = conn.execute(text(rankings_query), shared_params).fetchall()
                for snap_date, rating in rankings_rows:
                    date_str = snap_date.isoformat() if hasattr(snap_date, "isoformat") else str(snap_date)
                    if date_str and rating is not None:
                        by_date[date_str] = float(rating)

                history_query = """
                    SELECT snapshot_date, new_fargo_rating
                    FROM fargo_rating_history
                    WHERE player_name = ANY(:names)
                      AND new_fargo_rating IS NOT NULL
                """
                if ranking_like:
                    history_query += " AND ranking_system LIKE :ranking_like"
                history_query += " ORDER BY snapshot_date DESC, id DESC LIMIT :max_points"
                history_rows = conn.execute(text(history_query), shared_params).fetchall()
                for snap_date, rating in history_rows:
                    date_str = snap_date.isoformat() if hasattr(snap_date, "isoformat") else str(snap_date)
                    if date_str and rating is not None and date_str not in by_date:
                        by_date[date_str] = float(rating)

                latest_dates = sorted(by_date.keys(), reverse=True)[:lookback]
                if len(latest_dates) < min_tournaments:
                    continue
                for d in reversed(latest_dates):
                    fargo_history.append({"tournament": "", "date": d, "rating": float(by_date[d])})

                oldest_rating = float(fargo_history[0]["rating"])
                newest_rating = float(fargo_history[-1]["rating"])
                if newest_rating <= oldest_rating:
                    continue
                fargo_hot_players.append({
                    "player_name": player_name,
                    "fargo_history": fargo_history,
                    "fargo_trend_score": newest_rating - oldest_rating,
                    "recent_tournaments_count": len(fargo_history),
                })

            fargo_hot_players.sort(key=lambda x: -x["fargo_trend_score"])
            if limit:
                fargo_hot_players = fargo_hot_players[:limit]

            out: List[Dict[str, Any]] = []
            for i, row in enumerate(fargo_hot_players):
                player_name = row["player_name"]
                canonical = self._canonical_player_name(player_name)
                pid, first_name, last_name = self._resolve_player_id(
                    conn, player_name, None, canonical, system=None
                )
                if not first_name and not last_name:
                    first_name, last_name = self._split_player_name(player_name)
                if not pid:
                    pid = self._generate_player_id_from_name(player_name, None)
                avatar_url = None
                fargo_score = None
                if pid:
                    try:
                        r = conn.execute(
                            text("SELECT avatar_url, fargo_rating FROM players WHERE player_id = :pid"),
                            {"pid": pid},
                        ).fetchone()
                        if r:
                            avatar_url = str(r[0]) if r[0] is not None else None
                            fargo_score = int(r[1]) if r[1] is not None else None
                    except Exception:
                        pass
                if fargo_score is None and row["fargo_history"]:
                    fargo_score = int(round(float(row["fargo_history"][-1]["rating"])))

                out.append({
                    "player_id": str(pid),
                    "first_name": first_name or "Unknown",
                    "last_name": last_name or "Unknown",
                    "nickname": None,
                    "license_number": None,
                    "avatar_url": avatar_url,
                    "total_points": 0.0,
                    "current_rank": i + 1,
                    "total_tournaments_played": row["recent_tournaments_count"],
                    "hall_of_fame": False,
                    "hot_streak_count": 0,
                    "fargo_score": fargo_score,
                    "fargo_history": row["fargo_history"],
                    "fargo_trend_score": float(row["fargo_trend_score"]),
                    "nationality": None,
                    "membership_status": "active",
                    "win_percentage_matches": None,
                    "win_percentage_games": None,
                    "first_place_finishes": 0,
                    "second_place_finishes": 0,
                    "third_place_finishes": 0,
                    "last_placements": [],
                    "trend_score": 0.0,
                    "recent_tournaments_count": row["recent_tournaments_count"],
                })
            return out

    def sync_director_tournaments_to_rankings(self) -> Dict[str, Any]:
        """
        Sync director-run completed tournaments into rankings (LOCAL system).
        Preserves all data: rankings remains sole source of truth.
        Returns {players_synced, points_added, errors}.
        """
        from datetime import date
        stats = {"players_synced": 0, "points_added": 0, "errors": 0}
        today = date.today()
        with self.engine.connect() as conn:
            # Get completed director tournaments with placements
            result = conn.execute(text("""
                SELECT t.tournament_id, t.tournament_date, t.points_structure
                FROM tournaments t
                WHERE t.status = 'completed'
                ORDER BY t.tournament_date DESC
            """))
            tournaments = result.fetchall()
            if not tournaments:
                return stats

            # Aggregate points per player across all director tournaments
            player_points: Dict[str, float] = {}
            player_stops: Dict[str, int] = {}
            for tid, tdate, pts_json in tournaments:
                try:
                    pts_struct = json.loads(pts_json) if isinstance(pts_json, str) else (pts_json or {})
                except (TypeError, ValueError):
                    pts_struct = {}
                placements = conn.execute(text("""
                    SELECT p.player_id, tp.final_placement
                    FROM tournament_players tp
                    JOIN players p ON p.player_id = tp.player_id
                    WHERE tp.tournament_id = :tid AND tp.final_placement IS NOT NULL
                """), {"tid": tid}).fetchall()
                for player_id, placement in placements:
                    placement_str = str(placement) if placement is not None else ""
                    pts = float(pts_struct.get(placement_str, 0) or 0)
                    name_result = conn.execute(text(
                        "SELECT first_name, last_name FROM players WHERE player_id = :pid"
                    ), {"pid": player_id}).fetchone()
                    if name_result:
                        player_name = f"{name_result[0] or ''} {name_result[1] or ''}".strip()
                        if player_name:
                            player_points[player_name] = player_points.get(player_name, 0) + pts
                            player_stops[player_name] = player_stops.get(player_name, 0) + 1

            if not player_points:
                return stats

            # Build rankings rows: sort by points desc, assign rank
            sorted_players = sorted(player_points.items(), key=lambda x: -x[1])
            rows = []
            for rank, (player_name, points) in enumerate(sorted_players, 1):
                rows.append({
                    "name": player_name,
                    "rank": rank,
                    "points": points,
                    "country": None,
                    "license_number": None,
                    "stops_played": player_stops.get(player_name, 0),
                })
            try:
                count = self.save_rankings(rows, "LOCAL", today)
                stats["players_synced"] = count
                stats["points_added"] = sum(player_points.values())
            except Exception as e:
                logger.warning("sync_director_tournaments_to_rankings failed: %s", e)
                stats["errors"] += 1
        return stats

    def sync_players_from_rankings(self) -> int:
        """
        Update players.total_points and players.current_rank from merged leaderboard (rankings).
        Keeps players in sync for screens that read from players. No data loss.
        """
        merged = self.get_leaderboard_from_rankings(limit=None)
        with self.engine.connect() as conn:
            for i, row in enumerate(merged, 1):
                pid = row.get("player_id")
                pts = row.get("total_points", 0)
                if not pid:
                    continue
                conn.execute(text("""
                    UPDATE players
                    SET total_points = :pts, current_rank = :rank, updated_at = CURRENT_TIMESTAMP
                    WHERE player_id = :pid
                """), {"pid": pid, "pts": pts, "rank": i})
            conn.commit()
        return len(merged)

    def update_ranking_row(
        self,
        row_id: int,
        updates: Dict[str, Any],
    ) -> bool:
        """Update a single rankings row by id. Director/Admin only. Updates only first-class columns present in updates."""
        allowed = {"player_name", "rank", "points", "stops_played"}
        # Map frontend keys to DB column names
        key_to_col = {
            "name": "player_name",
            "rank": "rank",
            "points": "points",
            "country": "country",
            "stops_played": "stops_played",
        }
        set_parts = []
        params: Dict[str, Any] = {"id": row_id}
        for k, v in updates.items():
            col = key_to_col.get(k, k)
            if col not in allowed:
                continue
            set_parts.append(f"{col} = :{col}")
            params[col] = v
        if not set_parts:
            return False
        with self.engine.connect() as conn:
            result = conn.execute(
                text("UPDATE rankings SET " + ", ".join(set_parts) + " WHERE id = :id"),
                params,
            )
            conn.commit()
            return result.rowcount > 0

    def get_snapshot_dates(self, system: str, limit: int = 30) -> List[str]:
        """Get distinct snapshot dates for a system (most recent first)"""
        with self.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT DISTINCT snapshot_date
                FROM rankings
                WHERE ranking_system = :system
                ORDER BY snapshot_date DESC
                LIMIT :limit
            """), {'system': system, 'limit': limit})
            return [str(r[0]) for r in result.fetchall()]

    def remove_duplicate_rankings(self) -> Dict[str, Any]:
        """
        Remove duplicate rows from rankings (same ranking_system, snapshot_date, position).
        Keeps the row with the minimum id per group. Returns deleted count.
        """
        with self.engine.connect() as conn:
            result = conn.execute(text("""
                DELETE FROM rankings r
                USING rankings r2
                WHERE r.ranking_system = r2.ranking_system
                  AND r.snapshot_date = r2.snapshot_date
                  AND r.position = r2.position
                  AND r.id > r2.id
            """))
            deleted = result.rowcount
            conn.commit()
            return {"deleted": deleted}
    
    def run_quality_checks(self) -> Dict:
        """Run data quality checks on rankings"""
        with self.engine.connect() as conn:
            issues = []
            passed = True
            
            # 1. Duplicate (ranking_system, snapshot_date, position) — one row per list slot
            result = conn.execute(text("""
                SELECT ranking_system, snapshot_date, position, COUNT(*) as cnt
                FROM rankings
                WHERE position IS NOT NULL
                GROUP BY ranking_system, snapshot_date, position
                HAVING COUNT(*) > 1
            """))
            dup_rows = result.fetchall()
            if dup_rows:
                passed = False
                issues.append({
                    "check": "duplicate_position",
                    "severity": "error",
                    "message": "Same (system, date, position) appears more than once",
                    "count": len(dup_rows),
                    "details": [{"ranking_system": r[0], "snapshot_date": str(r[1]), "position": r[2], "count": r[3]} for r in dup_rows],
                })
            
            # 2. Missing or invalid fields
            result = conn.execute(text("""
                SELECT id, player_name, rank, points, ranking_system, snapshot_date
                FROM rankings
                WHERE TRIM(COALESCE(player_name, '')) = ''
                   OR COALESCE(rank, 0) < 1
                   OR COALESCE(points, -1) < 0
            """))
            invalid_rows = result.fetchall()
            if invalid_rows:
                passed = False
                issues.append({
                    "check": "missing_or_invalid_fields",
                    "severity": "error",
                    "message": "Rows with empty name, non-positive rank, or negative points",
                    "count": len(invalid_rows),
                    "details": [{"id": r[0], "player_name": r[1], "rank": r[2], "points": r[3], "system": r[4], "snapshot_date": str(r[5])} for r in invalid_rows],
                })

            # 3. WPA Men: total points must equal sum of all event columns (math vs import/scraper)
            wpa_men_mismatches = self.verify_wpa_men_totals()
            if wpa_men_mismatches:
                passed = False
                issues.append({
                    "check": "wpa_men_total_mismatch",
                    "severity": "error",
                    "message": "WPA Men: stored total points do not match sum of event columns (fix: re-import or re-split)",
                    "count": len(wpa_men_mismatches),
                    "details": wpa_men_mismatches[:50],
                })
            
            return {
                "passed": passed,
                "issues_count": len([i for i in issues if i["severity"] == "error"]),
                "warnings_count": len([i for i in issues if i["severity"] == "warning"]),
                "issues": issues,
            }

    def get_players_without_fargo(self) -> Dict[str, Any]:
        """Names in `players` or latest snapshot rows in `rankings` with no Fargo rating (admin tooling)."""
        with self.engine.connect() as conn:
            from_players_table = 0
            from_rankings_count = 0
            player_rows: List[Tuple[str, str]] = []

            try:
                pr = conn.execute(
                    text("""
                        SELECT name FROM players
                        WHERE fargo_rating IS NULL
                          AND TRIM(COALESCE(name, '')) != ''
                    """)
                ).fetchall()
                from_players_table = len(pr)
                for row in pr:
                    player_rows.append((row[0].strip(), "players"))
            except Exception as e:
                logger.warning("players-without-fargo: players table query skipped: %s", e)

            try:
                rr = conn.execute(
                    text("""
                        SELECT DISTINCT player_name
                        FROM rankings r
                        WHERE r.fargo_rating IS NULL
                          AND TRIM(COALESCE(player_name, '')) != ''
                          AND r.snapshot_date = (
                              SELECT MAX(snapshot_date)
                              FROM rankings r2
                              WHERE r2.ranking_system = r.ranking_system
                          )
                    """)
                ).fetchall()
                from_rankings_count = len(rr)
                for row in rr:
                    player_rows.append((row[0].strip(), "rankings"))
            except Exception as e:
                logger.error("players-without-fargo: rankings query failed: %s", e)
                raise

        by_norm_source: Dict[str, str] = {}
        by_norm_name: Dict[str, str] = {}
        for name, src in player_rows:
            key = name.lower()
            if key not in by_norm_name:
                by_norm_name[key] = name
            if key not in by_norm_source:
                by_norm_source[key] = src
            elif by_norm_source[key] != src:
                by_norm_source[key] = "both"

        players = [
            {"name": by_norm_name[k], "source": by_norm_source[k]}
            for k in sorted(by_norm_name.keys(), key=lambda nk: by_norm_name[nk].lower())
        ]

        return {
            "players": players,
            "from_players_table": from_players_table,
            "from_rankings": from_rankings_count,
        }
    
    def append_audit(self, actor_role: str, actor_subject: str, action: str, details: Optional[Dict[str, Any]] = None) -> None:
        """Append an audit log entry"""
        with self.engine.connect() as conn:
            details_json = json.dumps(details) if details is not None else None
            conn.execute(text("""
                INSERT INTO audit_log (actor_role, actor_subject, action, details)
                VALUES (:role, :subject, :action, :details)
            """), {
                'role': actor_role,
                'subject': actor_subject,
                'action': action,
                'details': details_json
            })
            conn.commit()
    
    def get_audit_log(self, limit: int = 50) -> List[Dict]:
        """Get recent audit log entries (newest first). Uses timestamp (audit_log has timestamp, not created_at)."""
        with self.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT id, timestamp, actor_role, actor_subject, action, details
                FROM audit_log
                ORDER BY timestamp DESC
                LIMIT :limit
            """), {'limit': limit})

            entries = []
            for row in result.fetchall():
                entry = {
                    'id': row[0],
                    'created_at': str(row[1]),  # timestamp
                    'actor_role': row[2] if len(row) > 2 else None,
                    'actor_subject': row[3] if len(row) > 3 else None,
                    'action': row[4] if len(row) > 4 else None,
                    'details': row[5] if len(row) > 5 else None,
                }
                if entry['details']:
                    try:
                        entry['details'] = json.loads(entry['details']) if isinstance(entry['details'], str) else entry['details']
                    except (TypeError, json.JSONDecodeError) as e:
                        logger.debug("Could not decode audit_log.details for entry %s: %s", entry['id'], e)
                entries.append(entry)
            return entries
    
    def add_notify_subscription(self, email: str, player_name: str, system: str) -> str:
        """Add email subscription for ranking-change notifications"""
        token = str(uuid.uuid4())
        with self.engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO email_rank_subscriptions (email, player_name, ranking_system, unsubscribe_token)
                VALUES (:email, :name, :system, :token)
            """), {
                'email': email.strip().lower(),
                'name': player_name.strip(),
                'system': system.upper(),
                'token': token
            })
            conn.commit()
        return token
    
    def get_subscriptions_for_player_system(self, player_name: str, system: str) -> List[Dict]:
        """Get all email subscriptions for a given player and system"""
        with self.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT id, email, player_name, ranking_system, unsubscribe_token, created_at
                FROM email_rank_subscriptions
                WHERE player_name = :name AND ranking_system = :system
            """), {'name': player_name, 'system': system.upper()})
            
            return [
                {
                    'id': r[0],
                    'email': r[1],
                    'player_name': r[2],
                    'ranking_system': r[3],
                    'unsubscribe_token': r[4],
                    'created_at': str(r[5])
                }
                for r in result.fetchall()
            ]
    
    def get_recent_change_player_systems(self, limit: int = 200) -> List[tuple]:
        """Get (player_name, ranking_system) pairs that had recent ranking changes"""
        with self.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT DISTINCT player_name, ranking_system
                FROM ranking_changes
                ORDER BY change_date DESC, id DESC
                LIMIT :limit
            """), {'limit': limit})
            return [(r[0], r[1]) for r in result.fetchall()]
    
    def unsubscribe_notify_by_token(self, token: str) -> bool:
        """Remove subscription by unsubscribe token"""
        with self.engine.connect() as conn:
            result = conn.execute(text("""
                DELETE FROM email_rank_subscriptions
                WHERE unsubscribe_token = :token
            """), {'token': token})
            conn.commit()
            return result.rowcount > 0
    
    # Tournament definitions
    
    def get_tournament_definitions(self) -> List[Dict]:
        """Get all tournament definitions"""
        with self.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT id, name, points_by_place, is_default_for_import, created_at, updated_at
                FROM tournament_definitions
                ORDER BY name
            """))
            
            definitions = []
            for row in result.fetchall():
                d = {
                    'id': row[0],
                    'name': row[1],
                    'points_by_place': row[2],
                    'is_default_for_import': bool(row[3]),
                    'created_at': str(row[4]),
                    'updated_at': str(row[5])
                }
                try:
                    d['points_by_place'] = json.loads(d['points_by_place']) if isinstance(d['points_by_place'], str) else d['points_by_place']
                except (TypeError, json.JSONDecodeError):
                    d['points_by_place'] = []
                definitions.append(d)
            return definitions
    
    def create_tournament_definition(self, name: str, points_by_place: List[float], is_default_for_import: bool = False) -> int:
        """Create a tournament definition"""
        name = name.strip()
        if not name:
            raise ValueError("Tournament name cannot be empty")
        
        pts_json = json.dumps([float(p) for p in points_by_place])
        
        with self.engine.connect() as conn:
            if is_default_for_import:
                conn.execute(text("UPDATE tournament_definitions SET is_default_for_import = 0"))
            
            result = conn.execute(text("""
                INSERT INTO tournament_definitions (name, points_by_place, is_default_for_import, updated_at)
                VALUES (:name, :points, :is_default, :updated_at)
                RETURNING id
            """), {
                'name': name,
                'points': pts_json,
                'is_default': 1 if is_default_for_import else 0,
                'updated_at': datetime.utcnow()
            })
            tid = result.fetchone()[0]
            conn.commit()
            return tid
    
    def update_tournament_definition(self, definition_id: int, name: Optional[str] = None, 
                                    points_by_place: Optional[List[float]] = None, 
                                    is_default_for_import: Optional[bool] = None) -> bool:
        """Update a tournament definition"""
        with self.engine.connect() as conn:
            # Get current values
            result = conn.execute(text("""
                SELECT name, points_by_place, is_default_for_import
                FROM tournament_definitions
                WHERE id = :id
            """), {'id': definition_id})
            row = result.fetchone()
            
            if not row:
                return False
            
            current_name, current_pts, _ = row[0], row[1], row[2]
            new_name = name.strip() if name is not None else current_name
            new_pts = json.dumps([float(p) for p in points_by_place]) if points_by_place is not None else current_pts
            
            if is_default_for_import is True:
                conn.execute(text("UPDATE tournament_definitions SET is_default_for_import = 0"))
            
            if is_default_for_import is not None:
                result = conn.execute(text("""
                    UPDATE tournament_definitions
                    SET name = :name, points_by_place = :points, is_default_for_import = :is_default, updated_at = :updated_at
                    WHERE id = :id
                """), {
                    'name': new_name,
                    'points': new_pts,
                    'is_default': 1 if is_default_for_import else 0,
                    'updated_at': datetime.utcnow(),
                    'id': definition_id
                })
            else:
                result = conn.execute(text("""
                    UPDATE tournament_definitions
                    SET name = :name, points_by_place = :points, updated_at = :updated_at
                    WHERE id = :id
                """), {
                    'name': new_name,
                    'points': new_pts,
                    'updated_at': datetime.utcnow(),
                    'id': definition_id
                })
            
            conn.commit()
            return result.rowcount > 0
    
    def set_tournament_definition_default(self, definition_id: int) -> bool:
        """Set one tournament definition as default for import"""
        with self.engine.connect() as conn:
            conn.execute(text("UPDATE tournament_definitions SET is_default_for_import = 0"))
            result = conn.execute(text("""
                UPDATE tournament_definitions
                SET is_default_for_import = 1, updated_at = :updated_at
                WHERE id = :id
            """), {'updated_at': datetime.utcnow(), 'id': definition_id})
            conn.commit()
            return result.rowcount > 0
    
    def delete_tournament_definition(self, definition_id: int) -> bool:
        """Delete a tournament definition"""
        with self.engine.connect() as conn:
            result = conn.execute(text("""
                DELETE FROM tournament_definitions
                WHERE id = :id
            """), {'id': definition_id})
            conn.commit()
            return result.rowcount > 0
    
    # Tournament imports
    
    def get_tournament_imports(self, system: str = "WPBA") -> List[Dict]:
        """Get all tournament imports for a system"""
        with self.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT id, name, raw_results, points_by_place, status, ranking_system, created_at, updated_at
                FROM tournament_imports
                WHERE ranking_system = :system
                ORDER BY created_at DESC
            """), {'system': system.upper()})
            
            imports = []
            for row in result.fetchall():
                d = {
                    'id': row[0],
                    'name': row[1],
                    'raw_results': row[2],
                    'points_by_place': row[3],
                    'status': row[4],
                    'ranking_system': row[5],
                    'created_at': str(row[6]),
                    'updated_at': str(row[7])
                }
                for key in ('raw_results', 'points_by_place'):
                    if d.get(key):
                        try:
                            d[key] = json.loads(d[key]) if isinstance(d[key], str) else d[key]
                        except (TypeError, json.JSONDecodeError):
                            d[key] = [] if key == "points_by_place" else []
                if not d.get('points_by_place'):
                    d['points_by_place'] = []
                imports.append(d)
            return imports
    
    def get_tournament_import(self, import_id: int) -> Optional[Dict]:
        """Get one tournament import by id"""
        with self.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT id, name, raw_results, points_by_place, status, ranking_system, created_at, updated_at
                FROM tournament_imports
                WHERE id = :id
            """), {'id': import_id})
            row = result.fetchone()
            
            if not row:
                return None
            
            d = {
                'id': row[0],
                'name': row[1],
                'raw_results': row[2],
                'points_by_place': row[3],
                'status': row[4],
                'ranking_system': row[5],
                'created_at': str(row[6]),
                'updated_at': str(row[7])
            }
            for key in ('raw_results', 'points_by_place'):
                if d.get(key):
                    try:
                        d[key] = json.loads(d[key]) if isinstance(d[key], str) else d[key]
                    except (TypeError, json.JSONDecodeError):
                        d[key] = [] if key == "points_by_place" else []
            return d
    
    def create_tournament_import(self, name: str, raw_results: List[Dict], ranking_system: str = "WPBA") -> int:
        """Create a tournament import (status=incomplete)"""
        raw_json = json.dumps(raw_results)
        
        with self.engine.connect() as conn:
            result = conn.execute(text("""
                INSERT INTO tournament_imports (name, raw_results, status, ranking_system, updated_at)
                VALUES (:name, :results, 'incomplete', :system, :updated_at)
                RETURNING id
            """), {
                'name': name.strip() or "Tournament from file",
                'results': raw_json,
                'system': ranking_system.upper(),
                'updated_at': datetime.utcnow()
            })
            tid = result.fetchone()[0]
            conn.commit()
            return tid
    
    def update_tournament_import(self, import_id: int, name: Optional[str] = None, 
                                points_by_place: Optional[List[float]] = None) -> bool:
        """Update name and/or points_by_place"""
        with self.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT name, points_by_place, status
                FROM tournament_imports
                WHERE id = :id
            """), {'id': import_id})
            row = result.fetchone()
            
            if not row:
                return False
            
            current_name, current_pts, status = row[0], row[1], row[2]
            new_name = name.strip() if name is not None else current_name
            
            if points_by_place is not None:
                pts_json = json.dumps([float(p) for p in points_by_place])
                new_status = "complete" if len(points_by_place) > 0 else status
                result = conn.execute(text("""
                    UPDATE tournament_imports
                    SET name = :name, points_by_place = :points, status = :status, updated_at = :updated_at
                    WHERE id = :id
                """), {
                    'name': new_name,
                    'points': pts_json,
                    'status': new_status,
                    'updated_at': datetime.utcnow(),
                    'id': import_id
                })
            else:
                result = conn.execute(text("""
                    UPDATE tournament_imports
                    SET name = :name, updated_at = :updated_at
                    WHERE id = :id
                """), {
                    'name': new_name,
                    'updated_at': datetime.utcnow(),
                    'id': import_id
                })
            
            conn.commit()
            return result.rowcount > 0
    
    def confirm_tournament_import(self, import_id: int) -> bool:
        """Set status to 'confirmed' if tournament has points_by_place"""
        imp = self.get_tournament_import(import_id)
        if not imp or not imp.get('points_by_place'):
            return False
        
        with self.engine.connect() as conn:
            result = conn.execute(text("""
                UPDATE tournament_imports
                SET status = 'confirmed', updated_at = :updated_at
                WHERE id = :id
            """), {'updated_at': datetime.utcnow(), 'id': import_id})
            conn.commit()
            return result.rowcount > 0
    
    def get_confirmed_tournament_imports(self, system: str = "WPBA") -> List[Dict]:
        """Get all confirmed tournament imports (for merging into rankings)"""
        with self.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT id, name, raw_results, points_by_place, status, ranking_system
                FROM tournament_imports
                WHERE ranking_system = :system AND status = 'confirmed'
                ORDER BY id
            """), {'system': system.upper()})
            
            imports = []
            for row in result.fetchall():
                d = {
                    'id': row[0],
                    'name': row[1],
                    'raw_results': row[2],
                    'points_by_place': row[3],
                    'status': row[4],
                    'ranking_system': row[5]
                }
                for key in ('raw_results', 'points_by_place'):
                    if d.get(key):
                        try:
                            d[key] = json.loads(d[key]) if isinstance(d[key], str) else d[key]
                        except (TypeError, json.JSONDecodeError):
                            d[key] = [] if key == "points_by_place" else []
                imports.append(d)
            return imports
    
    def delete_tournament_import(self, import_id: int) -> bool:
        """Delete a tournament import"""
        with self.engine.connect() as conn:
            result = conn.execute(text("""
                DELETE FROM tournament_imports
                WHERE id = :id
            """), {'id': import_id})
            conn.commit()
            return result.rowcount > 0
    
    # Additional methods for startup and maintenance
    
    def check_startup_refresh_needed(self, stale_threshold_hours: int = 24) -> Dict:
        """Check if rankings data is stale and needs refreshing"""
        with self.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT 
                    ranking_system,
                    MAX(snapshot_date) as last_snapshot_date,
                    EXTRACT(EPOCH FROM (NOW() - MAX(snapshot_date))) / 3600 as hours_old
                FROM rankings
                GROUP BY ranking_system
            """))
            
            systems_status = []
            needs_refresh = False
            
            for row in result.fetchall():
                system = row[0]
                last_date = row[1]
                hours_old = float(row[2]) if row[2] else 0
                
                is_stale = hours_old > stale_threshold_hours
                if is_stale:
                    needs_refresh = True
                
                systems_status.append({
                    'system': system,
                    'last_snapshot_date': str(last_date),
                    'hours_old': round(hours_old, 2),
                    'is_stale': is_stale
                })
            
            return {
                'needs_refresh': needs_refresh,
                'threshold_hours': stale_threshold_hours,
                'systems': systems_status
            }
    
    def ensure_archive_table_exists(self) -> bool:
        """Ensure rankings_archive table exists (already in schema_postgres.sql)"""
        with self.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'rankings_archive'
                )
            """))
            exists = result.fetchone()[0]

            if exists:
                logger.info("rankings_archive table verified")
                return True
            else:
                logger.warning("rankings_archive table missing - run schema_postgres.sql")
                return False

    def archive_existing_rankings(self, system: str, snapshot_date: date) -> int:
        """
        Archive existing rankings for a system/date before updating with new data.
        Returns the number of records archived.
        """
        with self.engine.begin() as conn:  # Use begin() to get a transaction
            # Check if there's existing data to archive
            result = conn.execute(text("""
                SELECT COUNT(*) FROM rankings
                WHERE ranking_system = :system AND snapshot_date = :date
            """), {'system': system, 'date': snapshot_date})

            existing_count = result.fetchone()[0]
            if existing_count == 0:
                return 0

            # Archive existing data
            conn.execute(text("""
                INSERT INTO rankings_archive (
                    original_id, player_name, ranking_system, rank, points,
                    country, snapshot_date, license_number, fargo_rating,
                    archived_at, archive_reason
                )
                SELECT
                    id, player_name, ranking_system, rank, points,
                    country, snapshot_date, license_number, fargo_rating,
                    CURRENT_TIMESTAMP, 'pre_update'
                FROM rankings
                WHERE ranking_system = :system AND snapshot_date = :date
            """), {'system': system, 'date': snapshot_date})

            # Get the count of newly archived records
            archived_count = conn.execute(text("""
                SELECT COUNT(*) FROM rankings_archive
                WHERE ranking_system = :system AND snapshot_date = :date
                AND archive_reason = 'pre_update'
                AND archived_at >= CURRENT_TIMESTAMP - INTERVAL '1 minute'
            """), {'system': system, 'date': snapshot_date}).fetchone()[0]

            if archived_count > 0:
                logger.info(f"Archived {archived_count} existing {system} rankings for {snapshot_date}")

            return archived_count

    def restore_rankings_from_archive(self, system: str, snapshot_date: date) -> int:
        """
        Restore rankings from archive for a specific system and date.
        Returns the number of records restored.
        """
        with self.engine.connect() as conn:
            # Check if archived data exists
            result = conn.execute(text("""
                SELECT COUNT(*) FROM rankings_archive
                WHERE ranking_system = :system AND snapshot_date = :date
            """), {'system': system, 'date': snapshot_date})

            archived_count = result.fetchone()[0]
            if archived_count == 0:
                logger.info(f"No archived data found for {system} {snapshot_date}")
                return 0

            # Delete any existing data for this system/date
            conn.execute(text("""
                DELETE FROM rankings
                WHERE ranking_system = :system AND snapshot_date = :date
            """), {'system': system, 'date': snapshot_date})

            # Restore from archive
            conn.execute(text("""
                INSERT INTO rankings (
                    player_name, ranking_system, rank, points, country,
                    license_number, fargo_rating, snapshot_date, source_data
                )
                SELECT
                    player_name, ranking_system, rank, points, country,
                    license_number, fargo_rating, snapshot_date, '{}'::jsonb
                FROM rankings_archive
                WHERE ranking_system = :system AND snapshot_date = :date
                ORDER BY rank
            """), {'system': system, 'date': snapshot_date})

            restored_count = conn.execute(text("""
                SELECT COUNT(*) FROM rankings
                WHERE ranking_system = :system AND snapshot_date = :date
            """), {'system': system, 'date': snapshot_date}).fetchone()[0]

            logger.info(f"Restored {restored_count} rankings for {system} {snapshot_date} from archive")
            return restored_count
    
    def get_last_snapshot_date(self, ranking_system: str) -> Optional[date]:
        """Get the most recent snapshot date for a ranking system"""
        with self.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT MAX(snapshot_date) as last_date
                FROM rankings
                WHERE ranking_system = :system
            """), {'system': ranking_system})
            row = result.fetchone()
            return row[0] if row and row[0] else None

    def fill_tournament_history_from_rankings_snapshots(
        self,
        *,
        ranking_systems: Optional[List[str]] = None,
        limit_snapshots_per_system: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Create or update tournament_history and tournament_results from existing
        rankings snapshots (no new scraping). Each (ranking_system, snapshot_date)
        becomes one tournament_history row (e.g. "WPBA Women Rankings (2025-03-15)")
        with tournament_results filled from that snapshot (placement=rank, points=points).

        Args:
            ranking_systems: If provided, only these ranking_system values (e.g. WPBA_Women, WPA_Women).
            limit_snapshots_per_system: If set, only process this many most recent snapshots per system.

        Returns:
            Dict with tournaments_created, tournaments_updated, results_upserted, errors.
        """
        stats = {"tournaments_created": 0, "tournaments_updated": 0, "results_upserted": 0, "errors": 0}
        with self.engine.connect() as conn:
            # Distinct (ranking_system, snapshot_date), optionally filtered
            sys_filter = ""
            params: Dict[str, Any] = {}
            if ranking_systems:
                sys_filter = " AND ranking_system = ANY(:systems)"
                params["systems"] = ranking_systems
            limit_clause = ""
            if limit_snapshots_per_system is not None:
                # Subquery to limit per system: get latest N snapshot_dates per system
                limit_clause = """
                    AND (ranking_system, snapshot_date) IN (
                        SELECT ranking_system, snapshot_date FROM (
                            SELECT ranking_system, snapshot_date,
                                   ROW_NUMBER() OVER (PARTITION BY ranking_system ORDER BY snapshot_date DESC) AS rn
                            FROM (SELECT ranking_system, snapshot_date FROM rankings GROUP BY ranking_system, snapshot_date) d
                        ) t WHERE rn <= :limit_per_system
                    )
                """
                params["limit_per_system"] = limit_snapshots_per_system

            result = conn.execute(text(f"""
                SELECT DISTINCT ranking_system, snapshot_date
                FROM rankings
                WHERE 1=1 {sys_filter} {limit_clause}
                ORDER BY ranking_system, snapshot_date DESC
            """), params)
            snapshots = [(r[0], r[1]) for r in result.fetchall()]

            for ranking_system, snapshot_date in snapshots:
                try:
                    # Association: keep WPBA, WPA, and Heyball separate (do not mix)
                    rs = (ranking_system or "").strip()
                    if rs.startswith("WPA_Heyball"):
                        association = "HEYBALL"
                    elif rs.startswith("WPBA"):
                        association = "WPBA"
                    elif rs.startswith("WPA"):
                        association = "WPA"
                    else:
                        association = (rs.split("_")[0] or "Other") if rs else "Other"
                    # Snapshot pseudo-rows ("... Rankings (date)") are NOT real tournaments: this
                    # writer keys tournament_id by (association, date), so every ranking system on a
                    # date collapses into one fake "tournament" and accumulates hundreds of bogus
                    # results (e.g. 501). Real completed events have dedicated sources:
                    #   - WPBA: the ranking-PDF per-event pipeline (wpba_evt_*, fill_tournament_history_from_wpba_women_events)
                    #   - WPA / HEYBALL: digitalpool archive events (fill_tournament_history_from_cp_archives)
                    # so skip all three. (Snapshot-pseudo is superseded; see docs/WPA_TOURNAMENT_SSOT.md.)
                    if association in ("WPBA", "WPA", "HEYBALL"):
                        continue
                    year = snapshot_date.year if hasattr(snapshot_date, "year") else int(str(snapshot_date)[:4])
                    date_str = str(snapshot_date) if snapshot_date else ""
                    display_name = f"{ranking_system.replace('_', ' ')} Rankings ({date_str})"
                    tournament_id = f"rankings_snapshot_{association}_{date_str}".replace(" ", "_")

                    # Upsert tournament_history
                    conn.execute(text("""
                        INSERT INTO tournament_history
                        (tournament_id, name, year, date, association, status)
                        VALUES (:tid, :name, :year, CAST(:dt AS date), :assoc, 'completed')
                        ON CONFLICT (tournament_id) DO UPDATE SET
                            name = EXCLUDED.name,
                            date = EXCLUDED.date,
                            year = EXCLUDED.year,
                            association = EXCLUDED.association,
                            status = EXCLUDED.status,
                            updated_at = CURRENT_TIMESTAMP
                    """), {
                        "tid": tournament_id,
                        "name": display_name[:255],
                        "year": year,
                        "dt": date_str,
                        "assoc": association[:32],
                    })
                    conn.commit()
                    stats["tournaments_updated"] += 1

                    # Fetch rankings rows for this snapshot
                    rows = conn.execute(
                        text("""
                            SELECT player_name, rank, points, stops_played
                            FROM rankings
                            WHERE ranking_system = :system AND snapshot_date = :dt
                            ORDER BY position ASC NULLS LAST, rank ASC, id ASC
                        """),
                        {"system": ranking_system, "dt": snapshot_date},
                    ).fetchall()

                    for player_name, rank, points, stops_played in rows:
                        if not (player_name or "").strip():
                            continue
                        try:
                            conn.execute(text("""
                                INSERT INTO tournament_results
                                (tournament_id, player_name, placement, points, stops_played)
                                VALUES (:tid, :player, :placement, :points, :stops)
                                ON CONFLICT (tournament_id, player_name) DO UPDATE SET
                                    placement = EXCLUDED.placement,
                                    points = EXCLUDED.points,
                                    stops_played = EXCLUDED.stops_played
                            """), {
                                "tid": tournament_id,
                                "player": (player_name or "").strip()[:255],
                                "placement": rank,
                                "points": float(points or 0),
                                "stops": stops_played,
                            })
                            stats["results_upserted"] += 1
                        except Exception as e:
                            logger.debug("tournament_results upsert %s: %s", player_name, e)
                            stats["errors"] += 1

                    conn.commit()
                except Exception as e:
                    logger.warning("fill_tournament_history_from_rankings snapshot %s %s: %s", ranking_system, snapshot_date, e)
                    stats["errors"] += 1
                    try:
                        conn.rollback()
                    except Exception as rollback_error:
                        logger.warning(
                            "Rollback failed after rankings snapshot import error (%s %s): %s",
                            ranking_system,
                            snapshot_date,
                            rollback_error,
                        )

        try:
            self.refresh_materialized_views()
        except Exception as e:
            logger.warning("refresh_materialized_views after fill_tournament_history: %s", e)
        return stats

    def _wpba_women_event_label_for_system(self, ranking_system: str) -> str:
        """Human-readable tournament name for a WPBA_Women_* per-event ranking system."""
        rs = (ranking_system or "").strip()
        for _column_key, target_system, label in self.WPBA_WOMEN_COLUMN_MAPPING:
            if target_system == rs:
                return label
        suffix = rs.replace("WPBA_Women_", "", 1) if rs.startswith("WPBA_Women_") else rs
        parts = re.sub(r"([A-Z])", r" \1", suffix).strip().split()
        return " ".join(p for p in parts if p) or rs

    def _get_wpba_women_rankings_for_snapshot(self, snapshot_date: Union[date, datetime, str]) -> List[Dict[str, Any]]:
        """
        Load WPBA_Women overall rows for one snapshot_date with source_data merged into dicts
        (same shape as get_rankings_paginated for WPBA_Women) so _points_from_single_column works.
        """
        if isinstance(snapshot_date, str):
            snapshot_date = datetime.strptime(snapshot_date[:10], "%Y-%m-%d").date()
        elif isinstance(snapshot_date, datetime):
            snapshot_date = snapshot_date.date()

        with self.engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT
                        r.player_name,
                        r.rank,
                        r.points,
                        r.stops_played,
                        r.snapshot_date,
                        r.source_data
                    FROM rankings r
                    WHERE r.ranking_system = 'WPBA_Women'
                      AND r.snapshot_date = :dt
                    ORDER BY r.position ASC NULLS LAST, r.rank ASC, r.id ASC
                """),
                {"dt": snapshot_date},
            )
            rows_raw = result.fetchall()

        rankings: List[Dict[str, Any]] = []
        for r in rows_raw:
            base: Dict[str, Any] = {
                "name": r[0],
                "rank": r[1],
                "points": r[2],
                "stops_played": r[3],
                "date": str(r[4]),
            }
            sd = r[5]
            if isinstance(sd, str):
                try:
                    sd = json.loads(sd) if sd else None
                except (TypeError, ValueError):
                    sd = None
            if sd:
                for k, v in sd.items():
                    if k not in base:
                        base[k] = v
            base = self._normalize_display_row(base)
            rankings.append(base)
        return rankings

    def _resolve_wpba_event_date(
        self,
        conn,
        display_name: str,
        year_val: int,
    ) -> Optional[date]:
        """Return the real date for a WPBA event by fuzzy-matching existing schedule/upcoming
        rows (non-evt WPBA rows) by name + year, or ``None`` when there is no confident match.

        The caller owns the fallback chain so that an existing good date on the canonical
        ``wpba_evt_*`` row is never overwritten by a fallback. This keeps the per-event pipeline
        self-sufficient even after the duplicate calendar rows are removed.
        """
        name_words = re.sub(r"[^a-z0-9 ]", "", display_name.lower()).split()
        if len(name_words) >= 2:
            like_pattern = "%" + "%".join(name_words[:4]) + "%"
            row = conn.execute(
                text("""
                    SELECT date FROM tournament_history
                    WHERE association = 'WPBA'
                      AND tournament_id NOT LIKE 'wpba_evt_%%'
                      AND LOWER(name) LIKE :pat
                      AND year = :yr
                      AND date IS NOT NULL
                    ORDER BY date ASC
                    LIMIT 1
                """),
                {"pat": like_pattern, "yr": year_val},
            ).fetchone()
            if row and row[0]:
                return row[0] if isinstance(row[0], date) else date.fromisoformat(str(row[0]))

        return None

    def _upsert_wpba_event_tournament_history(
        self,
        conn,
        *,
        tid: str,
        display_name: str,
        snapshot_date: Union[date, datetime],
        result_rows: List[Tuple[Any, ...]],
    ) -> int:
        """
        Insert/update tournament_history and replace tournament_results for one WPBA event.
        result_rows: list of (player_name, rank, points, stops_played).
        Returns number of tournament_results rows written.
        """
        if isinstance(snapshot_date, datetime):
            snapshot_date = snapshot_date.date()
        year_val = self._extract_year_from_text(display_name)
        if not year_val:
            year_val = snapshot_date.year if hasattr(snapshot_date, "year") else int(str(snapshot_date)[:4])

        matched_date = self._resolve_wpba_event_date(conn, display_name, year_val)
        # Caller owns the fallback chain. On INSERT use the matched real date, else Jan 1 of the
        # event year (so events sort by year, not scrape date), else the snapshot date. On UPDATE
        # only overwrite the stored date when we have a real matched date — never clobber an
        # existing good date with a fallback (keeps wpba_evt_* self-sufficient after cleanup).
        fallback_date = date(year_val, 1, 1) if (year_val and year_val != snapshot_date.year) else snapshot_date
        insert_date = matched_date or fallback_date
        has_matched_date = matched_date is not None

        conn.execute(
            text("""
                INSERT INTO tournament_history
                (tournament_id, name, year, date, association, status)
                VALUES (:tid, :name, :year, CAST(:dt AS date), :assoc, 'completed')
                ON CONFLICT (tournament_id) DO UPDATE SET
                    name = EXCLUDED.name,
                    year = EXCLUDED.year,
                    association = EXCLUDED.association,
                    status = EXCLUDED.status,
                    date = CASE WHEN :has_matched_date THEN EXCLUDED.date ELSE tournament_history.date END,
                    updated_at = CURRENT_TIMESTAMP
            """),
            {
                "tid": tid,
                "name": display_name[:255],
                "year": year_val,
                "dt": str(insert_date),
                "assoc": "WPBA",
                "has_matched_date": has_matched_date,
            },
        )
        conn.execute(
            text("DELETE FROM tournament_results WHERE tournament_id = :tid"),
            {"tid": tid},
        )
        n = 0
        for player_name, rank, points, stops_played in result_rows:
            pn = (player_name or "").strip() if player_name is not None else ""
            if not pn:
                continue
            conn.execute(
                text("""
                    INSERT INTO tournament_results
                    (tournament_id, player_name, placement, points, stops_played)
                    VALUES (:tid, :player, :placement, :points, :stops)
                    ON CONFLICT (tournament_id, player_name) DO UPDATE SET
                        placement = EXCLUDED.placement,
                        points = EXCLUDED.points,
                        stops_played = EXCLUDED.stops_played
                """),
                {
                    "tid": tid,
                    "player": pn[:255],
                    "placement": rank,
                    "points": float(points or 0),
                    "stops": stops_played,
                },
            )
            n += 1
        return n

    def fill_tournament_history_from_wpba_women_events(
        self,
        *,
        snapshot_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        """
        Upsert tournament_history and tournament_results for WPBA per-event tournaments.

        Primary path: derive events from the latest WPBA_Women PDF columns (same mapping as
        split_wpba_women_to_column_buttons) so history updates even if split skipped a column.

        Secondary path: any WPBA_Women_* ranking_system rows for the snapshot not covered above.

        Does not refresh materialized views; callers should refresh after all writes.
        """
        stats: Dict[str, Any] = {
            "tournaments_upserted": 0,
            "results_upserted": 0,
            "systems_skipped": 0,
            "errors": 0,
        }

        with self.engine.connect() as conn:
            if snapshot_date is None:
                row = conn.execute(
                    text("SELECT MAX(snapshot_date) FROM rankings WHERE ranking_system = 'WPBA_Women'")
                ).fetchone()
                if not row or row[0] is None:
                    logger.info("fill_tournament_history_from_wpba_women_events: no WPBA_Women snapshot")
                    return stats
                raw_dt = row[0]
                if isinstance(raw_dt, str):
                    snapshot_date = datetime.strptime(raw_dt[:10], "%Y-%m-%d").date()
                else:
                    snapshot_date = raw_dt

            rankings = self._get_wpba_women_rankings_for_snapshot(snapshot_date)
            if not rankings:
                logger.info("fill_tournament_history_from_wpba_women_events: no WPBA_Women rows for %s", snapshot_date)
                return stats

            processed_tids: set = set()
            # Merge labels from every row so names match the PDF even if the first row lacked source_data.
            label_map: Dict[str, str] = {}
            for rec in rankings:
                raw = rec.get("wpba_column_labels")
                if isinstance(raw, dict) and raw:
                    for k, v in raw.items():
                        if k and v:
                            label_map[str(k)] = str(v).strip()

            column_mapping = self._get_wpba_recent_column_mapping(
                rankings, limit=self.WPBA_WOMEN_EVENT_COLUMN_LIMIT
            )

            for column_key, target_system, label in column_mapping:
                if column_key == WPBA_ROTATING_11TH_KEY:
                    stats["systems_skipped"] += 1
                    continue
                try:
                    scored: List[Tuple[str, float, Any]] = []
                    for rec in rankings:
                        pts = float(self._points_from_single_column(rec, column_key))
                        if pts <= 0:
                            continue
                        name = (rec.get("name") or rec.get("player") or "").strip()
                        if not name:
                            continue
                        scored.append((name, pts, rec.get("stops_played")))
                    if not scored:
                        stats["systems_skipped"] += 1
                        continue

                    scored.sort(key=lambda x: (-x[1], x[0]))
                    result_rows = [
                        (name, i + 1, pts, stops)
                        for i, (name, pts, stops) in enumerate(scored)
                    ]
                    tid = f"wpba_evt_{target_system}"[:255]
                    display_name = (label_map.get(column_key) or label).strip()[:255]
                    n = self._upsert_wpba_event_tournament_history(
                        conn,
                        tid=tid,
                        display_name=display_name,
                        snapshot_date=snapshot_date,
                        result_rows=result_rows,
                    )
                    conn.commit()
                    processed_tids.add(tid)
                    stats["tournaments_upserted"] += 1
                    stats["results_upserted"] += n
                except Exception as e:
                    logger.warning("fill_tournament_history_from_wpba_women_events column %s: %s", column_key, e)
                    stats["errors"] += 1
                    try:
                        conn.rollback()
                    except Exception as rollback_error:
                        logger.debug("Rollback after wpba event history error: %s", rollback_error)

            sys_rows = conn.execute(
                text("""
                    SELECT DISTINCT ranking_system
                    FROM rankings
                    WHERE snapshot_date = :dt
                      AND ranking_system LIKE 'WPBA_Women_%'
                      AND ranking_system != 'WPBA_Women_Col'
                      AND ranking_system NOT LIKE 'WPBA_Women_col_%'
                    ORDER BY ranking_system
                """),
                {"dt": snapshot_date},
            ).fetchall()

            for sys_row in sys_rows:
                rs = (sys_row[0] or "").strip() if sys_row else ""
                if not rs or rs == "WPBA_Women_Rotating11th":
                    continue
                tid = f"wpba_evt_{rs}"[:255]
                if tid in processed_tids:
                    continue
                try:
                    display_name = self._wpba_women_event_label_for_system(rs)[:255]
                    rows = conn.execute(
                        text("""
                            SELECT player_name, rank, points, stops_played
                            FROM rankings
                            WHERE ranking_system = :sys AND snapshot_date = :dt
                              AND COALESCE(points, 0) > 0
                            ORDER BY rank ASC NULLS LAST, player_name ASC
                        """),
                        {"sys": rs, "dt": snapshot_date},
                    ).fetchall()

                    if not rows:
                        stats["systems_skipped"] += 1
                        continue

                    n = self._upsert_wpba_event_tournament_history(
                        conn,
                        tid=tid,
                        display_name=display_name,
                        snapshot_date=snapshot_date,
                        result_rows=rows,
                    )
                    conn.commit()
                    processed_tids.add(tid)
                    stats["tournaments_upserted"] += 1
                    stats["results_upserted"] += n
                except Exception as e:
                    logger.warning("fill_tournament_history_from_wpba_women_events %s: %s", rs, e)
                    stats["errors"] += 1
                    try:
                        conn.rollback()
                    except Exception as rollback_error:
                        logger.debug("Rollback after wpba event history error: %s", rollback_error)

        return stats

    def fill_tournament_history_from_cp_archives(
        self,
        archive_dirs: List[Union[str, Path]],
        *,
        association_from_name: bool = True,
    ) -> Dict[str, Any]:
        """
        Fill tournament_history and tournament_results from CP / External Pool
        scrape archives (JSON files in data/externalpool_archive, data/cp_archive,
        or paths on the server). Reads all *.json in the given directories; each file may
        contain a "tournaments" array with tournament_name, players, and/or standings.

        Args:
            archive_dirs: List of directory paths (str or Path) to scan for JSON archives.
            association_from_name: If True, set association from tournament name (WPBA/WPA).

        Returns:
            Dict with tournaments_created, tournaments_updated, results_upserted, files_read, errors.
        """
        # Noise strings to skip when treating players list as placements
        SKIP_PLAYER_NAMES = frozenset({
            "apps", "upgrade", "login", "sign up", "overview", "schedule", "bracket",
            "tournament", "classic", "championship", "invitational", "iron city", "colorado",
        })

        def _is_noise(name: str) -> bool:
            if not name or len(name) > 200:
                return True
            lower = name.lower().strip()
            if lower in SKIP_PLAYER_NAMES:
                return True
            if any(lower.startswith(p) for p in ("apps", "upgrade", "login", "sign up")):
                return True
            # Title-like: all caps long
            if len(lower) > 30 and lower.isupper():
                return True
            return False

        def _association_from_name(tournament_name: str) -> str:
            n = (tournament_name or "").upper()
            # Heyball first so WPA Heyball events are not lumped with WPA pool
            if "HEYBALL" in n or "HEY BALL" in n:
                return "HEYBALL"
            if "WPBA" in n:
                return "WPBA"
            if "WPA" in n:
                return "WPA"
            return "ExternalPool"

        def _year_from_name_or_scraped(tournament_name: str, scraped_at: Any) -> Optional[int]:
            m = re.search(r"\b(20\d{2})\b", (tournament_name or ""))
            if m:
                return int(m.group(1))
            if scraped_at:
                s = str(scraped_at)[:4]
                if s.isdigit():
                    return int(s)
            return None

        def _slug_tournament_id(name: str, year: Optional[int], association: str) -> str:
            norm_assoc = _normalize_association(association)
            slug = re.sub(r"[^a-z0-9]+", "_", (name or "").lower()).strip("_")[:120]
            y = year or 0
            return f"{y}_{norm_assoc}_{slug}" if slug else f"{y}_{norm_assoc}_event"

        def _normalize_association(assoc: Optional[str]) -> str:
            """Normalize association from archive (e.g. 'WPA Men' -> 'WPA', 'WPA Heyball' -> 'HEYBALL')."""
            a = (assoc or "").strip().upper()
            if "HEYBALL" in a or a == "WPA HEYBALL":
                return "HEYBALL"
            if a.startswith("WPBA"):
                return "WPBA"
            if a.startswith("WPA") or a in ("WPA MEN", "WPA WOMEN", "WPA ARTISTIC"):
                return "WPA"
            return (a[:32]) if a else "Other"

        _NEWS_ARTICLE_PATTERNS = (
            "congratulates", "crowned", "passes at", "historic beginning",
            "introducing the", "concludes in", "announces", "press release",
        )

        def _is_news_article(name: str) -> bool:
            lower = (name or "").lower()
            return any(p in lower for p in _NEWS_ARTICLE_PATTERNS)

        stats = {
            "tournaments_created": 0,
            "tournaments_updated": 0,
            "results_upserted": 0,
            "files_read": 0,
            "errors": 0,
        }

        # Collect (tournament_id, name, year, association, results_list) from all archives
        entries: List[Dict[str, Any]] = []
        # Tournament-history archive style: "data" array of tournaments or results
        data_tournament_rows: List[Dict[str, Any]] = []
        data_result_rows: List[Dict[str, Any]] = []

        for dir_path in archive_dirs:
            d = Path(dir_path)
            if not d.is_dir():
                logger.debug("Archive dir not found or not a directory: %s", d)
                continue
            for jpath in sorted(d.glob("*.json")):
                try:
                    with open(jpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    stats["files_read"] += 1
                except Exception as e:
                    logger.warning("Could not read archive %s: %s", jpath, e)
                    stats["errors"] += 1
                    continue

                # Tournament-history archive format: top-level "data" array or top-level list (tournaments or results)
                raw_data = data.get("data") if isinstance(data, dict) else (data if isinstance(data, list) else None)
                if isinstance(raw_data, list) and raw_data:
                    first = raw_data[0]
                    if isinstance(first, dict):
                        if "player_name" in first and "placement" in first and "tournament_id" in first:
                            for row in raw_data:
                                if not isinstance(row, dict):
                                    continue
                                tid = row.get("tournament_id")
                                pname = (row.get("player_name") or "").strip()
                                if not tid or not pname:
                                    continue
                                try:
                                    place = int(row.get("placement") or 0)
                                except (TypeError, ValueError):
                                    place = 0
                                pts = row.get("points")
                                try:
                                    pts = float(pts) if pts is not None else 0.0
                                except (TypeError, ValueError):
                                    pts = 0.0
                                data_result_rows.append({
                                    "tournament_id": tid[:255],
                                    "player_name": pname[:255],
                                    "placement": place,
                                    "points": pts,
                                    "tournament_name": (row.get("tournament_name") or "").strip()[:255],
                                    "year": row.get("year"),
                                    "association": _normalize_association(row.get("association")),
                                })
                        elif "tournament_id" in first and "name" in first and "player_name" not in first:
                            for row in raw_data:
                                if not isinstance(row, dict):
                                    continue
                                tid = row.get("tournament_id")
                                name = (row.get("name") or "").strip()
                                if not tid or not name or _is_news_article(name):
                                    continue
                                year = row.get("year")
                                if year is not None:
                                    try:
                                        year = int(year)
                                    except (TypeError, ValueError):
                                        year = None
                                assoc = _normalize_association(row.get("association"))
                                tid = _slug_tournament_id(name, year, assoc)
                                date_val = row.get("date")
                                source_url = row.get("source_url")
                                status = (row.get("status") or "completed")[:32]
                                data_tournament_rows.append({
                                    "tournament_id": tid[:255],
                                    "name": name[:255],
                                    "year": year,
                                    "date": date_val,
                                    "association": assoc[:32],
                                    "source_url": source_url,
                                    "status": status,
                                })
                    continue  # file handled as data format; skip tournaments/tournament_list

                if not isinstance(data, dict):
                    continue
                tournaments = data.get("tournaments") or data.get("tournament_list") or []
                if not tournaments:
                    continue

                for t in tournaments:
                    try:
                        name = (t.get("tournament_name") or t.get("name") or t.get("title") or "").strip()
                        if not name or _is_news_article(name):
                            continue
                        scraped_at = t.get("scraped_at") or data.get("scraped_at")
                        association = _association_from_name(name) if association_from_name else "ExternalPool"
                        year = _year_from_name_or_scraped(name, scraped_at)
                        tournament_id = _slug_tournament_id(name, year, association)

                        # Build results: (player_name, placement, points)
                        results = []
                        standings = t.get("standings") or []
                        if standings:
                            for s in standings:
                                pname = (s.get("player_name") or s.get("name") or s.get("player") or "").strip()
                                if _is_noise(pname):
                                    continue
                                place = s.get("place") or s.get("placement") or s.get("rank")
                                if place is None and isinstance(s, (list, tuple)) and len(s) >= 2:
                                    place = s[0]
                                    pname = str(s[1]).strip()
                                try:
                                    place = int(place) if place is not None else len(results) + 1
                                except (TypeError, ValueError):
                                    place = len(results) + 1
                                pts = s.get("points")
                                try:
                                    pts = float(pts) if pts is not None else 0.0
                                except (TypeError, ValueError):
                                    pts = 0.0
                                results.append((pname[:255], place, pts))
                        else:
                            players = t.get("players") or []
                            for idx, p in enumerate(players):
                                if isinstance(p, dict):
                                    pname = (p.get("name") or p.get("player_name") or "").strip()
                                    place = p.get("place") or p.get("placement") or p.get("rank") or (idx + 1)
                                    pts = p.get("points")
                                    try:
                                        pts = float(pts) if pts is not None else 0.0
                                    except (TypeError, ValueError):
                                        pts = 0.0
                                else:
                                    pname = str(p).strip()
                                    place = idx + 1
                                    pts = 0.0
                                if _is_noise(pname):
                                    continue
                                results.append((pname[:255], int(place) if isinstance(place, int) else (idx + 1), pts))

                        if results:
                            entries.append({
                                "tournament_id": tournament_id,
                                "name": name[:255],
                                "year": year,
                                "association": association[:32],
                                "results": results,
                            })
                    except Exception as e:
                        logger.debug("Parse tournament from archive: %s", e)
                        stats["errors"] += 1

        # WPBA tournament history is owned by the ranking-PDF per-event pipeline (wpba_evt_*).
        # Archive imports must never create WPBA rows — their names/years/result counts are
        # unreliable and duplicate the canonical events. WPA / Heyball / CP imports are unaffected.
        entries = [e for e in entries if _normalize_association(e.get("association")) != "WPBA"]
        data_tournament_rows = [r for r in data_tournament_rows if _normalize_association(r.get("association")) != "WPBA"]
        data_result_rows = [r for r in data_result_rows if _normalize_association(r.get("association")) != "WPBA"]

        # Upsert into DB
        with self.engine.connect() as conn:
            for item in entries:
                try:
                    conn.execute(text("""
                        INSERT INTO tournament_history
                        (tournament_id, name, year, association, status, source_url)
                        VALUES (:tid, :name, :year, :assoc, 'completed', :url)
                        ON CONFLICT (tournament_id) DO UPDATE SET
                            name = EXCLUDED.name,
                            year = EXCLUDED.year,
                            association = EXCLUDED.association,
                            updated_at = CURRENT_TIMESTAMP
                    """), {
                        "tid": item["tournament_id"],
                        "name": item["name"],
                        "year": item["year"],
                        "assoc": item["association"],
                        "url": None,
                    })
                    conn.commit()
                    stats["tournaments_updated"] += 1

                    for player_name, placement, points in item["results"]:
                        if not player_name:
                            continue
                        try:
                            conn.execute(text("""
                                INSERT INTO tournament_results
                                (tournament_id, player_name, placement, points)
                                VALUES (:tid, :player, :placement, :points)
                                ON CONFLICT (tournament_id, player_name) DO UPDATE SET
                                    placement = EXCLUDED.placement,
                                    points = EXCLUDED.points
                            """), {
                                "tid": item["tournament_id"],
                                "player": player_name,
                                "placement": placement,
                                "points": points,
                            })
                            stats["results_upserted"] += 1
                        except Exception as e:
                            logger.debug("Upsert result %s: %s", player_name, e)
                            stats["errors"] += 1
                    conn.commit()
                except Exception as e:
                    logger.warning("fill_tournament_history_from_cp_archives: %s", e)
                    stats["errors"] += 1
                    try:
                        conn.rollback()
                    except Exception as rollback_error:
                        logger.warning("Rollback failed while importing CP archive entry: %s", rollback_error)

            # Upsert tournament-history archive format: tournaments then results
            for row in data_tournament_rows:
                try:
                    conn.execute(text("""
                        INSERT INTO tournament_history
                        (tournament_id, name, year, date, association, status, source_url)
                        VALUES (:tid, :name, :year, CAST(:dt AS date), :assoc, :status, :url)
                        ON CONFLICT (tournament_id) DO UPDATE SET
                            name = COALESCE(EXCLUDED.name, tournament_history.name),
                            year = COALESCE(EXCLUDED.year, tournament_history.year),
                            date = COALESCE(EXCLUDED.date::date, tournament_history.date),
                            association = COALESCE(EXCLUDED.association, tournament_history.association),
                            status = COALESCE(EXCLUDED.status, tournament_history.status),
                            source_url = COALESCE(EXCLUDED.source_url, tournament_history.source_url),
                            updated_at = CURRENT_TIMESTAMP
                    """), {
                        "tid": row["tournament_id"],
                        "name": row["name"],
                        "year": row.get("year"),
                        "dt": str(row["date"]) if row.get("date") else None,
                        "assoc": row["association"],
                        "status": row.get("status") or "completed",
                        "url": row.get("source_url"),
                    })
                    conn.commit()
                    stats["tournaments_updated"] += 1
                except Exception as e:
                    logger.debug("Upsert data tournament %s: %s", row.get("tournament_id"), e)
                    stats["errors"] += 1
                    try:
                        conn.rollback()
                    except Exception as rollback_error:
                        logger.warning(
                            "Rollback failed after data_tournament_rows upsert (%s): %s",
                            row.get("tournament_id"),
                            rollback_error,
                        )

            for row in data_result_rows:
                try:
                    tname = row.get("tournament_name") or row["tournament_id"]
                    if _is_news_article(tname):
                        continue
                    year = row.get("year")
                    assoc = _normalize_association(row.get("association"))
                    tid = _slug_tournament_id(tname, year, assoc)
                    conn.execute(text("""
                        INSERT INTO tournament_history (tournament_id, name, year, association, status)
                        VALUES (:tid, :name, :year, :assoc, 'completed')
                        ON CONFLICT (tournament_id) DO UPDATE SET updated_at = CURRENT_TIMESTAMP
                    """), {"tid": tid, "name": tname[:255], "year": year, "assoc": assoc[:32]})
                    conn.execute(text("""
                        INSERT INTO tournament_results
                        (tournament_id, player_name, placement, points)
                        VALUES (:tid, :player, :placement, :points)
                        ON CONFLICT (tournament_id, player_name) DO UPDATE SET
                            placement = EXCLUDED.placement,
                            points = EXCLUDED.points
                    """), {
                        "tid": tid,
                        "player": row["player_name"],
                        "placement": row["placement"],
                        "points": row["points"],
                    })
                    conn.commit()
                    stats["results_upserted"] += 1
                except Exception as e:
                    logger.debug("Upsert result %s: %s", row.get("player_name"), e)
                    stats["errors"] += 1
                    try:
                        conn.rollback()
                    except Exception as rollback_error:
                        logger.warning(
                            "Rollback failed after data_result_rows upsert (%s): %s",
                            row.get("player_name"),
                            rollback_error,
                        )

        try:
            self.refresh_materialized_views()
        except Exception as e:
            logger.warning("refresh_materialized_views after cp archive fill: %s", e)
        return stats

    def enrich_player_data(self, additional_enrichment_data: Optional[Dict[str, List[Dict]]] = None) -> Dict[str, Any]:
        """
        Enrich player data with cross-system data (license, fargo, country).

        This method implements industry-standard practices:
        - Transaction safety with proper rollback on errors
        - Comprehensive error handling and recovery
        - Detailed logging for monitoring and debugging
        - Data validation and integrity checks
        - Batch processing for performance
        - Idempotent operations (safe to run multiple times)

        Args:
            additional_enrichment_data: Optional dict of system_name -> List[player_records]
                Used to include freshly scraped data (e.g., CP) in enrichment

        Returns:
            Dict[str, Any] containing enrichment statistics and results with keys:
            - processed_players (int): Number of players processed
            - enriched_records (int): Number of records updated
            - fields_filled (int): Number of individual fields filled
            - errors_encountered (int): Number of errors encountered
            - skipped_records (int): Number of records skipped
            - duration_seconds (float): Time taken to complete enrichment
        """
        """
        Enrich player data with cross-system data (license, fargo, country).

        This method implements industry-standard practices:
        - Transaction safety with proper rollback on errors
        - Comprehensive error handling and recovery
        - Detailed logging for monitoring and debugging
        - Data validation and integrity checks
        - Batch processing for performance
        - Idempotent operations (safe to run multiple times)

        Returns:
            Dict containing enrichment statistics and results
        """
        logger.info("Starting cross-system player data enrichment")
        start_time = time.time()

        stats = {
            'processed_players': 0,
            'enriched_records': 0,
            'fields_filled': 0,
            'errors_encountered': 0,
            'skipped_records': 0,
            'duration_seconds': 0.0
        }

        try:
            with self.engine.begin() as conn:  # Transaction context manager
                # Step 1: Identify players eligible for enrichment
                cross_system_players = self._identify_cross_system_players(conn)

                if not cross_system_players:
                    logger.info("No players found for cross-system enrichment")
                    stats['duration_seconds'] = time.time() - start_time
                    return stats

                stats['processed_players'] = len(cross_system_players)
                logger.info(f"Found {len(cross_system_players)} players eligible for enrichment")
                logger.debug(f"Cross-system players: {cross_system_players[:5]}{'...' if len(cross_system_players) > 5 else ''}")

                # Step 2: Process players in batches for better performance
                batch_size = 50
                for i in range(0, len(cross_system_players), batch_size):
                    batch_players = cross_system_players[i:i + batch_size]
                    batch_stats = self._process_enrichment_batch(conn, batch_players, additional_enrichment_data)

                    # Update cumulative stats
                    for key, value in batch_stats.items():
                        if key in stats:
                            stats[key] += value

                    logger.info(f"Processed batch {i//batch_size + 1}: {batch_stats}")

                # Step 3: Final validation and cleanup
                self._validate_enrichment_results(conn, stats)

        except Exception as e:
            logger.error(f"Critical error during enrichment: {e}", exc_info=True)
            logger.warning("Enrichment process failed - check logs for details")
            stats['errors_encountered'] += 1
            raise  # Re-raise to maintain transaction rollback

        finally:
            stats['duration_seconds'] = time.time() - start_time
            logger.info(f"Enrichment completed in {stats['duration_seconds']:.2f}s: "
                       f"{stats['processed_players']} players, "
                       f"{stats['enriched_records']} records enriched, "
                       f"{stats['fields_filled']} fields filled")

        return stats

    def _identify_cross_system_players(self, conn) -> List[str]:
        """
        Identify players who appear in multiple ranking systems and are eligible for enrichment.
        Uses canonical name matching, license-based matching, and Fargo rating validation
        for comprehensive cross-system identification.
        """
        try:
            # Initialize enrichment engine for name normalization
            from database.enrichment_engine import EnrichmentEngine
            enrichment_engine = EnrichmentEngine()

            # Step 1: Find players with canonical name matches across systems
            all_players_result = conn.execute(text("""
                SELECT DISTINCT player_name, ranking_system
                FROM rankings
                ORDER BY player_name
            """))

            # Group players by ranking system
            players_by_system = {}
            for row in all_players_result.fetchall():
                system = row[1]
                if system not in players_by_system:
                    players_by_system[system] = []
                players_by_system[system].append(row[0])

            # Find canonical name matches across systems
            canonical_matches = set()

            # Compare each system pair that should share players
            system_pairs = [
                ('WPBA_Women', 'WPA_Women'),
                ('WPBA_Women', 'Competitors_Pool_Women'),
                ('WPA_Women', 'Competitors_Pool_Women'),
                ('WPA_Men', 'Competitors_Pool_Men'),
                ('WPA_Heyball_Women', 'WPA_Women'),
                ('WPA_Heyball_Men', 'WPA_Men')
            ]

            for system1, system2 in system_pairs:
                if system1 in players_by_system and system2 in players_by_system:
                    system1_players = players_by_system[system1]
                    system2_players = players_by_system[system2]

                    # Find canonical matches between these systems
                    for operator in system1_players:
                        for player2 in system2_players:
                            if enrichment_engine._names_match_canonical(operator, player2):
                                canonical_matches.add(operator)
                                canonical_matches.add(player2)
                                logger.debug(f"Canonical match found: '{operator}' ({system1}) ↔ '{player2}' ({system2})")

            name_based_players = list(canonical_matches)

            # Step 2: Find players with same license across WPBA/WPA systems (license-based matching)
            license_based_result = conn.execute(text("""
                SELECT DISTINCT r1.player_name, r2.player_name
                FROM rankings r1
                JOIN rankings r2 ON r1.license_number = r2.license_number
                    AND r1.license_number IS NOT NULL
                    AND r2.license_number IS NOT NULL
                    AND r1.ranking_system != r2.ranking_system
                    AND r1.player_name != r2.player_name
                WHERE r1.ranking_system LIKE 'WPBA%'
                    AND r2.ranking_system LIKE 'WPA%'
                    AND r1.snapshot_date = (SELECT MAX(snapshot_date) FROM rankings WHERE ranking_system = r1.ranking_system)
                    AND r2.snapshot_date = (SELECT MAX(snapshot_date) FROM rankings WHERE ranking_system = r2.ranking_system)
                ORDER BY r1.player_name
            """))

            # Collect both WPBA and WPA player names from license matches
            license_based_players = []
            for row in license_based_result.fetchall():
                license_based_players.extend([row[0], row[1]])  # Add both player names

            # Combine both lists and deduplicate
            all_players = list(set(name_based_players + license_based_players))

            logger.info(f"Identified {len(all_players)} cross-system players: {len(name_based_players)} by name, {len(license_based_players)} by license")
            if license_based_players:
                logger.info(f"License-matched players: {license_based_players[:5]}{'...' if len(license_based_players) > 5 else ''}")

            return all_players

        except Exception as e:
            logger.error(f"Failed to identify cross-system players: {e}")
            raise

    def _process_enrichment_batch(self, conn, player_names: List[str], additional_enrichment_data: Optional[Dict[str, List[Dict]]] = None) -> Dict[str, int]:
        """
        Process a batch of players for enrichment with proper error isolation.
        Each player is processed independently to prevent one failure from affecting others.
        """
        """
        Process a batch of players for enrichment with proper error isolation.
        Each player is processed independently to prevent one failure from affecting others.
        """
        batch_stats = {
            'enriched_records': 0,
            'fields_filled': 0,
            'errors_encountered': 0,
            'skipped_records': 0
        }

        for player_name in player_names:
            try:
                player_stats = self._enrich_single_player(conn, player_name, additional_enrichment_data)
                for key, value in player_stats.items():
                    if key in batch_stats:
                        batch_stats[key] += value

            except Exception as e:
                logger.warning(f"Failed to enrich player '{player_name}': {e}")
                batch_stats['errors_encountered'] += 1

        return batch_stats

    def _enrich_single_player(self, conn, player_name: str, additional_enrichment_data: Optional[Dict[str, List[Dict]]] = None) -> Dict[str, int]:
        """
        Enrich data for a single player across all their ranking records.
        For license-matched players, includes records from players with matching licenses.
        Implements data validation, conflict resolution, and audit logging.
        """
        # Fetch all records for this player (by name)
        result = conn.execute(text("""
            SELECT
                id, player_name, ranking_system, snapshot_date,
                license_number, fargo_rating, country,
                created_at
            FROM rankings
            WHERE player_name = :name
            ORDER BY snapshot_date DESC, ranking_system
        """), {'name': player_name})

        records = result.fetchall()

        # If this player was identified via license matching, also fetch records
        # from players with the same license number (for cross-system enrichment)
        license_records = []
        if records:
            # Get the license from the first record
            first_license = records[0][4]  # license_number column
            if first_license:
                license_result = conn.execute(text("""
                    SELECT
                        id, player_name, ranking_system, snapshot_date,
                        license_number, fargo_rating, country,
                        created_at
                    FROM rankings
                    WHERE license_number = :license
                        AND ranking_system != :exclude_system
                        AND snapshot_date = (SELECT MAX(snapshot_date) FROM rankings WHERE ranking_system = rankings.ranking_system)
                    ORDER BY snapshot_date DESC, ranking_system
                """), {'license': first_license, 'exclude_system': records[0][2]})  # exclude the current player's system

                license_records = license_result.fetchall()
                if license_records:
                    logger.debug(f"Found {len(license_records)} additional license-matched records for {player_name}")

        # Combine name-based and license-based records
        all_records = records + license_records

        if len(all_records) < 2:
            logger.debug(f"Skipping player '{player_name}': only {len(all_records)} records (name: {len(records)}, license: {len(license_records)})")
            return {'skipped_records': len(all_records)}

        # Analyze data across all systems for this player
        enrichment_data = self._analyze_player_data(records, additional_enrichment_data)
        if not enrichment_data['has_enrichable_data']:
            logger.debug(f"Skipping player '{player_name}': no enrichable data available")
            return {'skipped_records': len(all_records)}

        # Apply enrichment updates
        return self._apply_player_enrichment(conn, records, enrichment_data, player_name)

    def _analyze_player_data(self, records: List, additional_enrichment_data: Optional[Dict[str, List[Dict]]] = None) -> Dict[str, Any]:
        """
        Analyze player data across systems using intelligent enrichment engine.
        Implements sophisticated relationship-based data selection and conflict resolution.
        """
        from database.enrichment_engine import enrichment_engine

        # Convert records to dict format expected by enrichment engine
        player_records = []
        for record in records:
            record_id, name, system, date, license, fargo, country, created = record
            player_records.append({
                'id': record_id,
                'player_name': name,
                'ranking_system': system,
                'snapshot_date': date,
                'license_number': license,
                'fargo_rating': fargo,
                'country': country,
                'rank': None,  # Not needed for enrichment analysis
                'points': None  # Not needed for enrichment analysis
            })

        player_name = records[0][1] if records else ""

        # Include additional enrichment data (e.g., External Pool) if available
        if additional_enrichment_data:
            for system_name, system_records in additional_enrichment_data.items():
                # Find records for this player in the additional data
                player_additional_records = [
                    record for record in system_records
                    if record.get('name', '').lower() == player_name.lower()
                ]
                for additional_record in player_additional_records:
                    # Convert to the format expected by enrichment engine
                    additional_record_dict = {
                        'id': None,  # No database ID for fresh data
                        'player_name': additional_record.get('name', player_name),
                        'ranking_system': system_name,
                        'snapshot_date': datetime.now().date(),  # Use current date for fresh data
                        'license_number': additional_record.get('license_number'),
                        'fargo_rating': additional_record.get('fargo_rating'),
                        'country': additional_record.get('country'),
                        'rank': additional_record.get('rank'),
                        'points': additional_record.get('points', 0)
                    }
                    player_records.append(additional_record_dict)
                    logger.debug(f"Included additional {system_name} data for {player_name}")

        # Get intelligent enrichment recommendations
        enrichment_recommendations = enrichment_engine.enrich_player_data(player_name, player_records)

        # Convert recommendations to the expected analysis format
        analysis = {
            'best_license': None,
            'best_fargo': None,
            'best_country': None,
            'has_enrichable_data': False,
            'data_sources': set(),
            'quality_score': 0.0,
            'enrichment_recommendations': enrichment_recommendations,
            'high_confidence_updates': 0,
            'medium_confidence_updates': 0
        }

        # Validate matches using Fargo ratings as additional confirmation
        if player_records and len(player_records) > 1:
            is_valid_match = enrichment_engine._validate_match_with_fargo_rating(player_records)
            if not is_valid_match:
                logger.warning(f"Fargo rating validation failed for player '{player_name}' - skipping enrichment")
                # Clear recommendations for invalid matches
                enrichment_recommendations = {}
                analysis['enrichment_recommendations'] = {}
                analysis['high_confidence_updates'] = 0
                analysis['medium_confidence_updates'] = 0

        # Extract best values and track confidence levels
        license_data = {}
        fargo_data = {}
        country_data = {}

        for key, recommendation in enrichment_recommendations.items():
            target_sys = recommendation['target_system']
            field_name = recommendation['field']
            value = recommendation['value']
            confidence = recommendation['confidence']

            analysis['data_sources'].add(recommendation['source_system'])
            analysis['data_sources'].add(target_sys)

            if confidence >= 0.8:
                analysis['high_confidence_updates'] += 1
            else:
                analysis['medium_confidence_updates'] += 1

            # Store the recommended values for compatibility with existing code
            if field_name == 'license_number':
                license_data[target_sys] = value
                if not analysis['best_license']:
                    analysis['best_license'] = value
            elif field_name == 'fargo_rating':
                fargo_data[target_sys] = value
                if analysis['best_fargo'] is None or value > analysis['best_fargo']:
                    analysis['best_fargo'] = value
            elif field_name == 'country':
                country_data[target_sys] = value
                if not analysis['best_country']:
                    analysis['best_country'] = value

        analysis['has_enrichable_data'] = bool(enrichment_recommendations)

        # Calculate quality score based on confidence and data sources
        total_updates = analysis['high_confidence_updates'] + analysis['medium_confidence_updates']
        if total_updates > 0:
            confidence_ratio = analysis['high_confidence_updates'] / total_updates
            source_diversity = min(len(analysis['data_sources']), 5) / 5.0  # Max score at 5+ sources
            analysis['quality_score'] = (confidence_ratio * 0.7) + (source_diversity * 0.3)
        else:
            analysis['quality_score'] = 0.0

        return analysis

    def _apply_player_enrichment(self, conn, records: List, enrichment_data: Dict, player_name: str) -> Dict[str, int]:
        """
        Apply intelligent enrichment updates using recommendations from the enrichment engine.
        Each update includes confidence scoring and relationship-based validation.
        """
        stats = {'enriched_records': 0, 'fields_filled': 0}

        # Get the enrichment recommendations
        recommendations = enrichment_data.get('enrichment_recommendations', {})

        # Group recommendations by target record for batch processing
        record_updates = {}

        for recommendation_key, recommendation in recommendations.items():
            target_sys = recommendation['target_system']
            field_name = recommendation['field']
            value = recommendation['value']
            confidence = recommendation['confidence']

            # Immutable identity fields are managed by WPA lock tables.
            if field_name in {"license_number", "country"}:
                continue

            # Only apply high-confidence recommendations (configurable threshold)
            if confidence < 0.7:
                logger.debug(f"Skipping low-confidence enrichment for {player_name} in {target_sys}: {field_name} (confidence: {confidence:.2f})")
                continue

            # Find the target record
            for record in records:
                record_id, name, system, date, license, fargo, country, created = record
                if system == target_sys:
                    if record_id not in record_updates:
                        record_updates[record_id] = {}

                    # Check if this field needs updating (handle different field name mappings)
                    current_value = None
                    if field_name == 'license_number':
                        current_value = license
                    elif field_name == 'fargo_rating':
                        current_value = fargo
                    elif field_name == 'country':
                        current_value = country

                    # Only update if field is missing or empty
                    if current_value is None or current_value == '':
                        record_updates[record_id][field_name] = value
                    break

        # Apply updates in batch
        for record_id, update_fields in record_updates.items():
            if update_fields:
                try:
                    # Build dynamic UPDATE statement
                    set_parts = []
                    params = {'record_id': record_id}

                    for field_name, field_value in update_fields.items():
                        set_parts.append(f"{field_name} = :{field_name}")
                        params[field_name] = field_value

                    set_clause = ", ".join(set_parts)

                    conn.execute(text(f"""
                        UPDATE rankings
                        SET {set_clause}
                        WHERE id = :record_id
                    """), params)

                    stats['enriched_records'] += 1
                    stats['fields_filled'] += len(update_fields)

                    logger.debug(f"Applied intelligent enrichment to record {record_id} for {player_name}: {update_fields}")

                except Exception as e:
                    logger.warning(f"Failed to apply intelligent enrichment to record {record_id} for {player_name}: {e}")
                    continue

        return stats

    def _validate_enrichment_results(self, conn, stats: Dict) -> None:
        """
        Validate enrichment results and log summary statistics.
        Performs sanity checks to ensure data integrity.
        """
        try:
            # Verify enrichment didn't break anything
            result = conn.execute(text("""
                SELECT
                    COUNT(*) as total_records,
                    COUNT(CASE WHEN license_number IS NOT NULL THEN 1 END) as licensed_records,
                    COUNT(CASE WHEN fargo_rating IS NOT NULL THEN 1 END) as fargo_records,
                    COUNT(CASE WHEN country IS NOT NULL THEN 1 END) as country_records
                FROM rankings
            """))

            row = result.fetchone()
            logger.info(f"Post-enrichment validation: {row[0]} total records, "
                       f"{row[1]} with licenses, {row[2]} with Fargo ratings, {row[3]} with countries")

        except Exception as e:
            logger.warning(f"Enrichment validation failed: {e}")
            # Don't raise - validation failure shouldn't break enrichment
    
    def refresh_materialized_views(self) -> Dict:
        """Refresh materialized views for fast read paths"""
        logger.info("Refreshing materialized views...")
        
        views_refreshed = []
        errors = []
        
        with self.engine.connect() as conn:
            # Refresh mv_latest_rankings
            try:
                conn.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_latest_rankings"))
                views_refreshed.append('mv_latest_rankings')
                logger.info("Refreshed materialized view: mv_latest_rankings")
            except Exception as e:
                error_msg = f"mv_latest_rankings: {str(e)}"
                errors.append(error_msg)
                logger.error(f"Failed to refresh mv_latest_rankings: {e}")
                try:
                    conn.rollback()
                except Exception as rollback_error:
                    logger.warning("Rollback failed after mv_latest_rankings refresh error: %s", rollback_error)
            
            # Refresh mv_tournament_history_recent
            try:
                view_exists = conn.execute(
                    text(
                        "SELECT 1 FROM pg_matviews WHERE schemaname = 'public' AND matviewname = :name"
                    ),
                    {"name": "mv_tournament_history_recent"},
                ).first()
                if view_exists:
                    conn.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_tournament_history_recent"))
                    views_refreshed.append('mv_tournament_history_recent')
                    logger.info("Refreshed materialized view: mv_tournament_history_recent")
                else:
                    logger.info("Materialized view mv_tournament_history_recent not found; skipping refresh")
            except Exception as e:
                error_msg = f"mv_tournament_history_recent: {str(e)}"
                errors.append(error_msg)
                logger.error(f"Failed to refresh mv_tournament_history_recent: {e}")
                try:
                    conn.rollback()
                except Exception as rollback_error:
                    logger.warning(
                        "Rollback failed after mv_tournament_history_recent refresh error: %s",
                        rollback_error,
                    )
            
            conn.commit()
        
        return {
            'views_refreshed': views_refreshed,
            'count': len(views_refreshed),
            'errors': errors
        }

    def delete_news_from_tournament_history(self) -> Dict[str, Any]:
        """
        Delete rows from tournament_history that are news/events or rankings snapshots
        (so Tournament History list and Leaderboard show only real tournaments).
        tournament_results are removed by ON DELETE CASCADE. Refreshes mv_tournament_history_recent.
        """
        with self.engine.connect() as conn:
            result = conn.execute(text("""
                DELETE FROM tournament_history th
                WHERE th.tournament_id LIKE 'rankings_snapshot%'
                   OR th.name LIKE '% Rankings (%'
                   OR th.name ILIKE '% News%'
                   OR th.name ILIKE '% Events'
                   OR LOWER(TRIM(th.name)) IN ('wpba events', 'latest wpa news', 'wpa news', 'wpba news')
                   OR (th.name ILIKE '%CELEBRATES%' AND th.name ILIKE '%LOOKS FORWARD%')
                   OR (th.name ILIKE '%Chinese Billiards%' AND th.name ILIKE '%Come Home%')
                   OR (
                       th.association = 'WPA'
                       AND EXISTS (
                           SELECT 1 FROM tournament_history m
                           WHERE LOWER(TRIM(m.name)) = LOWER(TRIM(th.name))
                             AND m.association = 'WPA Men'
                       )
                       AND EXISTS (
                           SELECT 1 FROM tournament_history w
                           WHERE LOWER(TRIM(w.name)) = LOWER(TRIM(th.name))
                             AND w.association = 'WPA Women'
                       )
                   )
            """))
            deleted = result.rowcount
            conn.commit()
            try:
                conn.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_tournament_history_recent"))
                conn.commit()
            except Exception as e:
                logger.warning("Refresh mv_tournament_history_recent after delete_news: %s", e)
            return {"deleted": deleted}
    
    def get_tournament_history_stats(self) -> Dict:
        """Get tournament history statistics for all tournaments"""
        with self.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT 
                    name,
                    COUNT(*) as total_tournaments,
                    MIN(year) as first_year,
                    MAX(year) as last_year
                FROM tournament_history
                WHERE name IS NOT NULL
                GROUP BY name
            """))
            
            stats = {}
            for row in result.fetchall():
                name = row[0]
                stats[name] = {
                    'total_tournaments': row[1],
                    'first_year': row[2],
                    'last_year': row[3]
                }
            
            return stats

    def get_tournament_performance(self, tournament_id: str) -> Dict[str, Any]:
        """
        Build per-player performance summary for one tournament using tournament_results
        (placements) and tournament_history_matches (match-level outcomes/scores).
        """
        with self.engine.connect() as conn:
            meta = conn.execute(
                text(
                    """
                    SELECT tournament_id, name, association, date
                    FROM tournament_history
                    WHERE tournament_id = :tournament_id
                    LIMIT 1
                    """
                ),
                {"tournament_id": tournament_id},
            ).mappings().first()
            if not meta:
                return {}

            rows = conn.execute(
                text(
                    """
                    WITH field_size_cte AS (
                        SELECT COUNT(DISTINCT player_name)::int AS field_size
                        FROM tournament_results
                        WHERE tournament_id = :tournament_id
                    ),
                    placements AS (
                        SELECT
                            player_name,
                            MIN(placement)::int AS placement
                        FROM tournament_results
                        WHERE tournament_id = :tournament_id
                          AND player_name IS NOT NULL
                          AND TRIM(player_name) <> ''
                        GROUP BY player_name
                    ),
                    match_sides AS (
                        SELECT
                            operator_name AS player_name,
                            CASE WHEN winner_name = operator_name THEN 1 ELSE 0 END AS won,
                            COALESCE(operator_score, 0)::int AS points_for,
                            COALESCE(player2_score, 0)::int AS points_against
                        FROM tournament_history_matches
                        WHERE tournament_id = :tournament_id
                          AND operator_name IS NOT NULL
                          AND player2_name IS NOT NULL
                          AND TRIM(operator_name) <> ''
                          AND TRIM(player2_name) <> ''
                        UNION ALL
                        SELECT
                            player2_name AS player_name,
                            CASE WHEN winner_name = player2_name THEN 1 ELSE 0 END AS won,
                            COALESCE(player2_score, 0)::int AS points_for,
                            COALESCE(operator_score, 0)::int AS points_against
                        FROM tournament_history_matches
                        WHERE tournament_id = :tournament_id
                          AND operator_name IS NOT NULL
                          AND player2_name IS NOT NULL
                          AND TRIM(operator_name) <> ''
                          AND TRIM(player2_name) <> ''
                    ),
                    match_agg AS (
                        SELECT
                            player_name,
                            COUNT(*)::int AS matches_played,
                            SUM(won)::int AS matches_won,
                            (COUNT(*) - SUM(won))::int AS matches_lost,
                            SUM(points_for)::int AS points_for,
                            SUM(points_against)::int AS points_against
                        FROM match_sides
                        GROUP BY player_name
                    ),
                    player_union AS (
                        SELECT player_name FROM placements
                        UNION
                        SELECT player_name FROM match_agg
                    )
                    SELECT
                        pu.player_name,
                        p.placement,
                        ma.matches_played,
                        ma.matches_won,
                        ma.matches_lost,
                        ma.points_for,
                        ma.points_against,
                        fs.field_size
                    FROM player_union pu
                    LEFT JOIN placements p ON p.player_name = pu.player_name
                    LEFT JOIN match_agg ma ON ma.player_name = pu.player_name
                    CROSS JOIN field_size_cte fs
                    ORDER BY
                        p.placement ASC NULLS LAST,
                        COALESCE(ma.matches_won, 0) DESC,
                        pu.player_name ASC
                    """
                ),
                {"tournament_id": tournament_id},
            ).mappings().all()

            out_players: List[Dict[str, Any]] = []
            field_size = int(rows[0]["field_size"] or 0) if rows else 0
            for r in rows:
                played = int(r["matches_played"] or 0)
                won = int(r["matches_won"] or 0)
                lost = int(r["matches_lost"] or 0)
                pf = int(r["points_for"] or 0)
                pa = int(r["points_against"] or 0)
                placement = int(r["placement"]) if r["placement"] is not None else None
                finish_percentile: Optional[float] = None
                if placement is not None and field_size > 1:
                    finish_percentile = round(((field_size - placement) * 100.0) / (field_size - 1), 1)
                elif placement is not None and field_size == 1:
                    finish_percentile = 100.0
                win_rate = round((won / played) * 100.0, 1) if played > 0 else None
                out_players.append(
                    {
                        "player_name": r["player_name"],
                        "placement": placement,
                        "finish_percentile": finish_percentile,
                        "matches_played": played,
                        "matches_won": won,
                        "matches_lost": lost,
                        "win_rate": win_rate,
                        "points_for": pf,
                        "points_against": pa,
                        "score_diff": pf - pa,
                    }
                )

            return {
                "tournament_id": meta["tournament_id"],
                "tournament_name": meta["name"],
                "association": meta["association"],
                "tournament_date": meta["date"],
                "field_size": field_size,
                "players": out_players,
            }

    @staticmethod
    def _nonempty_tab_schedule(tab_schedule: Any) -> bool:
        if not tab_schedule:
            return False
        if isinstance(tab_schedule, dict):
            br = tab_schedule.get("bracket_rows") or []
            mr = tab_schedule.get("match_rows") or []
            return len(br) > 0 or len(mr) > 0
        if isinstance(tab_schedule, list):
            return len(tab_schedule) > 0
        return False

    @staticmethod
    def _nonempty_tab_live_scores(tab_live: Any) -> bool:
        if not tab_live:
            return False
        if isinstance(tab_live, dict):
            br = tab_live.get("bracket_matches") or []
            mr = tab_live.get("matches") or []
            return len(br) > 0 or len(mr) > 0
        if isinstance(tab_live, list):
            return len(tab_live) > 0
        return False

    @staticmethod
    def _nonempty_tab_performance(tab_perf: Any) -> bool:
        if not tab_perf:
            return False
        if isinstance(tab_perf, dict):
            br = tab_perf.get("bracket_matches") or []
            mr = tab_perf.get("matches") or []
            return len(br) > 0 or len(mr) > 0
        if isinstance(tab_perf, list):
            return len(tab_perf) > 0
        return False

    @staticmethod
    def _tab_coverage_flags_from_parts(
        overview: Any,
        players: List[Any],
        brackets: List[Any],
        matches: List[Any],
        *,
        tab_schedule: Any = None,
        tab_live_scores: Any = None,
        tab_stats: Any = None,
        tab_performance: Any = None,
    ) -> Dict[str, Any]:
        """Compute has_* flags and counts from archived tournament tab payloads."""
        overview = overview or {}
        players = players or []
        brackets = brackets or []
        matches = matches or []

        has_schedule = any((b or {}).get("scheduled_time") for b in brackets) or any(
            (m or {}).get("scheduled_time") for m in matches
        )
        has_schedule = has_schedule or PostgresManager._nonempty_tab_schedule(tab_schedule)

        has_live_scores = any(
            str((m or {}).get("status") or "").lower() in {"in_progress", "live"} for m in matches
        )
        has_live_scores = has_live_scores or PostgresManager._nonempty_tab_live_scores(tab_live_scores)

        has_stats = any(
            (p or {}).get("fargo_robustness") is not None
            or (p or {}).get("skill_level") not in (None, "")
            or (p or {}).get("points") is not None
            for p in players
        )
        if tab_stats is not None and isinstance(tab_stats, list) and len(tab_stats) > 0:
            has_stats = True

        has_performance = any(
            (m or {}).get("player_score") is not None or (m or {}).get("opponent_score") is not None
            for m in matches
        ) or any(
            (b or {}).get("challenger1_score") is not None or (b or {}).get("challenger2_score") is not None
            for b in brackets
        )
        has_performance = has_performance or PostgresManager._nonempty_tab_performance(tab_performance)

        return {
            "has_overview": bool(overview),
            "has_bracket": len(brackets) > 0,
            "has_live_scores": has_live_scores,
            "has_matches": len(matches) > 0,
            "has_schedule": has_schedule,
            "has_players": len(players) > 0,
            "has_stats": has_stats,
            "has_performance": has_performance,
            "players_count": len(players),
            "bracket_matches_count": len(brackets),
            "matches_count": len(matches),
        }

    def get_tournament_tab_coverage(self, tournament_id: str, *, include_payload: bool = False) -> Dict[str, Any]:
        """
        Return latest archived tournament tab snapshot for one tournament_id.
        JSON archives are read from EXTERNALPOOL_TAB_ARCHIVE_DIR (default /tmp/externalpool_tabs).
        """
        with self.engine.connect() as conn:
            meta = conn.execute(
                text(
                    """
                    SELECT tournament_id, name
                    FROM tournament_history
                    WHERE tournament_id = :tournament_id
                    LIMIT 1
                    """
                ),
                {"tournament_id": tournament_id},
            ).mappings().first()
            if not meta:
                return {}

        archive_dir = Path(os.getenv("EXTERNALPOOL_TAB_ARCHIVE_DIR", "/tmp/externalpool_tabs"))
        pattern = f"{tournament_id}_*.json"
        files = sorted(archive_dir.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True) if archive_dir.exists() else []
        if not files:
            return {
                "tournament_id": meta["tournament_id"],
                "tournament_name": meta["name"],
                "archive_dir": str(archive_dir),
            }

        latest = files[0]
        try:
            payload = json.loads(latest.read_text(encoding="utf-8"))
        except Exception:
            return {
                "tournament_id": meta["tournament_id"],
                "tournament_name": meta["name"],
                "archive_dir": str(archive_dir),
                "latest_archive_file": latest.name,
            }

        players = payload.get("players") or []
        brackets = payload.get("brackets") or []
        matches = payload.get("matches") or []
        overview = payload.get("tournament_overview") or {}
        tab_schedule = payload.get("tab_schedule")
        tab_live_scores = payload.get("tab_live_scores")
        tab_stats = payload.get("tab_stats")
        tab_performance = payload.get("tab_performance")

        flags = self._tab_coverage_flags_from_parts(
            overview,
            players,
            brackets,
            matches,
            tab_schedule=tab_schedule,
            tab_live_scores=tab_live_scores,
            tab_stats=tab_stats,
            tab_performance=tab_performance,
        )

        out: Dict[str, Any] = {
            "tournament_id": meta["tournament_id"],
            "tournament_name": meta["name"],
            "latest_archive_file": latest.name,
            "captured_at": payload.get("captured_at"),
            "archive_dir": str(archive_dir),
            **flags,
        }
        if include_payload:
            out["tab_overview"] = overview if isinstance(overview, dict) else {}
            out["tab_players"] = players if isinstance(players, list) else []
            out["tab_brackets"] = brackets if isinstance(brackets, list) else []
            out["tab_matches"] = matches if isinstance(matches, list) else []
            out["tab_schedule"] = tab_schedule
            out["tab_live_scores"] = tab_live_scores
            out["tab_stats"] = tab_stats
            out["tab_performance"] = tab_performance
        return out

    def get_tournament_tab_coverage_list(
        self,
        *,
        limit: int = 50,
        association: Optional[str] = None,
        year: Optional[int] = None,
        incomplete_only: bool = False,
    ) -> Dict[str, Any]:
        """
        List tab-coverage snapshots for recent tournaments.
        """
        limit = max(1, min(int(limit), 300))
        archive_dir = Path(os.getenv("EXTERNALPOOL_TAB_ARCHIVE_DIR", "/tmp/externalpool_tabs"))

        query = """
            SELECT tournament_id, name, association, date
            FROM tournament_history
            WHERE name IS NOT NULL
              AND date IS NOT NULL
        """
        params: Dict[str, Any] = {"limit": limit}
        if association:
            query += " AND association = :association"
            params["association"] = association
        if year:
            query += " AND EXTRACT(YEAR FROM date) = :year"
            params["year"] = int(year)
        query += " ORDER BY date DESC, tournament_id DESC LIMIT :limit"

        def _coverage_from_payload(meta_row: Dict[str, Any], payload: Dict[str, Any], latest_name: str) -> Dict[str, Any]:
            players = payload.get("players") or []
            brackets = payload.get("brackets") or []
            matches = payload.get("matches") or []
            overview = payload.get("tournament_overview") or {}
            flags = PostgresManager._tab_coverage_flags_from_parts(
                overview,
                players,
                brackets,
                matches,
                tab_schedule=payload.get("tab_schedule"),
                tab_live_scores=payload.get("tab_live_scores"),
                tab_stats=payload.get("tab_stats"),
                tab_performance=payload.get("tab_performance"),
            )
            return {
                "tournament_id": meta_row["tournament_id"],
                "tournament_name": meta_row["name"],
                "association": meta_row.get("association"),
                "tournament_date": meta_row.get("date"),
                "latest_archive_file": latest_name,
                "captured_at": payload.get("captured_at"),
                "archive_dir": str(archive_dir),
                **flags,
            }

        with self.engine.connect() as conn:
            rows = conn.execute(text(query), params).mappings().all()

        items: List[Dict[str, Any]] = []
        for row in rows:
            files: List[Path] = []
            if archive_dir.exists():
                files = sorted(
                    archive_dir.glob(f"{row['tournament_id']}_*.json"),
                    key=lambda p: p.stat().st_mtime,
                    reverse=True,
                )
            if not files:
                record = {
                    "tournament_id": row["tournament_id"],
                    "tournament_name": row["name"],
                    "association": row.get("association"),
                    "tournament_date": row.get("date"),
                    "archive_dir": str(archive_dir),
                    "has_overview": False,
                    "has_bracket": False,
                    "has_live_scores": False,
                    "has_matches": False,
                    "has_schedule": False,
                    "has_players": False,
                    "has_stats": False,
                    "has_performance": False,
                    "players_count": 0,
                    "bracket_matches_count": 0,
                    "matches_count": 0,
                }
            else:
                latest = files[0]
                try:
                    payload = json.loads(latest.read_text(encoding="utf-8"))
                    record = _coverage_from_payload(dict(row), payload, latest.name)
                except Exception:
                    record = {
                        "tournament_id": row["tournament_id"],
                        "tournament_name": row["name"],
                        "association": row.get("association"),
                        "tournament_date": row.get("date"),
                        "latest_archive_file": latest.name,
                        "archive_dir": str(archive_dir),
                        "has_overview": False,
                        "has_bracket": False,
                        "has_live_scores": False,
                        "has_matches": False,
                        "has_schedule": False,
                        "has_players": False,
                        "has_stats": False,
                        "has_performance": False,
                        "players_count": 0,
                        "bracket_matches_count": 0,
                        "matches_count": 0,
                    }

            if incomplete_only:
                complete = (
                    record.get("has_overview")
                    and record.get("has_bracket")
                    and record.get("has_matches")
                    and record.get("has_schedule")
                    and record.get("has_players")
                    and record.get("has_stats")
                    and record.get("has_performance")
                )
                if complete:
                    continue
            items.append(record)

        return {"total": len(items), "items": items}

    def get_staleness_info(self, ranking_system: str, stale_after_hours: int = 24) -> dict:
        """Get staleness information for a ranking system"""
        from datetime import datetime, timedelta
        last_date = self.get_last_snapshot_date(ranking_system)
        if not last_date:
            return {"is_stale": True, "last_update": None, "hours_ago": None}
        
        # last_date is already a date object, convert to datetime at midnight
        last_update = datetime.combine(last_date, datetime.min.time())
        hours_ago = (datetime.now() - last_update).total_seconds() / 3600
        is_stale = hours_ago > stale_after_hours
        return {
            "is_stale": is_stale,
            "last_update": last_date,
            "hours_ago": round(hours_ago, 2)
        }


# Singleton instance
_postgres_manager = None

def get_postgres_manager() -> PostgresManager:
    """Get or create PostgresManager singleton"""
    global _postgres_manager
    if _postgres_manager is None:
        _postgres_manager = PostgresManager()
    return _postgres_manager


__all__ = ['PostgresManager', 'get_postgres_manager']
