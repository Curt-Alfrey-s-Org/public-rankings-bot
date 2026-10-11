"""
Bracket generation and advancement for Test Center.

Single elimination: standard binary tree.

Double elimination: winners bracket + losers bracket (standard drop-in pattern) + grand final.
Grand final is a single match (WPBA one-set final, race_to_final); no bracket-reset match.
"""

from __future__ import annotations

import logging
import math
import random
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# WPBA-style R-points (Iron City VI / repo sample; placements 25+ not awarded in source data)
WPBA_CLASSIC_POINTS: Dict[int, int] = {
    1: 11000,
    2: 7000,
    3: 4800,
    4: 3600,
    5: 2600,  # 5-6
    7: 2100,  # 7-8
    9: 1600,  # 9-12
    13: 1200,  # 13-16
    17: 800,  # 17-24
}


def wpba_default_points_structure() -> Dict[str, int]:
    """Placement 1..24 -> R-points for persistence / API defaults."""
    out: Dict[str, int] = {}
    for p in range(1, 25):
        pts = wpba_points_for_placement(p)
        if pts is not None:
            out[str(p)] = pts
    return out


def wpba_points_for_placement(placement: int) -> Optional[int]:
    """Return R-points for finishing place (1-based). Uses banded WPBA classic table."""
    if placement < 1:
        return None
    if placement <= 4:
        return WPBA_CLASSIC_POINTS.get(placement)
    if placement <= 6:
        return WPBA_CLASSIC_POINTS[5]
    if placement <= 8:
        return WPBA_CLASSIC_POINTS[7]
    if placement <= 12:
        return WPBA_CLASSIC_POINTS[9]
    if placement <= 16:
        return WPBA_CLASSIC_POINTS[13]
    if placement <= 24:
        return WPBA_CLASSIC_POINTS[17]
    return None


def next_power_of_two(n: int) -> int:
    if n <= 1:
        return 1
    return 1 << (n - 1).bit_length()


def generate_seeding_order(draw_size: int) -> List[int]:
    """Seed numbers 1..draw_size in bracket leaf order (standard pairing).

    Each round doubles the bracket size. At size *s*, seed *p* plays
    seed *s + 1 - p* (standard 1-vs-N, 2-vs-(N-1) pairing).  The previous
    implementation incorrectly used the final draw_size at every expansion
    step, producing only a handful of unique values for large brackets.
    """
    if draw_size < 2 or draw_size & (draw_size - 1):
        raise ValueError("draw_size must be a power of 2 and >= 2")
    placements = [1]
    size = 2
    while size <= draw_size:
        placements = sum(([p, size + 1 - p] for p in placements), [])
        size *= 2
    return placements


def make_match_id(tournament_id: str, round_num: int, match_index: int, bracket_type: str = "winners") -> str:
    safe_bt = bracket_type.replace(":", "_")
    return f"{tournament_id}::bt{safe_bt}::r{round_num}::m{match_index}"


def parse_match_id(match_id: str) -> Optional[Tuple[str, str, int, int]]:
    if "::" not in match_id:
        return None
    parts = match_id.split("::")
    if len(parts) != 4:
        return None
    tid, bt_part, r_part, m_part = parts
    if not bt_part.startswith("bt") or not r_part.startswith("r") or not m_part.startswith("m"):
        return None
    bracket_type = bt_part[2:]
    try:
        r = int(r_part[1:])
        m = int(m_part[1:])
    except ValueError:
        return None
    return tid, bracket_type, r, m


def advancement_target_winner(match_id: str) -> Optional[Tuple[str, str, int, int, int]]:
    """Where the winner of this match goes: (next_match_id, tid, nr, ni, slot 0=p1 1=p2)."""
    parsed = parse_match_id(match_id)
    if not parsed:
        return None
    tid, bt, r, m = parsed

    if bt == "grand_final":
        return None

    if bt == "winners":
        draw = _draw_size_rounds.get(tid) or 8
        last_r = last_winners_round(draw)
        if r >= last_r:
            if _tournament_format.get(tid) == "double_elimination" and draw == 64:
                nxt = make_match_id(tid, 1, 0, "grand_final")
                return nxt, tid, 1, 0, 0
            return None
        nxt = make_match_id(tournament_id=tid, round_num=r + 1, match_index=m // 2, bracket_type="winners")
        return nxt, tid, r + 1, m // 2, m % 2

    if bt == "losers":
        return _losers_winner_next(tid, r, m)

    return None


def advancement_target(match_id: str) -> Optional[Tuple[str, str, int, int, int]]:
    """Backward-compatible alias: winner advancement."""
    return advancement_target_winner(match_id)


def advancement_target_loser(match_id: str) -> Optional[Tuple[str, str, int, int, int]]:
    """
    Where the losers-bracket drop goes. Only for full double-elim (64) pattern.
    Single elimination: no loser routing (returns None).
    """
    parsed = parse_match_id(match_id)
    if not parsed:
        return None
    tid, bt, r, m = parsed
    if bt != "winners":
        return None
    if _tournament_format.get(tid) != "double_elimination" or _draw_size_rounds.get(tid) != 64:
        return None
    last_r = last_winners_round(64)
    if r == 1:
        # WB R1 loser -> LB1[m//2], slot m%2
        nxt = make_match_id(tid, 1, m // 2, "losers")
        return nxt, tid, 1, m // 2, m % 2
    if r == 2:
        nxt = make_match_id(tid, 2, m, "losers")
        return nxt, tid, 2, m, 1
    if r == 3:
        nxt = make_match_id(tid, 4, m, "losers")
        return nxt, tid, 4, m, 1
    if r == 4:
        nxt = make_match_id(tid, 6, m, "losers")
        return nxt, tid, 6, m, 1
    if r == 5:
        nxt = make_match_id(tid, 8, m, "losers")
        return nxt, tid, 8, m, 1
    if r == last_r:
        nxt = make_match_id(tid, 10, 0, "losers")
        return nxt, tid, 10, 0, 1
    return None


_draw_size_rounds: Dict[str, int] = {}
_tournament_format: Dict[str, str] = {}


def set_tournament_draw_size(tournament_id: str, draw_size: int) -> None:
    """Register draw size (player count) for advancement_target."""
    _draw_size_rounds[tournament_id] = draw_size


def set_tournament_format(tournament_id: str, format_type: str) -> None:
    """Register bracket format (single_elimination vs double_elimination)."""
    _tournament_format[tournament_id] = format_type


def _losers_winner_next(
    tid: str, r: int, m: int
) -> Optional[Tuple[str, str, int, int, int]]:
    if r == 1:
        nxt = make_match_id(tid, 2, m, "losers")
        return nxt, tid, 2, m, 0
    if r == 2:
        nxt = make_match_id(tid, 3, m // 2, "losers")
        return nxt, tid, 3, m // 2, m % 2
    if r == 3:
        nxt = make_match_id(tid, 4, m, "losers")
        return nxt, tid, 4, m, 0
    if r == 4:
        nxt = make_match_id(tid, 5, m // 2, "losers")
        return nxt, tid, 5, m // 2, m % 2
    if r == 5:
        nxt = make_match_id(tid, 6, m, "losers")
        return nxt, tid, 6, m, 0
    if r == 6:
        nxt = make_match_id(tid, 7, m // 2, "losers")
        return nxt, tid, 7, m // 2, m % 2
    if r == 7:
        nxt = make_match_id(tid, 8, m, "losers")
        return nxt, tid, 8, m, 0
    if r == 8:
        nxt = make_match_id(tid, 9, 0, "losers")
        return nxt, tid, 9, 0, m
    if r == 9:
        nxt = make_match_id(tid, 10, 0, "losers")
        return nxt, tid, 10, 0, 0
    if r == 10:
        nxt = make_match_id(tid, 1, 0, "grand_final")
        return nxt, tid, 1, 0, 1
    return None


def simulation_sort_key(match: Dict[str, Any]) -> Tuple[int, int, str]:
    """
    Ordering so simulate-all resolves dependencies: WB waves alternate with LB waves
    (WB1 -> LB1 -> WB2 -> LB2 -> ... -> GF).
    """
    bt = (match.get("bracket_type") or "winners").strip()
    r = int(match.get("round_number") or 1)
    mid = str(match.get("match_id") or "")
    wave = _simulation_wave(bt, r)
    return (wave, r, mid)


def _simulation_wave(bracket_type: str, round_number: int) -> int:
    if bracket_type == "grand_final":
        return 9000
    if bracket_type == "winners":
        # WB round k -> wave 2*k-1 (WB1=1, WB2=3, ...)
        return 2 * round_number - 1
    if bracket_type == "losers":
        # LB round k -> wave 2*k (LB1=2, LB2=4, ...)
        return 2 * round_number
    return 9999


def _eligible_players(players: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [p for p in players if (p.get("name") or "").strip()]


def _sort_players_for_seeding(players: List[Dict[str, Any]], shuffle_seeds: bool) -> List[Dict[str, Any]]:
    def seed_key(p: Dict[str, Any]) -> Tuple[int, str]:
        s = p.get("seed")
        try:
            si = int(s) if s is not None else 10**9
        except (TypeError, ValueError):
            si = 10**9
        return (si, str(p.get("player_id") or ""))

    ordered = sorted(players, key=seed_key)
    if shuffle_seeds:
        random.shuffle(ordered)
    return ordered


def _winner_dict(match: Dict[str, Any], players: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    wid = match.get("winner_id")
    if not wid:
        return None
    for p in players:
        if p.get("player_id") == wid:
            return p
    name = (
        match.get("operator_name")
        if wid == match.get("operator_id")
        else match.get("player2_name")
    )
    return {"player_id": wid, "name": (name or "").strip()}


def _child_side(
    child: Optional[Dict[str, Any]], players: List[Dict[str, Any]]
) -> Tuple[Optional[Dict[str, Any]], bool]:
    if child is None:
        return None, False
    if child["status"] == "completed" and child.get("winner_id"):
        return _winner_dict(child, players), False
    if child["status"] == "pending":
        return None, True
    return None, False


def _empty_match(
    tournament_id: str,
    bracket_type: str,
    rnd: int,
    idx: int,
    race_to: int,
    *,
    table_number: Optional[int] = None,
) -> Dict[str, Any]:
    mid = make_match_id(tournament_id, rnd, idx, bracket_type)
    return {
        "match_id": mid,
        "tournament_id": tournament_id,
        "bracket_type": bracket_type,
        "round_number": rnd,
        "operator_id": None,
        "player2_id": None,
        "operator_name": "TBD",
        "player2_name": "TBD",
        "operator_score": 0,
        "player2_score": 0,
        "winner_id": None,
        "status": "pending",
        "table_number": table_number,
        "race_to": race_to,
    }


def generate_single_elimination(
    tournament_id: str,
    players: List[Dict[str, Any]],
    draw_size: int,
    race_to: int,
    *,
    shuffle_seeds: bool = False,
    bracket_type: str = "winners",
) -> List[Dict[str, Any]]:
    eligible = _eligible_players(players)
    if not eligible:
        return []
    if draw_size < 2 or draw_size & (draw_size - 1):
        raise ValueError("draw_size must be a power of 2 and >= 2")
    k = len(eligible)
    if k > draw_size:
        raise ValueError(f"Too many players ({k}) for draw_size {draw_size}")

    ordered = _sort_players_for_seeding(eligible, shuffle_seeds)
    seed_to_player: Dict[int, Dict[str, Any]] = {i + 1: ordered[i] for i in range(min(k, draw_size))}

    ordering = generate_seeding_order(draw_size)
    leaves: List[Optional[Dict[str, Any]]] = [seed_to_player.get(s) for s in ordering]

    all_matches: List[Dict[str, Any]] = []
    num_rounds = int(math.log2(draw_size))

    r1: List[Dict[str, Any]] = []
    for i in range(draw_size // 2):
        p1, p2 = leaves[2 * i], leaves[2 * i + 1]
        mid = make_match_id(tournament_id, 1, i, bracket_type)
        if p1 and p2:
            r1.append(
                {
                    "match_id": mid,
                    "tournament_id": tournament_id,
                    "bracket_type": bracket_type,
                    "round_number": 1,
                    "operator_id": p1["player_id"],
                    "player2_id": p2["player_id"],
                    "operator_name": (p1.get("name") or "").strip(),
                    "player2_name": (p2.get("name") or "").strip(),
                    "operator_score": 0,
                    "player2_score": 0,
                    "winner_id": None,
                    "status": "pending",
                    "table_number": (i % 32) + 1,
                    "race_to": race_to,
                }
            )
        elif p1 and not p2:
            r1.append(
                {
                    "match_id": mid,
                    "tournament_id": tournament_id,
                    "bracket_type": bracket_type,
                    "round_number": 1,
                    "operator_id": p1["player_id"],
                    "player2_id": None,
                    "operator_name": (p1.get("name") or "").strip(),
                    "player2_name": "BYE",
                    "operator_score": 0,
                    "player2_score": 0,
                    "winner_id": p1["player_id"],
                    "status": "completed",
                    "table_number": None,
                    "race_to": race_to,
                }
            )
        elif p2 and not p1:
            r1.append(
                {
                    "match_id": mid,
                    "tournament_id": tournament_id,
                    "bracket_type": bracket_type,
                    "round_number": 1,
                    "operator_id": None,
                    "player2_id": p2["player_id"],
                    "operator_name": "BYE",
                    "player2_name": (p2.get("name") or "").strip(),
                    "operator_score": 0,
                    "player2_score": 0,
                    "winner_id": p2["player_id"],
                    "status": "completed",
                    "table_number": None,
                    "race_to": race_to,
                }
            )
        else:
            r1.append(
                {
                    "match_id": mid,
                    "tournament_id": tournament_id,
                    "bracket_type": bracket_type,
                    "round_number": 1,
                    "operator_id": None,
                    "player2_id": None,
                    "operator_name": "BYE",
                    "player2_name": "BYE",
                    "status": "completed",
                    "operator_score": 0,
                    "player2_score": 0,
                    "winner_id": None,
                    "table_number": None,
                    "race_to": race_to,
                }
            )
    all_matches.extend(r1)
    prev_round: List[Dict[str, Any]] = r1

    for rnd in range(2, num_rounds + 1):
        cur: List[Dict[str, Any]] = []
        for j in range(len(prev_round) // 2):
            left = prev_round[2 * j]
            right = prev_round[2 * j + 1]
            pl, tbd_l = _child_side(left, players)
            pr, tbd_r = _child_side(right, players)
            mid = make_match_id(tournament_id, rnd, j, bracket_type)

            def row(
                p1: Optional[str],
                n1: str,
                p2: Optional[str],
                n2: str,
                st: str,
                wid: Optional[str],
            ) -> Dict[str, Any]:
                return {
                    "match_id": mid,
                    "tournament_id": tournament_id,
                    "bracket_type": bracket_type,
                    "round_number": rnd,
                    "operator_id": p1,
                    "player2_id": p2,
                    "operator_name": n1,
                    "player2_name": n2,
                    "operator_score": 0,
                    "player2_score": 0,
                    "winner_id": wid,
                    "status": st,
                    "table_number": (j % 32) + 1 if st == "pending" else None,
                    "race_to": race_to,
                }

            if pl and pr:
                cur.append(row(pl["player_id"], pl["name"], pr["player_id"], pr["name"], "pending", None))
            elif pl and tbd_r:
                cur.append(row(pl["player_id"], pl["name"], None, "TBD", "pending", None))
            elif pr and tbd_l:
                cur.append(row(None, "TBD", pr["player_id"], pr["name"], "pending", None))
            elif tbd_l and tbd_r:
                cur.append(row(None, "TBD", None, "TBD", "pending", None))
            elif pl and not pr and not tbd_r:
                cur.append(row(pl["player_id"], pl["name"], None, "BYE", "completed", pl["player_id"]))
            elif pr and not pl and not tbd_l:
                cur.append(row(None, "BYE", pr["player_id"], pr["name"], "completed", pr["player_id"]))
            else:
                cur.append(row(None, "BYE", None, "BYE", "completed", None))
        all_matches.extend(cur)
        prev_round = cur

    return all_matches


def generate_double_elimination(
    tournament_id: str,
    players: List[Dict[str, Any]],
    draw_size: int,
    race_to: int,
    *,
    race_to_final: int = 10,
    shuffle_seeds: bool = False,
) -> List[Dict[str, Any]]:
    """
    Full double elimination for power-of-two draw_size (tested pattern for 64).
    Includes winners bracket, losers bracket (10 rounds for 64), and one grand final.
    """
    if draw_size < 2 or draw_size & (draw_size - 1):
        raise ValueError("draw_size must be a power of 2 and >= 2")
    if draw_size != 64:
        # Generalize later; for now only 64 supported for full DE
        raise ValueError("Full double elimination is implemented for 64 players only; use single_elimination for other sizes")

    wb = generate_single_elimination(
        tournament_id, players, draw_size, race_to, shuffle_seeds=shuffle_seeds, bracket_type="winners"
    )
    out: List[Dict[str, Any]] = list(wb)

    # Losers bracket rounds 1..10 (see plan)
    lb_counts = [16, 16, 8, 8, 4, 4, 2, 2, 1, 1]
    for ri, cnt in enumerate(lb_counts, start=1):
        for j in range(cnt):
            out.append(_empty_match(tournament_id, "losers", ri, j, race_to, table_number=(j % 14) + 1))

    out.append(
        {
            "match_id": make_match_id(tournament_id, 1, 0, "grand_final"),
            "tournament_id": tournament_id,
            "bracket_type": "grand_final",
            "round_number": 1,
            "operator_id": None,
            "player2_id": None,
            "operator_name": "TBD",
            "player2_name": "TBD",
            "operator_score": 0,
            "player2_score": 0,
            "winner_id": None,
            "status": "pending",
            "table_number": 1,
            "race_to": race_to_final,
        }
    )

    return out


def build_bracket_matches(
    tournament_id: str,
    players: List[Dict[str, Any]],
    format_type: str,
    draw_size: int,
    race_to: int,
    shuffle_seeds: bool = False,
    race_to_final: int = 10,
) -> List[Dict[str, Any]]:
    set_tournament_format(tournament_id, format_type)
    set_tournament_draw_size(tournament_id, draw_size)
    if format_type == "double_elimination":
        return generate_double_elimination(
            tournament_id,
            players,
            draw_size,
            race_to,
            race_to_final=race_to_final,
            shuffle_seeds=shuffle_seeds,
        )
    return generate_single_elimination(
        tournament_id, players, draw_size, race_to, shuffle_seeds=shuffle_seeds, bracket_type="winners"
    )


def fill_tbd_name_for_advancement(
    cursor: Any,
    tournament_id: str,
    player_id: str,
    player_name: str,
    next_match_id: str,
    slot: int,
) -> None:
    if slot == 0:
        cursor.execute(
            """
            UPDATE test_tournament_matches
            SET operator_id = %s, operator_name = %s, updated_at = CURRENT_TIMESTAMP
            WHERE match_id = %s AND tournament_id = %s
            """,
            (player_id, player_name, next_match_id, tournament_id),
        )
    else:
        cursor.execute(
            """
            UPDATE test_tournament_matches
            SET player2_id = %s, player2_name = %s, updated_at = CURRENT_TIMESTAMP
            WHERE match_id = %s AND tournament_id = %s
            """,
            (player_id, player_name, next_match_id, tournament_id),
        )


def last_winners_round(draw_size: int) -> int:
    return int(math.log2(draw_size))
