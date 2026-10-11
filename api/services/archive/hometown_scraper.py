"""
Scrape hometown (and other public profile info) from WPBA/WPA player pages.
Uses only public, accessibly sources. Updates players table.
"""

import logging
import re
from typing import List, Tuple

import httpx

logger = logging.getLogger(__name__)

USER_AGENT = "RankingsBot/1.0 (hometown)"
WPBA_PLAYERS_URL = "https://wpba.com/players"
WPA_RANKINGS_URL = "https://wpapool.com/rankings/"


def _normalize_name(name: str) -> str:
    return re.sub(r"\s+", " ", (name or "").strip()).lower()


def scrape_wpba_players_hometowns() -> List[Tuple[str, str]]:
    """
    Fetch WPBA players page and try to extract (player_name, hometown).
    Returns list of (name, hometown) for names we could match.
    """
    results: List[Tuple[str, str]] = []
    try:
        with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=20) as client:
            r = client.get(WPBA_PLAYERS_URL)
            r.raise_for_status()
            html = r.text
    except Exception as e:
        logger.warning("Failed to fetch WPBA players page: %s", e)
        return results
    # Look for common patterns: "Hometown:", "From ...", or data attributes
    # WPBA may use Squarespace; look for text like "Hometown" or "From" near names
    hometown_pattern = re.compile(
        r"(?:hometown|from|location)\s*[:\-]\s*([^<\n]+)",
        re.IGNORECASE
    )
    name_pattern = re.compile(
        r"<[^>]*class=[^>]*player[^>]*>([^<]+)</",
        re.IGNORECASE
    )
    for m in hometown_pattern.finditer(html):
        hometown = m.group(1).strip()
        if len(hometown) > 2 and len(hometown) < 120:
            # Try to find preceding player name in nearby context
            start = max(0, m.start() - 500)
            block = html[start : m.end() + 50]
            name_m = name_pattern.search(block)
            if name_m:
                name = name_m.group(1).strip()
                if name and not name.startswith("http"):
                    results.append((name, hometown))
    # Alternative: look for "Name" ... "Hometown" in table-like structure
    if not results:
        row_pattern = re.compile(
            r"<tr[^>]*>([\s\S]*?)</tr>",
            re.IGNORECASE
        )
        cell_pattern = re.compile(r"<t[dh][^>]*>([^<]+)</t[dh]>", re.IGNORECASE)
        for row_m in row_pattern.finditer(html):
            row = row_m.group(1)
            cells = cell_pattern.findall(row)
            if len(cells) >= 2:
                name = cells[0].strip()
                hometown = cells[1].strip() if len(cells) > 1 else ""
                if name and hometown and 2 < len(hometown) < 120:
                    results.append((name, hometown))
    # Dedupe by name (keep first)
    seen = set()
    unique = []
    for name, hometown in results:
        key = _normalize_name(name)
        if key not in seen:
            seen.add(key)
            unique.append((name, hometown))
    return unique


def update_players_hometowns_from_scrape(conn, matches: List[Tuple[str, str]]) -> int:
    """Update players table hometown from list of (normalized_name, hometown). Returns count updated. Requires DB connection (Postgres)."""
    if not matches:
        return 0
    cursor = conn.cursor()
    updated = 0
    try:
        for name, hometown in matches:
            parts = [p.strip() for p in re.sub(r"\s+", " ", name).split() if p.strip()]
            if len(parts) >= 2:
                first, last = parts[0], " ".join(parts[1:])
                cursor.execute(
                    "UPDATE players SET hometown = %s WHERE LOWER(TRIM(first_name)) = %s AND LOWER(TRIM(last_name)) = %s AND membership_status = 'active'",
                    (hometown[:200], first.lower(), last.lower()),
                )
                if cursor.rowcount > 0:
                    updated += cursor.rowcount
            elif len(parts) == 1:
                cursor.execute(
                    "UPDATE players SET hometown = %s WHERE (LOWER(TRIM(first_name)) = %s OR LOWER(TRIM(last_name)) = %s) AND membership_status = 'active'",
                    (hometown[:200], parts[0].lower(), parts[0].lower()),
                )
                if cursor.rowcount > 0:
                    updated += cursor.rowcount
        conn.commit()
    finally:
        pass
    return updated


def run_scrape_hometowns(conn) -> dict:
    """Scrape WPBA (and optionally WPA) for hometowns and update players. Returns { updated, scraped, errors }. Requires DB connection (Postgres)."""
    scraped = scrape_wpba_players_hometowns()
    updated = 0
    try:
        updated = update_players_hometowns_from_scrape(conn, scraped)
    except Exception as e:
        logger.exception("Failed to update hometowns: %s", e)
        return {"updated": 0, "scraped": len(scraped), "errors": [str(e)]}
    return {"updated": updated, "scraped": len(scraped), "errors": []}
