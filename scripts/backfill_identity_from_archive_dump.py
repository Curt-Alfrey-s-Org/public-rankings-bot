#!/usr/bin/env python3
"""
Backfill identity fields (country/license) from an archived PostgreSQL dump.

Safe behavior:
- Restores the dump into a temporary DB.
- Reads country/license from restored rankings (+ players when available).
- Fills only NULL/empty identity fields in live DB.
- Never overwrites existing non-empty values.
"""

from __future__ import annotations

import argparse
import os
import re
import shlex
import subprocess
import sys
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import psycopg2
import psycopg2.extras


CORE_SYSTEMS = ("WPA_Men", "WPA_Women", "WPBA_Women")


@dataclass
class IdentityRecord:
    country: Optional[str]
    license_number: Optional[str]
    snapshot_date: Optional[datetime]
    source_name: str


def _run(cmd: str, env: Optional[Dict[str, str]] = None) -> Tuple[int, str]:
    proc = subprocess.run(
        cmd,
        shell=True,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return proc.returncode, proc.stdout


def _clean_str(value: Optional[str]) -> Optional[str]:
    s = " ".join(str(value or "").split()).strip()
    return s if s else None


def _canon_name(name: str) -> str:
    raw = _clean_str(name) or ""
    if "," in raw:
        parts = [p.strip() for p in raw.split(",", 1)]
        if len(parts) == 2 and parts[0] and parts[1]:
            raw = f"{parts[1]} {parts[0]}"
    return _clean_str(raw) or ""


def _swap_last(name: str) -> str:
    parts = [p for p in (name or "").split() if p]
    if len(parts) < 2:
        return " ".join(parts)
    return " ".join([parts[-1], *parts[:-1]])


def _name_key(name: str) -> str:
    raw = _canon_name(name).lower()
    raw = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "", raw)


def _license_key(license_number: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "", str(license_number or "").upper())


def _score_record(rec: IdentityRecord) -> int:
    score = 0
    if rec.country:
        score += 1
    if rec.license_number:
        score += 2
    return score


def _pick_better(a: Optional[IdentityRecord], b: IdentityRecord) -> IdentityRecord:
    if a is None:
        return b

    # Prefer newer snapshots.
    if b.snapshot_date and a.snapshot_date and b.snapshot_date > a.snapshot_date:
        return b
    if b.snapshot_date and not a.snapshot_date:
        return b

    # Then prefer richer identity data.
    if _score_record(b) > _score_record(a):
        return b

    return a


def _restore_dump(dump_path: Path, host: str, port: int, user: str, password: str, temp_db: str) -> None:
    env = {**os.environ, "PGPASSWORD": password}
    _run(f"dropdb -h {host} -p {port} -U {user} --if-exists {temp_db}", env=env)

    rc, out = _run(f"createdb -h {host} -p {port} -U {user} {temp_db}", env=env)
    if rc != 0:
        raise RuntimeError(f"createdb failed: {out.strip()}")

    cmd = (
        f"pg_restore -h {host} -p {port} -U {user} -d {temp_db} "
        f"--no-owner --no-privileges {shlex.quote(str(dump_path))}"
    )
    rc, out = _run(cmd, env=env)
    if rc != 0:
        raise RuntimeError(f"pg_restore failed: {out.strip()}")


def _drop_temp_db(host: str, port: int, user: str, password: str, temp_db: str) -> None:
    env = {**os.environ, "PGPASSWORD": password}
    _run(f"dropdb -h {host} -p {port} -U {user} --if-exists {temp_db}", env=env)


def _load_source_maps(restore_dsn: str) -> Tuple[Dict[str, IdentityRecord], Dict[str, IdentityRecord]]:
    by_name: Dict[str, IdentityRecord] = {}
    by_license: Dict[str, IdentityRecord] = {}

    conn = psycopg2.connect(restore_dsn)
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema='public' AND table_name='rankings'
                """
            )
            rankings_cols = {r[0] for r in cur.fetchall()}
            has_country = "country" in rankings_cols
            has_license = "license_number" in rankings_cols
            if not (has_country or has_license):
                return by_name, by_license

            select_rankings = (
                "SELECT player_name, "
                + ("COALESCE(license_number, '')" if has_license else "''")
                + " AS license_number, "
                + ("COALESCE(country, '')" if has_country else "''")
                + " AS country, "
                + "snapshot_date FROM rankings"
            )
            cur.execute(select_rankings)
            for player_name, license_number, country, snapshot_date in cur.fetchall():
                rec = IdentityRecord(
                    country=_clean_str(country),
                    license_number=_clean_str(license_number),
                    snapshot_date=snapshot_date,
                    source_name=str(player_name or ""),
                )
                if _score_record(rec) == 0:
                    continue

                lk = _license_key(rec.license_number or "")
                if lk:
                    by_license[lk] = _pick_better(by_license.get(lk), rec)

                for nm in {player_name, _canon_name(player_name), _swap_last(_canon_name(player_name))}:
                    nk = _name_key(str(nm or ""))
                    if nk:
                        by_name[nk] = _pick_better(by_name.get(nk), rec)

            cur.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema='public' AND table_name='players'
                """
            )
            players_cols = {r[0] for r in cur.fetchall()}
            if not {"first_name", "last_name"} <= players_cols:
                return by_name, by_license

            has_players_license = "license_number" in players_cols
            has_players_country = "nationality" in players_cols
            if not (has_players_license or has_players_country):
                return by_name, by_license

            select_players = (
                "SELECT concat_ws(' ', first_name, last_name) AS full_name, "
                + ("COALESCE(license_number, '')" if has_players_license else "''")
                + " AS license_number, "
                + ("COALESCE(nationality, '')" if has_players_country else "''")
                + " AS country "
                + "FROM players"
            )
            cur.execute(select_players)
            for full_name, license_number, country in cur.fetchall():
                rec = IdentityRecord(
                    country=_clean_str(country),
                    license_number=_clean_str(license_number),
                    snapshot_date=None,
                    source_name=str(full_name or ""),
                )
                if _score_record(rec) == 0:
                    continue

                lk = _license_key(rec.license_number or "")
                if lk:
                    by_license[lk] = _pick_better(by_license.get(lk), rec)

                for nm in {full_name, _canon_name(full_name), _swap_last(_canon_name(full_name))}:
                    nk = _name_key(str(nm or ""))
                    if nk:
                        by_name[nk] = _pick_better(by_name.get(nk), rec)
    finally:
        conn.close()

    return by_name, by_license


def _match_source(
    player_name: str,
    license_number: str,
    by_name: Dict[str, IdentityRecord],
    by_license: Dict[str, IdentityRecord],
) -> Optional[IdentityRecord]:
    lk = _license_key(license_number)
    if lk and lk in by_license:
        return by_license[lk]

    for nm in {player_name, _canon_name(player_name), _swap_last(_canon_name(player_name))}:
        nk = _name_key(str(nm or ""))
        if nk and nk in by_name:
            return by_name[nk]
    return None


def _fetch_live_players(live_dsn: str):
    conn = psycopg2.connect(live_dsn)
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, first_name, last_name, COALESCE(license_number, ''), COALESCE(nationality, '')
                FROM players
                """
            )
            return cur.fetchall()
    finally:
        conn.close()


def _fetch_live_latest_rows(live_dsn: str, systems: Iterable[str]):
    conn = psycopg2.connect(live_dsn)
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                """
                WITH latest AS (
                  SELECT ranking_system, MAX(snapshot_date) AS d
                  FROM rankings
                  WHERE ranking_system = ANY(%s)
                  GROUP BY ranking_system
                )
                SELECT r.id, r.ranking_system, r.rank, r.player_name, COALESCE(r.license_number, ''), COALESCE(r.country, '')
                FROM rankings r
                JOIN latest l ON l.ranking_system = r.ranking_system AND l.d = r.snapshot_date
                WHERE NULLIF(TRIM(COALESCE(r.country, '')), '') IS NULL
                   OR NULLIF(TRIM(COALESCE(r.license_number, '')), '') IS NULL
                ORDER BY ranking_system, rank
                """,
                (list(systems),),
            )
            return cur.fetchall()
    finally:
        conn.close()


def _apply_updates(
    live_dsn: str,
    player_updates: List[Dict[str, object]],
    ranking_updates: List[Dict[str, object]],
    apply: bool,
) -> None:
    if not apply:
        return

    conn = psycopg2.connect(live_dsn)
    try:
        with conn, conn.cursor() as cur:
            if player_updates:
                psycopg2.extras.execute_batch(
                    cur,
                    """
                    UPDATE players
                    SET
                      license_number = COALESCE(NULLIF(license_number, ''), NULLIF(%(license_number)s, ''), license_number),
                      nationality = COALESCE(NULLIF(nationality, ''), NULLIF(%(country)s, ''), nationality)
                    WHERE id = %(id)s
                    """,
                    player_updates,
                    page_size=500,
                )

            if ranking_updates:
                psycopg2.extras.execute_batch(
                    cur,
                    """
                    UPDATE rankings
                    SET
                      license_number = COALESCE(NULLIF(license_number, ''), NULLIF(%(license_number)s, ''), license_number),
                      country = COALESCE(NULLIF(country, ''), NULLIF(%(country)s, ''), country),
                      license_source = CASE
                        WHEN NULLIF(license_number, '') IS NULL AND NULLIF(%(license_number)s, '') IS NOT NULL THEN 'archive_dump'
                        ELSE license_source
                      END,
                      country_source = CASE
                        WHEN NULLIF(country, '') IS NULL AND NULLIF(%(country)s, '') IS NOT NULL THEN 'archive_dump'
                        ELSE country_source
                      END
                    WHERE id = %(id)s
                    """,
                    ranking_updates,
                    page_size=500,
                )
        conn.commit()
    finally:
        conn.close()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Backfill country/license from archived dump")
    p.add_argument("--dump-path", required=True, help="Path to .dump file")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=5434)
    p.add_argument("--user", default="rankingsbot_user")
    p.add_argument("--password", default=os.getenv("PGPASSWORD", "123123"))
    p.add_argument("--live-db", default="rankingsbot")
    p.add_argument("--temp-db", default="rankingsbot_restore_tmp")
    p.add_argument("--apply", action="store_true", help="Apply updates; default is dry-run")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    dump_path = Path(args.dump_path)
    if not dump_path.exists():
        print(f"Dump not found: {dump_path}", file=sys.stderr)
        return 1

    live_dsn = f"postgresql://{args.user}:change-me@{args.host}:{args.port}/{args.live_db}"
    restore_dsn = f"postgresql://{args.user}:change-me@{args.host}:{args.port}/{args.temp_db}"

    try:
        _restore_dump(dump_path, args.host, args.port, args.user, args.password, args.temp_db)
        by_name, by_license = _load_source_maps(restore_dsn)

        players = _fetch_live_players(live_dsn)
        latest_rows = _fetch_live_latest_rows(live_dsn, CORE_SYSTEMS)
        now_utc = datetime.now(timezone.utc)

        player_updates: List[Dict[str, object]] = []
        ranking_updates: List[Dict[str, object]] = []

        matched_players = 0
        for pid, first_name, last_name, current_license, current_country in players:
            source = _match_source(f"{first_name or ''} {last_name or ''}", current_license, by_name, by_license)
            if source is None:
                continue

            need_license = _clean_str(current_license) is None and source.license_number is not None
            need_country = _clean_str(current_country) is None and source.country is not None
            if not (need_license or need_country):
                continue

            matched_players += 1
            player_updates.append(
                {
                    "id": pid,
                    "license_number": source.license_number if need_license else "",
                    "country": source.country if need_country else "",
                    "updated_at": now_utc,
                }
            )

        matched_rankings = 0
        for rid, ranking_system, rank, player_name, current_license, current_country in latest_rows:
            source = _match_source(player_name, current_license, by_name, by_license)
            if source is None:
                continue

            need_license = _clean_str(current_license) is None and source.license_number is not None
            need_country = _clean_str(current_country) is None and source.country is not None
            if not (need_license or need_country):
                continue

            matched_rankings += 1
            ranking_updates.append(
                {
                    "id": rid,
                    "license_number": source.license_number if need_license else "",
                    "country": source.country if need_country else "",
                    "updated_at": now_utc,
                }
            )

        print(f"Source map keys: names={len(by_name)}, licenses={len(by_license)}")
        print(f"Matched live players needing identity fill: {matched_players}")
        print(f"Matched latest core ranking rows needing identity fill: {matched_rankings}")

        if not args.apply:
            print("Dry-run only. Re-run with --apply to write updates.")
            return 0

        _apply_updates(live_dsn, player_updates, ranking_updates, apply=True)
        print(f"Applied player identity updates: {len(player_updates)}")
        print(f"Applied ranking identity updates: {len(ranking_updates)}")
        return 0
    finally:
        _drop_temp_db(args.host, args.port, args.user, args.password, args.temp_db)


if __name__ == "__main__":
    raise SystemExit(main())

