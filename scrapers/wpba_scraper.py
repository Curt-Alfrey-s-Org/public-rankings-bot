#!/usr/bin/env python3
"""
WPBA Rankings Scraper - PDF Version
Scrapes rankings from WPBA PDF files.
Uses fetch_utils for retries and rate-limit handling.
"""

# Doc refs (AI / maintainers): docs/RANKINGS_DATA_DOC_HOOKS.md; docs/WPBA_DATA_FLOW.md;
#   docs/RANKINGS_TABLE_DESIGN.md

import json
import re
import logging
import requests
from datetime import datetime
from pathlib import Path
import pdfplumber
import time
from io import BytesIO
from typing import List, Dict, Optional, Tuple
from urllib.parse import urljoin, urlparse

from scrapers.base_scraper import retry_with_backoff, NonRetryableError

from scrapers.fetch_utils import get_with_retry
from scrapers.wpba_pdf_columns import (
    WPBA_ROTATING_11TH_KEY,
    WPBA_ROTATING_11TH_LABEL,
    WPBA_ROTATING_TEN_COLUMNS,
    wpba_default_column_labels,
)
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Primary rankings page (PDF links in page HTML). /rankings-1 returned 404 as of 2026-05;
# keep a single canonical URL to avoid noisy retries on a dead path.
WPBA_PDF_DISCOVERY_URLS = (
    "https://wpba.com/rankings",
)
_RE_SQS_PDF = re.compile(r'(/s/[A-Za-z0-9._+-]+\.pdf)', re.IGNORECASE)


def _normalize_header_key(text: str, index: int) -> str:
    """Turn PDF table header into a safe key."""
    t = (text or "").strip().lower()
    t = re.sub(r"\s+", "_", t)
    t = re.sub(r"[^\w]", "", t)
    return t or f"col_{index}"


# Keys that are NOT per-tournament point columns (metadata, totals, etc.)
_WPBA_NON_TOURNAMENT_KEYS = frozenset({
    "rank", "name", "points", "total", "stops", "stops_played",
    "country", "license_number", "col_0", "col_1",
})


def _is_wpba_tournament_column(key: str, value) -> bool:
    """True if key looks like a per-tournament points column (excludes rank, name, total)."""
    if not key or key in _WPBA_NON_TOURNAMENT_KEYS:
        return False
    if "total" in key.lower() or "rank" in key.lower() or "name" in key.lower():
        return False
    if key.startswith("col_") and key in ("col_0", "col_1"):
        return False
    try:
        n = float(str(value).replace(",", "").strip())
        return n >= 0
    except (ValueError, TypeError):
        return False


class WPBAScraper:
    """Scraper for WPBA rankings from PDF"""
    
    def __init__(self, timeout: int = 30):
        # PDF URL must come from discover_pdf_url(); no hardcoded fallback
        self.pdf_url: Optional[str] = None
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        # Prefer project archive path, but do not fail scraping if filesystem is read-only.
        self.scraped_data_dir: Optional[Path] = None
        for candidate in (Path("scraped_data/wpba"), Path("/tmp/scraped_data/wpba")):
            try:
                candidate.mkdir(parents=True, exist_ok=True)
                self.scraped_data_dir = candidate
                break
            except Exception:
                continue
        if self.scraped_data_dir is None:
            logger.warning("WPBA scraper archive directory unavailable; continuing without local JSON archive writes")

    @staticmethod
    def _score_pdf_candidate(full_url: str, link_text: str = "") -> Tuple[bool, int, str]:
        path = urlparse(full_url).path or ""
        is_sqs = path.startswith("/s/") and path.lower().endswith(".pdf")
        ul, tl = full_url.lower(), (link_text or "").lower()
        relevance = 0
        if "ranking" in ul or "wpba" in ul:
            relevance += 4
        if "ranking" in tl or "wpba" in tl:
            relevance += 4
        basename = path.rsplit("/", 1)[-1] if path else ""
        return (is_sqs, relevance, basename)

    def _collect_pdf_candidates(self, html: str, base: str) -> List[Tuple[bool, int, str, str]]:
        """Parse anchors and raw HTML for Squarespace ``/s/....pdf`` URLs."""
        rows: List[Tuple[bool, int, str, str]] = []
        seen_paths: set = set()

        for path in _RE_SQS_PDF.findall(html or ""):
            if path in seen_paths:
                continue
            seen_paths.add(path)
            full = urljoin(base, path)
            is_sqs, rel, base_name = self._score_pdf_candidate(full, "")
            rows.append((is_sqs, rel, base_name, full))

        if BeautifulSoup is not None:
            soup = BeautifulSoup(html, "html.parser")
            for link in soup.find_all("a", href=True):
                raw = (link.get("href") or "").strip()
                if not raw.lower().endswith(".pdf"):
                    continue
                if raw.startswith("/"):
                    full = urljoin(base, raw)
                elif raw.startswith("http://") or raw.startswith("https://"):
                    full = raw
                    host = urlparse(full).netloc.lower().replace("www.", "")
                    if host != "wpba.com":
                        continue
                else:
                    continue
                text = (link.get_text() or "").strip()
                is_sqs, rel, base_name = self._score_pdf_candidate(full, text)
                rows.append((is_sqs, rel, base_name, full))

        return rows

    @retry_with_backoff(
        max_attempts=3,
        initial_delay=2.0,
        retry_on_exceptions=(requests.RequestException,),
        non_retryable_exceptions=(NonRetryableError,),
    )
    def discover_pdf_url(self) -> Optional[str]:
        """Discover WPBA rankings PDF from wpba.com.

        Squarespace file links look like ``/s/2026-WPBA-Ranking-....pdf`` on ``/rankings``.
        """
        if BeautifulSoup is None:
            logger.warning("BeautifulSoup not available, skipping PDF URL discovery")
            return None

        base = "https://wpba.com"
        merged: Dict[str, Tuple[bool, int, str, str]] = {}

        try:
            for page_url in WPBA_PDF_DISCOVERY_URLS:
                try:
                    response = self.session.get(page_url, timeout=self.timeout)
                    response.raise_for_status()
                except requests.RequestException as e:
                    logger.warning("WPBA discovery skip %s: %s", page_url, e)
                    continue
                text = response.text or ""
                for row in self._collect_pdf_candidates(text, base):
                    _sqs, rel, bname, full = row
                    if full not in merged or rel > merged[full][1]:
                        merged[full] = row
                logger.debug(
                    "WPBA discovery scanned %s (%d bytes), candidates so far %d",
                    page_url,
                    len(text),
                    len(merged),
                )

            if not merged:
                logger.warning(
                    "No WPBA PDF links on %s",
                    ", ".join(WPBA_PDF_DISCOVERY_URLS),
                )
                return None

            rows = list(merged.values())
            prefer_sqs = [r for r in rows if r[0]]
            pool = prefer_sqs if prefer_sqs else rows
            _, _rel, _base, url = max(pool, key=lambda r: (r[1], r[2]))
            logger.info("Discovered WPBA PDF URL: %s", url)
            return url

        except Exception as e:
            logger.error("Failed to discover WPBA PDF URL: %s", e)
            return None

    def scrape_rankings(self) -> List[Dict]:
        """
        Scrape WPBA rankings from PDF discovered on wpba.com/rankings.
        If discovery fails, returns [] (no alternate URL).

        Returns:
            List of dicts with keys: rank, name, points, plus all PDF columns in source_data
        """
        discovered_url = self.discover_pdf_url()
        if not discovered_url:
            logger.error(
                "WPBA scrape aborted: no PDF link found on wpba.com/rankings (no fallback URL)"
            )
            return []

        self.pdf_url = discovered_url
        logger.info("Fetching WPBA rankings PDF from %s", self.pdf_url[:80] + "...")
        
        try:
            # Start timing
            t_start = time.perf_counter()
            # Download PDF
            t_fetch_start = time.perf_counter()
            response = self.session.get(self.pdf_url, timeout=self.timeout)
            if response.status_code in (403, 404):
                raise NonRetryableError(f"HTTP {response.status_code} for WPBA PDF")
            response.raise_for_status()
            fetch_ms = (time.perf_counter() - t_fetch_start) * 1000
            logger.info(f"[{time.strftime('%H:%M:%S')}] WPBA PDF fetched in {fetch_ms:.0f}ms ({len(response.content)} bytes)")
            
            # Parse PDF
            t_parse_start = time.perf_counter()
            rankings = []
            with pdfplumber.open(BytesIO(response.content)) as pdf:
                # Primary: word-position parser. The WPBA PDF has no ruling lines,
                # so pdfplumber's table strategies mis-split columns; only the
                # x-coordinate of each value reliably identifies which tournament
                # column a blank belongs to (text extraction collapses blanks and
                # can only align players who played all 10 events). See
                # docs/WPBA_TOURNAMENT_SSOT.md §5.
                rankings = self._parse_pages_by_words(pdf.pages)
                if not rankings:
                    # Fallback: table extraction, then text-line parsing.
                    for page in pdf.pages:
                        rankings.extend(self._parse_page(page))
            parse_ms = (time.perf_counter() - t_parse_start) * 1000
            total_ms = (time.perf_counter() - t_start) * 1000
            rankings = self._dedupe_rankings(rankings)
            # Attach tournament column order for rolling-10 (from first row).
            # The 11th numeric column (rotating out) must not be included in rolling-10 sum.
            if rankings:
                first = rankings[0]
                tournament_cols = [
                    k for k, v in first.items()
                    if _is_wpba_tournament_column(k, v) and k != WPBA_ROTATING_11TH_KEY
                ]
                for r in rankings:
                    r["_wpba_tournament_columns"] = tournament_cols
            logger.info(f"[{time.strftime('%H:%M:%S')}] WPBA parse {parse_ms:.0f}ms | total {total_ms:.0f}ms | {len(rankings)} rankings")
            self._save_scraped_data(rankings, self.pdf_url)
            return rankings
            
        except requests.RequestException as e:
            logger.error(f"Error fetching WPBA PDF: {e}")
            raise
        except Exception as e:
            logger.error(f"Error parsing WPBA PDF: {e}")
            raise

    # --- Word-position parser -------------------------------------------------
    # The live WPBA PDF carries no table rules, so column membership is encoded
    # purely by x-coordinate. We cluster the per-event value tokens into column
    # anchors (document-wide for stability), then assign each player's values to
    # the nearest column. Blanks (events not entered) correctly map to 0, and a
    # per-player ``sum(in-window) == total`` check guards against misalignment.

    _ROW_TOLERANCE = 4.0          # px: words within this top-delta are one row
    _ANCHOR_GAP = 20.0            # px: x-gap that separates two columns
    _NUM_RE = re.compile(r"^\d[\d,]*(?:\.\d+)?$")
    _INT_RE = re.compile(r"^\d+$")
    _RANK_NAME_RE = re.compile(r"^(\d+)([A-Za-z].*)$")

    # --- Dynamic column-header discovery constants ---------------------------
    _HEADER_YEAR_RE = re.compile(r"^20\d{2}$")
    _HEADER_STOP_TOKENS = frozenset({"wpba"})
    _HEADER_COL_LEAD = 14.0       # px: how far left of a column's "<year> WPBA" marker a value/name may sit
    _HEADER_METADATA_PAD = 16.0   # px: words whose centre is this far left of the first column are metadata
    _HEADER_FRAG_GAP = 13.0       # px: x-gap that separates two event names on the bottom header line
    _HEADER_FRAG_MAX_DIST = 35.0  # px: max anchor↔fragment-centre distance to trust a bottom-line name

    @staticmethod
    def _xc(word: dict) -> float:
        return (word["x0"] + word["x1"]) / 2.0

    def _word_rows(self, page) -> List[List[dict]]:
        """Group a page's words into visual rows (clustered by ``top``)."""
        words = page.extract_words(use_text_flow=False, keep_blank_chars=False)
        words.sort(key=lambda w: (w["top"], w["x0"]))
        rows: List[List[dict]] = []
        current: List[dict] = []
        last_top: Optional[float] = None
        for w in words:
            if last_top is None or abs(w["top"] - last_top) <= self._ROW_TOLERANCE:
                current.append(w)
            else:
                rows.append(current)
                current = [w]
            last_top = w["top"]
        if current:
            rows.append(current)
        return rows

    def _player_fields(self, row_words: List[dict]) -> Optional[Dict]:
        """Extract rank, name, stops, total and event value-tokens from a row.

        Handles the WPBA layout where rank is glued to the first name token
        (e.g. ``"1Kristina"``) as well as a plain integer rank token.
        Returns ``None`` for non-player rows (headers, notes).
        """
        toks = sorted(row_words, key=lambda w: w["x0"])
        if not toks or toks[0]["x0"] >= 55:
            return None

        head = toks[0]["text"]
        glued = self._RANK_NAME_RE.match(head)
        if glued:
            rank = int(glued.group(1))
            name_parts = [glued.group(2)]
            rest = toks[1:]
        elif self._INT_RE.fullmatch(head):
            rank = int(head)
            name_parts = []
            rest = toks[1:]
        else:
            return None
        if rank > 400:
            return None

        numbers: List[dict] = []
        for w in rest:
            if self._NUM_RE.fullmatch(w["text"].replace(" ", "")):
                numbers.append(w)
            else:
                name_parts.append(w["text"])

        name = " ".join(p for p in name_parts if p).strip()
        if not name or len(numbers) < 2:
            return None

        numbers.sort(key=self._xc)
        stops = self._safe_int(numbers[0]["text"])
        total = self._safe_float(numbers[1]["text"])
        events = numbers[2:]
        return {
            "rank": rank,
            "name": name,
            "stops": stops,
            "total": total if total is not None else 0.0,
            "events": events,
        }

    def _cluster_anchors(self, xs: List[float]) -> Optional[List[float]]:
        """Cluster event-value x-centers into column anchors (sorted)."""
        if not xs:
            return None
        xs = sorted(xs)
        clusters: List[List[float]] = [[xs[0]]]
        for x in xs[1:]:
            if x - clusters[-1][-1] <= self._ANCHOR_GAP:
                clusters[-1].append(x)
            else:
                clusters.append([x])
        return [sum(c) / len(c) for c in clusters]

    # --- Dynamic column-header discovery -------------------------------------
    # The WPBA PDF publishes a rolling 10-event window: when a new event is
    # added it enters at the left, every other event shifts right, and the
    # event leaving the window drops into the rotating-11th (out-of-window)
    # column before disappearing. A hardcoded column list therefore goes stale
    # the moment a new event is published (values land under the wrong event
    # name — the bug this method fixes). The single reliable signal is that
    # *each event column header verifiably begins with a "<year> WPBA" marker*,
    # which gives the authoritative column count, left-to-right order and year.
    #
    # Event NAMES wrap across up to four header lines and, being centre-aligned
    # inside narrow columns, the wide words ("Invitational", "Championship")
    # bleed across neighbouring columns. So raw header text is NOT trusted for
    # column identity. Instead:
    #   1. derive ordered column boundaries + years from the "<year> WPBA" markers;
    #   2. reconstruct a (noisy) per-column header text by word x-centre;
    #   3. resolve identity by token-overlap against the known event dictionary
    #      (WPBA_ROTATING_TEN_COLUMNS) so recurring events keep their canonical
    #      keys/labels regardless of bleed (exact then strong-fuzzy, greedy);
    #   4. mint clean keys for genuinely new events from the bottom header line,
    #      where each event's short distinguishing name (e.g. "Islands US Open")
    #      sits correctly under its own column.
    # Returns ``None`` on any ambiguity so the caller falls back to the static
    # list — this method must never regress the parser. See docs/WPBA_TOURNAMENT_SSOT.md §5.

    @classmethod
    def _header_tokens(cls, text: str) -> List[str]:
        """Split header/key text into lowercase alphanumeric tokens (underscore-aware)."""
        return [t for t in re.split(r"[^a-z0-9]+", (text or "").lower()) if t]

    def _bottom_line_fragments(self, band: List[dict], metadata_right: float) -> List[Tuple[float, str]]:
        """Return (centre_x, text) for each event name on the lowest header line.

        The bottom header line carries each event's short distinguishing name,
        correctly positioned under its column. Metadata labels (Rank/Points/...)
        are dropped and names are segmented by x-gap so "Islands US Open" stays
        whole.
        """
        rows: List[List[dict]] = []
        current: List[dict] = []
        last_top: Optional[float] = None
        for w in sorted(band, key=lambda w: (w["top"], w["x0"])):
            if last_top is None or abs(w["top"] - last_top) <= self._ROW_TOLERANCE:
                current.append(w)
            else:
                rows.append(current)
                current = [w]
            last_top = w["top"]
        if current:
            rows.append(current)
        if not rows:
            return []
        bottom = max(rows, key=lambda r: max(w["top"] for w in r))
        bottom = sorted(
            [w for w in bottom if self._xc(w) >= metadata_right],
            key=lambda w: w["x0"],
        )
        if not bottom:
            return []
        frags: List[List[dict]] = [[bottom[0]]]
        for w in bottom[1:]:
            if w["x0"] - frags[-1][-1]["x1"] > self._HEADER_FRAG_GAP:
                frags.append([w])
            else:
                frags[-1].append(w)
        return [
            ((fr[0]["x0"] + fr[-1]["x1"]) / 2.0, " ".join(x["text"] for x in fr))
            for fr in frags
        ]

    def _new_event_key_label(
        self,
        idx: int,
        year: int,
        anchors: List[float],
        bottom_frags: List[Tuple[float, str]],
        col_text: str,
    ) -> Tuple[str, str]:
        """Build a clean ``(key, label)`` for an event not present in the known dictionary.

        Prefers the bottom-line short name nearest this column's value anchor;
        falls back to the (noisy) per-column reconstruction with its leading
        year/WPBA prefix stripped.
        """
        name = ""
        if bottom_frags:
            centre, frag_text = min(bottom_frags, key=lambda f: abs(f[0] - anchors[idx]))
            if abs(centre - anchors[idx]) <= self._HEADER_FRAG_MAX_DIST:
                name = frag_text.strip()
        if not name:
            toks = [
                t for t in self._header_tokens(col_text)
                if not self._HEADER_YEAR_RE.match(t) and t not in self._HEADER_STOP_TOKENS
            ]
            name = " ".join(toks).strip()

        norm = re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", name.lower())).strip("_")
        if not norm:
            return f"wpba_col_{idx}", f"WPBA Column {idx + 1}"
        if year:
            return f"{year}_wpba_{norm}", f"{year} WPBA {name}"
        return f"wpba_{norm}", f"WPBA {name}"

    def _extract_column_headers(self, page, anchors: List[float]) -> Optional[List[Tuple[str, str]]]:
        """Discover ``(column_key, label)`` per value-column anchor from the PDF header.

        Returns a list aligned 1:1 with ``anchors`` (newest column first), or
        ``None`` when the header cannot be read confidently (caller then uses the
        static ``WPBA_ROTATING_TEN_COLUMNS`` list).
        """
        try:
            words = page.extract_words(use_text_flow=False, keep_blank_chars=False)
            if not words:
                return None

            first_player_top: Optional[float] = None
            for row in self._word_rows(page):
                if self._player_fields(row) is not None:
                    first_player_top = min(w["top"] for w in row)
                    break
            if first_player_top is None:
                return None

            prelim = [w for w in words if w["top"] < first_player_top - 1.0]

            # 1) "<year> WPBA" markers -> ordered column left-edges + years.
            markers: List[Tuple[float, float, int]] = []  # (top, year_x0, year)
            for w in prelim:
                if w["text"].upper() != "WPBA":
                    continue
                yr_x0 = w["x0"]
                yr_val = 0
                for c in prelim:
                    if (abs(c["top"] - w["top"]) <= self._ROW_TOLERANCE
                            and self._HEADER_YEAR_RE.match(c["text"])
                            and 0.0 < (w["x0"] - c["x1"]) < 14.0):
                        yr_x0 = c["x0"]
                        yr_val = int(c["text"])
                        break
                markers.append((w["top"], yr_x0, yr_val))

            if len(markers) != len(anchors):
                logger.info(
                    "WPBA header-parse: %d '<year> WPBA' markers vs %d value columns; "
                    "using static column list",
                    len(markers), len(anchors),
                )
                return None

            # Header band: from the top of the highest marker down to the data.
            header_top = min(m[0] for m in markers) - 2.0
            band = [w for w in words if header_top <= w["top"] < first_player_top - 1.0]
            if not band:
                return None

            markers.sort(key=lambda m: m[1])
            bounds = [m[1] for m in markers]
            years = [m[2] for m in markers]
            n = len(bounds)
            metadata_right = bounds[0] - self._HEADER_METADATA_PAD

            # 2) Noisy per-column header text (word x-centre within year-edge bands).
            col_words: Dict[int, List[dict]] = {i: [] for i in range(n)}
            for w in band:
                xc = self._xc(w)
                if xc < metadata_right:
                    continue
                idx = n - 1
                for i in range(n):
                    hi = bounds[i + 1] - self._HEADER_COL_LEAD if i + 1 < n else float("inf")
                    if bounds[i] - self._HEADER_COL_LEAD <= xc < hi:
                        idx = i
                        break
                col_words[idx].append(w)
            col_text: Dict[int, str] = {}
            for i in range(n):
                ws = sorted(col_words[i], key=lambda w: (round(w["top"] / 4.0), w["x0"]))
                col_text[i] = " ".join(w["text"] for w in ws)

            bottom_frags = self._bottom_line_fragments(band, metadata_right)

            # 3) Known-event dictionary (canonical keys/labels) for identity matching.
            known: List[Dict] = []
            for key, label in WPBA_ROTATING_TEN_COLUMNS:
                ktoks = set(self._header_tokens(key))
                kyr = next((int(t) for t in ktoks if self._HEADER_YEAR_RE.match(t)), 0)
                known.append({
                    "key": key,
                    "label": label,
                    "yr": kyr,
                    "dist": ktoks - self._HEADER_STOP_TOKENS - {str(kyr)},
                })

            assigned: Dict[int, Tuple[str, str]] = {}
            used: set = set()
            col_norm = {i: "_".join(self._header_tokens(col_text[i])) for i in range(n)}

            # Pass A: exact canonical-key match.
            for i in range(n):
                for j, k in enumerate(known):
                    if j in used:
                        continue
                    if col_norm[i] and col_norm[i] == k["key"]:
                        assigned[i] = (k["key"], k["label"])
                        used.add(j)
                        break

            # Pass B: strong fuzzy match (same year + distinctive-token overlap), greedy by score.
            scored: List[Tuple[int, int, int]] = []
            for i in range(n):
                if i in assigned:
                    continue
                ctoks = set(self._header_tokens(col_text[i])) - self._HEADER_STOP_TOKENS
                cyr = next((int(t) for t in ctoks if self._HEADER_YEAR_RE.match(t)), 0)
                cdist = ctoks - {str(cyr)}
                for j, k in enumerate(known):
                    if j in used:
                        continue
                    if k["yr"] and cyr and k["yr"] != cyr:
                        continue
                    s = len(cdist & k["dist"])
                    # Strong = 2+ shared distinctive tokens, or every known token present
                    # (guards against a new event stealing a rotated-out event's key on a
                    # single generic word like "invitational").
                    if s >= 2 or (s >= 1 and k["dist"] and s == len(k["dist"])):
                        scored.append((s, i, j))
            scored.sort(reverse=True)
            for s, i, j in scored:
                if i in assigned or j in used:
                    continue
                assigned[i] = (known[j]["key"], known[j]["label"])
                used.add(j)

            # Pass C: genuinely new events -> clean key/label from the bottom-line name.
            for i in range(n):
                if i in assigned:
                    continue
                assigned[i] = self._new_event_key_label(
                    i, years[i], anchors, bottom_frags, col_text[i]
                )

            # Defensive: two columns must never share a key (would overwrite split data).
            out: List[Tuple[str, str]] = []
            seen: set = set()
            for i in range(n):
                key, label = assigned[i]
                if key in seen:
                    key = f"{key}_{i}"
                seen.add(key)
                out.append((key, label))

            logger.info(
                "WPBA header-parse: %d columns from PDF headers (%d matched known, %d new): %s",
                n, len(used), n - len(used),
                ", ".join(k for k, _ in out[:n]),
            )
            return out
        except Exception as e:
            logger.warning("WPBA header-parse failed (%s); using static column list", e)
            return None

    def _parse_pages_by_words(self, pages) -> List[Dict]:
        """Parse all pages via x-position. Returns [] to signal fallback."""
        per_page: List[List[Dict]] = []
        event_xs: List[float] = []
        for page in pages:
            page_players: List[Dict] = []
            for row in self._word_rows(page):
                fields = self._player_fields(row)
                if fields is None:
                    continue
                page_players.append(fields)
                event_xs.extend(self._xc(w) for w in fields["events"])
            per_page.append(page_players)

        anchors = self._cluster_anchors(event_xs)
        if anchors is None or len(anchors) not in (10, 11):
            logger.warning(
                "WPBA word-parse: expected 10-11 column anchors, got %s; "
                "falling back to table/text parsing",
                None if anchors is None else len(anchors),
            )
            return []

        # Column keys/labels come from the PDF header itself (dynamic rolling
        # window). Fall back to the static list only when the header cannot be
        # read confidently, so a new event never lands under a stale event name.
        header_cols = None
        try:
            first_page = pages[0] if len(pages) else None
            if first_page is not None:
                header_cols = self._extract_column_headers(first_page, anchors)
        except Exception as e:
            logger.warning("WPBA header extraction errored (%s); using static column list", e)
            header_cols = None

        if header_cols and len(header_cols) == len(anchors):
            active_cols = [k for k, _ in header_cols[:10]]
            labels = {k: lab for k, lab in header_cols[:10]}
            labels[WPBA_ROTATING_11TH_KEY] = WPBA_ROTATING_11TH_LABEL
        else:
            active_cols = [k for k, _ in WPBA_ROTATING_TEN_COLUMNS]
            labels = wpba_default_column_labels()
        rankings: List[Dict] = []
        skipped = 0
        for page_players in per_page:
            for f in page_players:
                entry: Dict = {
                    "rank": f["rank"],
                    "name": f["name"],
                    "points": f["total"],
                    "stops_played": f["stops"],
                }
                # Assign each value to its nearest column anchor; blanks -> "0".
                slots: List[Optional[str]] = [None] * len(anchors)
                for w in f["events"]:
                    xc = self._xc(w)
                    idx = min(range(len(anchors)), key=lambda i: abs(anchors[i] - xc))
                    slots[idx] = w["text"]
                in_window_sum = sum(
                    float(v.replace(",", "")) for v in slots[:10] if v
                )
                # Per-player guard: in-window events must reconstruct the total.
                if abs(in_window_sum - f["total"]) < 1.0:
                    for idx, key in enumerate(active_cols):
                        val = slots[idx] if idx < len(slots) else None
                        entry[key] = val if val else "0"
                    if len(anchors) >= 11:
                        eleventh = slots[10]
                        entry[WPBA_ROTATING_11TH_KEY] = eleventh if eleventh else "0"
                else:
                    skipped += 1
                    logger.debug(
                        "WPBA word-parse: %s (rank %s) in-window sum %.0f != total "
                        "%.0f; omitting per-event detail for this player",
                        f["name"], f["rank"], in_window_sum, f["total"],
                    )
                entry["wpba_column_labels"] = dict(labels)
                rankings.append(entry)

        if rankings:
            with_events = sum(
                1 for r in rankings
                if any(_is_wpba_tournament_column(k, v) for k, v in r.items())
            )
            logger.info(
                "WPBA word-parse: %d players, %d with per-event detail "
                "(%d skipped on sum-check), %d column anchors",
                len(rankings), with_events, skipped, len(anchors),
            )
        return rankings

    def _parse_page(self, page) -> List[Dict]:
        """Parse a PDF page for rankings.

        Table extraction is preferred because it preserves column positions:
        blank cells (tournaments a player didn't enter) stay as empty in the
        correct column instead of being silently skipped.  Text-line parsing
        is the secondary parser when table extraction returns nothing.
        """
        rankings = self._parse_table(page)
        if rankings:
            return rankings
        text = page.extract_text() or ""
        return self._parse_text_lines(text) if text else []

    def _parse_table(self, page) -> List[Dict]:
        """Extract rankings from pdfplumber table extraction.

        Column positions are preserved so blank cells (tournaments not played)
        naturally map to zero points for the correct tournament column.

        Expected PDF column layout (after phantom removal):
            Rank | Name | Stops | Total | T1 | T2 | ... | T10 | [T11]
        """
        try:
            table_settings = {
                "vertical_strategy": "text",
                "horizontal_strategy": "text",
            }
            tables = page.extract_tables(table_settings) or []
        except Exception:
            return []

        rankings: List[Dict] = []
        active_cols = [k for k, _ in WPBA_ROTATING_TEN_COLUMNS]
        labels = wpba_default_column_labels()

        for table in tables:
            if not table or len(table) < 2:
                continue

            data_start = 0
            for i, row in enumerate(table):
                first = ((row[0] if row else None) or "").strip()
                if self._safe_int(first) is not None:
                    data_start = i
                    break
            else:
                continue

            data_rows_raw = table[data_start:]

            # The "text" strategy can create phantom columns from alignment
            # gaps.  Detect them: any column that is blank for a player who
            # played all 10 tournaments is an artifact, not a real blank.
            phantom_cols: set = set()
            for row in data_rows_raw:
                cells = [(c or "").strip() for c in row]
                if len(cells) < 5:
                    continue
                stops = self._safe_int(cells[2])
                if stops is not None and stops >= 10:
                    for j in range(4, len(cells)):
                        if not cells[j]:
                            phantom_cols.add(j)
                    break

            for raw_row in data_rows_raw:
                if not raw_row:
                    continue
                raw_cells = [(c or "").strip() for c in raw_row]
                cells = [c for j, c in enumerate(raw_cells) if j not in phantom_cols]
                if len(cells) < 5:
                    continue

                rank = self._safe_int(cells[0])
                if rank is None:
                    continue
                name = cells[1]
                if not name or re.fullmatch(r"[\d,]+(?:\.\d+)?", name):
                    continue

                stops = self._safe_int(cells[2])
                points = self._safe_float(cells[3])
                if points is None:
                    points = 0.0

                entry: Dict = {
                    "rank": rank,
                    "name": name,
                    "points": points,
                    "stops_played": stops,
                }

                tournament_cells = cells[4:]
                for idx, key in enumerate(active_cols):
                    if idx < len(tournament_cells):
                        val = tournament_cells[idx]
                        entry[key] = val if val else "0"
                    else:
                        entry[key] = "0"

                if len(tournament_cells) > 10:
                    val = tournament_cells[10]
                    entry[WPBA_ROTATING_11TH_KEY] = val if val else "0"

                entry["wpba_column_labels"] = dict(labels)
                rankings.append(entry)

        return rankings

    def _parse_text_lines(self, text: str) -> List[Dict]:
        """Parse rankings from text lines with flexible spacing."""
        rankings = []
        for raw_line in text.split('\n'):
            line = re.sub(r'\s+', ' ', raw_line).strip()
            if not line:
                continue
            if 'rank' in line.lower() and 'points' in line.lower():
                continue
            # Rotating-10 format: rank + name + stops (played) + total + tournament points...
            # WPBA PDFs circa 2026 glue rank to first name in extract_text() output
            # (e.g. "1Kristina Tkach 10 146,750 ...") — allow \s* after rank.
            rotating = re.match(
                r'^(\d+)\s*([^\d].*?)\s+(\d{1,2})\s+([\d,]+(?:\.\d+)?)(?:\s+(.+))?$',
                line,
            )
            if not rotating:
                continue
            rank = self._safe_int(rotating.group(1))
            name = rotating.group(2).strip()
            stops = self._safe_int(rotating.group(3))
            points = self._safe_float(rotating.group(4))
            if rank is None or not name or points is None:
                continue

            row = {
                'rank': rank,
                'name': name,
                'points': points,
                'stops_played': stops
            }

            tail = (rotating.group(5) or "").strip()
            if tail:
                vals = re.findall(r'[\d,]+(?:\.\d+)?', tail)
                if len(vals) >= 10:
                    active_cols = [k for k, _ in WPBA_ROTATING_TEN_COLUMNS]
                    first_10_sum = sum(
                        float(v.replace(",", "").strip()) for v in vals[:10]
                    )
                    if abs(first_10_sum - points) < 1.0:
                        for idx, key in enumerate(active_cols):
                            row[key] = vals[idx]
                        if len(vals) >= 11:
                            row[WPBA_ROTATING_11TH_KEY] = vals[10]
                    else:
                        logger.warning(
                            "WPBA text parse: %s (rank %s) extracted sum %.0f != "
                            "PDF total %.0f -- blank cells likely shifted values; "
                            "skipping per-tournament assignment",
                            name, rank, first_10_sum, points,
                        )
            row["wpba_column_labels"] = wpba_default_column_labels()

            rankings.append(row)
        return rankings

    def _safe_int(self, value: str) -> Optional[int]:
        try:
            return int(value.strip())
        except (TypeError, ValueError):
            return None

    def _safe_float(self, value: str) -> Optional[float]:
        try:
            return float(value.replace(',', '').strip())
        except (TypeError, ValueError):
            return None

    def _save_scraped_data(self, rankings: List[Dict], source_url: str) -> None:
        """Save scraped rankings data to JSON file in scraped_data/wpba/"""
        if self.scraped_data_dir is None:
            return
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        data = {
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "scraper": "wpba_scraper",
                "source_url": source_url,
                "total_rankings": len(rankings)
            },
            "rankings": rankings
        }

        filename = f"wpba_rankings_{timestamp}.json"
        filepath = self.scraped_data_dir / filename

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved WPBA scraped data to {filepath}")
        except Exception as e:
            logger.error(f"Failed to save WPBA scraped data to {filepath}: {e}")

    def _dedupe_rankings(self, rankings: List[Dict]) -> List[Dict]:
        """Merge duplicates across pages/parsers, keeping richer source columns."""
        by_key: Dict[Tuple[Optional[int], Optional[str]], Dict] = {}
        order: List[Tuple[Optional[int], Optional[str]]] = []
        for ranking in rankings:
            key = (ranking.get('rank'), ranking.get('name'))
            if key not in by_key:
                by_key[key] = dict(ranking)
                order.append(key)
                continue
            merged = by_key[key]
            for k, v in ranking.items():
                if k == "wpba_column_labels" and isinstance(v, dict):
                    prev = merged.get(k) if isinstance(merged.get(k), dict) else {}
                    if len(v) >= len(prev):
                        merged[k] = v
                    continue
                if k not in merged or merged[k] in (None, "", []):
                    merged[k] = v
        return [by_key[k] for k in order]


def main():
    """Test the scraper"""
    logging.basicConfig(level=logging.INFO)
    
    scraper = WPBAScraper()
    rankings = scraper.scrape_rankings()
    
    if rankings:
        print(f"\n✓ Scraped {len(rankings)} WPBA rankings\n")
        print("Top 10:")
        for r in rankings[:10]:
            print(f"  {r['rank']}. {r['name']} - {r['points']} pts")
    else:
        print("\n✗ Failed to scrape rankings")


if __name__ == "__main__":
    main()
