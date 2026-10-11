#!/usr/bin/env python3
"""
Verify API endpoints match between frontend and backend.
Run from project root with API running: python scripts/verify_endpoints.py
Or with base URL: API_BASE=http://localhost:8003 python scripts/verify_endpoints.py
"""

import os
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

BASE = os.environ.get("API_BASE", "http://127.0.0.1:8003").rstrip("/")

# Endpoints that should return 200 (or 401 for auth-required) - not 404
# Format: (method, path, description)
ENDPOINTS = [
    # Health (no auth)
    ("GET", "/api/health", "Health check"),
    # Auth
    ("GET", "/api/auth/me", "Auth me (401 without token)"),
    # Rankings
    ("GET", "/api/rankings/wpba", "Rankings WPBA"),
    ("GET", "/api/rankings/wpba-women", "Rankings WPBA Women"),
    ("GET", "/api/rankings/wpa", "Rankings WPA"),
    ("GET", "/api/rankings/wpa-women", "Rankings WPA Women"),
    ("GET", "/api/rankings/wpa-men", "Rankings WPA Men"),
    ("GET", "/api/rankings/movement", "Movement (requires system param)"),
    ("GET", "/api/rankings/movement-climbers", "Movement climbers (requires system param)"),
    ("GET", "/api/rankings/snapshots", "Snapshots (requires system param)"),
    ("GET", "/api/rankings/years", "Years"),
    # Tournament history
    ("GET", "/api/tournament-history/tournaments", "Tournament history"),
    ("GET", "/api/tournament-history/upcoming", "Upcoming events"),
    ("GET", "/api/tournament-history/statistics", "Tournament statistics"),
    ("GET", "/api/tournament-history/years", "Tournament years"),
    # Events
    ("GET", "/api/events/future", "Future events"),
    # System
    ("GET", "/api/system/health", "System health"),
    ("GET", "/api/app-version", "App version + build hash"),
    # Fargo
    ("GET", "/api/fargo/status", "Fargo status"),
    # Player performance
    ("GET", "/api/player-performance/me", "Player performance me (401 without token)"),
    # Login features
    ("GET", "/api/login-features", "Login features"),
    # Splash config
    ("GET", "/api/splash-config", "Splash config"),
]


def main():
    try:
        import urllib.request
        import urllib.error
    except ImportError:
        import urllib.request
        import urllib.error

    print(f"Verifying endpoints against {BASE}")
    print("=" * 60)

    failed = []
    for method, path, desc in ENDPOINTS:
        url = f"{BASE}{path}"
        # Add required query params for some endpoints
        if "movement" in path and "?" not in path:
            url += "?system=WPBA"
        elif "snapshots" in path:
            url += "?system=WPBA"
        elif "years" in path and "tournament-history" not in path:
            url += "?system=WPBA_Women"

        req = urllib.request.Request(url, method=method)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                status = resp.status
                ok = status in (200, 401)  # 401 = auth required, endpoint exists
                symbol = "✓" if ok else "✗"
                print(f"  {symbol} {method:4} {path:45} -> {status} ({desc})")
                if not ok and status != 401:
                    failed.append((path, status, desc))
        except urllib.error.HTTPError as e:
            if e.code == 401:
                print(f"  ✓ {method:4} {path:45} -> 401 (auth required) ({desc})")
            elif e.code == 404:
                print(f"  ✗ {method:4} {path:45} -> 404 NOT FOUND ({desc})")
                failed.append((path, 404, desc))
            else:
                print(f"  ✗ {method:4} {path:45} -> {e.code} ({desc})")
                failed.append((path, e.code, desc))
        except Exception as e:
            print(f"  ✗ {method:4} {path:45} -> ERROR: {e} ({desc})")
            failed.append((path, str(e), desc))

    print("=" * 60)
    if failed:
        print(f"\n{len(failed)} endpoint(s) failed:")
        for path, status, desc in failed:
            print(f"  - {path} ({desc}): {status}")
        return 1
    print("\nAll endpoints verified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
