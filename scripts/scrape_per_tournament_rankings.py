#!/usr/bin/env python3
"""
Scrape WPBA and WPA per-tournament rankings for charts.
Outputs JSON with player, rank, total points, and points per tournament.

Usage:
  python scripts/scrape_per_tournament_rankings.py [--output data/per_tournament_rankings.json]
"""

import argparse
import json
import logging
import re
import sys
from io import BytesIO
from pathlib import Path

# Add project root for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def scrape_wpa_per_tournament(division: str = "Men") -> dict:
    """
    Scrape WPA rankings with per-tournament points.
    Returns {tournaments: [...], players: [{rank, name, points, country, tournament_points: {tourney: pts}}]}
    """
    url = "https://wpapool.com/rankings/"
    r = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    soup = BeautifulSoup(r.text, "html.parser")
    tables = soup.find_all("table")

    div_map = {"men": 0, "women": 1, "heyball": 2, "artistic": 3}
    table_idx = div_map.get(division.lower(), 0)
    if table_idx >= len(tables):
        return {"tournaments": [], "players": [], "division": division}

    table = tables[table_idx]
    rows = table.find_all("tr")
    if not rows:
        return {"tournaments": [], "players": [], "division": division}

    # Parse header: Rank, Player, License, Country, Total Points, then tournament columns
    header_cells = rows[0].find_all(["th", "td"])
    tournaments = []
    for i, cell in enumerate(header_cells[5:], 5):  # Skip first 5 cols
        name = (cell.get_text(strip=True) or "").strip()
        if name and not name.isdigit():
            tournaments.append({"index": i, "name": name})

    players = []
    for row in rows[1:]:
        cells = row.find_all(["td", "th"])
        if len(cells) < 5:
            continue
        try:
            rank = int(re.sub(r"[^\d]", "", (cells[0].get_text(strip=True) or "0")) or 0)
            name = (cells[1].get_text(strip=True) or "").strip()
            country = (cells[3].get_text(strip=True) or "").strip() or None
            total_str = (cells[4].get_text(strip=True) or "").replace(",", "")
            points = float(total_str) if total_str else 0.0

            tournament_points = {}
            for t in tournaments:
                if t["index"] < len(cells):
                    pt_str = (cells[t["index"]].get_text(strip=True) or "").replace(",", "").strip()
                    if pt_str and pt_str.isdigit():
                        tournament_points[t["name"]] = int(pt_str)

            players.append({
                "rank": rank,
                "name": name,
                "points": points,
                "country": country,
                "tournament_points": tournament_points,
            })
        except (ValueError, IndexError) as e:
            logger.debug("Skip row: %s", e)
            continue

    return {
        "source": "wpapool.com",
        "division": division,
        "tournaments": [t["name"] for t in tournaments],
        "players": players,
    }


def scrape_wpba_per_tournament() -> dict:
    """
    Scrape WPBA PDF for per-tournament points.
    PDF text layout: Rank Player Name Played Points [tourney1_pts] [tourney2_pts] ...
    Header has tournament names across multiple lines.
    """
    url = "https://static1.squarespace.com/static/5acf990e8ab7220efae54260/t/69790f395a72ed315c31d877/1769541433685/2026+WPBA+Ranking+Post+ICB+VI+MASTER.pdf"
    r = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})

    import pdfplumber

    players = []
    tournaments = []

    with pdfplumber.open(BytesIO(r.content)) as pdf:
        full_text = ""
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                full_text += t + "\n"

    lines = full_text.split("\n")
    # Find header: "Rank Player Name Played Points" then tournament name fragments
    header_line_idx = None
    for i, line in enumerate(lines):
        if "Rank" in line and "Player" in line and "Points" in line:
            header_line_idx = i
            break

    # Known WPBA 2025-2026 tournament names (from PDF header structure)
    # Header: "VI Championship Classic Masters Mezz Invitational V Championship Invitational Invitational Classic Invitational"
    # Combined with year lines: 2026 Olhausen Iron City VI, 2025 DR Pool Championship, 2025 Olhausen Colorado Classic, etc.
    WPBA_TOURNAMENT_NAMES = [
        "2026 WPBA Olhausen Iron City VI",
        "2025 WPBA DR Pool Championship",
        "2025 WPBA Olhausen Colorado Classic",
        "2025 WPBA Jacoby Tour Masters",
        "2025 WPBA Mezz Invitational",
        "2025 WPBA Soaring Eagle Invitational",
        "2024 WPBA Olhausen Capital City V",
        "2024 WPBA Jacoby Tour Championship",
        "2024 WPBA Cuespeed Invitational",
        "2024 WPBA NAPA Colorado Billiards",
        "2024 WPBA Palmetto Invitational",
        "2024 WPBA Olhausen Raxx Classic",
    ]

    # Row format: "1 Kristina Tkach 10 132,750 20000 15750 ..."
    row_re = re.compile(
        r"^(\d+)\s+(.+?)\s+(\d+)\s+([\d,]+)\s+(.*)$"
    )

    for line in lines:
        line = line.strip()
        if not line or ("Rank" in line and "Player" in line):
            continue
        m = row_re.match(line)
        if not m:
            continue
        rank_s, name_part, played_s, points_s, rest = m.groups()
        try:
            rank = int(rank_s)
            played = int(played_s)
            points = float(points_s.replace(",", ""))
        except ValueError:
            continue

        name_tokens = []
        for tok in name_part.split():
            if tok.isdigit():
                break
            name_tokens.append(tok)
        name = " ".join(name_tokens)
        if not name or len(name) < 2:
            continue

        tournament_vals = []
        for part in rest.split():
            part = part.replace(",", "")
            if part.isdigit():
                tournament_vals.append(int(part))

        # Map to tournament names
        tournament_points = {}
        for j, pts in enumerate(tournament_vals):
            name_key = WPBA_TOURNAMENT_NAMES[j] if j < len(WPBA_TOURNAMENT_NAMES) else f"Tournament_{j+1}"
            tournament_points[name_key] = pts

        players.append({
            "rank": rank,
            "name": name,
            "played": played,
            "points": points,
            "tournament_points": tournament_points,
            "tournament_points_list": tournament_vals,
        })

    # Use actual count from first player
    if players:
        n = len(players[0]["tournament_points_list"])
        tournaments = [WPBA_TOURNAMENT_NAMES[i] if i < len(WPBA_TOURNAMENT_NAMES) else f"Tournament_{i+1}" for i in range(n)]

    return {
        "source": "wpba.com PDF",
        "division": "Women",
        "tournaments": tournaments,
        "players": players,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", "-o", default="data/per_tournament_rankings.json")
    ap.add_argument("--wpa-only", action="store_true")
    ap.add_argument("--wpba-only", action="store_true")
    args = ap.parse_args()

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    result = {}

    if not args.wpba_only:
        logger.info("Scraping WPA Men per-tournament...")
        result["wpa_men"] = scrape_wpa_per_tournament("Men")
        logger.info("  -> %d players, %d tournaments", len(result["wpa_men"]["players"]), len(result["wpa_men"]["tournaments"]))

        logger.info("Scraping WPA Women per-tournament...")
        result["wpa_women"] = scrape_wpa_per_tournament("Women")
        logger.info("  -> %d players, %d tournaments", len(result["wpa_women"]["players"]), len(result["wpa_women"]["tournaments"]))

        logger.info("Scraping WPA Heyball per-tournament...")
        result["wpa_heyball"] = scrape_wpa_per_tournament("Heyball")
        logger.info("  -> %d players, %d tournaments", len(result["wpa_heyball"]["players"]), len(result["wpa_heyball"]["tournaments"]))

        logger.info("Scraping WPA Artistic per-tournament...")
        result["wpa_artistic"] = scrape_wpa_per_tournament("Artistic")
        logger.info("  -> %d players, %d tournaments", len(result["wpa_artistic"]["players"]), len(result["wpa_artistic"]["tournaments"]))

    if not args.wpa_only:
        logger.info("Scraping WPBA PDF per-tournament...")
        result["wpba_women"] = scrape_wpba_per_tournament()
        logger.info("  -> %d players, %d tournament columns", len(result["wpba_women"]["players"]), len(result["wpba_women"]["tournaments"]))

    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)

    logger.info("Wrote %s", out_path)

    # Print sample for quick inspection
    print("\n=== Sample WPA Men (first 2 players, first 3 tournaments) ===")
    if "wpa_men" in result and result["wpa_men"]["players"]:
        p = result["wpa_men"]["players"][0]
        print(json.dumps({**p, "tournament_points": dict(list(p.get("tournament_points", {}).items())[:3])}, indent=2))
    print("\n=== Sample WPBA (first 2 players) ===")
    if "wpba_women" in result and result["wpba_women"]["players"]:
        p = result["wpba_women"]["players"][0]
        out = {k: v for k, v in p.items() if k != "tournament_points_list"}
        print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
