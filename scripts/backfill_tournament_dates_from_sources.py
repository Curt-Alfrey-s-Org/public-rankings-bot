#!/usr/bin/env python3
"""
Backfill tournament_history.date from authoritative sources:
- WPBA: wpba.com events pages (discovery)
- WPA: wpapool.com calendar/events (discovery)
- WPA MEC: wpapool.com mec-events API + event page JSON-LD (Heyball, Artistic, etc.)
- Web search: for remaining missing dates

Use --dry-run to preview without writing.
"""

import argparse
import json
import logging
import re
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx

from database import get_database_manager

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def _normalize_name(s: str) -> str:
    """Lowercase, collapse spaces, remove punctuation for matching."""
    if not s:
        return ""
    return re.sub(r"[^\w\s]", "", (s or "").lower()).strip()


def _is_news_or_event_article(name: str) -> bool:
    """Skip news articles and event announcements (not actual tournaments)."""
    if not name or len(name) < 20:
        return False
    n = name.lower()
    patterns = (
        "crowned", "congratulates", "launches", "passes at", "introducing",
        "concludes in", "concludes with", "kick off", "officially declare",
        "looks forward", "celebrates", "come home",
    )
    return any(p in n for p in patterns)


def _name_matches(db_name: str, event_name: str) -> bool:
    """Check if tournament names match (fuzzy)."""
    n1 = _normalize_name(db_name)
    n2 = _normalize_name(event_name)
    if not n1 or not n2:
        return False
    # Exact or one contains the other
    if n1 == n2:
        return True
    # "2026 WPBA Olhausen Iron City VI" vs "WPBA Iron City Invitational VI"
    # Remove year prefix for comparison
    n1_no_year = re.sub(r"^\d{4}\s*", "", n1)
    n2_no_year = re.sub(r"^\d{4}\s*", "", n2)
    if n1_no_year in n2_no_year or n2_no_year in n1_no_year:
        return True
    # Key tokens overlap (e.g. "iron city", "heyball", "world championship")
    t1 = set(n1.split())
    t2 = set(n2.split())
    return len(t1 & t2) >= 2


def _collect_discovery_dates() -> dict[str, str]:
    """Fetch dates from WPBA and WPA discovery. Returns name -> date (ISO)."""
    out: dict[str, str] = {}
    try:
        from scrapers.tournament_history_discovery import discover_past_events

        events = discover_past_events(wpba=True, wpa=True, include_future=True)
        for e in events:
            name = (e.get("name") or "").strip()
            # Use start_date for past (when played), end_date for future
            start = e.get("start_date")
            end = e.get("end_date")
            dt = start or end
            if name and dt:
                # Prefer start for "when played"; avoid Dec 31 placeholders when possible
                if start and end and end.endswith("-12-31") and start != end:
                    dt = start
                out[name] = dt
                # Also add normalized variants
                out[_normalize_name(name)] = dt
    except Exception as e:
        logger.warning("Discovery failed: %s", e)
    return out


def _collect_wpa_mec_dates(include_past: bool = True) -> dict[str, str]:
    """Fetch WPA MEC events and parse dates from event pages (including past)."""
    out: dict[str, str] = {}
    today = date.today()
    mec_url = "https://wpapool.com/wp-json/wp/v2/mec-events?per_page=100"
    script_re = re.compile(
        r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        re.IGNORECASE | re.DOTALL,
    )

    try:
        with httpx.Client(
            headers={"User-Agent": "RankingsBot/1.0 (backfill-dates)"},
            timeout=12.0,
            follow_redirects=True,
        ) as client:
            # Fetch MEC events
            posts: list[dict] = []
            for page in (1, 2):
                r = client.get(f"{mec_url}&page={page}")
                if r.status_code != 200:
                    break
                chunk = r.json()
                if not isinstance(chunk, list) or not chunk:
                    break
                posts.extend([p for p in chunk if isinstance(p, dict)])
                if len(chunk) < 100:
                    break

            for post in posts[:60]:  # Limit to avoid hammering
                if not isinstance(post, dict):
                    continue
                link = str(post.get("link") or "").strip()
                if not link:
                    continue
                title = ""
                if isinstance(post.get("title"), dict):
                    title = (post.get("title", {}).get("rendered") or "").strip()
                else:
                    title = str(post.get("title") or "").strip()
                title = re.sub(r"<[^>]+>", "", title).strip()
                if not title or len(title) < 5:
                    continue

                try:
                    html = client.get(link).text
                except Exception:
                    continue

                start_d, end_d = None, None
                for m in script_re.finditer(html):
                    try:
                        data = json.loads(m.group(1).strip())
                    except Exception:
                        continue
                    for node in (data if isinstance(data, list) else [data]):
                        if not isinstance(node, dict) or node.get("@type") != "Event":
                            continue
                        start = node.get("startDate")
                        end = node.get("endDate")
                        if start:
                            try:
                                start_d = datetime.fromisoformat(start.replace("Z", "+00:00")).date()
                            except Exception:
                                pass
                        if end:
                            try:
                                end_d = datetime.fromisoformat(end.replace("Z", "+00:00")).date()
                            except Exception:
                                pass
                        break
                    if start_d or end_d:
                        break

                dt = start_d or end_d
                if not dt:
                    continue
                if not include_past and dt < today:
                    continue

                out[title] = dt.isoformat()
                out[_normalize_name(title)] = dt.isoformat()
    except Exception as e:
        logger.warning("WPA MEC fetch failed: %s", e)
    return out


def _web_search_dates(missing: list[tuple[str, str]], limit: int = 20) -> dict[str, str]:
    """Placeholder for web search - Google blocks automated requests.
    Dates from web search are added to _known_dates_from_research() instead."""
    return {}


def _known_dates_from_research() -> dict[str, str]:
    """Dates from WPBA/WPA official pages and web search (when played, not scrape/edit dates)."""
    return {
        # WPBA 2025 past (web search verified)
        "2025 WPBA Olhausen Iron City Invitational V": "2025-01-29",
        "2025 WPBA Olhausen Raxx Mezz Invitational": "2025-04-30",
        "2025 WPBA Soaring Eagle Masters": "2025-06-05",
        "2025 Oneida WPA Women's World 8-ball Championship": "2025-07-02",
        "2025 WPBA Felt Colorado Classic": "2025-08-21",
        # WPBA 2026 (completed + future)
        "2026 WPBA Iron City Invitational VI": "2026-01-14",
        "WPBA Iron City Invitational VI": "2026-01-14",
        "WPBA Classic Billiards Players Championship": "2026-02-12",
        "WPBA Raxx Mezz Olhausen CPBA Invitational": "2026-03-11",
        "WPBA Mezz Olhausen Raxx Invitational": "2026-03-15",
        "WPBA Raxx Mezz Olhausen Invitational": "2026-03-15",
        "WPBA Island Casino US Open": "2026-04-15",
        "WPBA Soaring Eagle Masters": "2026-06-04",
        "WPBA Bike Week II": "2026-06-10",
        "WPBA Felt Colorado Classic": "2026-08-19",
        "WPBA Borderline Billiards": "2026-10-07",
        "WPBA DR Pool/Jacoby Tour Championship": "2026-12-09",
        # Aliases
        "2026 WPBA Olhausen Iron City VI": "2026-01-14",
        "WPBA Olhausen IronCity 2025": "2025-04-30",
        "2025 WPBA Olhausen Colorado Classic": "2025-08-21",
        "WPBA Olhausen Colorado Classic 2025": "2025-08-21",
        "WPBA Raxx Mezz 2025": "2025-04-30",
        "WPBA SE Masters 2025": "2025-06-05",
        # WPA 2025 (web search)
        "2025 WPA World Nine-ball Championship": "2025-07-21",
        "WPA World Nine-ball Championship 2025": "2025-07-21",
        "WPA World Nine-ball Championship": "2025-07-21",
        "2025 WPA Heyball World Championship": "2025-11-01",
        "WPA Heyball World Championship 2025": "2025-11-01",
        "WPA Heyball World Championship": "2025-11-01",
        "2025 WPA APD Artistic Pool World Championship": "2025-02-12",
        "WPA Artistic Pool World Championship 2025": "2025-02-12",
        "WPA APD Artistic Pool World Championship": "2025-02-12",
        "2025 Oneida WPA Women's World 8-ball Championship": "2025-07-02",
        "Oneida WPA Women's World 8-ball Championship 2025": "2025-07-02",
        # Heyball 2025 (web search verified - correct dates)
        "Heyball World Championship 2025": "2025-11-01",
        "Heyball Champion of Champions 2025": "2025-09-18",
        "African Heyball Open 2025": "2025-11-27",
        "North American Heyball Open 2025": "2025-10-22",
        "Pan American Heyball Open 2025": "2025-10-16",
        "Oceania Heyball Open 2025": "2025-09-24",
        "Asian Heyball Open 2025": "2025-10-08",
        "European Heyball Open 2025": "2025-11-01",
        "2025 WPA African Heyball Open": "2025-11-27",
        "2025 WPA African Heyball Open Concludes in Sharm El Sheikh With Spectacular Champions and Global Participation": "2025-11-27",
        # Artistic 2025 (web search: Feb 12-15, Bay City MI)
        "WPA APD Artistic Pool World Championship": "2025-02-12",
        # WPA 2025 (web search verified - actual play dates, not scrape dates)
        "Kamui Las Vegas Open 2025": "2025-02-19",
        "International 9-Ball Open 2025": "2025-11-14",
        "Little Monster International Open 2025": "2025-11-25",
        "2025 WPA Kamui Women's 9-Ball World Championship": "2025-12-18",
        "WPA Kamui Women's 9-Ball World Championship 2025": "2025-12-18",
        "WPA 9-Ball World Championship 2025": "2025-07-21",
        "9-Ball World Championship 2025": "2025-07-21",
        # Iron City VI was 2026 (fix mislabeled 2025)
        "2025 WPBA Iron City Invitational VI": "2026-01-14",
        # More WPA 2025 (web search verified)
        "Indonesia International 10-Ball Open 2025": "2025-07-12",
        "Jax Men's International Open 2025": "2025-12-16",
        "Poison Saigon 9-Ball Open 2025": "2025-09-20",
    }


def backfill_from_sources(
    dry_run: bool = True,
    web_search: bool = False,
    known_only: bool = False,
) -> dict:
    """Backfill tournament_history.date from discovery, MEC, and known dates."""
    db = get_database_manager()
    conn = db.engine.connect()

    # Build lookup: normalized name -> date
    lookup: dict[str, str] = {}
    lookup.update(_known_dates_from_research())

    if not known_only:
        # Add discovery dates
        for name, dt in _collect_discovery_dates().items():
            lookup[name] = dt
            lookup[_normalize_name(name)] = dt

        # Add WPA MEC dates (past + future)
        for name, dt in _collect_wpa_mec_dates(include_past=True).items():
            lookup[name] = dt
            lookup[_normalize_name(name)] = dt

    # Fetch tournaments needing dates (null/placeholder) or matching known_dates for correction
    from sqlalchemy import text

    known_names = list(_known_dates_from_research().keys())
    # Suspicious dates: often WPA scrape/page-update dates, not actual play dates
    suspicious_dates = [
        "2025-12-08", "2025-12-18", "2025-12-22", "2026-02-24",
    ]
    result = conn.execute(
        text("""
            SELECT tournament_id, name, year, date, association
            FROM tournament_history
            WHERE (
                (date IS NULL OR date IN ('2025-12-31', '2026-01-01', '2026-12-31'))
                OR (name = ANY(:known_names))
                OR (date::text = ANY(:suspicious_dates))
            )
              AND name NOT LIKE '% Rankings (%'
              AND tournament_id NOT LIKE 'rankings_snapshot%'
              AND name NOT LIKE 'Total Points'
            ORDER BY year DESC NULLS LAST, name
        """),
        {"known_names": known_names, "suspicious_dates": suspicious_dates},
    )
    rows = result.fetchall()

    updated = 0
    cleared = 0
    skipped = 0
    missing: list[tuple[str, str]] = []

    for row in rows:
        tid, name, year, current_date, assoc = row[0], row[1], row[2], row[3], row[4]
        name = (name or "").strip()
        if not name:
            continue
        if _is_news_or_event_article(name):
            skipped += 1
            continue

        # Find matching date
        new_date = None
        for key in [name, _normalize_name(name), re.sub(r"^\d{4}\s+", "", name)]:
            if key in lookup:
                new_date = lookup[key]
                break

        # Try fuzzy match
        if not new_date:
            norm = _normalize_name(name)
            for k, v in lookup.items():
                if _name_matches(name, k) or (norm and k == norm):
                    new_date = v
                    break

        if new_date:
            updated += 1
            logger.info("Match: %s -> %s", name[:60], new_date)
            if not dry_run:
                conn.execute(
                    text("""
                        UPDATE tournament_history
                        SET date = CAST(:dt AS date), updated_at = CURRENT_TIMESTAMP
                        WHERE tournament_id = :tid
                    """),
                    {"dt": new_date, "tid": tid},
                )
        else:
            skipped += 1
            missing.append((tid, name))
            # Clear placeholder dates (year-only) when we have no real match
            if current_date and str(current_date) in ("2025-12-31", "2026-01-01", "2026-12-31"):
                cleared += 1
                if not dry_run:
                    conn.execute(
                        text("""
                            UPDATE tournament_history
                            SET date = NULL, updated_at = CURRENT_TIMESTAMP
                            WHERE tournament_id = :tid
                        """),
                        {"tid": tid},
                    )
                logger.info("Cleared placeholder date for %s (no real month/day)", name[:50])

    # Web search for remaining missing (tid -> date)
    if web_search and missing:
        ws_dates = _web_search_dates(missing, limit=15)
        for tid, name in missing:
            if tid in ws_dates:
                new_date = ws_dates[tid]
                updated += 1
                logger.info("Web search: %s -> %s", name[:60], new_date)
                if not dry_run:
                    conn.execute(
                        text("""
                            UPDATE tournament_history
                            SET date = CAST(:dt AS date), updated_at = CURRENT_TIMESTAMP
                            WHERE tournament_id = :tid
                        """),
                        {"dt": new_date, "tid": tid},
                    )
                skipped -= 1

    if dry_run:
        conn.rollback()
    else:
        conn.commit()
    conn.close()

    view_status = {}
    if not dry_run and (updated > 0 or cleared > 0):
        try:
            view_status = db.refresh_materialized_views()
        except Exception as exc:
            logger.warning("Could not refresh materialized views: %s", exc)

    return {"updated": updated, "cleared": cleared, "skipped": skipped, "dry_run": dry_run, "view_status": view_status}


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill tournament_history.date from WPBA/WPA sources")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--web-search", action="store_true", help="Attempt web search for missing (may be rate-limited)")
    parser.add_argument("--known-only", action="store_true", help="Use only known dates (skip discovery/MEC HTTP calls)")
    args = parser.parse_args()

    result = backfill_from_sources(
        dry_run=args.dry_run,
        web_search=args.web_search,
        known_only=args.known_only,
    )
    logger.info(
        "Done. Updated: %d, Cleared placeholders: %d, Skipped: %d",
        result.get("updated", 0),
        result.get("cleared", 0),
        result.get("skipped", 0),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
