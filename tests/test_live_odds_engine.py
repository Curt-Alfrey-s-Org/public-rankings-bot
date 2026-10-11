"""Pure unit tests for live odds race-to math (no DB)."""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running without package install
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.services.live_odds_engine import match_win_prob, rack_win_prob


def test_rack_equal_ratings_near_half() -> None:
    p = rack_win_prob(500.0, 500.0)
    assert abs(p - 0.5) < 1e-9


def test_rack_favorite_favored() -> None:
    p = rack_win_prob(600.0, 500.0)
    assert p > 0.5
    assert rack_win_prob(400.0, 500.0) < 0.5


def test_match_start_equal_half() -> None:
    p1, p2 = match_win_prob(0, 0, 7, 7, 0.5)
    assert abs(p1 - 0.5) < 1e-9
    assert abs(p2 - 0.5) < 1e-9


def test_match_decided() -> None:
    p1, p2 = match_win_prob(7, 3, 7, 7, 0.5)
    assert p1 == 1.0 and p2 == 0.0
    p1, p2 = match_win_prob(2, 7, 7, 7, 0.5)
    assert p1 == 0.0 and p2 == 1.0


def test_trailing_favorite_still_favored_but_lower() -> None:
    p_rack = rack_win_prob(650.0, 500.0)
    p_start, _ = match_win_prob(0, 0, 7, 7, p_rack)
    p_trail, _ = match_win_prob(2, 5, 7, 7, p_rack)
    assert p_start > 0.5
    assert p_trail < p_start
    assert p_trail > 0.0


def test_handicapped_races() -> None:
    # p2 needs fewer games (race 5 vs 7) → p2 favored at equal rack strength
    p1, p2 = match_win_prob(0, 0, 7, 5, 0.5)
    assert p2 > p1
