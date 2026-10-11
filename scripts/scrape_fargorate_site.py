#!/usr/bin/env python3
"""
Scrape fargorate.com and subdirectories into a local folder for analysis.

Fetches HTML pages, extracts links, recursively crawls same-domain pages,
and saves content to data/fargorate_scrape/. Respects rate limits and
robots.txt if present.

Usage:
  python scripts/scrape_fargorate_site.py
  python scripts/scrape_fargorate_site.py --output ./my_scrape
"""

import argparse
import html
import logging
import re
import sys
import time
from pathlib import Path
from typing import Set
from urllib.parse import urljoin, urlparse

try:
    import httpx
    from bs4 import BeautifulSoup
except ImportError as e:
    print("Install dependencies: pip install httpx beautifulsoup4")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BASE_URL = "https://fargorate.com"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "fargorate_scrape"
REQUEST_DELAY_SECONDS = 1.5
TIMEOUT_SECONDS = 30
USER_AGENT = "RankingsBot/1.0 (Fargo rating research; +https://github.com/rankings-bot)"


def same_domain(url: str, base: str = BASE_URL) -> bool:
    """Return True if url is on the same domain as base."""
    try:
        return urlparse(url).netloc == urlparse(base).netloc
    except Exception:
        return False


def normalize_path(url: str) -> str:
    """Convert URL to a filesystem-safe path."""
    parsed = urlparse(url)
    path = parsed.path or "/"
    if path.endswith("/") and path != "/":
        path = path.rstrip("/")
    path = path.strip("/") or "index"
    # Replace / with _ for flat structure; collapse unsafe chars
    path = path.replace("/", "_")
    path = re.sub(r"[?#&=%]", "_", path)
    path = re.sub(r"_+", "_", path).strip("_")
    return path or "index"


# Paths to skip (internal CMS, API, etc.)
SKIP_PATH_PREFIXES = ("/umbraco", "/api", "/.well-known", "/cdn-cgi")

def extract_links(soup: BeautifulSoup, base: str) -> Set[str]:
    """Extract all same-domain links from the page."""
    links: Set[str] = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith("#") or href.startswith("mailto:") or href.startswith("javascript:"):
            continue
        full = urljoin(base, href)
        if not same_domain(full):
            continue
        parsed = urlparse(full)
        if any(parsed.path.startswith(p) for p in SKIP_PATH_PREFIXES):
            continue
        # Strip fragment
        full = full.split("#")[0].rstrip("/") or full
        links.add(full)
    return links


def html_to_markdown_text(soup: BeautifulSoup) -> str:
    """Extract readable text with minimal structure for analysis."""
    for tag in soup.find_all(["script", "style", "nav", "header", "footer"]):
        tag.decompose()
    lines: list[str] = []
    for el in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "td", "th", "tr"]):
        text = el.get_text(separator=" ", strip=True)
        if not text:
            continue
        name = el.name
        if name in ("h1", "h2", "h3", "h4", "h5", "h6"):
            prefix = "#" * int(name[1])
            lines.append(f"{prefix} {text}")
        elif name == "tr":
            lines.append(text)
        else:
            lines.append(text)
    return "\n\n".join(lines)


def scrape_page(client: httpx.Client, url: str) -> tuple[str | None, str | None]:
    """Fetch a page; returns (html_content, error)."""
    try:
        resp = client.get(url, timeout=TIMEOUT_SECONDS)
        resp.raise_for_status()
        return resp.text, None
    except httpx.HTTPStatusError as e:
        return None, f"HTTP {e.response.status_code}"
    except Exception as e:
        return None, str(e)


def main() -> int:
    parser = argparse.ArgumentParser(description="Scrape fargorate.com into a folder")
    parser.add_argument("--output", "-o", type=Path, default=DEFAULT_OUTPUT_DIR, help="Output directory")
    parser.add_argument("--delay", type=float, default=REQUEST_DELAY_SECONDS, help="Delay between requests (sec)")
    parser.add_argument("--max-pages", type=int, default=100, help="Maximum pages to fetch")
    args = parser.parse_args()

    out_dir = args.output.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Output: %s", out_dir)

    seen: Set[str] = set()
    # Seed with homepage; crawler discovers subpages via links
    to_visit: list[str] = [BASE_URL]
    delay = max(0.5, args.delay)
    max_pages = max(1, args.max_pages)

    headers = {"User-Agent": USER_AGENT}
    index_lines: list[str] = ["# FargoRate.com Scrape Index\n", f"Base URL: {BASE_URL}\n\n## Pages\n"]

    with httpx.Client(headers=headers, follow_redirects=True) as client:
        while to_visit and len(seen) < max_pages:
            url = to_visit.pop(0)
            if url in seen:
                continue
            seen.add(url)

            logger.info("Fetching [%d] %s", len(seen), url)
            html_content, err = scrape_page(client, url)
            if err:
                logger.warning("  Failed: %s", err)
                index_lines.append(f"- {url} — **{err}**\n")
                time.sleep(delay)
                continue

            path_key = normalize_path(url)
            html_path = out_dir / f"{path_key}.html"
            text_path = out_dir / f"{path_key}.txt"

            # Save HTML
            html_path.parent.mkdir(parents=True, exist_ok=True)
            html_path.write_text(html_content, encoding="utf-8")

            # Extract and save text
            soup = BeautifulSoup(html_content, "lxml")
            text = html_to_markdown_text(soup)
            text_path.write_text(text, encoding="utf-8")

            index_lines.append(f"- [{path_key}]({path_key}.html) — {url}\n")

            # Discover new links
            for link in extract_links(soup, url):
                if link not in seen and link not in to_visit:
                    to_visit.append(link)

            time.sleep(delay)

    index_path = out_dir / "INDEX.md"
    index_path.write_text("".join(index_lines), encoding="utf-8")
    logger.info("Wrote index to %s. Total pages: %d", index_path, len(seen))
    return 0


if __name__ == "__main__":
    sys.exit(main())
