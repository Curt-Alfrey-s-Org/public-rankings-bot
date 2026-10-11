#!/usr/bin/env python3
"""
Cross-fill data for "obviously" the same person across systems when exact name differs.

E.g. "Margarita" in WPBA and "Margarita Fefilova" in WPA are the same person (no other
Margarita in either list). Matches when one normalized name is a prefix of the other
and the stem is unique per system, then merges best license/Fargo/country across the cluster.

Run after enrich_cross_system_data.py (which handles exact name matches).
Uses DATABASE_URL. Use --execute to apply.
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def _norm(name: str) -> str:
    return (name or "").strip().lower()


# Enhanced same-person name pairs combining manual mappings with historical patterns
OBVIOUS_SAME_PERSON_PAIRS: set[tuple[str, str]] = {
    # Manual mappings
    ("margaret fefilova-styer", "fefilova, margarita"),
    ("margaret fefilova-styer", "margarita fefilova"),
    ("margarita fefilova", "fefilova, margarita"),

    # Historical FairMatch scraper patterns - common name format variations
    # These represent patterns found during historical FargoRate lookups
    ("alex kazakis", "kazakis, alexander"),
    ("alexander kazakis", "kazakis, alex"),
    ("mike ferrell", "ferrell, michael"),
    ("michael ferrell", "ferrell, mike"),
    ("dave yap", "yap, david"),
    ("david yap", "yap, dave"),
    ("steve lipsky", "lipsky, stephen"),
    ("stephen lipsky", "lipsky, steve"),
}


def _generate_name_variants(name: str) -> set[str]:
    """Generate name variants using historical FairMatch scraper patterns."""
    variants = set()
    name = name.strip()

    if "," in name:
        # Format: "Last, First"
        comma_parts = name.split(",", 1)
        if len(comma_parts) == 2:
            last_name = comma_parts[0].strip()
            first_name = comma_parts[1].strip()
            variants.add(f"{first_name} {last_name}")  # "First Last"
            variants.add(name)  # Original "Last, First"
    else:
        # Standard format "First Last" or space-separated
        variants.add(name)  # Original
        parts = name.split()
        if len(parts) >= 2:
            # Reverse: "Last First" or "Last, First"
            variants.add(" ".join(reversed(parts)))
            variants.add(", ".join(reversed(parts)))

    return variants

def _is_obvious_pair(name_a: str, name_b: str, by_system: dict) -> bool:
    """Enhanced obvious pair detection using historical patterns."""
    na, nb = _norm(name_a), _norm(name_b)

    # Exact match
    if na == nb:
        return True

    # Known manual mappings
    if (na, nb) in OBVIOUS_SAME_PERSON_PAIRS or (nb, na) in OBVIOUS_SAME_PERSON_PAIRS:
        return True

    # Historical name variant matching - check if any variant combinations match
    variants_a = _generate_name_variants(na)
    variants_b = _generate_name_variants(nb)

    # Check if any variant from A matches any variant from B
    if variants_a & variants_b:
        return True

    # Original stem-based logic for additional matches
    if na.startswith(nb) or nb.startswith(na):
        shorter = na if len(na) <= len(nb) else nb
        # Stem = first word of shorter (e.g. "margarita")
        stem = shorter.split()[0] if shorter.split() else shorter
        # In each system, count names that have this stem as prefix
        for system, names in by_system.items():
            with_stem = [n for n in names if _norm(n).startswith(stem) or _norm(n) == stem]
            if len(with_stem) > 1:
                # Ambiguous in this system (e.g. two "Kelly"s)
                return False
        return True

    return False


def get_latest_records(conn) -> list[dict]:
    """All rankings rows in latest snapshot per (player_name, ranking_system)."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, player_name, ranking_system, license_number, fargo_rating, country
        FROM rankings r
        WHERE r.snapshot_date = (
            SELECT MAX(r2.snapshot_date)
            FROM rankings r2
            WHERE r2.player_name = r.player_name AND r2.ranking_system = r.ranking_system
        )
        ORDER BY r.player_name, r.ranking_system
        """
    )
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def find_obvious_clusters(records: list[dict]) -> list[list[dict]]:
    """Group records into clusters that are obviously the same person across systems."""
    by_system: dict[str, list[str]] = defaultdict(list)
    name_to_records: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        name = (r.get("player_name") or "").strip()
        sys_ = (r.get("ranking_system") or "").strip()
        if not name or not sys_:
            continue
        by_system[sys_].append(name)
        key = (name, sys_)
        name_to_records[key].append(r)

    # Build pairs: (name_a, sys_a) <-> (name_b, sys_b) where obviously same
    pairs: set[tuple[tuple[str, str], tuple[str, str]]] = set()
    systems = list(by_system.keys())
    for i, sys_a in enumerate(systems):
        for sys_b in systems[i + 1 :]:
            for name_a in by_system[sys_a]:
                for name_b in by_system[sys_b]:
                    if _is_obvious_pair(name_a, name_b, by_system):
                        pairs.add(((name_a, sys_a), (name_b, sys_b)))

    # Union-find: merge transitive clusters
    parent: dict[tuple[str, str], tuple[str, str]] = {}

    def find(x: tuple[str, str]) -> tuple[str, str]:
        if x not in parent:
            parent[x] = x
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]

    def union(a: tuple[str, str], b: tuple[str, str]) -> None:
        pa, pb = find(a), find(b)
        if pa != pb:
            parent[pa] = pb

    for (a, b) in pairs:
        union(a, b)

    all_keys = [(n, s) for s, names in by_system.items() for n in set(names)]
    clusters: dict[tuple[str, str], list[tuple[str, str]]] = defaultdict(list)
    for key in all_keys:
        root = find(key)
        clusters[root].append(key)

    # Each cluster: list of records (by id) to merge
    out: list[list[dict]] = []
    seen_ids: set[int] = set()
    for root, members in clusters.items():
        if len(members) < 2:
            continue
        cluster_records: list[dict] = []
        for (name, sys_) in members:
            key = (name, sys_)
            for r in name_to_records.get(key, []):
                rid = r.get("id")
                if rid is not None and rid not in seen_ids:
                    seen_ids.add(rid)
                    cluster_records.append(r)
        if len(cluster_records) >= 2:
            out.append(cluster_records)
    return out


def best_values(records: list[dict]) -> dict:
    """Best license, fargo, country across records (same logic as enrich_cross_system_data)."""
    best_license = None
    best_fargo = None
    best_country = None
    for r in records:
        ln = (r.get("license_number") or "").strip() or None
        if ln and not best_license:
            best_license = ln
        fr = r.get("fargo_rating")
        if fr is not None:
            try:
                f = float(fr)
                if best_fargo is None or f > best_fargo:
                    best_fargo = f
            except (TypeError, ValueError) as e:
                logger.debug("Could not parse fargo_rating '%s' for record id %s: %s", fr, r.get("id"), e)
        co = (r.get("country") or "").strip() or None
        if co and not best_country:
            best_country = co
    return {"license_number": best_license, "fargo_rating": best_fargo, "country": best_country}


def enrich_cluster(cursor, cluster: list[dict], dry_run: bool, has_source_cols: bool) -> int:
    """Apply best values to all records in cluster; remember source as obvious_same_person."""
    best = best_values(cluster)
    updated = 0
    for r in cluster:
        rid = r.get("id")
        if rid is None:
            continue
        set_clauses = []
        params = []
        if not (r.get("license_number") or "").strip() and best.get("license_number"):
            set_clauses.append("license_number = %s")
            params.append(best["license_number"])
            if has_source_cols:
                set_clauses.append("license_source = %s")
                params.append("obvious_same_person")
        if r.get("fargo_rating") is None and best.get("fargo_rating") is not None:
            set_clauses.append("fargo_rating = %s")
            params.append(best["fargo_rating"])
            if has_source_cols:
                set_clauses.append("fargo_source = %s")
                params.append("obvious_same_person")
        if not (r.get("country") or "").strip() and best.get("country"):
            set_clauses.append("country = %s")
            params.append(best["country"])
            if has_source_cols:
                set_clauses.append("country_source = %s")
                params.append("obvious_same_person")
        if not set_clauses:
            continue
        params.append(rid)
        if not dry_run:
            cursor.execute(
                f"UPDATE rankings SET {', '.join(set_clauses)} WHERE id = %s",
                params,
            )
        updated += 1
    return updated


def main() -> int:
    parser = argparse.ArgumentParser(description="Cross-fill obvious same person across systems")
    parser.add_argument("--execute", action="store_true", help="Apply updates (default: dry run)")
    parser.add_argument("--player", type=str, help="Limit to clusters containing this name (for testing)")
    args = parser.parse_args()

    try:
        from database import get_database_manager
    except ImportError:
        import os
        import psycopg2
        from psycopg2.extras import RealDictCursor
        url = os.getenv("DATABASE_URL", "").strip()
        if not url:
            logger.error("DATABASE_URL not set")
            return 1
        conn = psycopg2.connect(url)
    else:
        conn = get_database_manager().get_connection()

    try:
        records = get_latest_records(conn)
        clusters = find_obvious_clusters(records)

        if args.player:
            player_lower = args.player.strip().lower()
            clusters = [c for c in clusters if any((r.get("player_name") or "").lower() == player_lower or player_lower in (r.get("player_name") or "").lower() for r in c)]

        logger.info("Found %d obvious same-person clusters (exact name not required)", len(clusters))

        cur = conn.cursor()
        cur.execute(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = 'rankings' AND column_name = 'country_source'"
        )
        has_source_cols = cur.fetchone() is not None

        total_updated = 0
        for cluster in clusters:
            names = [f"{r.get('player_name')} ({r.get('ranking_system')})" for r in cluster]
            logger.info("Cluster: %s", " | ".join(names))
            n = enrich_cluster(cur, cluster, dry_run=not args.execute, has_source_cols=has_source_cols)
            total_updated += n

        if args.execute:
            conn.commit()
            logger.info("Updated %d records across %d clusters", total_updated, len(clusters))
        else:
            conn.rollback()
            logger.info("Dry run: would update %d records in %d clusters. Use --execute to apply.", total_updated, len(clusters))
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
