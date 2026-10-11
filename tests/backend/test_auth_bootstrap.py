"""Startup auth bootstrap (review 2026-09-25, finding 3).

- No hardcoded/default password exists in api.auth.
- Users are created only from env credentials (<PREFIX>_PASSWORD / <PREFIX>_PASSWORD_HASH).
- Production (DEBUG unset/false) without SUPER_ADMIN_PASSWORD raises BootstrapConfigError
  when the super admin does not exist yet; dev (DEBUG=true) skips with a warning.
- Created users have must_change_password=True; existing users are never overwritten.
"""
import os
import sys
import types
import unittest
from unittest import mock

os.environ.setdefault("JWT_SECRET", "unit-test-secret-not-production")

from api import auth  # noqa: E402

_BOOTSTRAP_ENV_KEYS = [
    f"{prefix}_{suffix}"
    for prefix, *_ in auth.BOOTSTRAP_ACCOUNTS
    for suffix in ("USERNAME", "PASSWORD", "PASSWORD_HASH")
] + ["DEBUG"]

# Generated per run; never a real credential.
STRONG = "Unit-Test-" + os.urandom(4).hex() + "-Aa1!"


class FakeUser:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class _FakeQuery:
    def __init__(self, rows):
        self._rows = rows
        self._filters = {}

    def filter_by(self, **kw):
        self._filters = kw
        return self

    def first(self):
        for row in self._rows:
            if all(getattr(row, k, None) == v for k, v in self._filters.items()):
                return row
        return None


class FakeSession:
    def __init__(self, rows=None):
        self.rows = list(rows or [])
        self.pending = []
        self.committed = False
        self.rolled_back = False

    def query(self, _model):
        return _FakeQuery(self.rows + self.pending)

    def add(self, obj):
        self.pending.append(obj)

    def commit(self):
        self.rows.extend(self.pending)
        self.pending = []
        self.committed = True

    def rollback(self):
        self.pending = []
        self.rolled_back = True


class BootstrapTestBase(unittest.TestCase):
    def setUp(self):
        fake_module = types.ModuleType("api.models.user")
        fake_module.User = FakeUser
        self._modules = mock.patch.dict(sys.modules, {"api.models.user": fake_module})
        self._modules.start()
        self._env = mock.patch.dict(os.environ, {}, clear=False)
        self._env.start()
        for key in _BOOTSTRAP_ENV_KEYS:
            os.environ.pop(key, None)

    def tearDown(self):
        self._env.stop()
        self._modules.stop()


class TestNoHardcodedPassword(unittest.TestCase):
    def test_temp_password_constants_removed(self):
        for name in ("TEMP_PASSWORD", "SUPER_ADMIN_DEFAULT_PASSWORD", "get_super_admin_password_default"):
            self.assertFalse(hasattr(auth, name), name)

    def test_legacy_bootstrap_functions_removed(self):
        self.assertFalse(hasattr(auth, "ensure_default_users_bootstrap"))
        self.assertFalse(hasattr(auth, "ensure_super_admin_bootstrap"))


class TestProductionBootstrap(BootstrapTestBase):
    def test_missing_super_admin_password_fails_loudly(self):
        db = FakeSession()
        with self.assertRaises(auth.BootstrapConfigError) as ctx:
            auth.ensure_bootstrap_users(db)
        self.assertIn("SUPER_ADMIN_PASSWORD", str(ctx.exception))
        self.assertEqual(db.rows, [])

    def test_existing_super_admin_needs_no_password(self):
        db = FakeSession([FakeUser(username="tornybotca1", role="admin", email="x@y")])
        summary = auth.ensure_bootstrap_users(db)
        self.assertIn("tornybotca1", summary["existing"])
        self.assertEqual(db.rows[0].role, "super_admin")  # role repaired, password untouched

    def test_creates_users_from_env_only(self):
        os.environ.update({
            "SUPER_ADMIN_USERNAME": "boss",
            "SUPER_ADMIN_PASSWORD": STRONG,
            "ADMIN_USERNAME": "Bama",
            "ADMIN_PASSWORD": STRONG,
        })
        db = FakeSession()
        summary = auth.ensure_bootstrap_users(db)
        self.assertEqual(sorted(summary["created"]), ["Bama", "boss"])
        by_name = {u.username: u for u in db.rows}
        self.assertEqual(by_name["boss"].role, "super_admin")
        self.assertEqual(by_name["Bama"].role, "admin")
        for user in db.rows:
            self.assertTrue(user.must_change_password)
            self.assertTrue(user.password_hash.startswith("$argon2"))
            self.assertTrue(auth._verify_password(STRONG, user.password_hash))
        # Optional accounts without a password are skipped, not created with a default.
        self.assertNotIn("director", by_name)
        self.assertNotIn("user", by_name)
        self.assertNotIn("scorekeeper", by_name)

    def test_weak_password_rejected(self):
        os.environ["SUPER_ADMIN_PASSWORD"] = "short"
        with self.assertRaises(auth.BootstrapConfigError):
            auth.ensure_bootstrap_users(FakeSession())

    def test_password_hash_env_is_used_verbatim(self):
        pw_hash = auth.hash_password(STRONG)
        os.environ["SUPER_ADMIN_PASSWORD_HASH"] = pw_hash
        db = FakeSession()
        auth.ensure_bootstrap_users(db)
        self.assertEqual(db.rows[0].password_hash, pw_hash)

    def test_existing_password_never_overwritten(self):
        os.environ.update({"SUPER_ADMIN_PASSWORD": STRONG, "DIRECTOR_PASSWORD": STRONG})
        existing = FakeUser(username="director", role="director", password_hash="keep-me", email="d@x")
        db = FakeSession([existing])
        auth.ensure_bootstrap_users(db)
        self.assertEqual(existing.password_hash, "keep-me")


class TestDevBootstrap(BootstrapTestBase):
    def test_dev_without_passwords_creates_nothing_and_does_not_raise(self):
        os.environ["DEBUG"] = "true"
        db = FakeSession()
        summary = auth.ensure_bootstrap_users(db)
        self.assertEqual(summary["created"], [])
        self.assertEqual(db.rows, [])


if __name__ == "__main__":
    unittest.main()
