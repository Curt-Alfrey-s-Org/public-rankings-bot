"""Tests for Inside Spin Tier-2 importer gap-fill transaction ordering."""
import unittest
from unittest.mock import MagicMock

from api.services.event_crosswalk import CrosswalkResolution
from api.services.insidesp_tier2_importer import InsideSpinTier2Importer


class TestInsideSpinTier2ImporterGapFill(unittest.TestCase):
    def _run_ingest_with_existing_count(self, existing_count: int) -> tuple[dict, list[str]]:
        mock_db = MagicMock()
        mock_conn = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_conn)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_db.engine.begin.return_value = mock_ctx
        mock_db.engine.connect.return_value = mock_ctx

        mock_scraper = MagicMock()
        mock_scraper.fetch_tournaments_catalog.return_value = [{
            "name": "2022 UK Open",
            "name_slug": "2022ukopen",
            "results_count": 64,
            "start_date": "2022-06-01",
            "top_finishers": [{"player_name": "A", "position": "1", "winnings": 0}],
        }]
        mock_scraper.is_pro_like.return_value = True
        mock_scraper.archive_catalog.return_value = None
        mock_scraper.fetch_participant_rows.return_value = []
        mock_scraper.rows_to_results.return_value = [
            {"player_name": "A", "placement": 1, "points": 0.0},
        ]
        mock_scraper.BASE_URL = "https://www.insidesp.in"

        mock_resolver = MagicMock()
        mock_resolver.resolve.return_value = CrosswalkResolution(
            tournament_id="dp_2022ukopen",
            matched=True,
            match_method="exact",
            match_score=1.0,
        )

        importer = InsideSpinTier2Importer(
            scraper=mock_scraper,
            resolver=mock_resolver,
            db=mock_db,
        )

        call_order: list[str] = []

        def _count(_tid: str) -> int:
            call_order.append("count")
            return existing_count

        importer._local_results_count = _count  # type: ignore[method-assign]

        stats = importer.ingest(max_events=1, fetch_detail=False)
        if mock_db.engine.begin.called:
            call_order.append("begin")
        return stats, call_order

    def test_skips_gap_fill_when_local_results_exist(self) -> None:
        stats, call_order = self._run_ingest_with_existing_count(3)
        self.assertEqual(call_order, ["count", "begin"])
        self.assertEqual(stats["skipped_has_results"], 1)
        self.assertEqual(stats["gap_filled"], 0)
        self.assertEqual(stats["results_written"], 0)

    def test_gap_fill_writes_when_local_results_empty(self) -> None:
        stats, call_order = self._run_ingest_with_existing_count(0)
        self.assertEqual(call_order, ["count", "begin"])
        self.assertEqual(stats["gap_filled"], 1)
        self.assertEqual(stats["results_written"], 1)


if __name__ == "__main__":
    unittest.main()
