"""
Competitors import helpers for tournament data.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import requests

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


def fetch_competitors_tournament(slug: str) -> Dict:
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


def _update_match(cursor, match_id: str, updates: Dict) -> None:
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


def import_competitors_tournament(
    tournament_id: str,
    slug: str,
    generate_bracket: bool = True,
    race_to: int = 7,
    dry_run: bool = False,
) -> Dict[str, int | str | None]:
    tm = TournamentManager()
    tournament = tm.get_tournament(tournament_id)
    if not tournament:
        raise ValueError(f"Tournament {tournament_id} not found")

    dp_tournament = fetch_competitors_tournament(slug)
    players_data = dp_tournament.get("tournament_players") or []
    matches_data = dp_tournament.get("tournament_brackets") or []

    existing_players = tm.get_all_players(active_only=False)
    players_by_name = {
        normalize_name(f"{p.get('first_name', '')} {p.get('last_name', '')}"): p
        for p in existing_players
    }

    player_id_map: Dict[str, str] = {}
    created_players = 0

    for player in players_data:
        name = (player.get("name") or "").strip()
        if not name:
            continue
        key = normalize_name(name)
        existing = players_by_name.get(key)
        if existing:
            player_id_map[key] = existing["player_id"]
            continue
        if dry_run:
            player_id_map[key] = f"DRY_{key[:8]}"
            continue
        try:
            player_id = tm.create_player_from_ranking(
                name=name,
                country=player.get("country"),
            )
            player_id_map[key] = player_id
            created_players += 1
        except DuplicatePlayerError as exc:
            logger.warning("Duplicate player for %s: %s", name, exc)
        except Exception as exc:
            logger.error("Failed to create player %s: %s", name, exc)

    registered_players = 0
    if not dry_run:
        for player in players_data:
            name = (player.get("name") or "").strip()
            if not name:
                continue
            key = normalize_name(name)
            player_id = player_id_map.get(key)
            if not player_id or player_id.startswith("DRY_"):
                continue
            seed = player.get("seed")
            if tm.register_player(tournament_id, player_id, seed_position=seed):
                registered_players += 1

    matches = tm.get_tournament_matches(tournament_id)
    if not matches and generate_bracket and not dry_run:
        tm.generate_bracket(tournament_id, race_to=race_to, shuffle_seeds=False)
        matches = tm.get_tournament_matches(tournament_id)

    match_index: Dict[Tuple[str, int, int], Dict] = {}
    for match in matches:
        key = (match.get("bracket_type"), int(match.get("round_number")), int(match.get("match_number")))
        match_index[key] = match

    matches_updated = 0
    matches_skipped = 0

    conn = None
    cursor = None
    if not dry_run:
        conn = tm.get_connection()
        cursor = conn.cursor()

    for match in matches_data:
        bracket_type = map_bracket_type(match.get("identifier"))
        round_number = int(match.get("round") or 0)
        match_number = int(match.get("match_number") or 0)
        if round_number == 0 or match_number == 0:
            matches_skipped += 1
            continue

        db_match = match_index.get((bracket_type, round_number, match_number))
        if not db_match:
            matches_skipped += 1
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

        if dry_run:
            matches_updated += 1
        else:
            _update_match(cursor, db_match["match_id"], updates)
            matches_updated += 1

    if not dry_run and conn:
        conn.commit()
        conn.close()

    placements_updated = 0
    winner_id = None
    runner_up_id = None

    if not dry_run:
        stats: Dict[str, Dict[str, int]] = {}
        matches = tm.get_tournament_matches(tournament_id)
        for match in matches:
            if match.get("status") != "completed":
                continue
            p1_id = match.get("operator_id")
            p2_id = match.get("player2_id")
            if not p1_id or not p2_id:
                continue
            p1_score = int(match.get("operator_score") or 0)
            p2_score = int(match.get("player2_score") or 0)
            winner = match.get("winner_id")
            loser = match.get("loser_id")

            for pid, scored, conceded in ((p1_id, p1_score, p2_score), (p2_id, p2_score, p1_score)):
                stats.setdefault(pid, {"matches_played": 0, "matches_won": 0, "matches_lost": 0, "games_won": 0, "games_lost": 0})
                stats[pid]["matches_played"] += 1
                stats[pid]["games_won"] += scored
                stats[pid]["games_lost"] += conceded
            if winner:
                stats.setdefault(winner, {"matches_played": 0, "matches_won": 0, "matches_lost": 0, "games_won": 0, "games_lost": 0})
                stats[winner]["matches_won"] += 1
            if loser:
                stats.setdefault(loser, {"matches_played": 0, "matches_won": 0, "matches_lost": 0, "games_won": 0, "games_lost": 0})
                stats[loser]["matches_lost"] += 1

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
                    tournament_id,
                    player_id,
                ),
            )

        for player in players_data:
            name = (player.get("name") or "").strip()
            key = normalize_name(name)
            player_id = player_id_map.get(key)
            if not player_id:
                continue
            placement = parse_place(player.get("place"))
            points = player.get("points") or 0
            cursor.execute(
                """
                UPDATE tournament_players
                SET final_placement = %s, points_earned = %s
                WHERE tournament_id = %s AND player_id = %s
                """,
                (placement, points, tournament_id, player_id),
            )
            placements_updated += 1
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
            (winner_id, runner_up_id, len(players_data), tournament_id),
        )

        conn.commit()
        conn.close()

    return {
        "created_players": created_players,
        "registered_players": registered_players,
        "matches_updated": matches_updated,
        "matches_skipped": matches_skipped,
        "placements_updated": placements_updated,
        "winner_player_id": winner_id,
        "runner_up_player_id": runner_up_id,
        "actual_players": len(players_data),
    }
