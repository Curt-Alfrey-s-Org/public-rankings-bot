"""
Logs Routes
Provides access to bot logs
"""

import json
import logging
import os
import re
from collections import deque
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from api.auth import require_admin
from project_root import PROJECT_ROOT

logger = logging.getLogger(__name__)

router = APIRouter()

# Matches api/main.py FileHandler: %(asctime)s - %(name)s - %(levelname)s - %(message)s
_LOG_LINE_RE = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) - (?P<logger>.+?) - "
    r"(?P<level>DEBUG|INFO|WARNING|ERROR|CRITICAL) - (?P<message>.*)$"
)


def _log_file_path() -> Path:
    raw = os.environ.get("LOG_FILE", "").strip()
    if raw:
        return Path(raw).resolve()
    return PROJECT_ROOT / "rankings_bot.log"


def _read_log_raw_lines(max_lines: int) -> List[str]:
    path = _log_file_path()
    if not path.is_file():
        return []
    dq: deque[str] = deque(maxlen=max_lines)
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                dq.append(line.rstrip("\n"))
    except OSError as e:
        logger.warning("Failed to read log file %s: %s", path, e)
        return []
    return list(dq)


def _parse_log_line(raw: str) -> Dict[str, Any]:
    m = _LOG_LINE_RE.match(raw.strip())
    if m:
        return {
            "raw": raw,
            "timestamp": m.group("timestamp"),
            "level": m.group("level"),
            "logger": m.group("logger"),
            "message": m.group("message"),
        }
    return {
        "raw": raw,
        "timestamp": "",
        "level": "INFO",
        "logger": "unparsed",
        "message": raw,
    }


@router.get("")
async def list_logs(
    limit: int = Query(500, ge=1, le=5000),
    level: Optional[str] = Query(None),
    logger_name: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    sort_by: str = Query("timestamp"),
    sort_order: str = Query("desc"),
    tail: bool = Query(True),
    _user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """
    Return parsed lines from rankings_bot.log (most recent chunk of file for performance).
    Admin or super_admin only.
    """
    _ = tail  # reserved; file read is always tail-biased via bounded deque
    if sort_by not in ("timestamp", "level", "logger"):
        raise HTTPException(status_code=400, detail="sort_by must be timestamp, level, or logger")
    if sort_order not in ("asc", "desc"):
        raise HTTPException(status_code=400, detail="sort_order must be asc or desc")

    path = _log_file_path()
    exists = path.is_file()
    if not exists:
        return {"logs": [], "total": 0, "file": str(path), "exists": False}

    max_scan = min(200_000, max(limit * 200, 10_000))
    raw_lines = _read_log_raw_lines(max_scan)
    entries = [_parse_log_line(line) for line in raw_lines]

    lev = (level or "").strip().upper()
    if lev and lev != "ALL":
        entries = [e for e in entries if e["level"] == lev]

    if logger_name and logger_name.strip():
        ln = logger_name.strip().lower()
        entries = [e for e in entries if ln in (e.get("logger") or "").lower()]

    if search and search.strip():
        s = search.strip().lower()
        entries = [
            e
            for e in entries
            if s in (e.get("message") or "").lower() or s in (e.get("raw") or "").lower()
        ]

    reverse = sort_order == "desc"
    if sort_by == "timestamp":

        def ts_key(e: Dict[str, Any]) -> str:
            return e.get("timestamp") or ""

        entries.sort(key=ts_key, reverse=reverse)
    elif sort_by == "level":
        entries.sort(key=lambda e: e.get("level") or "", reverse=reverse)
    else:
        entries.sort(key=lambda e: e.get("logger") or "", reverse=reverse)

    entries = entries[:limit]

    return {"logs": entries, "total": len(entries), "file": str(path), "exists": True}


@router.post("/frontend", status_code=status.HTTP_202_ACCEPTED)
async def ingest_frontend_log(request: Request) -> Dict[str, Any]:
    """
    Accept best-effort frontend monitoring payloads.
    The UI uses navigator.sendBeacon(), so payload may be text/plain.
    Always returns 202 so monitoring never causes user-facing errors.
    """
    try:
        raw_body = await request.body()
        parsed_payload: Any = None
        if raw_body:
            try:
                parsed_payload = json.loads(raw_body.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError) as decode_err:
                logger.debug("Frontend log body not JSON: %s", decode_err)
                parsed_payload = None

        if isinstance(parsed_payload, dict):
            logger.warning(
                "Frontend log: %s",
                parsed_payload.get("message", "unknown"),
                extra={"frontend_log": parsed_payload},
            )
        elif parsed_payload is not None:
            logger.warning("Frontend log payload received (non-object)")
    except Exception as e:
        logger.warning("Failed to ingest frontend log payload: %s", e)
    # Always return 202; never raise so this route never returns 500
    return {"success": True}
