"""Unit tests for Test Center bracket generation (no database)."""

from api.services.bracket_engine import (
    build_bracket_matches,
    advancement_target,
    advancement_target_winner,
    parse_match_id,
    next_power_of_two,
    set_tournament_format,
    set_tournament_draw_size,
)


def test_next_power_of_two():
    assert next_power_of_two(1) == 1
    assert next_power_of_two(80) == 128


def test_single_elim_eight_players_full_tree():
    players = [{"player_id": str(i), "name": f"Player {i}", "seed": i} for i in range(1, 9)]
    tid = "test_tid"
    matches = build_bracket_matches(tid, players, "single_elimination", 8, 9, shuffle_seeds=False)
    by_round = {}
    for m in matches:
        by_round.setdefault(m["round_number"], []).append(m)
    assert len(by_round[1]) == 4
    assert len(by_round[2]) == 2
    assert len(by_round[3]) == 1
    assert sum(len(v) for v in by_round.values()) == 7


def test_match_id_parse_and_advancement():
    mid = "tid::btwinners::r1::m0"
    p = parse_match_id(mid)
    assert p == ("tid", "winners", 1, 0)
    set_tournament_draw_size("tid", 8)
    set_tournament_format("tid", "single_elimination")
    tgt = advancement_target(mid)
    assert tgt is not None
    next_mid, tid, nr, ni, slot = tgt
    assert tid == "tid"
    assert nr == 2 and ni == 0 and slot == 0
    assert "r2::m0" in next_mid


def test_double_elimination_64_total_matches():
    players = [{"player_id": str(i), "name": f"Player {i}", "seed": i} for i in range(1, 65)]
    tid = "de64"
    matches = build_bracket_matches(
        tid, players, "double_elimination", 64, 8, shuffle_seeds=False, race_to_final=10
    )
    assert len(matches) == 126
    kinds = {}
    for m in matches:
        kinds[m["bracket_type"]] = kinds.get(m["bracket_type"], 0) + 1
    assert kinds.get("winners") == 63
    assert kinds.get("losers") == 62
    assert kinds.get("grand_final") == 1


def test_wb_final_routes_to_grand_final_when_double_elim_64():
    tid = "de64"
    set_tournament_draw_size(tid, 64)
    set_tournament_format(tid, "double_elimination")
    mid = f"{tid}::btwinners::r6::m0"
    tgt = advancement_target_winner(mid)
    assert tgt is not None
    assert "grand_final" in tgt[0]
    assert tgt[4] == 0
