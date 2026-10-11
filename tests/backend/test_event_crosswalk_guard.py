"""Tests for the crosswalk 1:1 per-source mapping guard in EventCrosswalkResolver."""
import unittest
from unittest.mock import MagicMock

from api.services.event_crosswalk import EventCrosswalkResolver


class TestSameSourceFuzzyGuard(unittest.TestCase):
    def _make_resolver(self, already_mapped: bool) -> EventCrosswalkResolver:
        resolver = EventCrosswalkResolver(db=MagicMock())
        resolver.get_crosswalk_tournament_id = MagicMock(return_value=None)  # type: ignore[method-assign]
        resolver.find_matching_tournament = MagicMock(  # type: ignore[method-assign]
            return_value=("insidesp_2021championshipleaguegroup5", 0.90, "date+name", 4)
        )
        resolver._tournament_already_mapped_from_source = MagicMock(  # type: ignore[method-assign]
            return_value=already_mapped
        )
        resolver.record = MagicMock()  # type: ignore[method-assign]
        return resolver

    def test_rejects_fuzzy_match_when_tournament_owned_by_same_source(self) -> None:
        resolver = self._make_resolver(already_mapped=True)
        res = resolver.resolve(
            source="insidesp",
            source_event_id="2021championshipleaguegroup3",
            name="2021 Championship League Pool - Group 3",
            event_date="2021-03-01",
            use_llm=False,
        )
        self.assertFalse(res.matched)
        self.assertIsNone(res.tournament_id)
        resolver.record.assert_not_called()

    def test_accepts_fuzzy_match_when_tournament_unmapped(self) -> None:
        resolver = self._make_resolver(already_mapped=False)
        res = resolver.resolve(
            source="insidesp",
            source_event_id="2021championshipleaguegroup5",
            name="2021 Championship League Pool - Group 5",
            event_date="2021-03-01",
            use_llm=False,
        )
        self.assertTrue(res.matched)
        self.assertEqual(res.tournament_id, "insidesp_2021championshipleaguegroup5")
        self.assertEqual(res.match_method, "date+name")
        resolver.record.assert_called_once()


if __name__ == "__main__":
    unittest.main()
