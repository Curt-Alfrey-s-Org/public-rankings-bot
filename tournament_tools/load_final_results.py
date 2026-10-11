#!/usr/bin/env python3
"""
Load tournament results from final_results.txt (WPA-style: Position, Family Name, Given Names, Country, R-points, Award).
Produces a list of ranking dicts {rank, name, points, country} for saving to the rankings DB.
The file is the most recent tournament data (e.g. Iron City Invitational VI) imported from email.
Directors can define tournament point values (1st, 2nd, 3rd, ...); when provided, those replace the file's points.
"""
import re
from pathlib import Path
from typing import List, Dict, Optional, Union

# Default path: same directory as this script
DEFAULT_PATH = Path(__file__).resolve().parent / "final_results.txt"


def parse_final_results(path: Path = DEFAULT_PATH) -> List[Dict]:
    """
    Parse final_results.txt (tab-separated, WPA-style).
    Returns list of dicts: rank, name, points, country.
    """
    if not path.exists():
        return []

    text = path.read_text(encoding="utf-8", errors="replace")
    lines = [ln.rstrip() for ln in text.splitlines()]

    # Find header line (Position\tFamily Name\tGiven Names\t...)
    start = 0
    for i, line in enumerate(lines):
        if line.strip().startswith("Position") and "\t" in line:
            start = i + 1
            break

    results = []
    for line in lines[start:]:
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 4:
            continue
        try:
            position = int(parts[0].strip())
        except ValueError:
            continue
        family = parts[1].strip()
        given = parts[2].strip()
        country = (parts[3].strip() or None)
        # Award (R-points) is last column; may be empty for lower positions
        points_str = parts[5].strip() if len(parts) > 5 else ""
        points_str = re.sub(r"[\$,]", "", points_str)
        try:
            points = float(points_str) if points_str else 0.0
        except ValueError:
            points = 0.0
        # Full name: "Given Family" (e.g. Kristina Tkach)
        name = f"{given} {family}".strip() if given or family else family or given
        results.append({
            "rank": position,
            "name": name,
            "points": points,
            "country": country,
        })
    return results


def parse_final_results_multi(path: Path = DEFAULT_PATH) -> List[List[Dict]]:
    """
    Parse final_results.txt; may contain multiple tournaments separated by a blank line and a new "Position" header.
    Returns list of result lists (one per tournament).
    """
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = [ln.rstrip() for ln in text.splitlines()]
    blocks: List[List[Dict]] = []
    current: List[Dict] = []
    in_header = False
    for i, line in enumerate(lines):
        if line.strip().startswith("Position") and "\t" in line:
            if current:
                blocks.append(current)
            current = []
            in_header = True
            continue
        if not line.strip():
            if current:
                blocks.append(current)
                current = []
            in_header = False
            continue
        if not in_header and not current and line.strip():
            in_header = False
        parts = line.split("\t")
        if len(parts) < 4:
            continue
        try:
            position = int(parts[0].strip())
        except ValueError:
            continue
        family = parts[1].strip()
        given = parts[2].strip()
        country = (parts[3].strip() or None)
        points_str = parts[5].strip() if len(parts) > 5 else ""
        points_str = re.sub(r"[\$,]", "", points_str)
        try:
            points = float(points_str) if points_str else 0.0
        except ValueError:
            points = 0.0
        name = f"{given} {family}".strip() if given or family else family or given
        current.append({
            "rank": position,
            "name": name,
            "points": points,
            "country": country,
        })
    if current:
        blocks.append(current)
    return blocks if blocks else []


def apply_points_from_definition(
    results: List[Dict], points_by_place: Union[List[float], Dict[int, float]]
) -> List[Dict]:
    """
    Override each result's points using a tournament definition.
    points_by_place: list [pts_1st, pts_2nd, ...] or dict {1: pts, 2: pts, ...}.
    Place beyond the last defined gets 0.0.
    """
    if not points_by_place:
        return results
    if isinstance(points_by_place, dict):
        get_pts = lambda rank: float(points_by_place.get(rank, 0.0))
    else:
        get_pts = lambda rank: float(points_by_place[rank - 1]) if 1 <= rank <= len(points_by_place) else 0.0
    out = []
    for r in results:
        out.append({**r, "points": get_pts(r["rank"])})
    return out


def merge_confirmed_imports_to_rankings(imports: List[Dict]) -> List[Dict]:
    """
    Merge multiple confirmed tournament imports into one ranking list.
    Each import has raw_results with points; we sum points by player across all tournaments.
    Rankings are calculated strictly based on total points (no weighting).
    Returns list of {rank, name, points, country} sorted by total points descending.
    """
    from collections import defaultdict

    player_totals: Dict[str, float] = defaultdict(float)
    player_country: Dict[str, Optional[str]] = {}

    for imp in imports:
        raw = imp.get("raw_results") or []
        if not raw:
            continue
        # Use raw points directly without weighting
        for r in raw:
            name = (r.get("name") or "").strip()
            if not name:
                continue
            player_totals[name] += float(r.get("points") or 0)
            if r.get("country") and name not in player_country:
                player_country[name] = r.get("country")

    if not player_totals:
        return []

    sorted_players = sorted(player_totals.items(), key=lambda x: -x[1])
    return [
        {
            "rank": i + 1,
            "name": name,
            "points": round(points, 2),
            "country": player_country.get(name),
        }
        for i, (name, points) in enumerate(sorted_players)
    ]


def get_tournament_results_path(project_root: Optional[Path] = None) -> Path:
    """Return path to final_results.txt (under project_root/tournament_tools or default)."""
    if project_root is not None:
        p = project_root / "tournament_tools" / "final_results.txt"
        if p.exists():
            return p
    return DEFAULT_PATH


if __name__ == "__main__":
    import sys
    proj = Path(__file__).resolve().parent.parent
    path = get_tournament_results_path(proj)
    print(f"Reading: {path}")
    rows = parse_final_results(path)
    print(f"Parsed {len(rows)} results")
    for r in rows[:15]:
        print(f"  {r['rank']}. {r['name']} ({r.get('country','')}) — {r['points']} pts")
