#!/usr/bin/env python3
"""
Import competitors tournament data into Rankings Bot tournament tables.

Usage:
  python3 scripts/import_competitors_tournament.py --slug <competitors-slug> --tournament-id <TXXXXXX>

Optional:
  --dry-run            Do not write to database
  --generate-bracket   Generate bracket if no matches exist
  --race-to <int>      Race-to used when generating bracket (default: 7)
  --save-raw <path>    Save raw competitors JSON payload
"""

import argparse
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests

from database import engine
from api.tournament_manager import TournamentManager, DuplicatePlayerError

logger = logging.getLogger(__name__)

COMPETITORS_GRAPHQL = "https://api-nyc.digitalpool.com/v1/graphql"

TOURNAMENT_QUERY = """
query GetTournament($slug: String!) {
  tournaments(where: {slug: {_eq: $slug}}) {
    id
    name
    slug
    start_date_time
    end_date_time
    tournament_brackets(order_by: {round: asc, match_number: asc}) {
      identifier
      round
      match_number
      group
      group_name
      status
      table_number
      scheduled_time
      start_time
      end_time
      challenger1_name
      challenger2_name
      challenger1_score
      challenger2_score
      challenger1_seed
      challenger2_seed
      challenger1_is_winner
      challenger2_is_winner
    }
    tournament_players(order_by: {seed: asc}) {
      name
      seed
      place
      points
      country
      player_id
    }
  }
}
"""


def normalize_name(name: str) -> str:
    cleaned = re.sub(r"[^a-z0-9\s]", "", (name or "").strip().lower())
    return re.sub(r"\s+", " ", cleaned)


def fetch_tournament(slug: str) -> Dict:
    response = requests.post(
        COMPETITORS_GRAPHQL,
        json={"query": TOURNAMENT_QUERY, "variables": {"slug": slug}},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("errors"):
        raise RuntimeError(payload["errors"])
    tournaments = payload.get("data", {}).get("tournaments") or []
    if not tournaments:
        raise ValueError(f"No tournament found for slug: {slug}")
    return tournaments[0]


def map_bracket_type(identifier: Optional[str]) -> str:
    ident = (identifier or "").upper()
    if ident.startswith("W"):
        return "winners"
    if ident.startswith("L"):
        return "losers"
    if ident.startswith("GF") or ident.startswith("F"):
        return "grand_final"
    return "winners"


def map_status(status: Optional[str]) -> str:
    if not status:
        return "pending"
    status = status.upper()
    return {
        "COMPLETED": "completed",
        "IN_PROGRESS": "in_progress",
        "PENDING": "pending",
        "BYE": "bye",
    }.get(status, "pending")


def parse_place(place: Optional[str]) -> Optional[int]:
    if not place:
        return None
    match = re.search(r"\d+", str(place))
    return int(match.group(0)) if match else None


def update_match(cursor, match_id: str, updates: Dict) -> None:
    set_parts = []
    values = []
    for key, value in updates.items():
        set_parts.append(f"{key} = %s")
        values.append(value)
    values.append(match_id)
    cursor.execute(
        f"UPDATE matches SET {', '.join(set_parts)} WHERE match_id = %s",
        values,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Import competitors tournament data")
    parser.add_argument("--slug", required=True, help="Competitors tournament slug")
    parser.add_argument("--tournament-id", required=True, help="Local tournament_id (e.g., T000123)")
    parser.add_argument("--dry-run", action="store_true", help="Do not write to database")
    parser.add_argument("--generate-bracket", action="store_true", help="Generate bracket if none exists")
    parser.add_argument("--race-to", type=int, default=7, help="Race-to when generating bracket")
    parser.add_argument("--save-raw", type=str, default=None, help="Path to save raw competitors JSON")
    parser.add_argument("--verbose", action="store_true", help="Verbose logging")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    tm = TournamentManager(engine=engine)
    tournament = tm.get_tournament(args.tournament_id)
    if not tournament:
        logger.error("Tournament %s not found", args.tournament_id)
        return 1

    dp_tournament = fetch_tournament(args.slug)
    if args.save_raw:
        path = Path(args.save_raw)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(dp_tournament, indent=2))
        logger.info("Saved raw competitors payload to %s", path)

    players_data = dp_tournament.get("tournament_players") or []
    matches_data = dp_tournament.get("tournament_brackets") or []

    existing_players = tm.get_all_players(active_only=False)
    players_by_name = {normalize_name(f"{p.get('first_name','')} {p.get('last_name','')}"): p for p in existing_players}

    player_id_map: Dict[str, str] = {}
    created = 0
    for player in players_data:
        name = (player.get("name") or "").strip()
        if not name:
            continue
        key = normalize_name(name)
        existing = players_by_name.get(key)
        if existing:
            player_id_map[key] = existing["player_id"]
            continue
        if args.dry_run:
            player_id_map[key] = f"DRY_{key[:8]}"
            continue
        try:
            player_id = tm.create_player_from_ranking(
                name=name,
                country=player.get("country"),
            )
            player_id_map[key] = player_id
            created += 1
            logger.info("Created player %s -> %s", name, player_id)
        except DuplicatePlayerError as exc:
            logger.warning("Duplicate player for %s: %s", name, exc)
        except Exception as exc:
            logger.error("Failed to create player %s: %s", name, exc)

    if created:
        logger.info("Created %s new players", created)

    if not args.dry_run:
        for player in players_data:
            name = (player.get("name") or "").strip()
            if not name:
                continue
            key = normalize_name(name)
            player_id = player_id_map.get(key)
            if not player_id or player_id.startswith("DRY_"):
                continue
            seed = player.get("seed")
            tm.register_player(args.tournament_id, player_id, seed_position=seed)

    matches = tm.get_tournament_matches(args.tournament_id)
    if not matches and args.generate_bracket and not args.dry_run:
        logger.info("No matches found. Generating bracket...")
        tm.generate_bracket(args.tournament_id, race_to=args.race_to, shuffle_seeds=False)
        matches = tm.get_tournament_matches(args.tournament_id)

    match_index: Dict[Tuple[str, int, int], Dict] = {}
    for match in matches:
        key = (match.get("bracket_type"), int(match.get("round_number")), int(match.get("match_number")))
        match_index[key] = match

    updated_matches = 0
    skipped_matches = 0

    if not args.dry_run:
        conn = tm.get_connection()
        cursor = conn.cursor()

    for match in matches_data:
        bracket_type = map_bracket_type(match.get("identifier"))
        round_number = int(match.get("round") or 0)
        match_number = int(match.get("match_number") or 0)
        if round_number == 0 or match_number == 0:
            skipped_matches += 1
            continue

        db_match = match_index.get((bracket_type, round_number, match_number))
        if not db_match:
            skipped_matches += 1
            continue

        p1_name = (match.get("challenger1_name") or "").strip()
        p2_name = (match.get("challenger2_name") or "").strip()
        p1_id = player_id_map.get(normalize_name(p1_name)) if p1_name else None
        p2_id = player_id_map.get(normalize_name(p2_name)) if p2_name else None

        p1_score = match.get("challenger1_score")
        p2_score = match.get("challenger2_score")
        status = map_status(match.get("status"))

        winner_id = None
        loser_id = None
        if status == "completed" and p1_id and p2_id:
            if match.get("challenger1_is_winner") is True:
                winner_id, loser_id = p1_id, p2_id
            elif match.get("challenger2_is_winner") is True:
                winner_id, loser_id = p2_id, p1_id
            elif p1_score is not None and p2_score is not None:
                if int(p1_score) >= int(p2_score):
                    winner_id, loser_id = p1_id, p2_id
                else:
                    winner_id, loser_id = p2_id, p1_id

        updates = {
            "operator_id": p1_id,
            "player2_id": p2_id,
            "operator_score": int(p1_score) if p1_score is not None else 0,
            "player2_score": int(p2_score) if p2_score is not None else 0,
            "status": status,
            "winner_id": winner_id,
            "loser_id": loser_id,
            "table_number": match.get("table_number"),
            "scheduled_time": match.get("scheduled_time"),
            "started_at": match.get("start_time"),
            "completed_at": match.get("end_time") if status == "completed" else None,
            "updated_at": datetime.now().isoformat(),
        }

        if args.dry_run:
            updated_matches += 1
        else:
            update_match(cursor, db_match["match_id"], updates)
            updated_matches += 1

    if not args.dry_run:
        conn.commit()
        conn.close()

    logger.info("Matches updated: %s, skipped: %s", updated_matches, skipped_matches)

    if not args.dry_run:
        matches = tm.get_tournament_matches(args.tournament_id)
        stats: Dict[str, Dict[str, int]] = {}
        for match in matches:
            if match.get("status") != "completed":
                continue
            p1_id = match.get("operator_id")
            p2_id = match.get("player2_id")
            if not p1_id or not p2_id:
                continue
            p1_score = int(match.get("operator_score") or 0)
            p2_score = int(match.get("player2_score") or 0)
            winner_id = match.get("winner_id")
            loser_id = match.get("loser_id")
            for pid, scored, conceded in ((p1_id, p1_score, p2_score), (p2_id, p2_score, p1_score)):
                stats.setdefault(pid, {"matches_played": 0, "matches_won": 0, "matches_lost": 0, "games_won": 0, "games_lost": 0})
                stats[pid]["matches_played"] += 1
                stats[pid]["games_won"] += scored
                stats[pid]["games_lost"] += conceded
            if winner_id:
                stats.setdefault(winner_id, {"matches_played": 0, "matches_won": 0, "matches_lost": 0, "games_won": 0, "games_lost": 0})
                stats[winner_id]["matches_won"] += 1
            if loser_id:
                stats.setdefault(loser_id, {"matches_played": 0, "matches_won": 0, "matches_lost": 0, "games_won": 0, "games_lost": 0})
                stats[loser_id]["matches_lost"] += 1

        conn = tm.get_connection()
        cursor = conn.cursor()
        for player_id, totals in stats.items():
            cursor.execute(
                """
                UPDATE tournament_players
                SET matches_played = %s,
                    matches_won = %s,
                    matches_lost = %s,
                    total_games_won = %s,
                    total_games_lost = %s
                WHERE tournament_id = %s AND player_id = %s
                """,
                (
                    totals["matches_played"],
                    totals["matches_won"],
                    totals["matches_lost"],
                    totals["games_won"],
                    totals["games_lost"],
                    args.tournament_id,
                    player_id,
                ),
            )
        conn.commit()
        conn.close()

    if not args.dry_run:
        conn = tm.get_connection()
        cursor = conn.cursor()
        winner_id = None
        runner_up_id = None
        for player in players_data:
            name = (player.get("name") or "").strip()
            key = normalize_name(name)
            player_id = player_id_map.get(key)
            if not player_id:
                continue
            placement = parse_place(player.get("place"))
            points = player.get("points")
            cursor.execute(
                """
                UPDATE tournament_players
                SET final_placement = %s, points_earned = %s
                WHERE tournament_id = %s AND player_id = %s
                """,
                (placement, points, args.tournament_id, player_id),
            )
            if placement == 1:
                winner_id = player_id
            elif placement == 2:
                runner_up_id = player_id

        cursor.execute(
            """
            UPDATE tournaments
            SET winner_player_id = %s, runner_up_player_id = %s, actual_players = %s
            WHERE tournament_id = %s
            """,
            (winner_id, runner_up_id, len(players_data), args.tournament_id),
        )
        conn.commit()
        conn.close()

    logger.info("Import completed for %s", args.tournament_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
