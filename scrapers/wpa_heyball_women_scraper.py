"""
Heyball Women association rankings — dedicated entrypoint (shared WPA parser).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from scrapers.wpa_scraper import WPAScraper


def scrape_wpa_heyball_women_rankings() -> Optional[List[Dict[str, Any]]]:
    return WPAScraper().scrape_rankings(division="Heyball_Women")
