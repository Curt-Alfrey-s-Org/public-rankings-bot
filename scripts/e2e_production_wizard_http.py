"""
Production wizard HTTP E2E — same API sequence as TournamentWizard.tsx step 4 + Bracket scoring.
Runs inside rankings-bot-api container; mints a short-lived director JWT (no password needed).

  docker exec -i rankings-bot-api python3 /app/scripts/e2e_production_wizard_http.py
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

import jwt
import urllib.error
import urllib.request

API = os.getenv("E2E_API_BASE", "http://127.0.0.1:8003")
SECRET = os.getenv("JWT_SECRET") or os.getenv("SECRET_KEY") or ""
USER = os.getenv("E2E_USER", "director")
ROLE = os.getenv("E2E_ROLE", "director")
RUN_ID = uuid.uuid4().hex[:8]
failures: list[str] = []


def check(label: str, cond: bool) -> None:
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {label}")
    if not cond:
        failures.append(label)


def mint_token() -> str:
    if not SECRET:
        raise RuntimeError("JWT_SECRET/SECRET_KEY not set in container env")
    payload = {
        "sub": USER,
        "user": USER,
        "role": ROLE,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
    }
    return jwt.encode(payload, SECRET, algorithm="HS256")


def request(method: str, path: str, token: str, body: dict | None = None) -> tuple[int, dict | list | str]:
    url = f"{API}{path}"
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8")
            code = resp.getcode()
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        code = exc.code
    if not raw:
        return code, {}
    try:
        return code, json.loads(raw)
    except json.JSONDecodeError:
        return code, raw


def main() -> int:
    print(f"=== Production wizard HTTP E2E (user={USER}, role={ROLE}) ===")
    token = mint_token()
    check("mint JWT", bool(token))

    name = f"E2E-Wizard-{RUN_ID}"
    code, created = request(
        "POST",
        "/api/tournaments/",
        token,
        {
            "tournament_name": name,
            "tournament_date": "2026-07-07",
            "elimination_type": "single",
            "max_players": 16,
            "points_structure": {"1": 100, "2": 75, "3": 50},
            "association": "WPBA",
            "game_type": "9-ball",
            "tables_available": 4,
            "created_by": USER,
        },
    )
    tid = created.get("tournament_id") if isinstance(created, dict) else ""
    check(f"POST /api/tournaments/ -> {code} tid={tid}", code in (200, 201) and bool(tid))
    if not tid:
        print(created)
        return 1

    code, players = request("GET", "/api/tournaments/players?active_only=true", token)
    pids = [p["player_id"] for p in players[:4] if isinstance(players, list) and p.get("player_id")]
    check(f"GET players ({len(pids)} selected)", code == 200 and len(pids) >= 2)
    if len(pids) < 2:
        return 1

    code, _bulk = request("POST", f"/api/tournaments/{tid}/players/bulk", token, {"player_ids": pids})
    check(f"POST players/bulk -> {code}", code in (200, 201))

    code, gen = request("POST", f"/api/tournaments/{tid}/generate-bracket", token, {"race_to": 7})
    matches_created = gen.get("matches_created", 0) if isinstance(gen, dict) else 0
    check(f"POST generate-bracket -> {code} matches={matches_created}", code in (200, 201) and matches_created > 0)

    code, matches = request("GET", f"/api/tournaments/{tid}/matches", token)
    playable = None
    if isinstance(matches, list):
        for m in matches:
            if m.get("status") == "pending" and m.get("operator_id") and m.get("player2_id"):
                playable = m
                break
    check("GET matches has playable match", playable is not None)
    if not playable:
        return 1

    p1 = playable["operator_id"]
    mid = playable["match_id"]
    code, _score = request(
        "PUT",
        f"/api/tournaments/matches/{mid}/score",
        token,
        {"operator_score": 7, "player2_score": 3, "winner_id": p1},
    )
    check(f"PUT match score -> {code}", code == 200)

    code, prog = request("GET", f"/api/tournaments/{tid}/progress", token)
    completed = prog.get("completed", 0) if isinstance(prog, dict) else 0
    check(f"GET progress completed={completed}", code == 200 and completed >= 1)

    code, _del = request("DELETE", f"/api/tournaments/{tid}", token)
    check(f"DELETE tournament -> {code}", code in (200, 204))

    print("\n=== SUMMARY ===")
    if failures:
        for f in failures:
            print(f"  - {f}")
        return 1
    print("ALL PRODUCTION WIZARD HTTP E2E PASSED")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        import traceback

        traceback.print_exc()
        sys.exit(1)
