#!/usr/bin/env python3
"""
Backfill Fargo/robustness from an archived PostgreSQL dump (no scraping).

Workflow:
1) Restore dump into temporary DB.
2) Build source mappings from restored rankings/players data.
3) Fill NULL Fargo fields in live players and latest rankings rows.
4) Drop temporary DB.
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
class SourceRecord:
    fargo: Optional[float]
    robustness: Optional[int]
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


def _canon_name(name: str) -> str:
    raw = " ".join((name or "").split()).strip()
    if "," in raw:
        parts = [p.strip() for p in raw.split(",", 1)]
        if len(parts) == 2 and parts[0] and parts[1]:
            raw = f"{parts[1]} {parts[0]}"
    return " ".join(raw.split()).strip()


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


def _pick_newer(a: Optional[SourceRecord], b: SourceRecord) -> SourceRecord:
    if a is None:
        return b
    if b.snapshot_date and a.snapshot_date and b.snapshot_date > a.snapshot_date:
        return b
    if b.snapshot_date and not a.snapshot_date:
        return b
    if (a.fargo is None and b.fargo is not None) or (a.robustness is None and b.robustness is not None):
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


def _load_source_maps(restore_dsn: str) -> Tuple[Dict[str, SourceRecord], Dict[str, SourceRecord]]:
    by_name: Dict[str, SourceRecord] = {}
    by_license: Dict[str, SourceRecord] = {}

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
            has_rankings_robustness = "fargo_robustness" in rankings_cols

            select_rankings = (
                "SELECT player_name, COALESCE(license_number, ''), fargo_rating, "
                + ("fargo_robustness, " if has_rankings_robustness else "NULL::integer AS fargo_robustness, ")
                + "snapshot_date FROM rankings WHERE fargo_rating IS NOT NULL"
            )

            cur.execute(select_rankings)
            for player_name, license_number, fargo_rating, fargo_robustness, snapshot_date in cur.fetchall():
                rec = SourceRecord(
                    fargo=float(fargo_rating) if fargo_rating is not None else None,
                    robustness=int(fargo_robustness) if fargo_robustness is not None else None,
                    snapshot_date=snapshot_date,
                    source_name=str(player_name or ""),
                )

                lk = _license_key(license_number)
                if lk:
                    by_license[lk] = _pick_newer(by_license.get(lk), rec)

                for nm in {player_name, _canon_name(player_name), _swap_last(_canon_name(player_name))}:
                    nk = _name_key(str(nm or ""))
                    if nk:
                        by_name[nk] = _pick_newer(by_name.get(nk), rec)

            cur.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema='public' AND table_name='players'
                """
            )
            players_cols = {r[0] for r in cur.fetchall()}
            if "fargo_score" not in players_cols:
                return by_name, by_license

            cur.execute(
                """
                SELECT concat_ws(' ', first_name, last_name), fargo_score
                FROM players
                WHERE fargo_score IS NOT NULL
                """
            )
            for full_name, fargo_score in cur.fetchall():
                rec = SourceRecord(
                    fargo=float(fargo_score) if fargo_score is not None else None,
                    robustness=None,
                    snapshot_date=None,
                    source_name=str(full_name or ""),
                )
                for nm in {full_name, _canon_name(full_name), _swap_last(_canon_name(full_name))}:
                    nk = _name_key(str(nm or ""))
                    if nk:
                        by_name[nk] = _pick_newer(by_name.get(nk), rec)
    finally:
        conn.close()

    return by_name, by_license


def _fetch_live_players(live_dsn: str):
    conn = psycopg2.connect(live_dsn)
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, first_name, last_name, COALESCE(license_number, ''), fargo_score, fargo_robustness
                FROM players
                """
            )
            return cur.fetchall()
    finally:
        conn.close()


def _fetch_live_missing_latest_rows(live_dsn: str, systems: Iterable[str]):
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
                ),
                players_by_name AS (
                  SELECT LOWER(TRIM(first_name || ' ' || last_name)) AS full_name,
                         MAX(fargo_score) AS fargo_score
                  FROM players
                  GROUP BY LOWER(TRIM(first_name || ' ' || last_name))
                )
                SELECT
                  r.id,
                  r.ranking_system,
                  r.rank,
                  r.player_name,
                  COALESCE(r.license_number, '') AS license_number,
                  r.fargo_rating,
                  r.fargo_robustness
                FROM rankings r
                JOIN latest l ON l.ranking_system = r.ranking_system AND l.d = r.snapshot_date
                LEFT JOIN players_by_name p1
                  ON p1.full_name = LOWER(
                    TRIM(
                      CASE
                        WHEN POSITION(',' IN r.player_name) > 0 THEN
                          TRIM(SPLIT_PART(r.player_name, ',', 2)) || ' ' || TRIM(SPLIT_PART(r.player_name, ',', 1))
                        ELSE r.player_name
                      END
                    )
                  )
                LEFT JOIN players_by_name p2
                  ON p2.full_name = LOWER(
                    TRIM(
                      REGEXP_REPLACE(
                        CASE
                          WHEN POSITION(',' IN r.player_name) > 0 THEN
                            TRIM(SPLIT_PART(r.player_name, ',', 2)) || ' ' || TRIM(SPLIT_PART(r.player_name, ',', 1))
                          ELSE r.player_name
                        END,
                        '^(.*)\\s+([^\\s]+)$',
                        '\\2 \\1'
                      )
                    )
                  )
                WHERE COALESCE(p1.fargo_score, p2.fargo_score, r.fargo_rating) IS NULL
                ORDER BY r.ranking_system, r.rank
                """,
                (list(systems),),
            )
            return cur.fetchall()
    finally:
        conn.close()


def _match_source(
    player_name: str,
    license_number: str,
    by_name: Dict[str, SourceRecord],
    by_license: Dict[str, SourceRecord],
) -> Optional[SourceRecord]:
    lk = _license_key(license_number)
    if lk and lk in by_license:
        return by_license[lk]

    for nm in {player_name, _canon_name(player_name), _swap_last(_canon_name(player_name))}:
        nk = _name_key(str(nm or ""))
        if nk and nk in by_name:
            return by_name[nk]
    return None


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
                      fargo_score = COALESCE(fargo_score, %(fargo_score)s),
                      fargo_robustness = COALESCE(fargo_robustness, %(fargo_robustness)s),
                      fargo_last_updated = COALESCE(fargo_last_updated, %(fargo_last_updated)s)
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
                      fargo_rating = COALESCE(fargo_rating, %(fargo_rating)s),
                      fargo_robustness = COALESCE(fargo_robustness, %(fargo_robustness)s),
                      fargo_last_updated = COALESCE(fargo_last_updated, %(fargo_last_updated)s)
                    WHERE id = %(id)s
                    """,
                    ranking_updates,
                    page_size=500,
                )
        conn.commit()
    finally:
        conn.close()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Backfill Fargo from archived dump")
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
        missing_latest_rows = _fetch_live_missing_latest_rows(live_dsn, CORE_SYSTEMS)
        now_utc = datetime.now(timezone.utc)

        player_updates: List[Dict[str, object]] = []
        matched_player_count = 0
        for pid, first_name, last_name, license_number, fargo_score, fargo_rob in players:
            source = _match_source(f"{first_name or ''} {last_name or ''}", license_number, by_name, by_license)
            if source is None:
                continue
            need_fargo = fargo_score is None and source.fargo is not None
            need_rob = fargo_rob is None and source.robustness is not None
            if not (need_fargo or need_rob):
                continue
            matched_player_count += 1
            player_updates.append(
                {
                    "id": pid,
                    "fargo_score": int(round(source.fargo)) if (need_fargo and source.fargo is not None) else None,
                    "fargo_robustness": int(source.robustness) if (need_rob and source.robustness is not None) else None,
                    "fargo_last_updated": now_utc,
                }
            )

        ranking_updates: List[Dict[str, object]] = []
        matched_ranking_count = 0
        for rid, ranking_system, rank, player_name, license_number, fargo_rating, fargo_rob in missing_latest_rows:
            source = _match_source(player_name, license_number, by_name, by_license)
            if source is None:
                continue
            need_fargo = fargo_rating is None and source.fargo is not None
            need_rob = fargo_rob is None and source.robustness is not None
            if not (need_fargo or need_rob):
                continue
            matched_ranking_count += 1
            ranking_updates.append(
                {
                    "id": rid,
                    "fargo_rating": float(source.fargo) if (need_fargo and source.fargo is not None) else None,
                    "fargo_robustness": int(source.robustness) if (need_rob and source.robustness is not None) else None,
                    "fargo_last_updated": now_utc,
                }
            )

        print(f"Source map keys: names={len(by_name)}, licenses={len(by_license)}")
        print(f"Matched live players needing fill: {matched_player_count}")
        print(f"Matched latest core ranking rows needing fill: {matched_ranking_count}")

        if not args.apply:
            print("Dry-run only. Re-run with --apply to write updates.")
            return 0

        _apply_updates(live_dsn, player_updates, ranking_updates, apply=True)
        print(f"Applied player updates: {len(player_updates)}")
        print(f"Applied ranking updates: {len(ranking_updates)}")
        return 0
    finally:
        _drop_temp_db(args.host, args.port, args.user, args.password, args.temp_db)


if __name__ == "__main__":
    raise SystemExit(main())

