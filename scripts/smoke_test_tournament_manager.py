"""
Disposable smoke test for the Postgres-fixed api/tournament_manager.py core path:
create tournament -> register players -> generate bracket -> record match results
-> verify advancement, for both single and double elimination, across several
bracket sizes (including non-power-of-2 with a BYE, and a non-8-player double
elim to prove the losers-bracket routing generalization).

Run inside the rankings-bot-api container (has DB env vars + deps installed):
    docker exec -i rankings-bot-api python3 /app/scripts/smoke_test_tournament_manager.py
    docker exec -i rankings-bot-api python3 /app/scripts/smoke_test_tournament_deferred.py

Creates and then deletes its own throwaway players/tournaments; does not touch
any real production data. Exits non-zero on first failed assertion.
"""
import sys
import traceback
import uuid

sys.path.insert(0, "/app")

from api.tournament_manager import TournamentManager  # noqa: E402

tm = TournamentManager()
RUN_ID = uuid.uuid4().hex[:8]

created_player_ids = []
created_tournament_ids = []
failures = []


def check(label, cond):
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {label}")
    if not cond:
        failures.append(label)


def make_players(n, prefix):
    ids = []
    for i in range(1, n + 1):
        pid = tm.create_player({
            "first_name": f"{prefix}",
            "last_name": f"Player{i}",
            "license_number": f"SMOKETEST-{RUN_ID}-{prefix}-{i}",
            "membership_status": "active",
        })
        ids.append(pid)
        created_player_ids.append(pid)
    return ids


def make_tournament(name, elimination_type):
    tid = tm.create_tournament({
        "tournament_name": name,
        "tournament_date": "2026-07-06",
        "elimination_type": elimination_type,
        "max_players": 32,
        "points_structure": {"1": 100, "2": 75, "3": 50},
        "created_by": "smoke-test",
    })
    created_tournament_ids.append(tid)
    return tid


def register_all(tid, player_ids):
    for i, pid in enumerate(player_ids, start=1):
        ok = tm.register_player(tid, pid, seed_position=i)
        check(f"register_player {pid} seed {i}", ok is True)


def play_round(tid, winner_rule):
    """Resolve every currently-playable pending match once. Returns True if any progress was made."""
    matches = tm.get_tournament_matches(tid)
    progressed = False
    for m in matches:
        if m["status"] in ("completed", "bye"):
            continue
        p1, p2 = m.get("operator_id"), m.get("player2_id")
        if not p1 or not p2:
            continue
        winner_id = winner_rule(m, p1, p2)
        loser_score = 3
        ok = tm.update_match_score(m["match_id"], 7 if winner_id == p1 else loser_score,
                                    7 if winner_id == p2 else loser_score)
        check(f"update_match_score {m['match_id']} winner={winner_id}", ok is True)
        progressed = True
    return progressed


def play_out(tid, winner_rule, max_iters=50):
    for _ in range(max_iters):
        if not play_round(tid, winner_rule):
            break


def p1_always_wins(m, p1, p2):
    return p1


def cleanup():
    for tid in created_tournament_ids:
        tm.delete_tournament(tid)
    if created_player_ids:
        conn = tm.get_connection()
        cur = conn.cursor()
        placeholders = ", ".join(["%s"] * len(created_player_ids))
        cur.execute(f"DELETE FROM player_statistics WHERE player_id IN ({placeholders})", created_player_ids)
        cur.execute(f"DELETE FROM players WHERE player_id IN ({placeholders})", created_player_ids)
        conn.commit()
        conn.close()
    print(f"Cleanup done: removed {len(created_tournament_ids)} tournaments, {len(created_player_ids)} players")


try:
    # --- Test 1: single elimination, 4 players (power of 2, no bye) ---
    print("\n=== Test 1: single elimination, 4 players ===")
    tid = make_tournament("SmokeTest SE4", "single")
    players = make_players(4, "SE4")
    register_all(tid, players)
    created = tm.generate_bracket(tid, race_to=7)
    check("generate_bracket SE4 created matches", created == 3)
    play_out(tid, p1_always_wins)
    matches = tm.get_tournament_matches(tid)
    final = [m for m in matches if m["round_number"] == 2]
    check("SE4 final exists and completed", len(final) == 1 and final[0]["status"] == "completed")
    check("SE4 final winner is top seed", final[0]["winner_id"] == players[0])

    # --- Test 2: single elimination, 5 players (non-power-of-2, exercises BYE + advancement) ---
    print("\n=== Test 2: single elimination, 5 players (BYE) ===")
    tid = make_tournament("SmokeTest SE5", "single")
    players = make_players(5, "SE5")
    register_all(tid, players)
    created = tm.generate_bracket(tid, race_to=7)
    check("generate_bracket SE5 created matches (4+2+1)", created == 7)
    matches = tm.get_tournament_matches(tid)
    byes = [m for m in matches if m["status"] == "bye"]
    check("SE5 has exactly 3 BYE matches (8-slot bracket, 5 real players)", len(byes) == 3)
    r2 = [m for m in matches if m["round_number"] == 2]
    all_advanced = all(
        any(m.get("operator_id") == b["winner_id"] or m.get("player2_id") == b["winner_id"] for m in r2)
        for b in byes
    )
    check("SE5 all 3 BYE winners were advanced into round 2 automatically", all_advanced)
    play_out(tid, p1_always_wins)
    final = [m for m in tm.get_tournament_matches(tid) if m["round_number"] == 3]
    check("SE5 final completed", len(final) == 1 and final[0]["status"] == "completed")

    # --- Test 3: double elimination, 4 players ---
    print("\n=== Test 3: double elimination, 4 players ===")
    tid = make_tournament("SmokeTest DE4", "double")
    players = make_players(4, "DE4")
    register_all(tid, players)
    created = tm.generate_bracket(tid, race_to=7)
    check("generate_bracket DE4 created matches", created == 6)
    play_out(tid, p1_always_wins)
    matches = tm.get_tournament_matches(tid)
    by_id = {m["match_id"]: m for m in matches}
    gf = by_id.get(f"{tid}-GF-M01")
    check("DE4 grand final exists and completed", gf is not None and gf["status"] == "completed")
    l1 = by_id.get(f"{tid}-L1-M01")
    l2 = by_id.get(f"{tid}-L2-M01")
    check("DE4 L1 completed", l1 is not None and l1["status"] == "completed")
    check("DE4 L2 completed", l2 is not None and l2["status"] == "completed")
    check("DE4 L1 pairs the two WB R1 losers", {l1["operator_id"], l1["player2_id"]} == {players[1], players[3]})
    check("DE4 L2 pairs L1 winner with WB final loser", players[2] in (l2["operator_id"], l2["player2_id"]))

    # --- Test 4: double elimination, 8 players ---
    print("\n=== Test 4: double elimination, 8 players ===")
    tid = make_tournament("SmokeTest DE8", "double")
    players = make_players(8, "DE8")
    register_all(tid, players)
    created = tm.generate_bracket(tid, race_to=7)
    check("generate_bracket DE8 created matches", created == 14)
    play_out(tid, p1_always_wins)
    matches = tm.get_tournament_matches(tid)
    by_id = {m["match_id"]: m for m in matches}
    gf = by_id.get(f"{tid}-GF-M01")
    check("DE8 grand final completed", gf is not None and gf["status"] == "completed")
    for mid in [f"{tid}-L1-M01", f"{tid}-L1-M02", f"{tid}-L2-M01", f"{tid}-L2-M02", f"{tid}-L3-M01", f"{tid}-L4-M01"]:
        m = by_id.get(mid)
        check(f"DE8 {mid} completed", m is not None and m["status"] == "completed")

    # --- Test 5: double elimination, 16 players ---
    print("\n=== Test 5: double elimination, 16 players ===")
    tid = make_tournament("SmokeTest DE16", "double")
    players = make_players(16, "DE16")
    register_all(tid, players)
    created = tm.generate_bracket(tid, race_to=7)
    check("generate_bracket DE16 created matches", created == 30)
    play_out(tid, p1_always_wins)
    matches = tm.get_tournament_matches(tid)
    by_id = {m["match_id"]: m for m in matches}
    gf = by_id.get(f"{tid}-GF-M01")
    check("DE16 grand final completed", gf is not None and gf["status"] == "completed")
    incomplete = [m for m in matches if m["status"] not in ("completed", "bye")]
    check("DE16 all matches resolved (no stragglers)", len(incomplete) == 0)

    # --- Test 6: set_match_outcome (forfeit/DQ path) + update_match (table assignment) ---
    print("\n=== Test 6: set_match_outcome + update_match ===")
    tid = make_tournament("SmokeTest SE4-Forfeit", "single")
    players = make_players(4, "FFT")
    register_all(tid, players)
    tm.generate_bracket(tid, race_to=7)
    matches = tm.get_tournament_matches(tid)
    m0 = matches[0]
    ok = tm.update_match(m0["match_id"], {"table_number": 3})
    check("update_match sets table_number", ok is True)
    m0_after = tm.get_match(m0["match_id"])
    check("update_match persisted table_number", m0_after["table_number"] == 3)
    ok = tm.set_match_outcome(m0["match_id"], outcome="forfeit", reason="no-show", winner_id=m0["operator_id"])
    check("set_match_outcome succeeds", ok is True)
    m0_after = tm.get_match(m0["match_id"])
    check("set_match_outcome sets status completed", m0_after["status"] == "completed")
    check("set_match_outcome sets correct winner", m0_after["winner_id"] == m0["operator_id"])
    r2 = [m for m in tm.get_tournament_matches(tid) if m["round_number"] == 2][0]
    check("set_match_outcome advanced winner to round 2", m0["operator_id"] in (r2["operator_id"], r2["player2_id"]))

except Exception:
    print("EXCEPTION DURING SMOKE TEST:")
    traceback.print_exc()
    failures.append("unhandled exception")
finally:
    cleanup()

print("\n=== SUMMARY ===")
if failures:
    print(f"{len(failures)} FAILURE(S):")
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)
else:
    print("ALL CHECKS PASSED")
    sys.exit(0)
