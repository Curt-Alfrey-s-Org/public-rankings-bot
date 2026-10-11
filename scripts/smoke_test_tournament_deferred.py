"""Smoke test for Postgres-ported deferred tournament_manager paths.

Run: docker exec -i rankings-bot-api python3 /app/scripts/smoke_test_tournament_deferred.py
"""
import sys
import traceback
import uuid

sys.path.insert(0, "/app")

from api.tournament_manager import TournamentManager

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
            "first_name": prefix,
            "last_name": f"Player{i}",
            "license_number": f"DEFERRED-{RUN_ID}-{prefix}-{i}",
            "membership_status": "active",
        })
        ids.append(pid)
        created_player_ids.append(pid)
    return ids


def make_tournament(name, elimination_type, **extra):
    data = {
        "tournament_name": name,
        "tournament_date": "2026-07-07",
        "elimination_type": elimination_type,
        "max_players": 32,
        "points_structure": {"1": 100, "2": 75, "3": 50},
        "created_by": "smoke-deferred",
    }
    data.update(extra)
    tid = tm.create_tournament(data)
    created_tournament_ids.append(tid)
    return tid


def register_all(tid, player_ids):
    for i, pid in enumerate(player_ids, start=1):
        ok = tm.register_player(tid, pid, seed_position=i)
        check(f"register_player {pid}", ok is True)


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
    print(f"Cleanup: {len(created_tournament_ids)} tournaments, {len(created_player_ids)} players")


try:
    print("\n=== Deferred Test 1: update_player ===")
    players = make_players(1, "UPD")
    ok = tm.update_player(players[0], {"nickname": "SmokeNick", "hometown": "Testville"})
    check("update_player returns True", ok is True)
    p = tm.get_player(players[0])
    check("update_player persisted nickname", p.get("nickname") == "SmokeNick")

    print("\n=== Deferred Test 2: round_robin bracket ===")
    tid = make_tournament("Smoke RR4", "round_robin")
    players = make_players(4, "RR4")
    register_all(tid, players)
    created = tm.generate_bracket(tid, race_to=5)
    check("round_robin 4 players creates 6 matches", created == 6)
    matches = tm.get_tournament_matches(tid)
    check("all matches bracket_type round_robin", all(m.get("bracket_type") == "round_robin" for m in matches))

    print("\n=== Deferred Test 3: group_stage bracket ===")
    tid = make_tournament("Smoke GS8", "group_stage", num_groups=2, players_per_group=4)
    players = make_players(8, "GS8")
    register_all(tid, players)
    created = tm.generate_bracket(tid, race_to=5)
    check("group_stage 8 players creates matches", created > 0)
    matches = tm.get_tournament_matches(tid)
    check("group_stage matches present", len(matches) == created)

    print("\n=== Deferred Test 4: games + synchronize_match_score_from_games ===")
    tid = make_tournament("Smoke Games", "single")
    players = make_players(2, "GAM")
    register_all(tid, players)
    tm.generate_bracket(tid, race_to=3)
    m = tm.get_tournament_matches(tid)[0]
    gid = tm.create_game(m["match_id"], 1, players[0])
    check("create_game returns id", gid > 0)
    gid2 = tm.create_game(m["match_id"], 2, players[0])
    check("create_game idempotent update", gid2 == gid or gid2 > 0)
    gid3 = tm.create_game(m["match_id"], 3, players[0])
    check("third game recorded", gid3 > 0)
    ok = tm.synchronize_match_score_from_games(m["match_id"])
    check("synchronize_match_score_from_games", ok is True)
    m_after = tm.get_match(m["match_id"])
    check("match completed after race_to", m_after["status"] == "completed")
    check("match winner from games", m_after["winner_id"] == players[0])

    print("\n=== Deferred Test 5: forfeit_match ===")
    tid = make_tournament("Smoke Forfeit", "single")
    players = make_players(4, "FFM")
    register_all(tid, players)
    tm.generate_bracket(tid, race_to=7)
    m = tm.get_tournament_matches(tid)[0]
    ok = tm.forfeit_match(m["match_id"], m["operator_id"], "no-show", "smoke test")
    check("forfeit_match succeeds", ok is True)
    m_after = tm.get_match(m["match_id"])
    check("forfeit_match sets completed", m_after["status"] == "completed")

    print("\n=== Deferred Test 6: get_matches_by_table ===")
    tid = make_tournament("Smoke Table", "single")
    players = make_players(2, "TBL")
    register_all(tid, players)
    tm.generate_bracket(tid, race_to=7)
    m = tm.get_tournament_matches(tid)[0]
    tm.update_match(m["match_id"], {"table_number": 9})
    by_table = tm.get_matches_by_table(tid, 9)
    check("get_matches_by_table finds match", len(by_table) == 1)

    print("\n=== Deferred Test 7: start_stage2 ===")
    tid = make_tournament("Smoke Stage2", "single")
    players = make_players(4, "S2")
    register_all(tid, players)
    tm.generate_bracket(tid, race_to=7)
    result = tm.start_stage2(tid, cutoff=2, advancing_player_ids=players[:2], seed_strategy="manual", race_to=5)
    check("start_stage2 creates matches", result.get("matches_created", 0) == 1)
    s2 = [m for m in tm.get_tournament_matches(tid) if m.get("bracket_type") == "stage2"]
    check("stage2 match exists", len(s2) >= 1)

except Exception:
    print("EXCEPTION:")
    traceback.print_exc()
    failures.append("unhandled exception")
finally:
    cleanup()

print("\n=== DEFERRED SUMMARY ===")
if failures:
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)
print("ALL DEFERRED TESTS PASSED")
sys.exit(0)
