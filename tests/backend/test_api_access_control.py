"""API access control middleware and must_change_password enforcement
(review 2026-09-25, findings 3 and 18). Policy: docs/API_ACCESS_POLICY.md.

Builds a small FastAPI app with the same middleware stack api/main.py registers, so no
database is needed. The password-change DB lookup is patched.
"""
import os
import unittest
from unittest import mock

os.environ.setdefault("JWT_SECRET", "unit-test-secret-not-production")

from fastapi import Depends, FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from api import auth  # noqa: E402
from api.middleware.access_control import (  # noqa: E402
    RequireApiKeyMiddleware,
    RequireUserOrAdminMiddleware,
)

API_KEY = "unit-test-key-" + os.urandom(6).hex()  # generated per run, not a real key


def _build_app(api_key=API_KEY, allow_missing_key=False):
    app = FastAPI()

    @app.get("/api/health")
    def health():
        return {"ok": True}

    @app.post("/api/auth/login")
    def login():
        return {"ok": True}

    @app.get("/api/splash-config")
    def splash():
        return {"ok": True}

    @app.patch("/api/splash-config")
    def splash_patch():
        return {"ok": True}

    @app.get("/api/tournaments/{tid}/stream")
    def stream(tid: str):
        return {"ok": tid}

    @app.get("/api/rankings/wpa-women")
    def rankings():
        return {"ok": True}

    @app.post("/api/ai-narrative/demo-ask")
    def demo_ask():
        return {"ok": True}

    @app.get("/api/test-tournaments/current")
    def test_center_current():
        return {"ok": True}

    @app.get("/api/protected")
    def protected(user: dict = Depends(auth.get_current_user)):
        return {"role": user["role"]}

    @app.post("/api/users/change-password")
    def change_password(user: dict = Depends(auth.get_current_user_allow_password_change)):
        return {"ok": True}

    @app.get("/api/auth/me")
    def me(user: dict = Depends(auth.get_current_user_allow_password_change)):
        return {"must_change_password": auth.password_change_pending(user)}

    @app.get("/")
    def root():
        return {"spa": True}

    app.add_middleware(RequireUserOrAdminMiddleware, session_validator=lambda token: (False, None))
    app.add_middleware(RequireApiKeyMiddleware, api_key=api_key, allow_missing_key=allow_missing_key)
    return app


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


class TestApiKeyAndAnonymous(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(_build_app())

    # --- no key / wrong key / anonymous ---
    def test_no_key_rejected(self):
        r = self.client.get("/api/rankings/wpa-women", headers={"X-User-Role": "user"})
        self.assertEqual(r.status_code, 401)

    def test_wrong_key_rejected(self):
        r = self.client.get(
            "/api/rankings/wpa-women", headers={"X-API-Key": "wrong", "X-User-Role": "user"}
        )
        self.assertEqual(r.status_code, 401)

    def test_anonymous_without_role_header_rejected(self):
        r = self.client.get("/api/rankings/wpa-women", headers={"X-API-Key": API_KEY})
        self.assertEqual(r.status_code, 401)

    def test_anonymous_with_empty_role_header_rejected(self):
        r = self.client.get(
            "/api/rankings/wpa-women", headers={"X-API-Key": API_KEY, "X-User-Role": ""}
        )
        self.assertEqual(r.status_code, 401)

    def test_unknown_role_header_forbidden(self):
        r = self.client.get(
            "/api/rankings/wpa-women", headers={"X-API-Key": API_KEY, "X-User-Role": "director"}
        )
        self.assertEqual(r.status_code, 403)

    def test_completely_anonymous_rejected(self):
        self.assertEqual(self.client.get("/api/rankings/wpa-women").status_code, 401)

    # --- follow-up 2026-09-25: no role-header exemptions left ---
    def test_demo_ask_needs_role_header(self):
        for headers in ({"X-API-Key": API_KEY}, {"X-API-Key": API_KEY, "X-User-Role": ""}):
            self.assertEqual(self.client.post("/api/ai-narrative/demo-ask", headers=headers).status_code, 401)

    def test_test_center_needs_role_header_or_token(self):
        self.assertEqual(
            self.client.get("/api/test-tournaments/current", headers={"X-API-Key": API_KEY}).status_code, 401
        )
        self.assertEqual(
            self.client.get(
                "/api/test-tournaments/current", headers={"X-API-Key": API_KEY, "X-User-Role": "user"}
            ).status_code,
            200,
        )
        token = auth.create_access_token("director", subject="dir")
        self.assertEqual(self.client.get("/api/test-tournaments/current", headers=_bearer(token)).status_code, 200)

    # --- USPBF proxy contract (key + X-User-Role: user) keeps working ---
    def test_key_and_user_role_allowed(self):
        headers = {"X-API-Key": API_KEY, "X-User-Role": "user"}
        self.assertEqual(self.client.get("/api/rankings/wpa-women", headers=headers).status_code, 200)
        self.assertEqual(self.client.post("/api/ai-narrative/demo-ask", headers=headers).status_code, 200)

    def test_role_header_does_not_grant_access_to_token_routes(self):
        r = self.client.get("/api/protected", headers={"X-API-Key": API_KEY, "X-User-Role": "admin"})
        self.assertEqual(r.status_code, 401)  # route dependency still needs a Bearer JWT

    # --- public / open endpoints ---
    def test_open_and_public_read_endpoints(self):
        self.assertEqual(self.client.get("/api/health").status_code, 200)
        self.assertEqual(self.client.post("/api/auth/login").status_code, 200)
        self.assertEqual(self.client.get("/api/splash-config").status_code, 200)
        self.assertEqual(self.client.get("/api/tournaments/t1/stream").status_code, 200)
        self.assertEqual(self.client.get("/").status_code, 200)

    def test_public_read_is_get_only(self):
        self.assertEqual(self.client.patch("/api/splash-config").status_code, 401)

    # --- Bearer tokens ---
    def test_valid_jwt_needs_no_key(self):
        token = auth.create_access_token("user", subject="alice")
        r = self.client.get("/api/protected", headers=_bearer(token))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["role"], "user")

    def test_invalid_bearer_rejected(self):
        r = self.client.get("/api/rankings/wpa-women", headers=_bearer("not-a-token"))
        self.assertEqual(r.status_code, 401)


class TestMissingKeyConfig(unittest.TestCase):
    def test_production_without_key_returns_503(self):
        client = TestClient(_build_app(api_key="", allow_missing_key=False))
        r = client.get("/api/rankings/wpa-women", headers={"X-User-Role": "user"})
        self.assertEqual(r.status_code, 503)

    def test_debug_without_key_still_requires_role(self):
        client = TestClient(_build_app(api_key="", allow_missing_key=True))
        self.assertEqual(client.get("/api/rankings/wpa-women", headers={"X-User-Role": "user"}).status_code, 200)
        self.assertEqual(client.get("/api/rankings/wpa-women").status_code, 401)


class TestMustChangePasswordEnforcement(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(_build_app())
        self.token = auth.create_access_token("super_admin", subject="boss", password_change_required=True)

    def test_restricted_token_blocked_everywhere_else(self):
        with mock.patch.object(auth, "_user_still_must_change_password", return_value=True):
            r = self.client.get("/api/protected", headers=_bearer(self.token))
            self.assertEqual(r.status_code, 403)
            self.assertEqual(r.json()["detail"], auth.PASSWORD_CHANGE_REQUIRED_DETAIL)
            r = self.client.get("/api/rankings/wpa-women", headers=_bearer(self.token))
            self.assertEqual(r.status_code, 403)

    def test_restricted_token_can_change_password_and_read_me(self):
        with mock.patch.object(auth, "_user_still_must_change_password", return_value=True):
            self.assertEqual(
                self.client.post("/api/users/change-password", headers=_bearer(self.token)).status_code, 200
            )
            r = self.client.get("/api/auth/me", headers=_bearer(self.token))
            self.assertEqual(r.status_code, 200)
            self.assertTrue(r.json()["must_change_password"])

    def test_dependency_enforces_without_middleware(self):
        # Defense in depth: get_current_user rejects the token even if middleware is bypassed.
        app = FastAPI()

        @app.get("/x")
        def x(user: dict = Depends(auth.get_current_user)):
            return user

        with mock.patch.object(auth, "_user_still_must_change_password", return_value=True):
            r = TestClient(app).get("/x", headers=_bearer(self.token))
        self.assertEqual(r.status_code, 403)

    def test_token_works_after_password_changed(self):
        with mock.patch.object(auth, "_user_still_must_change_password", return_value=False):
            r = self.client.get("/api/protected", headers=_bearer(self.token))
        self.assertEqual(r.status_code, 200)

    def test_optional_user_treats_restricted_token_as_anonymous(self):
        from fastapi.security import HTTPAuthorizationCredentials

        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=self.token)
        with mock.patch.object(auth, "_user_still_must_change_password", return_value=True):
            self.assertIsNone(auth.get_optional_user(creds))

    def test_normal_token_has_no_claim(self):
        payload = auth.decode_token(auth.create_access_token("user", subject="alice"))
        self.assertNotIn(auth.PASSWORD_CHANGE_CLAIM, payload)
        self.assertFalse(auth.password_change_pending(payload))


if __name__ == "__main__":
    unittest.main()
