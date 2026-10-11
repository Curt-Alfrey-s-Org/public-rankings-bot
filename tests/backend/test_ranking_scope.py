"""Tests for api.ranking_scope association mapping and validation."""
import unittest
from unittest.mock import patch

from api import ranking_scope as rs


class TestRankingSystemScope(unittest.TestCase):
    def test_wpba_family(self):
        self.assertEqual(rs.ranking_system_scope("WPBA_Women"), "WPBA")
        self.assertEqual(rs.ranking_system_scope("WPBA_Women_Jacoby2025"), "WPBA")

    def test_wpa_family(self):
        self.assertEqual(rs.ranking_system_scope("WPA_Men"), "WPA")
        self.assertEqual(rs.ranking_system_scope("WPA_Women"), "WPA")
        self.assertEqual(rs.ranking_system_scope("WPA_Heyball_Men"), "WPA")
        self.assertEqual(rs.ranking_system_scope("WPA_Artistic_2019_CAO"), "WPA")

    def test_cp(self):
        self.assertEqual(rs.ranking_system_scope("Competitors_Pool_9Ball"), "CP")

    def test_local(self):
        self.assertEqual(rs.ranking_system_scope("LOCAL"), "LOCAL")

    def test_unknown(self):
        self.assertIsNone(rs.ranking_system_scope(""))
        self.assertIsNone(rs.ranking_system_scope("   "))
        self.assertIsNone(rs.ranking_system_scope("NHL"))


class TestAssociationMembershipToScope(unittest.TestCase):
    def test_rows(self):
        self.assertEqual(rs.association_membership_to_scope("WPBA_Women"), "WPBA")
        self.assertEqual(rs.association_membership_to_scope("WPA_Men"), "WPA")


class TestIsValidRankingSystemForImport(unittest.TestCase):
    def test_explicit(self):
        self.assertTrue(rs.is_valid_ranking_system_for_import("WPA_Men"))
        self.assertTrue(rs.is_valid_ranking_system_for_import("WPBA_Women_Colorado2025"))

    def test_dynamic(self):
        self.assertTrue(rs.is_valid_ranking_system_for_import("WPBA_Women_CustomEvent2026"))
        self.assertTrue(rs.is_valid_ranking_system_for_import("WPA_Women_PBS_LasVegasOpen2026"))
        self.assertTrue(rs.is_valid_ranking_system_for_import("WPA_Men_9B_WorldChamp"))

    def test_invalid(self):
        self.assertFalse(rs.is_valid_ranking_system_for_import("NHL"))
        self.assertFalse(rs.is_valid_ranking_system_for_import(""))


class TestDirectorMayWrite(unittest.TestCase):
    def test_admin_bypass(self):
        ok, msg = rs.director_may_write_ranking_systems(
            {"role": "admin", "sub": "x"},
            ["WPA_Men", "WPBA_Women"],
        )
        self.assertTrue(ok)
        self.assertEqual(msg, "")

    def test_super_admin_bypass(self):
        ok, msg = rs.director_may_write_ranking_systems(
            {"role": "super_admin", "sub": "x"},
            ["WPA_Men"],
        )
        self.assertTrue(ok)

    @patch.object(rs, "get_user_association_scopes", return_value=set())
    def test_director_no_associations(self, _mock):
        ok, msg = rs.director_may_write_ranking_systems(
            {"role": "director", "sub": "d1"},
            ["WPBA_Women"],
        )
        self.assertFalse(ok)
        self.assertIn("No association", msg)

    @patch.object(rs, "get_user_association_scopes", return_value={"WPBA"})
    def test_director_wpba_only_blocks_wpa(self, _mock):
        ok, msg = rs.director_may_write_ranking_systems(
            {"role": "director", "sub": "d1"},
            ["WPA_Men"],
        )
        self.assertFalse(ok)
        self.assertIn("WPBA", msg)

    @patch.object(rs, "get_user_association_scopes", return_value={"WPBA"})
    def test_director_wpba_allows_wpba(self, _mock):
        ok, msg = rs.director_may_write_ranking_systems(
            {"role": "director", "sub": "d1"},
            ["WPBA_Women", "WPBA_Women_Jacoby2025"],
        )
        self.assertTrue(ok)

    @patch.object(rs, "get_user_association_scopes", return_value={"WPA"})
    def test_director_wpa_allows_dynamic_women(self, _mock):
        ok, msg = rs.director_may_write_ranking_systems(
            {"role": "director", "sub": "d1"},
            ["WPA_Women_NewCol_2026"],
        )
        self.assertTrue(ok)


class TestTournamentMerge(unittest.TestCase):
    @patch.object(rs, "get_user_association_scopes", return_value={"WPBA"})
    def test_director_wpba_merge(self, _mock):
        ok, msg = rs.director_may_run_tournament_ranking_merge(
            {"role": "director", "sub": "d1"},
            "WPBA",
        )
        self.assertTrue(ok)

    @patch.object(rs, "get_user_association_scopes", return_value={"WPBA"})
    def test_director_wpba_cannot_wpa_merge(self, _mock):
        ok, msg = rs.director_may_run_tournament_ranking_merge(
            {"role": "director", "sub": "d1"},
            "WPA",
        )
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
