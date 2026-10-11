#!/usr/bin/env python3
"""
Parse the 2026 WPBA Classic Billiards PDF to extract per-player points.

Usage:
  python3 scripts/parse_classic_billiards_pdf.py --pdf /path/to/pdf

Optional:
  --output-json <path>
  --output-csv <path>
  --tournament-id <TXXXXXX>   Compare results to a local tournament
"""

import argparse
import csv
import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pdfplumber

from database import engine
from api.tournament_manager import TournamentManager

logger = logging.getLogger(__name__)


def normalize_name(name: str) -> str:
    cleaned = re.sub(r"[^a-z0-9\s]", "", (name or "").strip().lower())
    return re.sub(r"\s+", " ", cleaned)


def group_words_by_line(words: List[Dict], tolerance: float = 0.6) -> Dict[float, List[Dict]]:
    lines: Dict[float, List[Dict]] = {}
    for word in words:
        top = word["top"]
        matched = None
        for key in lines.keys():
            if abs(key - top) <= tolerance:
                matched = key
                break
        if matched is None:
            lines[top] = [word]
        else:
            lines[matched].append(word)
    return lines


def find_classic_header(words: List[Dict]) -> Optional[Tuple[float, float, float]]:
    lines = group_words_by_line(words)
    for top, line_words in lines.items():
        text = " ".join(w["text"] for w in line_words)
        if "Classic" in text and "Billiards" in text:
            classic = next((w for w in line_words if w["text"] == "Classic"), None)
            billiards = next((w for w in line_words if w["text"] == "Billiards"), None)
            if classic and billiards:
                center = (classic["x0"] + billiards["x1"]) / 2
                return top, classic["x0"], center
    return None


def extract_rows(pdf_path: Path) -> List[Dict]:
    results: List[Dict] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page_index, page in enumerate(pdf.pages):
            words = page.extract_words()
            header = find_classic_header(words)
            if not header:
                continue
            _, classic_x0, classic_center = header
            lines = group_words_by_line(words)
            header_rank_top = None
            for top, line_words in lines.items():
                if any(w["text"] == "Rank" for w in line_words):
                    header_rank_top = top
                    break
            for top, line_words in sorted(lines.items()):
                if header_rank_top and top <= header_rank_top:
                    continue
                line_words = sorted(line_words, key=lambda w: w["x0"])
                if not line_words:
                    continue
                first = line_words[0]
                if not (first["text"].isdigit() and first["x0"] < 60):
                    continue
                rank = int(first["text"])
                numeric_words = [w for w in line_words if re.match(r"^[\d,]+$", w["text"]) and w["x0"] >= classic_x0 - 10]
                if not numeric_words:
                    continue
                first_score_x0 = min(w["x0"] for w in numeric_words)
                name_words = [w["text"] for w in line_words if first["x0"] < w["x0"] < first_score_x0 - 5 and not re.match(r"^[\d,]+$", w["text"]) ]
                player_name = " ".join(name_words).strip()
                classic_word = min(numeric_words, key=lambda w: abs((w["x0"] + w["x1"]) / 2 - classic_center))
                classic_points = int(classic_word["text"].replace(",", ""))
                results.append({
                    "rank": rank,
                    "player_name": player_name,
                    "classic_points": classic_points,
                    "page": page_index + 1,
                })
    return results


def compare_to_tournament(results: List[Dict], tournament_id: str) -> List[Dict]:
    tm = TournamentManager(engine=engine)
    players = tm.get_tournament_players(tournament_id)
    by_name = {normalize_name(f"{p.get('first_name','')} {p.get('last_name','')}"): p for p in players}

    comparisons = []
    for row in results:
        key = normalize_name(row["player_name"])
        match = by_name.get(key)
        comparisons.append({
            "player_name": row["player_name"],
            "classic_points": row["classic_points"],
            "tournament_points": match.get("points_earned") if match else None,
            "final_placement": match.get("final_placement") if match else None,
            "match_found": bool(match),
        })
    return comparisons


def main() -> int:
    parser = argparse.ArgumentParser(description="Parse Classic Billiards PDF")
    parser.add_argument("--pdf", default="/home/ansible/2026+WPBA+Ranking+Post+Classic+Billiards+MASTER.pdf")
    parser.add_argument("--output-json", default="data/classic_billiards_points.json")
    parser.add_argument("--output-csv", default="data/classic_billiards_points.csv")
    parser.add_argument("--tournament-id", default=None)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        logger.error("PDF not found: %s", pdf_path)
        return 1

    results = extract_rows(pdf_path)
    if not results:
        logger.error("No rows extracted from PDF")
        return 1

    json_path = Path(args.output_json)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(results, indent=2))

    csv_path = Path(args.output_csv)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=["rank", "player_name", "classic_points", "page"])
        writer.writeheader()
        writer.writerows(results)

    logger.info("Extracted %s rows", len(results))
    logger.info("Wrote JSON: %s", json_path)
    logger.info("Wrote CSV: %s", csv_path)

    if args.tournament_id:
        comparisons = compare_to_tournament(results, args.tournament_id)
        mismatches = [c for c in comparisons if not c["match_found"] or c["classic_points"] != c["tournament_points"]]
        logger.info("Comparison rows: %s, mismatches: %s", len(comparisons), len(mismatches))
        preview = mismatches[:10]
        if preview:
            logger.info("Sample mismatches: %s", preview)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
