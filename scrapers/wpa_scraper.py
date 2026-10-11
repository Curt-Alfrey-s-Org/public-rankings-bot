#!/usr/bin/env python3
"""
WPA Rankings Scraper
Scrapes current rankings from wpapool.com.
Uses fetch_utils for retries and rate-limit handling.
"""

# Doc refs (AI / maintainers): docs/RANKINGS_DATA_DOC_HOOKS.md; docs/WPA_RANKINGS_DATA_FLOW.md

import json
import logging
import re
import requests
from urllib.parse import urljoin, urlparse, parse_qs
from bs4 import BeautifulSoup
from typing import List, Dict, Optional, Tuple
import time
from datetime import date, datetime
from io import BytesIO
from pathlib import Path
from scrapers.base_scraper import retry_with_backoff, NonRetryableError
try:
    import pdfplumber
    HAS_PDF = True
except ImportError:
    HAS_PDF = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WPAScraper:
    """Scraper for WPA rankings"""

    # Fallback if the Rankings page does not link a World Rankings PDF.
    # Live file as of 2026-02-26: uploads/2026/02/WPA-World-Rankings-SH_SS-2_16_25.pdf
    ARTISTIC_RANKINGS_PDF_URL = (
        "https://wpapool.com/wp-content/uploads/2026/02/WPA-World-Rankings-SH_SS-2_16_25.pdf"
    )

    _DIVISION_TO_TABLE_INDEX = {
        "Men": 0,
        "Women": 1,
        "Heyball_Men": 2,
        "Heyball_Women": 3,
    }
    _DIVISION_TO_SAVE_KEY = {
        "Men": "men",
        "Women": "women",
        "Heyball_Men": "heyball_men",
        "Heyball_Women": "heyball_women",
    }

    def __init__(self, timeout: int = 30, max_pages: int = 20):
        """
        Initialize WPA scraper

        Args:
            timeout: Request timeout in seconds
        """
        self.base_url = "https://wpapool.com"
        self.rankings_url = f"{self.base_url}/rankings/"
        self.timeout = timeout
        self.max_pages = max_pages
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })

        # Prefer project archive path; fall back to /tmp when cwd is not writable (containers).
        self.scraped_data_dir: Optional[Path] = None
        for candidate in (Path("scraped_data/wpa"), Path("/tmp/scraped_data/wpa")):
            try:
                candidate.mkdir(parents=True, exist_ok=True)
                self.scraped_data_dir = candidate
                break
            except OSError:
                continue
        if self.scraped_data_dir is None:
            logger.warning("WPA scraper archive directory unavailable; continuing without local JSON archive writes")

    def _save_scraped_data(self, divisions: Dict[str, List[Dict]], source_url: str) -> None:
        """Persist a snapshot under scraped_data/wpa (WPBA-style metadata + divisions)."""
        if self.scraped_data_dir is None:
            return
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        counts = {k: len(v or []) for k, v in divisions.items()}
        data = {
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "scraper": "wpa_scraper",
                "source_url": source_url,
                "division_counts": counts,
                "total_rankings": sum(counts.values()),
            },
            "divisions": divisions,
        }
        filename = f"wpa_rankings_{timestamp}.json"
        filepath = self.scraped_data_dir / filename
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info("Saved WPA scraped data to %s", filepath)
        except OSError as e:
            logger.error("Failed to save WPA scraped data to %s: %s", filepath, e)

    @retry_with_backoff(
        max_attempts=3,
        initial_delay=2.0,
        retry_on_exceptions=(requests.RequestException,),
        non_retryable_exceptions=(NonRetryableError,),
    )
    def _fetch_all_rankings_soups(self) -> List[BeautifulSoup]:
        """Fetch /rankings/ and pagination once; return one BeautifulSoup per HTML page."""
        logger.info("Fetching WPA rankings from %s (single crawl)", self.rankings_url)
        t_start = time.perf_counter()
        soups: List[BeautifulSoup] = []
        visited: set = set()
        to_visit = [self.rankings_url]

        while to_visit:
            if len(visited) >= self.max_pages:
                logger.warning("Reached max_pages=%s; stopping WPA pagination", self.max_pages)
                break

            url = to_visit.pop(0)
            if url in visited:
                continue

            t_fetch_page = time.perf_counter()
            response = self._fetch_page(url)
            fetch_ms = (time.perf_counter() - t_fetch_page) * 1000
            logger.info(
                "[%s] WPA page fetched in %.0fms (%s chars): %s",
                time.strftime("%H:%M:%S"),
                fetch_ms,
                len(response.text),
                url,
            )

            soup = BeautifulSoup(response.text, "html.parser")
            soups.append(soup)
            visited.add(url)
            for page_url in self._discover_pagination_urls(soup):
                if page_url not in visited and page_url not in to_visit:
                    to_visit.append(page_url)

        total_ms = (time.perf_counter() - t_start) * 1000
        logger.info(
            "[%s] WPA HTML crawl finished in %.0fms | %s page(s)",
            time.strftime("%H:%M:%S"),
            total_ms,
            len(soups),
        )
        return soups

    def _rankings_from_soups_one_table(self, soups: List[BeautifulSoup], table_index: int) -> List[Dict]:
        rankings: List[Dict] = []
        for soup in soups:
            tables = soup.find_all("table")
            if len(tables) > table_index:
                rankings.extend(self._parse_table_rankings(tables[table_index]))
        return self._dedupe_rankings(rankings)

    def scrape_all_html_divisions(self, persist: bool = True) -> Dict[str, List[Dict]]:
        """
        One paginated crawl of /rankings/; parse Men, Women, Heyball men/women tables per page.
        Optionally writes one JSON snapshot (same pattern as WPBA scraper archives).
        """
        soups = self._fetch_all_rankings_soups()
        out: Dict[str, List[Dict]] = {
            "men": [],
            "women": [],
            "heyball_men": [],
            "heyball_women": [],
        }
        for soup in soups:
            tables = soup.find_all("table")
            if len(tables) >= 1:
                out["men"].extend(self._parse_table_rankings(tables[0]))
            if len(tables) >= 2:
                out["women"].extend(self._parse_table_rankings(tables[1]))
            if len(tables) >= 3:
                out["heyball_men"].extend(self._parse_table_rankings(tables[2]))
            if len(tables) >= 4:
                out["heyball_women"].extend(self._parse_table_rankings(tables[3]))
        for key in list(out.keys()):
            out[key] = self._dedupe_rankings(out[key])
        if persist and any(out.values()):
            self._save_scraped_data(out, self.rankings_url)
        return out

    def scrape_all_divisions(self, include_artistic: bool = True, persist: bool = True) -> Dict[str, List[Dict]]:
        """
        Full WPA snapshot: one HTML crawl for standard tables, optional Artistic PDF once.
        Writes a single JSON file with all divisions present (when persist=True).
        """
        out = self.scrape_all_html_divisions(persist=False)
        if include_artistic and HAS_PDF:
            try:
                artistic = self._scrape_artistic_pdf()
                if artistic:
                    out["artistic"] = artistic
            except Exception as e:
                logger.warning("WPA Artistic PDF scrape failed (continuing with HTML divisions): %s", e)
        if persist and any(out.values()):
            self._save_scraped_data(out, self.rankings_url)
        return out

    def scrape_rankings(self, division: Optional[str] = None) -> List[Dict]:
        """
        Scrape current WPA rankings from /rankings/.

        Args:
            division: 'Men', 'Women', 'Heyball_Men', 'Heyball_Women', 'Artistic', or None (default = all tables).

        Returns:
            List of dicts with keys: rank, name, points, country
            Example: [{'rank': 1, 'name': 'Player Name', 'points': 1500.0, 'country': 'USA'}, ...]
        """
        if division == "Artistic":
            try:
                rankings = self._scrape_artistic_pdf()
            except Exception as e:
                logger.error("WPA Artistic scrape failed: %s", e)
                return []
            if self.scraped_data_dir and rankings:
                self._save_scraped_data({"artistic": rankings}, self.ARTISTIC_RANKINGS_PDF_URL)
            return rankings

        t_start = time.perf_counter()
        try:
            soups = self._fetch_all_rankings_soups()
            if division is None:
                rankings = []
                for soup in soups:
                    for table in soup.find_all("table"):
                        rankings.extend(self._parse_table_rankings(table))
                rankings = self._dedupe_rankings(rankings)
                if self.scraped_data_dir and rankings:
                    self._save_scraped_data({"merged_all_tables": rankings}, self.rankings_url)
            elif division in self._DIVISION_TO_TABLE_INDEX:
                idx = self._DIVISION_TO_TABLE_INDEX[division]
                rankings = self._rankings_from_soups_one_table(soups, idx)
                sk = self._DIVISION_TO_SAVE_KEY.get(division)
                if self.scraped_data_dir and rankings and sk:
                    self._save_scraped_data({sk: rankings}, self.rankings_url)
            else:
                logger.warning("Unknown WPA division %r; returning empty list", division)
                rankings = []

            total_ms = (time.perf_counter() - t_start) * 1000
            logger.info(
                "[%s] WPA scrape total %.0fms | %s rankings (division=%s)",
                time.strftime("%H:%M:%S"),
                total_ms,
                len(rankings),
                division,
            )
            return rankings
        except requests.RequestException as e:
            logger.error("Error fetching WPA rankings: %s", e)
            raise
        except Exception as e:
            logger.error("Error parsing WPA rankings: %s", e)
            raise
    
    def _parse_rankings(self, soup: BeautifulSoup, division: Optional[str] = None) -> List[Dict]:
        """
        Parse rankings from HTML.
        
        Args:
            soup: BeautifulSoup object of rankings page
            division: If 'Men' use first table only; if 'Women' use second table only; else all tables.
            
        Returns:
            List of ranking dictionaries
        """
        rankings = []
        
        # WPA rankings might be in a table or divs
        tables = soup.find_all('table')

        if tables:
            if division == 'Men' and len(tables) >= 1:
                rankings = self._parse_table_rankings(tables[0])
            elif division == 'Women' and len(tables) >= 2:
                rankings = self._parse_table_rankings(tables[1])
            elif division == 'Heyball_Men' and len(tables) >= 3:
                rankings = self._parse_table_rankings(tables[2])
            elif division == 'Heyball_Women' and len(tables) >= 4:
                rankings = self._parse_table_rankings(tables[3])
            elif division == 'Artistic':
                # Artistic Pool rankings are in a separate PDF
                rankings = self._scrape_artistic_pdf()
            else:
                for table in tables:
                    rankings.extend(self._parse_table_rankings(table))
            return rankings
        
        # Strategy 2: Look for structured divs/lists
        ranking_divs = soup.find_all('div', class_=lambda x: x and 'rank' in x.lower())
        
        if ranking_divs:
            return self._parse_div_rankings(ranking_divs)
        
        logger.warning("Could not find rankings structure on WPA page")
        return rankings

    # Events in the current artistic PDF (newline-separated values, this order).
    # The Rankings page PDF updated 2/16/25 lists three world championships.
    ARTISTIC_EVENTS = [
        "2022_wc",
        "2023_wc",
        "2024_wc",
    ]


    def _artistic_pdf_url(self) -> str:
        """PDF linked from the WPA Rankings page, else the fallback constant."""
        import re
        from urllib.parse import urljoin

        page = "https://wpapool.com/rankings/"
        try:
            response = self.session.get(page, timeout=self.timeout)
            response.raise_for_status()
            hrefs = re.findall(r'href=["\']([^"\']+\.pdf)["\']', response.text, flags=re.I)
            for href in hrefs:
                low = href.lower()
                if "world-rankings" in low or "artistic" in low:
                    return href if href.startswith("http") else urljoin(page, href)
        except Exception as exc:
            logger.warning("Artistic PDF link discovery failed, using fallback: %s", exc)
        return self.ARTISTIC_RANKINGS_PDF_URL

    def _scrape_artistic_pdf(self) -> List[Dict]:
        """Scrape Artistic Pool rankings from the official WPA PDF.

        Extracts the full per-event breakdown (Position Pts, Score Pts,
        Discipline Pts, final computed points at 50%/100%) for each of 7
        events, plus the overall total.  Per-event final points are stored
        in source_data keyed as ``{event}_pts`` (e.g. ``2019_cao_pts``).
        Sub-breakdowns are ``{event}_position_pts``, ``{event}_score_pts``,
        ``{event}_discipline_pts``.
        """
        if not HAS_PDF:
            logger.warning("pdfplumber not available for PDF scraping")
            return []

        pdf_url = self._artistic_pdf_url()

        try:
            logger.info("Fetching Artistic Pool rankings PDF from %s", pdf_url)
            response = self.session.get(pdf_url, timeout=self.timeout)
            response.raise_for_status()

            rankings: List[Dict] = []
            with pdfplumber.open(BytesIO(response.content)) as pdf:
                for page_num in range(min(5, len(pdf.pages))):
                    page = pdf.pages[page_num]
                    tables = page.extract_tables()
                    if not tables:
                        continue

                    for table in tables:
                        if not table:
                            continue
                        start_row = 1 if page_num == 0 else 0
                        for row in table[start_row:]:
                            if not row or len(row) < 8:
                                continue
                            try:
                                player_name = (row[0] or "").strip().replace("\n", " ")
                                if not player_name or not player_name.replace(" ", "").replace("-", "").isalnum():
                                    continue

                                total_str = (row[6] or "0").strip().replace(",", "")
                                total_points = float(total_str) if total_str.replace(".", "").isdigit() else 0.0
                                if total_points <= 0:
                                    continue

                                rank_str = (row[7] or "").strip().split("/")[0].split("(")[0].strip()
                                try:
                                    rank_val = int(rank_str)
                                except (ValueError, TypeError):
                                    rank_val = len(rankings) + 1

                                rec: Dict = {
                                    "rank": rank_val,
                                    "name": player_name,
                                    "points": total_points,
                                    "country": None,
                                }

                                pos_vals = (row[1] or "").strip().split("\n")
                                score_vals = (row[2] or "").strip().split("\n")
                                disc_vals = (row[3] or "").strip().split("\n")
                                at50_vals = (row[4] or "").strip().split("\n")
                                atpool_opt_in_vals = (row[5] or "").strip().split("\n")

                                for idx, evt in enumerate(self.ARTISTIC_EVENTS):
                                    pp = self._pdf_num(pos_vals, idx)
                                    sp = self._pdf_num(score_vals, idx)
                                    dp = self._pdf_num(disc_vals, idx)
                                    f50 = self._pdf_num(at50_vals, idx)
                                    f100 = self._pdf_num(atpool_opt_in_vals, idx)

                                    final = f50 if f50 is not None else f100
                                    if final is None:
                                        continue

                                    rec[f"{evt}_pts"] = final
                                    rec[f"{evt}_position_pts"] = pp if pp is not None else 0
                                    rec[f"{evt}_score_pts"] = sp if sp is not None else 0
                                    rec[f"{evt}_discipline_pts"] = dp if dp is not None else 0
                                    raw = (pp or 0) + (sp or 0) + (dp or 0)
                                    rec[f"{evt}_raw_total"] = raw
                                    rec[f"{evt}_pct_applied"] = 50 if f50 is not None else 100

                                rankings.append(rec)

                            except (ValueError, IndexError) as e:
                                logger.debug("Error parsing Artistic PDF row on page %d: %s", page_num, e)
                                continue

            logger.info("Extracted %d Artistic Pool rankings from PDF across %d pages", len(rankings), min(5, len(pdf.pages)))
            return rankings

        except Exception as e:
            logger.exception("Error scraping Artistic Pool PDF: %s", e)
            raise

    @staticmethod
    def _pdf_num(vals: List[str], idx: int) -> Optional[float]:
        """Parse a numeric value from a list of newline-split PDF cell values.
        Returns None for missing/dashed entries."""
        if idx >= len(vals):
            return None
        raw = vals[idx].strip().replace(",", "")
        if not raw or raw.startswith("-"):
            return None
        try:
            return float(raw)
        except (ValueError, TypeError):
            return None

    def _fetch_page(self, url: str) -> requests.Response:
        """Fetch a WPA page with retries to handle transient errors."""
        delay = 1.5
        for attempt in range(1, 4):
            try:
                response = self.session.get(url, timeout=self.timeout)
                if response.status_code in (403, 404):
                    raise NonRetryableError(f"HTTP {response.status_code} for WPA page")
                response.raise_for_status()
                return response
            except requests.RequestException as e:
                if attempt >= 3:
                    logger.error("WPA page fetch failed for %s: %s", url, e)
                    raise
                logger.warning("WPA page fetch error for %s (attempt %s/3): %s", url, attempt, e)
                time.sleep(delay)
                delay *= 2.0

    def _discover_pagination_urls(self, soup: BeautifulSoup) -> List[str]:
        """Discover pagination links for WPA rankings pages."""
        urls = set()
        for link in soup.find_all('a'):
            href = (link.get('href') or '').strip()
            if not href or href.startswith('#'):
                continue
            if 'rankings' not in href:
                continue
            if 'page' not in href and 'paged' not in href and 'page-numbers' not in (link.get('class') or []):
                continue
            full_url = urljoin(self.base_url, href)
            urls.add(full_url)

        return sorted(urls, key=self._page_sort_key)

    def _page_sort_key(self, url: str) -> int:
        """Sort pagination URLs by page number when possible."""
        parsed = urlparse(url)
        path_match = None
        for part in parsed.path.split('/'):
            if part.isdigit():
                path_match = part
                break
        if path_match:
            return int(path_match)

        query = parse_qs(parsed.query)
        if 'paged' in query and query['paged'] and query['paged'][0].isdigit():
            return int(query['paged'][0])

        return 0

    def _dedupe_rankings(self, rankings: List[Dict]) -> List[Dict]:
        """Remove duplicate rankings across paginated pages."""
        seen = set()
        deduped = []
        for ranking in rankings:
            key = (ranking.get('rank'), ranking.get('name'))
            if key in seen:
                continue
            seen.add(key)
            deduped.append(ranking)
        return deduped
    
    def _normalize_header_key(self, text: str, index: int) -> str:
        """Turn header cell into a safe key (e.g. 'First Name(s)' -> 'first_name')."""
        t = (text or "").strip().lower()
        t = re.sub(r"\s+", "_", t)
        t = re.sub(r"[^\w]", "", t)
        return t or f"col_{index}"

    def _first_nonempty(self, full_row: Dict[str, Optional[str]], keys: Tuple[str, ...]) -> Optional[str]:
        """Return first non-empty value for any key in order."""
        for key in keys:
            val = (full_row.get(key) or "").strip() if full_row.get(key) is not None else ""
            if val:
                return val
        return None

    def _extract_player_name(self, full_row: Dict[str, Optional[str]], cell_texts: List[str]) -> str:
        """
        Extract player name from known WPA table shapes:
        - Player
        - Surname Family Name + First Name(s) Given Name(s)
        - (blank header) + Athlete
        """
        player = (full_row.get("player") or "").strip()
        if player:
            return player

        surname = (
            (full_row.get("surname_family_name") or "").strip()
            or (full_row.get("surname") or "").strip()
            or (full_row.get("col_1") or "").strip()
        )
        given = (
            (full_row.get("first_names_given_names") or "").strip()
            or (full_row.get("first_name") or "").strip()
            or (full_row.get("athlete") or "").strip()
        )
        if surname and given:
            return f"{surname} {given}".strip()
        if given:
            return given

        # Alternative: first non-rank text cell
        for idx in (1, 2):
            if idx < len(cell_texts):
                txt = (cell_texts[idx] or "").strip()
                if txt:
                    return txt
        return ""

    def _parse_table_rankings(self, table) -> List[Dict]:
        """Parse rankings from table; preserve all columns (first row = headers).
        WPA: Rank, Player name, License, Country, Points.
        Heyball: Rank, Surname, First Name(s), License, Country, Points, ... (up to 18 cols).
        Full row is stored so source_data can show all columns in the UI.
        """
        rankings = []
        rows = table.find_all("tr")
        if not rows:
            return rankings

        # First row: treat as headers to get column names for full-row storage
        header_cells = rows[0].find_all(["td", "th"])
        header_display = [(c.get_text() or "").strip() for c in header_cells]
        headers = [
            self._normalize_header_key(header_display[i] if i < len(header_display) else "", i)
            for i in range(len(header_cells))
        ]
        if not headers:
            headers = [f"col_{i}" for i in range(len(header_cells))]

        wpa_column_labels: Dict[str, str] = {}
        for i, norm_key in enumerate(headers):
            if i < len(header_display):
                raw = re.sub(r"\s+", " ", header_display[i]).strip()
                if norm_key and raw:
                    wpa_column_labels[norm_key] = raw

        data_start = 1
        for i in range(data_start, len(rows)):
            row = rows[i]
            cells = row.find_all(["td", "th"])
            if len(cells) < 2:
                continue
            try:
                cell_texts = [(cell.get_text(strip=True) or "").strip() for cell in cells]
                full_row: Dict[str, Optional[str]] = {}
                for j, text_val in enumerate(cell_texts):
                    key = headers[j] if j < len(headers) else f"col_{j}"
                    if key in full_row:
                        key = f"{key}_{j}"
                    full_row[key] = text_val or None

                rank = self._parse_rank(full_row.get("rank") or cell_texts[0])
                name = self._extract_player_name(full_row, cell_texts)
                license_number = self._first_nonempty(full_row, ("wpa_license_number", "license_number", "license"))
                country = self._first_nonempty(full_row, ("country",))
                points = self._parse_points(
                    self._first_nonempty(full_row, ("total_points", "total", "points")) or ""
                )
                if points <= 0:
                    # Handle legacy/irregular tables with no explicit total column.
                    for raw in cell_texts[1:]:
                        parsed = self._parse_points(raw)
                        if parsed > points:
                            points = parsed
                if not name:
                    continue

                # First-class fields + full row (extras go to source_data in save_rankings)
                ranking = {"rank": rank, "name": name, "points": points}
                if license_number:
                    ranking["license_number"] = license_number
                if country:
                    ranking["country"] = country
                for k, v in full_row.items():
                    if k not in ranking and v is not None:
                        ranking[k] = v
                if wpa_column_labels:
                    ranking["wpa_column_labels"] = dict(wpa_column_labels)
                rankings.append(ranking)
            except (ValueError, AttributeError, IndexError) as e:
                logger.debug("Error parsing row %s: %s", i, e)
                continue
        return rankings
    
    def _parse_rank(self, text: str) -> int:
        """Parse rank from text"""
        text = (text or "").replace('.', '').replace('#', '').replace('T', '').strip()
        if not text:
            raise ValueError("empty rank")
        return int(text)
    
    def _parse_points(self, text: str) -> float:
        """Parse points from text"""
        cleaned = str(text or "").replace(",", "").replace("$", "").strip()
        if not cleaned:
            return 0.0
        if re.fullmatch(r"-?\d+(?:\.\d+)?", cleaned):
            return float(cleaned)
        return 0.0

    def _parse_date_from_header(self, header_text: str) -> Optional[date]:
        """Parse snapshot date from header e.g. 'MEN'S PLAYER RANKING – 16th December 2025' or 'ARTISTIC POOL PROFESSIONAL RANKINGS' (no date)."""
        # Look for patterns like "16th December 2025", "8th November 2025", "December 16, 2025"
        text = (header_text or "").strip()
        # Ordinal + month name + year
        m = re.search(r"(\d{1,2})(?:st|nd|rd|th)?\s+(\w+)\s+(\d{4})", text, re.I)
        if m:
            day_s, month_s, year_s = m.group(1), m.group(2), m.group(3)
            try:
                dt = datetime.strptime(f"{day_s} {month_s} {year_s}", "%d %B %Y")
                return dt.date()
            except ValueError as e:
                logger.debug("Could not parse ordinal date '%s %s %s': %s", day_s, month_s, year_s, e)
        # Month day, year
        try:
            from dateutil.parser import parse as dateutil_parse
            dt = dateutil_parse(text, fuzzy=True)
            return dt.date()
        except Exception as e:
            logger.debug("Could not parse date from WPA header '%s': %s", text, e)
        return None

    def _discover_previous_ranking_pages(self, soup: BeautifulSoup, current_url: str) -> List[str]:
        """Discover pagination links for previous-ranking (e.g. /previous-ranking/page/2/)."""
        urls = set()
        base_path = "/previous-ranking"
        for link in soup.find_all("a"):
            href = (link.get("href") or "").strip()
            if not href or href.startswith("#"):
                continue
            full = urljoin(self.base_url, href)
            parsed = urlparse(full)
            if base_path not in parsed.path:
                continue
            # Same section: /previous-ranking/ or /previous-ranking/page/N/
            if parsed.path.rstrip("/") == base_path or re.match(r"^" + re.escape(base_path) + r"/page/\d+/?$", parsed.path):
                urls.add(full)
        return sorted(urls, key=self._page_sort_key)

    def scrape_historical_rankings(
        self,
        max_pages: int = 50,
    ) -> List[Tuple[str, str, List[Dict]]]:
        """
        Scrape WPA historical rankings from https://wpapool.com/previous-ranking/.
        Follows pagination (e.g. page/2/) to scrape all listed snapshots.
        Returns list of (ranking_type, snapshot_date_iso, rankings).
        Sections: Men, Women, Heyball Men/Women, Artistic Pool Professional.
        All table columns are preserved in each row (source_data in DB).
        """
        base_url = f"{self.base_url}/previous-ranking/"
        to_visit = [base_url]
        visited: set = set()
        results: List[Tuple[str, str, List[Dict]]] = []
        seen_sections: set = set()  # (ranking_type, snapshot_iso) to avoid duplicates across pages

        # Section headers and mapping to ranking_system
        section_patterns = [
            (re.compile(r"\bmen'?s?\s+player\s+ranking", re.I), "WPA_Men"),
            (re.compile(r"\bwomen'?s?\s+player\s+ranking", re.I), "WPA_Women"),
            (re.compile(r"\bmen'?s?\s+heyball\s+previous\s+ranking", re.I), "WPA_Heyball_Men"),
            (re.compile(r"women'?\s+heyball\s+ranking", re.I), "WPA_Heyball_Women"),
            (re.compile(r"artistic\s+pool\s+professional", re.I), "WPA_Artistic"),
        ]

        def _normalize_header(t: str) -> str:
            t = (t or "").strip()
            t = t.replace("\u2019", "'").replace("\u200b", "").replace("\u00a0", " ")
            return t

        while to_visit and len(visited) < max_pages:
            url = to_visit.pop(0)
            if url in visited:
                continue
            visited.add(url)
            logger.info("Fetching WPA historical rankings from %s", url)
            try:
                response = self._fetch_page(url)
            except Exception as e:
                logger.error("Failed to fetch previous-ranking page %s: %s", url, e)
                continue

            soup = BeautifulSoup(response.text, "html.parser")

            # Discover more pages
            for page_url in self._discover_previous_ranking_pages(soup, url):
                if page_url not in visited and page_url not in to_visit:
                    to_visit.append(page_url)

            for h2 in soup.find_all("h2"):
                header_text = _normalize_header(h2.get_text() or "")
                if not header_text:
                    continue
                ranking_type = None
                for pattern, rtype in section_patterns:
                    if pattern.search(header_text):
                        ranking_type = rtype
                        break
                if not ranking_type:
                    continue

                snapshot_date = self._parse_date_from_header(header_text)
                snapshot_iso = snapshot_date.isoformat() if snapshot_date else date.today().isoformat()
                key = (ranking_type, snapshot_iso)
                if key in seen_sections:
                    continue
                seen_sections.add(key)

                table = h2.find_next("table")
                if table:
                    rows = self._parse_table_rankings(table)
                    if rows:
                        results.append((ranking_type, snapshot_iso, rows))
                        logger.info(
                            "Historical %s (%s): %d players from '%s'",
                            ranking_type,
                            snapshot_iso,
                            len(rows),
                            header_text[:50],
                        )

        logger.info("Scraped %d historical sections from %d previous-ranking page(s)", len(results), len(visited))
        return results

    def get_player_rank(self, player_name: str) -> Optional[Dict]:
        """
        Get ranking info for specific player
        
        Args:
            player_name: Name of player to search for
            
        Returns:
            Dict with player ranking info or None if not found
        """
        rankings = self.scrape_rankings()
        
        for ranking in rankings:
            if player_name.lower() in ranking['name'].lower():
                return ranking
        
        return None


def main():
    """Test the scraper"""
    scraper = WPAScraper()
    rankings = scraper.scrape_rankings()
    
    if rankings:
        print(f"\nScraped {len(rankings)} WPA rankings")
        print("\nTop 10:")
        for ranking in rankings[:10]:
            country = ranking.get('country', 'N/A')
            print(f"  {ranking['rank']}. {ranking['name']} ({country}) - {ranking['points']} pts")
    else:
        print("Failed to scrape rankings")


if __name__ == '__main__':
    main()
