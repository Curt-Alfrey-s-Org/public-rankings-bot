"""Tests for Inside Spin Tier-2 scraper (RSC parser + pro-like filter)."""
import unittest
from pathlib import Path

from scrapers.insidesp_tier2_scraper import InsideSpinTier2Scraper

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "insidesp" / "2022ukopenfinal16.html"


class TestInsideSpinTier2Scraper(unittest.TestCase):
    def setUp(self) -> None:
        self.scraper = InsideSpinTier2Scraper()

    def test_extract_participant_rows_from_fixture(self) -> None:
        self.assertTrue(FIXTURE.is_file(), f"missing fixture: {FIXTURE}")
        html = FIXTURE.read_text(encoding="utf-8")
        rows = self.scraper.extract_participant_rows_from_html(html)
        self.assertGreaterEqual(len(rows), 48)
        self.assertEqual(rows[0].get("operator_name"), "Joshua Filler")
        self.assertEqual(rows[0].get("position"), "1")

    def test_rows_to_results_from_participant_rows(self) -> None:
        html = FIXTURE.read_text(encoding="utf-8")
        participant_rows = self.scraper.extract_participant_rows_from_html(html)
        results = self.scraper.rows_to_results(participant_rows)
        self.assertGreaterEqual(len(results), 16)
        self.assertEqual(results[0]["player_name"], "Joshua Filler")
        self.assertEqual(results[0]["placement"], 1)

    def test_is_pro_like_major_events(self) -> None:
        self.assertTrue(self.scraper.is_pro_like("2022 UK Open Final 16"))
        self.assertTrue(self.scraper.is_pro_like("WPA World 9-Ball Championship"))
        self.assertTrue(self.scraper.is_pro_like("WPBA Colorado Classic"))

    def test_is_pro_like_excludes_nwpa_and_amateur(self) -> None:
        self.assertFalse(self.scraper.is_pro_like("NWPA Regional Championship"))
        self.assertFalse(self.scraper.is_pro_like("Local Bar Box League Finals"))

    def test_parse_placement_ranges(self) -> None:
        self.assertEqual(self.scraper.parse_placement("1"), 1)
        self.assertEqual(self.scraper.parse_placement("5-8"), 5)
        self.assertIsNone(self.scraper.parse_placement(""))
