"""Self-test route discovery must see included FastAPI routers (OpenAPI paths)."""

from api.main import app
from api.routes.system import _collect_registered_paths


def test_collect_registered_paths_includes_messages_and_system():
    paths = _collect_registered_paths(app)
    assert "/api/messages" in paths
    assert "/api/system" in paths
    assert "/api/system/health" in paths
    assert len(paths) > 50


def test_messages_and_system_route_checks():
    paths = _collect_registered_paths(app)
    assert any(p == "/api/messages" or p.startswith("/api/messages/") for p in paths)
    assert any(
        p == "/api/system" or (p.startswith("/api/system/") and p != "/api/system/health")
        for p in paths
    )
