#!/usr/bin/env python3
"""
Post a Grok-generated fix suggestion as a PR comment when the Tests workflow fails.

Requires:
  XAI_API_KEY       — xAI API key (GitHub Actions secret)
  GITHUB_TOKEN      — token with actions:read, pull-requests:write
  GITHUB_REPOSITORY — owner/repo
  WORKFLOW_RUN_ID   — numeric id of the failed workflow run (set by CI)

If XAI_API_KEY is unset, exits 0 without commenting (fork PRs / optional secret).
"""

from __future__ import annotations

import io
import logging
import os
import sys
import zipfile
from pathlib import Path
from typing import Any, Dict, List

import httpx

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from api.services.ci_failure_suggestion import (  # noqa: E402
    build_ci_failure_user_message,
    call_xai_chat_sync,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("ci_grok_suggest_fix")

GITHUB_API = "https://api.github.com"


def _github_headers(token: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _client(token: str) -> httpx.Client:
    return httpx.Client(timeout=120.0, headers=_github_headers(token))


def _get_run(client: httpx.Client, repo: str, run_id: str) -> Dict[str, Any]:
    r = client.get(f"{GITHUB_API}/repos/{repo}/actions/runs/{run_id}")
    r.raise_for_status()
    return r.json()


def _extract_log_text(zip_bytes: bytes, max_chars: int = 120_000) -> str:
    parts: List[str] = []
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for name in sorted(zf.namelist()):
            if name.endswith("/") or not name.lower().endswith(".txt"):
                continue
            try:
                raw = zf.read(name).decode("utf-8", errors="replace")
                parts.append(f"===== {name} =====\n{raw}")
            except Exception as e:
                logger.warning("Skip zip member %s: %s", name, e)
    combined = "\n\n".join(parts)
    if len(combined) <= max_chars:
        return combined
    return combined[-max_chars:]


def _pr_numbers_from_run(client: httpx.Client, run: Dict[str, Any], repo: str) -> List[int]:
    prs = run.get("pull_requests") or []
    out: List[int] = []
    for p in prs:
        try:
            out.append(int(p["number"]))
        except (KeyError, TypeError, ValueError):
            continue
    if out:
        return out
    head = run.get("head_branch") or ""
    if not head:
        return []
    q = f"repo:{repo} head:{head} is:open"
    r = client.get(f"{GITHUB_API}/search/issues", params={"q": q})
    if r.status_code != 200:
        logger.warning("PR search failed: %s %s", r.status_code, r.text[:200])
        return []
    nums: List[int] = []
    for it in r.json().get("items") or []:
        if it.get("pull_request"):
            try:
                nums.append(int(it["number"]))
            except (KeyError, TypeError, ValueError):
                continue
    return nums[:3]


def _post_comment(client: httpx.Client, repo: str, pr_number: int, body: str) -> None:
    r = client.post(
        f"{GITHUB_API}/repos/{repo}/issues/{pr_number}/comments",
        json={"body": body},
    )
    r.raise_for_status()


def main() -> int:
    api_key = os.getenv("XAI_API_KEY", "").strip()
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN") or ""
    repo = os.getenv("GITHUB_REPOSITORY", "").strip()
    run_id = os.getenv("WORKFLOW_RUN_ID", "").strip()

    if not api_key:
        logger.info("XAI_API_KEY not set; skip Grok PR suggestion (configure secret to enable).")
        return 0
    if not token or not repo or not run_id:
        logger.error("Missing GITHUB_TOKEN, GITHUB_REPOSITORY, or WORKFLOW_RUN_ID")
        return 1

    with _client(token) as client:
        try:
            run = _get_run(client, repo, run_id)
        except Exception as e:
            logger.exception("Failed to fetch workflow run: %s", e)
            return 1

        logs_url = run.get("logs_url")
        if not logs_url:
            logger.error("Run has no logs_url")
            return 1

        try:
            lr = client.get(logs_url, follow_redirects=True, timeout=300.0)
            lr.raise_for_status()
            zip_bytes = lr.content
        except Exception as e:
            logger.exception("Failed to download logs: %s", e)
            return 1

        log_text = _extract_log_text(zip_bytes)
        if not log_text.strip():
            logger.warning("Empty log archive; skipping Grok")
            return 0

        prs = _pr_numbers_from_run(client, run, repo)
        if not prs:
            logger.info("No pull request associated with this run; skip comment.")
            return 0

        user_msg = build_ci_failure_user_message(
            log_text,
            workflow_name=str(run.get("name") or "Tests"),
            branch=str(run.get("head_branch") or ""),
            commit_sha=str(run.get("head_sha") or "")[:12],
        )
        try:
            suggestion = call_xai_chat_sync(api_key, user_msg)
        except Exception as e:
            logger.exception("Grok call failed: %s", e)
            return 1

        body = (
            "## CI failure — suggested fix (Grok)\n\n"
            "_Automated triage from workflow logs. Review before applying; "
            "this is advisory only._\n\n"
            f"{suggestion}\n\n"
            f"— workflow run `{run_id}`"
        )
        for num in prs:
            try:
                _post_comment(client, repo, num, body)
                logger.info("Posted suggestion comment on PR #%s", num)
            except Exception as e:
                logger.exception("Failed to comment on PR #%s: %s", num, e)
                return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
