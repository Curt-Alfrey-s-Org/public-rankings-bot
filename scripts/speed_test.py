#!/usr/bin/env python3
"""
Speed test for Rankings Bot API and optional DB calls.
Finds bottlenecks by measuring response times for key endpoints.

Usage:
  # API only (API must be running)
  python scripts/speed_test.py [--base-url URL] [--runs N]

  # API + in-process DB timing (from project root, DATABASE_URL set)
  python scripts/speed_test.py [--db]

Env:
  BASE_URL   Base API URL (default http://127.0.0.1:8000)
  --runs N  Runs per endpoint (default 5)
  --db      Also time get_all_rankings_from_db and get_movement in-process
"""

import argparse
import json
import os
import statistics
import sys
import time
import logging
from typing import List, Tuple
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)


def _url(base: str, path: str) -> str:
    base = base.rstrip("/")
    path = path if path.startswith("/") else "/" + path
    return base + path


def _time_request(url: str) -> Tuple[float, int]:
    """Return (duration_seconds, status_code)."""
    start = time.perf_counter()
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=30) as r:
            r.read()
            return (time.perf_counter() - start, r.status)
    except urllib.error.HTTPError as e:
        return (time.perf_counter() - start, e.code)
    except Exception as e:
        logger.warning("Request failed for %s: %s", url, e)
        return (time.perf_counter() - start, 0)


def _get_slideshow_first_url(base_url: str) -> str:
    """Fetch slideshow from API, return first URL path (e.g. /api/assets/serve/image/foo.jpg) or empty."""
    url = _url(base_url, "/api/media/slideshow")
    try:
        with urllib.request.urlopen(urllib.request.Request(url, method="GET"), timeout=10) as r:
            data = json.loads(r.read().decode())
    except Exception as e:
        logger.warning("Could not fetch slideshow metadata from %s: %s", url, e)
        return ""
    urls = data.get("urls") or []
    if not urls:
        return ""
    first = urls[0]
    return first if first.startswith("/") else "/" + first.lstrip("/")


def _stats(times_ms: List[float]) -> dict:
    if not times_ms:
        return {"min": 0, "median": 0, "avg": 0, "p95": 0}
    times_ms = sorted(times_ms)
    n = len(times_ms)
    p95_idx = min(int(n * 0.95), n - 1) if n else 0
    return {
        "min": times_ms[0],
        "median": statistics.median(times_ms),
        "avg": statistics.mean(times_ms),
        "p95": times_ms[p95_idx],
    }


# Key endpoints to measure (path only)
API_ENDPOINTS = [
    ("GET /api/health", "/api/health"),
    ("GET /api/rankings", "/api/rankings"),
    ("GET /api/rankings/wpba-women", "/api/rankings/wpba-women"),
    ("GET /api/rankings/movement", "/api/rankings/movement"),
    ("GET /api/rankings/last-update", "/api/rankings/last-update"),
    ("GET /api/rankings/types", "/api/rankings/types"),
    ("GET /api/fargo/org/WPBA", "/api/fargo/org/WPBA"),
    # Pics from DB (slideshow list + count; then first image fetch)
    ("GET /api/media/slideshow", "/api/media/slideshow"),
    ("GET /api/media/count", "/api/media/count"),
]


def run_api_tests(base_url: str, runs: int) -> List[dict]:
    results = []
    for label, path in API_ENDPOINTS:
        url = _url(base_url, path)
        times_ms = []
        statuses = []
        for _ in range(runs):
            dur_s, status = _time_request(url)
            times_ms.append(dur_s * 1000)
            statuses.append(status)
        ok = all(s == 200 for s in statuses)
        results.append({
            "label": label,
            "path": path,
            "ok": ok,
            "statuses": statuses,
            "times_ms": times_ms,
            "stats": _stats(times_ms),
        })

    # Website calling for pics from DB: get slideshow list, then time fetching first image
    first_path = _get_slideshow_first_url(base_url)
    if first_path:
        url = _url(base_url, first_path)
        times_ms = []
        statuses = []
        for _ in range(runs):
            dur_s, status = _time_request(url)
            times_ms.append(dur_s * 1000)
            statuses.append(status)
        results.append({
            "label": "GET first slideshow image (pic from DB)",
            "path": first_path,
            "ok": all(s == 200 for s in statuses),
            "statuses": statuses,
            "times_ms": times_ms,
            "stats": _stats(times_ms),
        })
    else:
        results.append({
            "label": "GET first slideshow image (pic from DB)",
            "path": "",
            "ok": False,
            "statuses": [],
            "times_ms": [],
            "stats": _stats([]),
        })

    return results


def run_db_tests() -> List[dict]:
    """Run in-process DB timing (requires DATABASE_URL and project root)."""
    results = []
    try:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from database import get_database_manager
    except ImportError as e:
        return [{"label": "DB (skip)", "error": str(e), "stats": None}]

    db = get_database_manager()
    runs = 5

    try:
        from api.routes.rankings import get_all_rankings_from_db
    except ImportError as e:
        results.append({"label": "DB get_all_rankings_from_db()", "error": str(e), "stats": None})
        get_all_rankings_from_db = None
    if get_all_rankings_from_db is not None:
        times_ms = []
        for _ in range(runs):
            start = time.perf_counter()
            try:
                get_all_rankings_from_db()
            except Exception as e:
                logger.warning("DB timing call get_all_rankings_from_db failed: %s", e)
            times_ms.append((time.perf_counter() - start) * 1000)
        results.append({
            "label": "DB get_all_rankings_from_db()",
            "ok": True,
            "stats": _stats(times_ms),
        })

    # get_movement
    times_ms = []
    for _ in range(runs):
        start = time.perf_counter()
        try:
            db.get_movement("WPBA_Women", limit=50)
        except Exception as e:
            logger.warning("DB timing call get_movement failed: %s", e)
        times_ms.append((time.perf_counter() - start) * 1000)
    results.append({
        "label": "DB get_movement(WPBA_Women)",
        "ok": True,
        "stats": _stats(times_ms),
    })

    return results


def main():
    parser = argparse.ArgumentParser(description="Speed test Rankings Bot API (and optional DB).")
    parser.add_argument("--base-url", default=os.getenv("BASE_URL", "http://127.0.0.1:8000"), help="API base URL")
    parser.add_argument("--runs", type=int, default=5, help="Runs per endpoint")
    parser.add_argument("--db", action="store_true", help="Also run in-process DB timing")
    parser.add_argument("--slow-ms", type=float, default=500, help="Flag endpoint if median exceeds this (ms)")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    print(f"Speed test: base_url={base_url}, runs={args.runs}, slow_threshold={args.slow_ms}ms")
    print()

    # API
    print("--- API endpoints ---")
    api_results = run_api_tests(base_url, args.runs)
    for r in api_results:
        ok_str = "ok" if r["ok"] else "FAIL"
        st = r["stats"]
        flag = "  [SLOW]" if st["median"] >= args.slow_ms else ""
        print(f"  {r['label']}: median={st['median']:.0f}ms avg={st['avg']:.0f}ms p95={st['p95']:.0f}ms  {ok_str}{flag}")
    print()

    # Optional DB
    if args.db:
        print("--- DB (in-process) ---")
        db_results = run_db_tests()
        for r in db_results:
            if r.get("error"):
                print(f"  {r['label']}: {r['error']}")
                continue
            st = r["stats"]
            if st is None:
                continue
            flag = "  [SLOW]" if st["median"] >= args.slow_ms else ""
            print(f"  {r['label']}: median={st['median']:.0f}ms avg={st['avg']:.0f}ms p95={st['p95']:.0f}ms{flag}")
        print()

    # Summary
    all_medians = [r["stats"]["median"] for r in api_results if r.get("stats")]
    if all_medians:
        worst = max(all_medians)
        worst_label = next(r["label"] for r in api_results if r.get("stats") and r["stats"]["median"] == worst)
        print(f"Slowest API (median): {worst_label} ({worst:.0f}ms)")
    print("Done.")


if __name__ == "__main__":
    main()
