"""Tests for api.auth password hashing (pwdlib: Argon2 current + bcrypt legacy).

Covers the June 2026 migration off passlib (Roadmap.md P0):
- new hashes are Argon2 (FastAPI security tutorial:
  https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/#password-hashing)
- legacy bcrypt hashes keep verifying
- verify_and_update semantics: legacy hashes transparently re-hash to Argon2
  on successful verification (pwdlib guide: https://frankie567.github.io/pwdlib/guide/)
"""
import os
import unittest
from unittest.mock import MagicMock

os.environ.setdefault("JWT_SECRET", "unit-test-secret-not-production")

import bcrypt  # pwdlib[bcrypt] dependency; used here to fabricate legacy hashes

from api import auth


def _legacy_bcrypt_hash(password: str) -> str:
    """Create a hash the way the pre-migration code did (bcrypt, 72-byte truncation)."""
    raw = password.encode("utf-8")[:72]
    return bcrypt.hashpw(raw, bcrypt.gensalt()).decode("utf-8")


class TestHashPassword(unittest.TestCase):
    def test_new_hash_is_argon2(self):
        h = auth.hash_password("CorrectHorse9!")
        self.assertTrue(h.startswith("$argon2"), h[:20])

    def test_new_hash_verifies(self):
        h = auth.hash_password("CorrectHorse9!")
        self.assertTrue(auth._verify_password("CorrectHorse9!", h))

    def test_wrong_password_fails_argon2(self):
        h = auth.hash_password("CorrectHorse9!")
        self.assertFalse(auth._verify_password("WrongHorse9!", h))

    def test_empty_inputs_fail(self):
        self.assertFalse(auth._verify_password("", auth.hash_password("x")))
        self.assertFalse(auth._verify_password("x", ""))


class TestLegacyBcrypt(unittest.TestCase):
    def test_legacy_bcrypt_hash_verifies(self):
        h = _legacy_bcrypt_hash("Legacy-Bcrypt-Pass9!")
        self.assertTrue(h.startswith("$2"), h[:4])
        self.assertTrue(auth._verify_password("Legacy-Bcrypt-Pass9!", h))

    def test_legacy_bcrypt_wrong_password_fails(self):
        h = _legacy_bcrypt_hash("Legacy-Bcrypt-Pass9!")
        self.assertFalse(auth._verify_password("NotThePassword1!", h))

    def test_legacy_long_password_still_verifies(self):
        # Pre-migration code truncated to 72 bytes before hashing; verification
        # must apply the same truncation (bcrypt>=4.1 raises beyond 72 bytes).
        long_pw = "A1!" + "x" * 100
        h = _legacy_bcrypt_hash(long_pw)
        self.assertTrue(auth._verify_password(long_pw, h))


class TestVerifyAndUpdate(unittest.TestCase):
    def test_legacy_hash_returns_argon2_upgrade(self):
        h = _legacy_bcrypt_hash("Legacy-Bcrypt-Pass9!")
        valid, updated = auth._verify_and_update_hash("Legacy-Bcrypt-Pass9!", h)
        self.assertTrue(valid)
        self.assertIsNotNone(updated)
        self.assertTrue(updated.startswith("$argon2"), updated[:20])
        # The upgraded hash must verify with the same password.
        self.assertTrue(auth._verify_password("Legacy-Bcrypt-Pass9!", updated))

    def test_legacy_long_password_upgrade_uses_full_password(self):
        # The bcrypt verify truncates to 72 bytes, but the upgraded Argon2 hash
        # must be of the FULL password the user types.
        long_pw = "A1!" + "x" * 100
        h = _legacy_bcrypt_hash(long_pw)
        valid, updated = auth._verify_and_update_hash(long_pw, h)
        self.assertTrue(valid)
        self.assertTrue(updated.startswith("$argon2"))
        self.assertTrue(auth._verify_password(long_pw, updated))

    def test_current_argon2_hash_needs_no_update(self):
        h = auth.hash_password("CorrectHorse9!")
        valid, updated = auth._verify_and_update_hash("CorrectHorse9!", h)
        self.assertTrue(valid)
        self.assertIsNone(updated)

    def test_wrong_password_returns_no_update(self):
        h = _legacy_bcrypt_hash("Legacy-Bcrypt-Pass9!")
        valid, updated = auth._verify_and_update_hash("wrong", h)
        self.assertFalse(valid)
        self.assertIsNone(updated)

    def test_malformed_hash_fails_closed(self):
        valid, updated = auth._verify_and_update_hash("x", "not-a-hash")
        self.assertFalse(valid)
        self.assertIsNone(updated)


class TestVerifyUserPasswordRehash(unittest.TestCase):
    def _user(self, password_hash: str):
        user = MagicMock()
        user.username = "tester"
        user.password_hash = password_hash
        return user

    def test_legacy_hash_rehashed_and_committed(self):
        db = MagicMock()
        user = self._user(_legacy_bcrypt_hash("Legacy-Bcrypt-Pass9!"))
        self.assertTrue(auth._verify_user_password(db, user, "Legacy-Bcrypt-Pass9!"))
        self.assertTrue(user.password_hash.startswith("$argon2"))
        db.commit.assert_called_once()

    def test_current_hash_not_rewritten(self):
        db = MagicMock()
        h = auth.hash_password("CorrectHorse9!")
        user = self._user(h)
        self.assertTrue(auth._verify_user_password(db, user, "CorrectHorse9!"))
        self.assertEqual(user.password_hash, h)
        db.commit.assert_not_called()

    def test_wrong_password_no_commit(self):
        db = MagicMock()
        user = self._user(_legacy_bcrypt_hash("Legacy-Bcrypt-Pass9!"))
        self.assertFalse(auth._verify_user_password(db, user, "wrong"))
        db.commit.assert_not_called()

    def test_failed_commit_does_not_block_login(self):
        db = MagicMock()
        db.commit.side_effect = RuntimeError("db down")
        user = self._user(_legacy_bcrypt_hash("Legacy-Bcrypt-Pass9!"))
        self.assertTrue(auth._verify_user_password(db, user, "Legacy-Bcrypt-Pass9!"))
        db.rollback.assert_called_once()


if __name__ == "__main__":
    unittest.main()
