"""
Parse tournament bracket/result pages for placements and match scores.
Supports: event page text (Champion / Runner-up / Final score), ExternalPool-style HTML when available.
"""

import asyncio
import logging
import re
from typing import List, Dict, Optional, Any

from scrapers.fetch_utils import get_with_retry

logger = logging.getLogger(__name__)


def _llm_extract_bracket(page_text: str) -> Optional[Dict[str, Any]]:
    """Ask Ollama to extract bracket data from page text. Returns None if unavailable."""
    try:
        from api.services.ollama_extractor import extract_bracket_data
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(extract_bracket_data(page_text))
        finally:
            loop.close()
    except Exception as e:
        logger.debug("LLM bracket extraction unavailable: %s", e)
        return None

HEADERS = {"User-Agent": "RankingsBot/1.0 (bracket-parser)"}


def _parse_champion_runner_up_from_html(html: str) -> Dict[str, Any]:
    """
    Extract champion, runner-up, and final score from event page text.
    Looks for patterns like: Champion: X, Runner-up: Y, Final: 9-7 or Winner: X def. Y 9-7.
    """
    out = {"champion": None, "runner_up": None, "final_score": None, "placements": [], "matches": []}
    # Strip tags for simple text search
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()

    # Champion: Name / Winner: Name
    for pattern in (
        r"(?:Champion|Winner)\s*[:\s]+([A-Za-z\s\-\.']{2,50}?)(?:\s*[,\n]|\s*Runner|\s*Final|\s*def\.|$)",
        r"1st\s*[:\s]+([A-Za-z\s\-\.']{2,50}?)(?:\s*[,\n]|\s*2nd|$)",
    ):
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            out["champion"] = m.group(1).strip()[:255]
            break

    # Runner-up: Name / 2nd: Name
    for pattern in (
        r"Runner[- ]?up\s*[:\s]+([A-Za-z\s\-\.']{2,50}?)(?:\s*[,\n]|\s*Final|$)",
        r"2nd\s*[:\s]+([A-Za-z\s\-\.']{2,50}?)(?:\s*[,\n]|$)",
    ):
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            out["runner_up"] = m.group(1).strip()[:255]
            break

    # Final score: 9-7 or 9 – 7 or Final: 9-7
    score_m = re.search(
        r"(?:Final|Score)\s*[:\s]*(\d+)\s*[–\-]\s*(\d+)|(\d+)\s*[–\-]\s*(\d+)\s*(?:$|\.|\s)",
        text,
        re.IGNORECASE,
    )
    if score_m:
        g = score_m.groups()
        if g[0] is not None and g[1] is not None:
            out["final_score"] = f"{g[0]}-{g[1]}"
        elif g[2] is not None and g[3] is not None:
            out["final_score"] = f"{g[2]}-{g[3]}"

    # Build placements from champion/runner_up
    if out["champion"]:
        out["placements"].append({"place": 1, "player_name": out["champion"]})
    if out["runner_up"]:
        out["placements"].append({"place": 2, "player_name": out["runner_up"]})

    # Single final match if we have both and a score
    if out["champion"] and out["runner_up"] and out["final_score"]:
        try:
            a, b = out["final_score"].split("-")
            s1, s2 = int(a.strip()), int(b.strip())
            out["matches"].append({
                "operator_name": out["champion"],
                "player2_name": out["runner_up"],
                "operator_score": s1,
                "player2_score": s2,
                "winner_name": out["champion"],
                "round_num": "Final",
            })
        except ValueError:
            out["matches"].append({
                "operator_name": out["champion"],
                "player2_name": out["runner_up"],
                "operator_score": None,
                "player2_score": None,
                "winner_name": out["champion"],
                "round_num": "Final",
            })
    return out


def _parse_externalpool_matches(html: str) -> List[Dict]:
    """
    Try to parse match rows from ExternalPool bracket page.
    Many bracket pages are JS-rendered; this looks for table rows or data attributes with player names and scores.
    """
    matches = []
    # Common patterns: "Player A 9" - "7 Player B" or data-score, data-player
    # Table: <tr> ... <td>Name</td><td>9</td>-<td>7</td><td>Name</td>
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")

    # Find tables that might be bracket/results
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        for tr in rows:
            cells = tr.find_all(["td", "th"])
            if len(cells) < 4:
                continue
            texts = [c.get_text(strip=True) for c in cells]
            # Look for two names and two numbers (scores)
            names = []
            scores = []
            for t in texts:
                if re.match(r"^\d+$", t):
                    scores.append(int(t))
                elif len(t) > 2 and re.search(r"[A-Za-z]", t):
                    names.append(t[:255])
            if len(names) >= 2 and len(scores) >= 2:
                matches.append({
                    "operator_name": names[0],
                    "player2_name": names[1],
                    "operator_score": scores[0],
                    "player2_score": scores[1],
                    "winner_name": names[0] if scores[0] > scores[1] else names[1],
                    "round_num": "Bracket",
                })
    return matches


def fetch_and_parse_event_page(event_url: str) -> Dict[str, Any]:
    """
    Fetch event page HTML and parse champion, runner-up, final score, and optionally matches.
    Falls back to LLM extraction when regex returns no champion.
    """
    try:
        r = get_with_retry(event_url, headers=HEADERS, timeout=20, max_retries=2)
        r.raise_for_status()
        result = _parse_champion_runner_up_from_html(r.text)

        if not result["champion"] and not result["placements"]:
            stripped = re.sub(r"<[^>]+>", " ", r.text)
            stripped = re.sub(r"\s+", " ", stripped).strip()
            llm_result = _llm_extract_bracket(stripped)
            if llm_result:
                logger.info("LLM fallback extracted bracket data for %s", event_url[:60])
                return llm_result

        return result
    except Exception as e:
        logger.warning("Failed to fetch/parse event page %s: %s", event_url[:60], e)
        return {"champion": None, "runner_up": None, "final_score": None, "placements": [], "matches": []}


def fetch_and_parse_bracket(bracket_url: str) -> Dict[str, Any]:
    """
    Fetch bracket page (e.g. ExternalPool) and parse placements + matches.
    Falls back to LLM extraction when regex/table parsing yields nothing.
    Returns { placements: [{place, player_name}], matches: [{...}] }.
    """
    out = {"placements": [], "matches": []}
    try:
        r = get_with_retry(bracket_url, headers=HEADERS, timeout=25, max_retries=2)
        r.raise_for_status()
        html = r.text
        matches = _parse_externalpool_matches(html)
        if matches:
            out["matches"] = matches
        from_event = _parse_champion_runner_up_from_html(html)
        if from_event["placements"]:
            out["placements"] = from_event["placements"]
        if from_event["matches"] and not out["matches"]:
            out["matches"] = from_event["matches"]

        if not out["placements"] and not out["matches"]:
            stripped = re.sub(r"<[^>]+>", " ", html)
            stripped = re.sub(r"\s+", " ", stripped).strip()
            llm_result = _llm_extract_bracket(stripped)
            if llm_result:
                logger.info("LLM fallback extracted bracket data for %s", bracket_url[:60])
                out["placements"] = llm_result.get("placements", [])
                out["matches"] = llm_result.get("matches", [])
    except Exception as e:
        logger.warning("Failed to fetch/parse bracket %s: %s", bracket_url[:60], e)
    return out


def get_tournament_results(
    event_url: str,
    bracket_url: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Get placements and match scores for a tournament: event page first, then bracket if provided.
    Merges champion/runner-up/final_score from event page with bracket matches when available.
    """
    result = fetch_and_parse_event_page(event_url)
    if bracket_url:
        bracket = fetch_and_parse_bracket(bracket_url)
        if bracket["matches"]:
            result["matches"] = bracket["matches"]
        if bracket["placements"] and not result["placements"]:
            result["placements"] = bracket["placements"]
    return result
