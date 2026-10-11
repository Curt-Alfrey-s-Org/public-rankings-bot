"""
Admin-only routes (rebuild website, appearance defaults, tournament history scrape, etc.).
"""

# Doc refs (AI / maintainers): docs/AUTH_DOC_HOOKS.md; docs/ROLES_AND_PERMISSIONS.md;
#   docs/ROLE_CAPABILITIES.md; docs/PRODUCTION_DEPLOYMENT.md; docs/CONTAINER_DRIFT_PREVENTION.md

import asyncio
import os
import subprocess
import json
import logging
from pathlib import Path
from typing import Optional, AsyncGenerator, Dict, Any
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api.auth import require_super_admin, require_admin, require_admin_or_super_admin
from api.services.cache_store import get_cache_backend, invalidate_cache
from api.services.cache_warmup import run_cache_warmup_impl
from api.services.live_log import (
    get_job,
    register_job,
    start_background_action,
    stream_log_response,
)
from api.services.live_topics import Topic
from api.services.live_updates import notify_data_changed
from database import get_database_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])

# Default rebuild script relative to project root (so button works without env var)
from project_root import PROJECT_ROOT


def _rebuild_log_file_path() -> Path:
    """
    Writable path for the admin rebuild log stream.

    Default: PROJECT_ROOT/logs/rebuild_website.log — matches production compose bind-mount
    of ../logs:/app/logs so non-root API (HOST_UID) can write. The repo root was not
    writable in-container, which caused endless 'Waiting for rebuild log file to be created'.
    """
    raw = os.getenv("REBUILD_WEBSITE_LOG_FILE", "").strip()
    if raw:
        return Path(raw)
    return PROJECT_ROOT / "logs" / "rebuild_website.log"
DEFAULT_APPEARANCE_FILE = PROJECT_ROOT / "config" / "default_appearance.json"
DEFAULT_REBUILD_SCRIPT = PROJECT_ROOT / "scripts" / "rebuild_website_now.sh"
REBUILD_ALL_SCRIPT = PROJECT_ROOT / "scripts" / "full_deploy.sh"
START_ALL_SCRIPT = PROJECT_ROOT / "scripts" / "start.sh"
STOP_ALL_SCRIPT = PROJECT_ROOT / "scripts" / "stop.sh"

# Use absolute path to shell so rebuild works when PATH is empty (e.g. systemd, minimal Docker).
# Per Python docs: prefer list form over shell=True to avoid injection; executable must be found.
REBUILD_SHELL = "/bin/bash"

# Allowlisted keys for run-command (super_admin only). Maps to script path or ("docker", "ps", ...).
ALLOWED_COMMAND_KEYS = frozenset({"start", "stop", "status"})
COMMAND_RUN_TIMEOUT_SEC = 90

# Live-log job id for the Full deploy button. Registered at import time so the GET
# /rebuild-all-images/log endpoint can resolve the same job that the POST runs into.
_FULL_DEPLOY_JOB = "full_deploy"
register_job(_FULL_DEPLOY_JOB, "Full deploy")


# ---------------------------------------------------------------------------
# Host deploy dispatch (production): the API container holds NO docker.sock —
# docker-group/socket access is root-equivalent on the host (Docker Engine
# security docs: https://docs.docker.com/engine/security/#docker-daemon-attack-surface).
# When DEPLOY_REQUEST_DIR is set (production compose), Update website / Full
# deploy write a request file there; the host systemd path unit
# (production/systemd/rankings-bot-deploy.path) runs the deploy scripts and
# appends to the same bind-mounted log files this API streams.
# See docs/ADMIN_DEPLOY_HOST_DISPATCH.md. Unset (dev): scripts run directly.
# ---------------------------------------------------------------------------

def _deploy_request_dir() -> Optional[Path]:
    raw = os.getenv("DEPLOY_REQUEST_DIR", "").strip()
    return Path(raw) if raw else None


def _queue_deploy_request(action: str, requested_by: str) -> Path:
    """Write <action>.request atomically (tmp + os.replace) so the host path unit
    never reads a partial file. Raises OSError if the queue dir is not writable."""
    from datetime import datetime as _dt

    req_dir = _deploy_request_dir()
    if req_dir is None:
        raise RuntimeError("DEPLOY_REQUEST_DIR is not configured")
    req_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "action": action,
        "requested_by": requested_by,
        "requested_at": _dt.utcnow().isoformat() + "Z",
    }
    tmp = req_dir / f".{action}.request.tmp"
    final = req_dir / f"{action}.request"
    tmp.write_text(json.dumps(payload), encoding="utf-8")
    os.replace(tmp, final)
    logger.info("Deploy request queued: %s (by %s)", final, requested_by or "?")
    return final


def _backfill_latest_fargo_snapshots() -> Dict[str, int]:
    """
    Backfill Fargo ratings into the latest snapshot for core systems.
    This is a no-scrape operation and is safe to run before rebuilds.
    """
    systems = ["WPBA_Women", "WPA_Women", "WPA_Men"]
    db = get_database_manager()
    results: Dict[str, int] = {}
    for system in systems:
        try:
            results[system] = db.backfill_latest_fargo(system)
        except Exception as exc:
            logger.warning("Fargo backfill failed for %s: %s", system, exc)
            results[system] = 0
    try:
        db.refresh_materialized_views()
    except Exception as exc:
        logger.warning("Materialized view refresh failed after Fargo backfill: %s", exc)
    return results


def _get_rebuild_script_path() -> Optional[Path]:
    """Return path to rebuild script: REBUILD_WEBSITE_SCRIPT env, then project-root default, then cwd-relative."""
    script = os.getenv("REBUILD_WEBSITE_SCRIPT", "").strip()
    if script:
        return Path(script)
    if DEFAULT_REBUILD_SCRIPT.is_file():
        return DEFAULT_REBUILD_SCRIPT
    # cwd-relative path when API is run from project root
    try:
        cwd_script = Path(os.getcwd()) / "scripts" / "rebuild_website_now.sh"
        if cwd_script.is_file():
            return cwd_script
    except OSError as e:
        logger.warning("Could not inspect cwd rebuild script path: %s", e)
    return None


def _rebuild_not_configured_message() -> str:
    """Message when rebuild script is not available (e.g. API in Docker)."""
    if Path("/.dockerenv").exists():
        return (
            "Rebuild script not found in container. Run on the host: "
            "cd <project> && bash scripts/rebuild_website_now.sh"
        )
    return (
        "Rebuild script not found. Set REBUILD_WEBSITE_SCRIPT or add scripts/rebuild_website_now.sh in the project."
    )


class RebuildResponse(BaseModel):
    status: str
    message: str
    configured: bool
    command: Optional[str] = None  # e.g. "bash scripts/full_deploy.sh"


class IdentityLockRequest(BaseModel):
    player_name: str
    lock_type: str = "both"  # license | country | both
    source_system: Optional[str] = "ADMIN_MANUAL"
    license_number: Optional[str] = None
    country: Optional[str] = None


def _run_backfill_in_background() -> None:
    """Run Fargo backfill in background; never raise (log only)."""
    try:
        _backfill_latest_fargo_snapshots()
    except Exception as exc:
        logger.warning("Pre-rebuild Fargo backfill failed (non-blocking): %s", exc)


@router.post("/rebuild-website", response_model=RebuildResponse)
async def rebuild_website(_user: dict = Depends(require_admin_or_super_admin)):
    """
    Trigger website rebuild so frontend updates are visible (build frontend, then restart API/containers).
    Production (DEPLOY_REQUEST_DIR set): queues a request for the host dispatcher.
    Dev: runs scripts/rebuild_website_now.sh directly.
    Streams output to logs/rebuild_website.log (or REBUILD_WEBSITE_LOG_FILE).
    Allowed: admin and super_admin.
    """
    # Run backfill in background so it never blocks or causes 500
    import threading
    threading.Thread(target=_run_backfill_in_background, daemon=True).start()

    if _deploy_request_dir() is not None:
        log_file = _rebuild_log_file_path()
        try:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            log_file.write_text(
                "[queued] Deploy request written; waiting for the host dispatcher "
                "(rankings-bot-deploy.path) to start the rebuild...\n"
            )
            _queue_deploy_request("rebuild_website", str(_user.get("sub") or ""))
        except OSError as e:
            logger.exception("Could not queue rebuild_website deploy request")
            raise HTTPException(
                status_code=500,
                detail=(
                    f"Cannot write deploy request ({e}). Ensure the API user can write "
                    "the logs directory (production: host ./logs mounted at /app/logs)."
                ),
            ) from e
        return RebuildResponse(
            status="started",
            message=(
                "Website rebuild queued; the host deploy dispatcher runs it. When it "
                "finishes, do a hard refresh (Ctrl+Shift+R or Cmd+Shift+R) to see updates."
            ),
            configured=True,
            command="host: scripts/rebuild_website_now.sh (via rankings-bot-deploy.service)",
        )

    path = _get_rebuild_script_path()
    if path is None:
        return RebuildResponse(
            status="not_configured",
            message=_rebuild_not_configured_message(),
            configured=False,
            command=None,
        )
    script = str(path)
    cmd_display = f"{REBUILD_SHELL} {path}"
    if not path.is_file():
        return RebuildResponse(
            status="not_configured",
            message=f"Script not found: {script}",
            configured=False,
            command=cmd_display,
        )
    log_file = _rebuild_log_file_path()
    try:
        try:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            log_file.write_text("")
        except OSError as e:
            logger.exception("Could not create/truncate rebuild log at %s", log_file)
            raise HTTPException(
                status_code=500,
                detail=(
                    f"Cannot write rebuild log at {log_file} ({e}). "
                    "Ensure the API user can write the project logs directory "
                    "(production: host ./logs mounted at /app/logs)."
                ),
            ) from e
        app_root = Path(__file__).resolve().parent.parent.parent
        log_path = str(log_file)
        env = {**os.environ, "REBUILD_WEBSITE_LOG": log_path}
        proc = subprocess.Popen(
            [REBUILD_SHELL, script],
            cwd=str(app_root),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
        )
        logger.info("Rebuild website started by admin (PID %s), script=%s", proc.pid, script)
    except Exception as e:
        logger.exception("Failed to start rebuild script")
        raise HTTPException(status_code=500, detail=f"Failed to start rebuild: {e!s}")
    return RebuildResponse(
        status="started",
        message="Website rebuild started. When it finishes, do a hard refresh (Ctrl+Shift+R or Cmd+Shift+R) to see updates.",
        configured=True,
        command=cmd_display,
    )


def _rebuild_log_stream_max_sec() -> int:
    """Seconds to keep GET /rebuild-website/log open; env override must be a positive int."""
    raw = os.getenv("REBUILD_WEBSITE_LOG_STREAM_MAX_SEC", "900").strip()
    try:
        n = int(raw, 10)
    except ValueError:
        logger.warning("Invalid REBUILD_WEBSITE_LOG_STREAM_MAX_SEC=%r; using 900", raw)
        n = 900
    return max(60, n)


async def _stream_rebuild_log() -> AsyncGenerator[bytes, None]:
    """Yield rebuild log content as it grows until 'Done in' or max wait (long Docker builds)."""
    log_path = _rebuild_log_file_path()
    # Immediate bytes so reverse proxies flush and the UI shows activity (nginx may buffer otherwise).
    yield f"[Connected - streaming {log_path.name} from {log_path.parent}/]\n".encode("utf-8")
    last_size = 0
    empty_file_notice_sent = False
    file_missing_ticks = 0
    _max_wait_sec = _rebuild_log_stream_max_sec()
    loop = asyncio.get_running_loop()
    deadline = loop.time() + _max_wait_sec
    while loop.time() < deadline:
        try:
            if log_path.is_file():
                with open(log_path, "rb") as f:
                    f.seek(last_size)
                    chunk = f.read()
                    if chunk:
                        last_size = f.tell()
                        yield chunk
                        if b"Done in" in chunk or b"Done in " in chunk:
                            return
                    elif (
                        last_size == 0
                        and log_path.stat().st_size == 0
                        and not empty_file_notice_sent
                    ):
                        # POST /rebuild-website truncates the file; script may not write for a moment.
                        yield "[Log file is empty - waiting for rebuild script output...]\n".encode(
                            "utf-8"
                        )
                        empty_file_notice_sent = True
            else:
                # Missing file: often means log never created (permissions) or stream hit another worker
                # before POST created the file — rare with shared FS; usually permissions on old path.
                file_missing_ticks += 1
                if file_missing_ticks == 1:
                    yield (
                        "[Waiting for log file…] If this repeats: click **Update website** first, "
                        "or fix write access to the logs directory "
                        f"({log_path}). Production uses ./logs → /app/logs in compose.\n"
                    ).encode("utf-8")
                elif file_missing_ticks % 40 == 0:
                    yield "[Still waiting for rebuild log file…]\n".encode("utf-8")
        except (OSError, IOError) as e:
            logger.warning("Error reading rebuild log: %s", e)
            yield f"\n[Log read error: {e!s}]\n".encode("utf-8", errors="replace")
            return
        await asyncio.sleep(0.35)
    _timeout_msg = (
        f"\n[Stream stopped after {_max_wait_sec}s timeout - "
        "rebuild may still be running on the server; check logs/rebuild_website.log or try View rebuild log again.]\n"
    )
    yield _timeout_msg.encode("utf-8")


@router.get("/rebuild-website/log")
async def rebuild_website_log_stream(_user: dict = Depends(require_admin_or_super_admin)):
    """Stream rebuild log (default logs/rebuild_website.log) for the admin UI. Allowed: admin and super_admin."""
    return StreamingResponse(
        _stream_rebuild_log(),
        media_type="text/plain; charset=utf-8",
        headers={
            "Cache-Control": "no-store",
            # nginx: disable buffering for this response (defense in depth; nginx configs also set proxy_buffering off).
            "X-Accel-Buffering": "no",
        },
    )


def _get_rebuild_all_script_path() -> Optional[Path]:
    """Path to full-deploy script (app + nginx/tunnel rebuild and restart)."""
    script = os.getenv("REBUILD_ALL_IMAGES_SCRIPT", "").strip()
    if script:
        p = Path(script)
        if p.is_file():
            return p
        return p  # return path so caller can show "Script not found: {path}"
    if REBUILD_ALL_SCRIPT.is_file():
        return REBUILD_ALL_SCRIPT
    # When API runs in Docker, script is at /app/scripts/full_deploy.sh (copied by Dockerfile)
    if Path("/.dockerenv").exists():
        docker_script = Path("/app/scripts/full_deploy.sh")
        if docker_script.is_file():
            return docker_script
    try:
        cwd_script = Path(os.getcwd()) / "scripts" / "full_deploy.sh"
        if cwd_script.is_file():
            return cwd_script
    except OSError as e:
        logger.warning("Could not inspect cwd full deploy script path: %s", e)
    return None


def _get_start_script_path() -> Optional[Path]:
    """Path to start-all script (main stack + nginx + tunnel)."""
    script = os.getenv("START_ALL_SCRIPT", "").strip()
    if script:
        p = Path(script)
        if p.is_file():
            return p
        return p
    if START_ALL_SCRIPT.is_file():
        return START_ALL_SCRIPT
    if Path("/.dockerenv").exists():
        p = Path("/app/scripts/start.sh")
        if p.is_file():
            return p
    try:
        cwd_script = Path(os.getcwd()) / "scripts" / "start.sh"
        if cwd_script.is_file():
            return cwd_script
    except OSError as e:
        logger.warning("Could not inspect cwd start script path: %s", e)
    return None


@router.get("/cache/status")
async def cache_status(_user: dict = Depends(require_super_admin)):
    """Return cache backend status for admins."""
    return {"status": "ok", "backend": get_cache_backend()}


@router.post("/cache/refresh")
async def refresh_cache(_user: dict = Depends(require_super_admin)):
    """Invalidate caches and warm them with fresh data (admin-only).

    After warmup, broadcast a SETTINGS topic event so connected browsers re-fetch
    their currently-mounted queries (RFC 9111 §4.4 invalidate-on-write applied to a
    deliberate full-cache flush).
    """
    loop = asyncio.get_running_loop()

    def _refresh() -> dict:
        invalidate_cache()
        return run_cache_warmup_impl()

    result = await loop.run_in_executor(None, _refresh)
    try:
        notify_data_changed(
            Topic.SETTINGS.value,
            message="Server cache flushed and warmed",
        )
    except Exception as e:
        logger.warning("notify_data_changed failed (cache/refresh): %s", e)
    return {"status": "ok", "backend": get_cache_backend(), "result": result}


def _get_stop_script_path() -> Optional[Path]:
    """Path to stop-all script (main stack + nginx)."""
    script = os.getenv("STOP_ALL_SCRIPT", "").strip()
    if script:
        p = Path(script)
        if p.is_file():
            return p
        return p
    if STOP_ALL_SCRIPT.is_file():
        return STOP_ALL_SCRIPT
    if Path("/.dockerenv").exists():
        p = Path("/app/scripts/stop.sh")
        if p.is_file():
            return p
    try:
        cwd_script = Path(os.getcwd()) / "scripts" / "stop.sh"
        if cwd_script.is_file():
            return cwd_script
    except OSError as e:
        logger.warning("Could not inspect cwd stop script path: %s", e)
    return None


@router.get("/rebuild-all-images/status", response_model=RebuildResponse)
async def rebuild_all_images_status(_user: dict = Depends(require_admin_or_super_admin)):
    """Return whether full-deploy script is configured. Admin/super_admin only."""
    if _deploy_request_dir() is not None:
        return RebuildResponse(
            status="configured",
            message="Full deploy is available (runs on the Docker host via the deploy dispatcher).",
            configured=True,
            command="host: scripts/full_deploy.sh --no-cache (via rankings-bot-deploy.service)",
        )
    path = _get_rebuild_all_script_path()
    if path is None or not path.is_file():
        return RebuildResponse(
            status="not_configured",
            message="Full-deploy script not found. Set REBUILD_ALL_IMAGES_SCRIPT or add scripts/full_deploy.sh.",
            configured=False,
            command=None,
        )
    return RebuildResponse(
        status="configured",
        message="Full deploy (rebuild all Docker images) is available.",
        configured=True,
        command=f"{REBUILD_SHELL} {path} --no-cache",
    )


@router.post("/rebuild-all-images", response_model=RebuildResponse)
async def rebuild_all_images(_user: dict = Depends(require_admin_or_super_admin)):
    """
    Full deploy: rebuild app + nginx/tunnel (scripts/full_deploy.sh).
    Production (DEPLOY_REQUEST_DIR set): queues a request for the host dispatcher,
    which appends to logs/full_deploy.log (same file the log stream reads).
    Admin or super_admin only. Long-running; streamed via GET /api/admin/rebuild-all-images/log.
    """
    import threading
    threading.Thread(target=_run_backfill_in_background, daemon=True).start()

    if _deploy_request_dir() is not None:
        job = get_job(_FULL_DEPLOY_JOB)
        if job is None:
            raise HTTPException(status_code=500, detail="full_deploy job not registered")
        log_path = job.log_path()
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text(
                "[queued] Deploy request written; waiting for the host dispatcher "
                "(rankings-bot-deploy.path) to start full_deploy.sh --no-cache...\n"
            )
            _queue_deploy_request("full_deploy", str(_user.get("sub") or ""))
        except OSError as e:
            logger.exception("Could not queue full_deploy deploy request")
            raise HTTPException(
                status_code=500,
                detail=(
                    f"Cannot write deploy request ({e}). Ensure the API user can write "
                    "the logs directory (production: host ./logs mounted at /app/logs)."
                ),
            ) from e
        return RebuildResponse(
            status="started",
            message="Full deploy queued; the host deploy dispatcher runs it. Watch the live log.",
            configured=True,
            command="host: scripts/full_deploy.sh --no-cache (via rankings-bot-deploy.service)",
        )

    path = _get_rebuild_all_script_path()
    if path is None or not path.is_file():
        return RebuildResponse(
            status="not_configured",
            message="Full-deploy script not found. Set REBUILD_ALL_IMAGES_SCRIPT or add scripts/full_deploy.sh.",
            configured=False,
            command=None,
        )
    cmd_display = f"{REBUILD_SHELL} {path} --no-cache"

    def _runner() -> None:
        # Spawn full_deploy.sh and stream its combined output into the live-log file
        # the GET /rebuild-all-images/log endpoint reads. We use subprocess.run (not
        # Popen) here because we want the helper to block until the script exits so
        # the wrapper's "Done in Xs" footer accurately reflects the deploy's elapsed
        # time. The wrapper runs us in a daemon thread, so blocking is fine.
        from api.services.live_log import get_job
        job = get_job(_FULL_DEPLOY_JOB)
        if job is None:
            raise RuntimeError("full_deploy job not registered")
        log_path = job.log_path()
        app_root = Path(__file__).resolve().parent.parent.parent
        env = os.environ.copy()
        logger.info("Spawning full_deploy.sh; output -> %s", log_path)
        with open(log_path, "a", encoding="utf-8") as logf:
            proc = subprocess.run(
                [REBUILD_SHELL, str(path), "--no-cache"],
                cwd=str(app_root),
                stdout=logf,
                stderr=subprocess.STDOUT,
                env=env,
                check=False,
            )
        logger.info("full_deploy.sh exit=%s", proc.returncode)
        if proc.returncode != 0:
            raise RuntimeError(f"full_deploy.sh exited with code {proc.returncode}")

    started = start_background_action(_FULL_DEPLOY_JOB, _runner)
    return RebuildResponse(
        status=started["status"],
        message=str(started["message"]),
        configured=True,
        command=cmd_display,
    )


@router.get("/rebuild-all-images/log")
async def stream_rebuild_all_images_log(
    _user: dict = Depends(require_admin_or_super_admin),
):
    """Stream the live log for the most recent Full deploy run."""
    return stream_log_response(_FULL_DEPLOY_JOB)


@router.post("/start-all", response_model=RebuildResponse)
async def start_all(_user: dict = Depends(require_super_admin)):
    """
    Start all Rankings Bot containers (main stack + nginx + tunnel).
    Super_admin only. Runs scripts/start.sh in background.
    """
    path = _get_start_script_path()
    if path is None or not path.is_file():
        return RebuildResponse(
            status="not_configured",
            message="Start script not found. Set START_ALL_SCRIPT or add scripts/start.sh.",
            configured=False,
            command=None,
        )
    cmd_display = f"{REBUILD_SHELL} {path}"
    try:
        app_root = Path(__file__).resolve().parent.parent.parent
        proc = subprocess.Popen(
            [REBUILD_SHELL, str(path)],
            cwd=str(app_root),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=os.environ.copy(),
        )
        logger.info("Start all started (PID %s), script=%s", proc.pid, path)
    except Exception as e:
        logger.exception("Failed to start start-all script")
        raise HTTPException(status_code=500, detail=f"Failed to start: {e!s}")
    return RebuildResponse(
        status="started",
        message="Start all started in background. Containers may take a minute to be ready.",
        configured=True,
        command=cmd_display,
    )


@router.post("/stop-all", response_model=RebuildResponse)
async def stop_all(_user: dict = Depends(require_super_admin)):
    """
    Stop all Rankings Bot containers (main stack + nginx). Tunnel left running unless STOP_TUNNEL=1.
    Super_admin only. Runs scripts/stop.sh in background.
    """
    path = _get_stop_script_path()
    if path is None or not path.is_file():
        return RebuildResponse(
            status="not_configured",
            message="Stop script not found. Set STOP_ALL_SCRIPT or add scripts/stop.sh.",
            configured=False,
            command=None,
        )
    cmd_display = f"{REBUILD_SHELL} {path}"
    try:
        app_root = Path(__file__).resolve().parent.parent.parent
        proc = subprocess.Popen(
            [REBUILD_SHELL, str(path)],
            cwd=str(app_root),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=os.environ.copy(),
        )
        logger.info("Stop all started (PID %s), script=%s", proc.pid, path)
    except Exception as e:
        logger.exception("Failed to start stop-all script")
        raise HTTPException(status_code=500, detail=f"Failed to start: {e!s}")
    return RebuildResponse(
        status="started",
        message="Stop all started in background.",
        configured=True,
        command=cmd_display,
    )


class RunCommandBody(BaseModel):
    key: str  # allowlisted: start, stop, status


class RunCommandResponse(BaseModel):
    status: str  # ok | error | timeout
    message: str
    output: Optional[str] = None
    exit_code: Optional[int] = None


@router.post("/run-command", response_model=RunCommandResponse)
async def run_command(body: RunCommandBody, _user: dict = Depends(require_super_admin)):
    """
    Run an allowlisted command (start, stop, status) and return output. Super_admin only.
    - start: run start script (may take ~60s)
    - stop: run stop script
    - status: run docker ps (quick)
    """
    key = (body.key or "").strip().lower()
    if key not in ALLOWED_COMMAND_KEYS:
        raise HTTPException(status_code=400, detail=f"Unknown command key. Allowed: {sorted(ALLOWED_COMMAND_KEYS)}")
    app_root = Path(__file__).resolve().parent.parent.parent
    loop = asyncio.get_running_loop()

    def _run() -> tuple[str, int, str]:
        if key == "status":
            # docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
            try:
                result = subprocess.run(
                    ["docker", "ps", "-a", "--format", "table {{.Names}}\t{{.Status}}\t{{.Ports}}"],
                    cwd=str(app_root),
                    capture_output=True,
                    text=True,
                    timeout=15,
                    env=os.environ.copy(),
                )
                out = (result.stdout or "") + (result.stderr or "")
                return out.strip() or "(no output)", result.returncode, "ok"
            except subprocess.TimeoutExpired:
                return "", -1, "timeout"
            except FileNotFoundError:
                return "docker not found (run on host with Docker)", -1, "error"
        if key == "start":
            path = _get_start_script_path()
            if not path or not path.is_file():
                return "Start script not found.", -1, "error"
            try:
                result = subprocess.run(
                    [REBUILD_SHELL, str(path)],
                    cwd=str(app_root),
                    capture_output=True,
                    text=True,
                    timeout=COMMAND_RUN_TIMEOUT_SEC,
                    env=os.environ.copy(),
                )
                out = (result.stdout or "") + (result.stderr or "")
                return out.strip() or "(no output)", result.returncode, "ok"
            except subprocess.TimeoutExpired:
                return "(timed out; containers may still be starting)", -1, "timeout"
        if key == "stop":
            path = _get_stop_script_path()
            if not path or not path.is_file():
                return "Stop script not found.", -1, "error"
            try:
                result = subprocess.run(
                    [REBUILD_SHELL, str(path)],
                    cwd=str(app_root),
                    capture_output=True,
                    text=True,
                    timeout=COMMAND_RUN_TIMEOUT_SEC,
                    env=os.environ.copy(),
                )
                out = (result.stdout or "") + (result.stderr or "")
                return out.strip() or "(no output)", result.returncode, "ok"
            except subprocess.TimeoutExpired:
                return "(timed out)", -1, "timeout"
        return "", 0, "ok"

    try:
        output, exit_code, st = await loop.run_in_executor(None, _run)
    except Exception as e:
        logger.exception("run-command failed: %s", e)
        return RunCommandResponse(status="error", message=str(e), output=None, exit_code=None)
    msg = "Command completed." if st == "ok" else ("Timed out." if st == "timeout" else "Command failed.")
    return RunCommandResponse(status=st, message=msg, output=output, exit_code=exit_code)


@router.get("/rebuild-website/status", response_model=RebuildResponse)
async def rebuild_website_status():
    """Return whether website rebuild script is configured. No auth so UI can show button state."""
    if _deploy_request_dir() is not None:
        return RebuildResponse(
            status="configured",
            message="Update website is available (runs on the Docker host via the deploy dispatcher).",
            configured=True,
            command="host: scripts/rebuild_website_now.sh (via rankings-bot-deploy.service)",
        )
    path = _get_rebuild_script_path()
    if path is None or not path.is_file():
        return RebuildResponse(
            status="not_configured",
            message=_rebuild_not_configured_message(),
            configured=False,
            command=None,
        )
    cmd_display = f"{REBUILD_SHELL} {path}"
    return RebuildResponse(
        status="configured",
        message="Update website (frontend build + restart) is available.",
        configured=True,
        command=cmd_display,
    )


# ---------- Default appearance (avatar/background for users without custom) ----------

class DefaultAppearanceResponse(BaseModel):
    default_avatar_url: str = ""
    default_background_url: str = ""


class DefaultAppearanceUpdate(BaseModel):
    default_avatar_url: Optional[str] = None
    default_background_url: Optional[str] = None


def _read_default_appearance() -> dict:
    path = DEFAULT_APPEARANCE_FILE
    if path.is_file():
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {
                    "default_avatar_url": data.get("default_avatar_url", "") or "",
                    "default_background_url": data.get("default_background_url", "") or "",
                }
        except Exception as e:
            logger.warning("Failed to read default appearance: %s", e)
    return {"default_avatar_url": "", "default_background_url": ""}


def _write_default_appearance(data: dict) -> None:
    path = DEFAULT_APPEARANCE_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


@router.get("/appearance/default", response_model=DefaultAppearanceResponse)
async def get_admin_default_appearance(_user: dict = Depends(require_admin)):
    """Admin: get default avatar/background URLs for users without custom."""
    return DefaultAppearanceResponse(**_read_default_appearance())


@router.patch("/appearance/default", response_model=DefaultAppearanceResponse)
async def update_admin_default_appearance(
    body: DefaultAppearanceUpdate,
    _user: dict = Depends(require_admin),
):
    """Admin: set default avatar/background for users who don't have access to set their own."""
    current = _read_default_appearance()
    if body.default_avatar_url is not None:
        current["default_avatar_url"] = (body.default_avatar_url or "").strip()
    if body.default_background_url is not None:
        current["default_background_url"] = (body.default_background_url or "").strip()
    _write_default_appearance(current)
    try:
        notify_data_changed(Topic.SETTINGS.value, message="Default appearance updated")
    except Exception as e:
        logger.warning("notify_data_changed failed (appearance/default): %s", e)
    return DefaultAppearanceResponse(**current)


# ---------- Tier config (AI Coach price levels; super admin can edit) ----------

from api.config.admin_config import (
    get_effective_tier_config,
    get_role_capabilities,
    get_tier_config as get_tier_config_file,
    save_role_capabilities,
    save_tier_config,
)


@router.get("/tier-config")
async def get_tier_config(_user: dict = Depends(require_admin_or_super_admin)):
    """Return AI Coach tier configuration. Uses file overrides when present."""
    return {"tiers": get_effective_tier_config()}


class TierConfigUpdate(BaseModel):
    tiers: dict


@router.put("/tier-config")
async def put_tier_config(
    body: TierConfigUpdate,
    _user: dict = Depends(require_super_admin),
):
    """Save tier config (prices, limits, features). Super admin only."""
    save_tier_config(body.tiers)
    try:
        notify_data_changed(Topic.SETTINGS.value, message="Tier config updated")
    except Exception as e:
        logger.warning("notify_data_changed failed (tier-config): %s", e)
    return {"tiers": get_effective_tier_config()}


# ---------- Role capabilities (super admin can edit) ----------


@router.get("/role-capabilities")
async def get_role_capabilities_endpoint(_user: dict = Depends(require_admin_or_super_admin)):
    """Return role capability matrix. Uses file overrides when present."""
    return {"capabilities": get_role_capabilities()}


class RoleCapabilitiesUpdate(BaseModel):
    capabilities: list


@router.put("/role-capabilities")
async def put_role_capabilities(
    body: RoleCapabilitiesUpdate,
    _user: dict = Depends(require_super_admin),
):
    """Save role capabilities. Super admin only."""
    save_role_capabilities(body.capabilities)
    try:
        notify_data_changed(Topic.SETTINGS.value, message="Role capabilities updated")
    except Exception as e:
        logger.warning("notify_data_changed failed (role-capabilities): %s", e)
    return {"capabilities": get_role_capabilities()}


@router.get("/logs/tail")
async def get_logs_tail(
    lines: int = Query(default=200, ge=1, le=2000),
    _user: dict = Depends(require_admin),
):
    """Return last N lines of rankings_bot.log. Admin only. Use after Update website to find errors."""
    log_file = Path(os.environ.get("LOG_FILE", "")).resolve() if os.environ.get("LOG_FILE") else PROJECT_ROOT / "rankings_bot.log"
    if not log_file.is_file():
        return {"lines": [], "message": "Log file not found"}
    try:
        with open(log_file, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()
        tail = all_lines[-lines:] if len(all_lines) > lines else all_lines
        return {"lines": [ln.rstrip("\n") for ln in tail]}
    except Exception as e:
        logger.warning("Failed to read log tail: %s", e)
        return {"lines": [], "message": str(e)}


# ---------- Alfa Rating Rollout Management (Admin Only) ----------

from datetime import datetime
from typing import Dict, Any, List

class FeatureFlagUpdateRequest(BaseModel):
    """Request to update a feature flag."""
    flag_name: str
    value: Any  # Boolean or percentage (0-100)
    reason: Optional[str] = None


class FeatureFlagResponse(BaseModel):
    """Response with feature flag status."""
    flag_name: str
    type: str  # "boolean" or "percentage"
    value: Any
    phase: int
    phase_name: str
    message: str


class RolloutStatusResponse(BaseModel):
    """Current rollout status with metrics."""
    current_phase: int
    phase_name: str
    alfa_percentage: int
    predictions_in_api: bool
    anomaly_detection_enabled: bool
    comparisons_shown: bool
    last_updated: str
    metrics: Optional[Dict[str, Any]] = None


class RolloutHistoryItem(BaseModel):
    """Historical rollout event."""
    timestamp: str
    phase: int
    percentage: int
    action: str  # "deploy", "rollback", "update"
    reason: Optional[str] = None
    user: str


@router.get("/rollout/status", response_model=RolloutStatusResponse)
async def get_rollout_status(_user: dict = Depends(require_admin)):
    """
    Get current Alfa rating rollout status.
    
    Returns:
    - Current phase (0-5)
    - Alfa rollout percentage
    - Feature flag states
    - Recent metrics (if available)
    """
    try:
        from models.feature_flag_manager import get_feature_flag_manager
        from models.rollout_manager import create_rollout_manager
        
        ffm = get_feature_flag_manager()
        rm = create_rollout_manager(ffm)
        
        current_phase = ffm.get_current_phase()
        alfa_pct = ffm.get_percentage("alfa_rating_enabled")
        
        return RolloutStatusResponse(
            current_phase=current_phase,
            phase_name=ffm.get_phase_name(current_phase),
            alfa_percentage=alfa_pct,
            predictions_in_api=ffm.is_enabled("alfa_predictions_in_api"),
            anomaly_detection_enabled=ffm.is_enabled("alfa_anomaly_detection_enabled"),
            comparisons_shown=ffm.get_percentage("alfa_vs_fargo_comparison") > 0,
            last_updated=datetime.utcnow().isoformat(),
            metrics=None  # Would query database in production
        )
    except Exception as e:
        logger.error(f"Failed to get rollout status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/rollout/feature-flags/{flag_name}", response_model=FeatureFlagResponse)
async def update_feature_flag(
    flag_name: str,
    request: FeatureFlagUpdateRequest,
    _user: dict = Depends(require_admin)
):
    """
    Update a feature flag at runtime.
    
    Supports:
    - alfa_rating_enabled: Set percentage (0-100) for gradual rollout
    - alfa_predictions_in_api: Enable/disable (true/false)
    - alfa_anomaly_detection_enabled: Enable/disable (true/false)
    - alfa_vs_fargo_comparison: Set percentage (0-100) for UI visibility
    
    Changes are immediately reflected in all services.
    """
    try:
        from models.feature_flag_manager import get_feature_flag_manager
        
        ffm = get_feature_flag_manager()
        flag = ffm.get_flag(flag_name)
        
        if flag is None:
            raise HTTPException(status_code=404, detail=f"Flag not found: {flag_name}")
        
        # Update the flag
        success, message = ffm.update_flag(flag_name, request.value)
        
        if not success:
            raise HTTPException(status_code=400, detail=message)
        
        # Log the change
        logger.info(
            f"Feature flag updated: {flag_name}={request.value} "
            f"by {_user.get('sub')} - Reason: {request.reason or 'none'}"
        )
        
        # Reload to get current state
        ffm.reload()
        current_phase = ffm.get_current_phase()

        try:
            notify_data_changed(Topic.SETTINGS.value, message="Feature flag updated")
        except Exception as e:
            logger.warning("notify_data_changed failed (feature-flag): %s", e)

        return FeatureFlagResponse(
            flag_name=flag_name,
            type=flag.get("type", "unknown"),
            value=request.value,
            phase=current_phase,
            phase_name=ffm.get_phase_name(current_phase),
            message=f"Flag {flag_name} updated successfully to {request.value}"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update feature flag: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rollout/all-flags", response_model=Dict[str, Any])
async def get_all_feature_flags(_user: dict = Depends(require_admin)):
    """
    Get all feature flags and their current values.
    
    Useful for dashboards and monitoring tools.
    """
    try:
        from models.feature_flag_manager import get_feature_flag_manager
        
        ffm = get_feature_flag_manager()
        all_flags = ffm.get_all_flags()
        
        return {
            "current_phase": ffm.get_current_phase(),
            "phase_name": ffm.get_phase_name(ffm.get_current_phase()),
            "flags": all_flags,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get feature flags: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rollout/rollback", response_model=Dict[str, Any])
async def rollback_alfa(
    body: BaseModel,
    _user: dict = Depends(require_admin)
):
    """
    Emergency rollback of Alfa rating system.
    
    Sets:
    - alfa_rating_enabled: 0%
    - alfa_predictions_in_api: false
    - alfa_anomaly_detection_enabled: false
    
    This is a critical operation that should be done with caution.
    Logs the rollback with reason for audit trail.
    """
    try:
        from models.feature_flag_manager import get_feature_flag_manager
        
        ffm = get_feature_flag_manager()
        
        # Disable all Alfa features
        ffm.update_flag("alfa_rating_enabled", 0)
        ffm.update_flag("alfa_predictions_in_api", False)
        ffm.update_flag("alfa_anomaly_detection_enabled", False)
        ffm.update_flag("alfa_vs_fargo_comparison", 0)
        
        logger.critical(
            f"ROLLBACK: Alfa rating system disabled by {_user.get('sub')} "
            f"- Emergency rollback executed"
        )

        try:
            notify_data_changed(
                Topic.SETTINGS.value,
                message="Alfa rollout rolled back to Phase 0",
            )
        except Exception as e:
            logger.warning("notify_data_changed failed (rollout/rollback): %s", e)

        return {
            "status": "rolled_back",
            "message": "Alfa rating system has been rolled back to Phase 0 (disabled)",
            "timestamp": datetime.utcnow().isoformat(),
            "user": _user.get('sub'),
            "alfa_percentage": 0,
            "current_phase": 0
        }
    except Exception as e:
        logger.error(f"Rollback failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rollout/change-log", response_model=List[Dict[str, Any]])
async def get_flag_change_log(
    limit: int = Query(default=50, ge=1, le=500),
    _user: dict = Depends(require_admin)
):
    """
    Get audit trail of feature flag changes.
    
    Shows all updates with timestamp, old/new values, and user info.
    """
    try:
        from models.feature_flag_manager import get_feature_flag_manager
        
        ffm = get_feature_flag_manager()
        changes = ffm.get_change_log(limit=limit)
        
        return changes
    except Exception as e:
        logger.error(f"Failed to get change log: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rollout/validate-phase", response_model=Dict[str, Any])
async def validate_phase(
    body: BaseModel,
    _user: dict = Depends(require_admin)
):
    """
    Validate that prerequisites are met for a specific rollout phase.
    
    Use before advancing to next phase to ensure all requirements are satisfied.
    """
    try:
        target_phase = getattr(body, 'phase', None)
        if target_phase is None:
            raise HTTPException(status_code=400, detail="Missing 'phase' parameter")
        
        from models.feature_flag_manager import get_feature_flag_manager
        
        ffm = get_feature_flag_manager()
        valid, message = ffm.validate_rollout_prerequisites(target_phase)
        
        return {
            "phase": target_phase,
            "valid": valid,
            "message": message,
            "phase_name": ffm.get_phase_name(target_phase),
            "timestamp": datetime.utcnow().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Phase validation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/conflicting-player-names", response_model=Dict[str, Any])
async def get_conflicting_player_names(_user: dict = Depends(require_admin_or_super_admin)):
    """
    Get list of player names that have unresolved data conflicts.
    Used to filter Player link mapping to only show users whose names need linking.
    """
    from api.db import get_db_manager

    db_manager = get_db_manager()
    conn = db_manager.get_connection()
    try:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT DISTINCT player_name
                FROM validation_conflicts
                WHERE resolved = FALSE
                ORDER BY player_name;
            """)
            names = [row[0] for row in cursor.fetchall() if row and row[0]]
        except Exception as e:
            logger.debug("conflicting-player-names: %s", e)
            names = []
        return {"conflictingNames": names}
    finally:
        conn.close()


@router.get("/data-quality-issues", response_model=Dict[str, Any])
async def get_data_quality_issues(_user: dict = Depends(require_super_admin)):
    """
    Get list of data quality issues for super admin investigation.
    
    Returns:
    - Conflicting player data across ranking systems
    - Players with missing critical data
    """
    from api.db import get_db_manager
    
    db_manager = get_db_manager()
    conn = db_manager.get_connection()
    
    try:
        cursor = conn.cursor()
        
        # Get unresolved conflicts
        cursor.execute("""
            SELECT 
                id,
                player_name,
                conflict_type,
                system1,
                value1,
                system2,
                value2,
                detected_at,
                resolution_notes
            FROM validation_conflicts
            WHERE resolved = FALSE
            ORDER BY detected_at DESC;
        """)
        
        conflicts = []
        for row in cursor.fetchall():
            conflicts.append({
                'id': row[0],
                'playerName': row[1],
                'conflictType': row[2],
                'system1': row[3],
                'value1': row[4],
                'system2': row[5],
                'value2': row[6],
                'detectedAt': row[7].isoformat() if row[7] else None,
                'notes': row[8]
            })
        
        # Get players with missing data in latest snapshots
        cursor.execute("""
            SELECT 
                name as player_name,
                ranking_system,
                CASE 
                    WHEN license_number IS NULL THEN 'license'
                    WHEN fargo_rating IS NULL THEN 'fargo'
                    WHEN country IS NULL THEN 'country'
                END as missing_field
            FROM mv_latest_rankings
            WHERE license_number IS NULL 
               OR fargo_rating IS NULL 
               OR country IS NULL
            ORDER BY name, ranking_system;
        """)
        
        missing_data_raw = cursor.fetchall()
        
        # Group missing data by player
        missing_data_grouped = {}
        for row in missing_data_raw:
            player_name = row[0]
            ranking_system = row[1]
            missing_field = row[2]
            
            if player_name not in missing_data_grouped:
                missing_data_grouped[player_name] = {
                    'playerName': player_name,
                    'systems': {}
                }
            
            if ranking_system not in missing_data_grouped[player_name]['systems']:
                missing_data_grouped[player_name]['systems'][ranking_system] = []
            
            missing_data_grouped[player_name]['systems'][ranking_system].append(missing_field)
        
        missing_data = list(missing_data_grouped.values())
        
        # Get summary stats
        cursor.execute("""
            SELECT 
                COUNT(DISTINCT player_name) as total_players_with_issues,
                COUNT(*) FILTER (WHERE conflict_type = 'COUNTRY') as country_conflicts,
                COUNT(*) FILTER (WHERE conflict_type = 'LICENSE') as license_conflicts,
                COUNT(*) FILTER (WHERE conflict_type = 'FARGO') as fargo_conflicts
            FROM validation_conflicts
            WHERE resolved = FALSE;
        """)
        
        stats_row = cursor.fetchone()
        stats = {
            'totalConflicts': len(conflicts),
            'totalPlayersWithMissingData': len(missing_data),
            'countryConflicts': stats_row[1] if stats_row else 0,
            'licenseConflicts': stats_row[2] if stats_row else 0,
            'fargoConflicts': stats_row[3] if stats_row else 0
        }
        
        return {
            'conflicts': conflicts,
            'missingData': missing_data,
            'stats': stats
        }
        
    except Exception as e:
        logger.error(f"Failed to get data quality issues: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.post("/data-quality-issues/{conflict_id}/resolve", response_model=Dict[str, str])
async def resolve_data_quality_conflict(
    conflict_id: int,
    resolution_notes: str = "",
    _user: dict = Depends(require_super_admin)
):
    """
    Mark a data quality conflict as resolved.
    
    Super admin only.
    """
    from api.db import get_db_manager
    
    db_manager = get_db_manager()
    conn = db_manager.get_connection()
    
    try:
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE validation_conflicts
            SET resolved = TRUE,
                resolution_notes = %s
            WHERE id = %s;
        """, (resolution_notes, conflict_id))
        
        conn.commit()
        try:
            # Conflict id is operator-internal but trim down to a generic event.
            notify_data_changed(
                Topic.SETTINGS.value,
                message="Data quality conflict resolved",
            )
        except Exception as e:
            logger.warning("notify_data_changed failed (resolve conflict): %s", e)

        return {
            'status': 'success',
            'message': f'Conflict {conflict_id} marked as resolved'
        }
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to resolve conflict {conflict_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.post("/data-quality/fix-missing-fargo", response_model=Dict[str, Any])
async def fix_missing_fargo_data(_user: dict = Depends(require_super_admin)):
    """Removed: Fargo scraping repair — use CSV import."""
    raise HTTPException(
        status_code=410,
        detail="Fargo scraping is disabled. Use the CSV import feature for Fargo-aligned ratings.",
    )


@router.post("/identity-locks/enforce-wpa", response_model=Dict[str, Any])
async def enforce_wpa_identity_locks(_user: dict = Depends(require_admin_or_super_admin)):
    """
    Re-apply WPA authoritative lockdowns for immutable identity fields.
    Safe to run repeatedly.
    """
    try:
        db = get_database_manager()
        license_stats = db.enforce_wpa_license_lockdown()
        country_stats = db.enforce_wpa_country_lockdown()
        try:
            notify_data_changed(
                Topic.PLAYERS.value,
                message="WPA identity locks enforced",
            )
        except Exception as e:
            logger.warning("notify_data_changed failed (enforce-wpa): %s", e)
        return {
            "status": "success",
            "license": license_stats,
            "country": country_stats,
        }
    except Exception as e:
        logger.error("Failed to enforce WPA identity locks: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/identity-locks/unlock", response_model=Dict[str, Any])
async def unlock_identity_locks(
    body: IdentityLockRequest,
    _user: dict = Depends(require_admin_or_super_admin),
):
    """
    Unlock immutable identity fields for one player.
    lock_type: license | country | both
    """
    try:
        db = get_database_manager()
        result = db.unlock_identity_locks(
            player_name=body.player_name,
            lock_type=body.lock_type,
        )
        try:
            # No PII (player_name) on the public SSE channel.
            notify_data_changed(
                Topic.PLAYERS.value,
                message="Identity lock unlocked",
            )
        except Exception as e:
            logger.warning("notify_data_changed failed (unlock): %s", e)
        return {"status": "success", "result": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Failed to unlock identity lock for %s: %s", body.player_name, e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/identity-locks/relock", response_model=Dict[str, Any])
async def relock_identity_locks(
    body: IdentityLockRequest,
    _user: dict = Depends(require_admin_or_super_admin),
):
    """
    Relock immutable identity fields for one player.
    If license/country is not provided, values are derived from latest WPA snapshots.
    lock_type: license | country | both
    """
    try:
        db = get_database_manager()
        result = db.relock_identity_fields(
            player_name=body.player_name,
            lock_type=body.lock_type,
            license_number=body.license_number,
            country=body.country,
            source_system=body.source_system or "ADMIN_MANUAL",
        )
        try:
            # No PII (player_name) on the public SSE channel.
            notify_data_changed(
                Topic.PLAYERS.value,
                message="Identity lock relocked",
            )
        except Exception as e:
            logger.warning("notify_data_changed failed (relock): %s", e)
        return {"status": "success", "result": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Failed to relock identity lock for %s: %s", body.player_name, e)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# AI Monitor — Ollama activity log
# ============================================================================

_TRUST_ZONE_WEBSITE = "('public_web', 'app_authenticated')"
# metadata is JSON text; COALESCE avoids NULL cast issues.
_SQL_TRUST_WEBSITE = (
    f"(COALESCE(metadata, '{{}}')::jsonb->>'trust_zone') IN {_TRUST_ZONE_WEBSITE}"
)
_SQL_TRUST_INTERNAL = (
    "((COALESCE(metadata, '{}')::jsonb->>'trust_zone') IS NULL OR "
    f"(COALESCE(metadata, '{{}}')::jsonb->>'trust_zone') NOT IN {_TRUST_ZONE_WEBSITE})"
)


def _ai_monitor_website_only_enabled() -> bool:
    return os.getenv("AI_MONITOR_WEBSITE_ONLY", "true").lower() in ("true", "1", "yes")


def _ai_monitor_where_clause(
    *,
    feature: Optional[str],
    status: Optional[str],
    scope: str,
) -> tuple[str, Dict[str, Any]]:
    """scope: 'website' | 'internal' | 'all'"""
    conditions: list[str] = []
    params: Dict[str, Any] = {}

    if scope == "website" and _ai_monitor_website_only_enabled():
        conditions.append(_SQL_TRUST_WEBSITE)
    elif scope == "internal":
        conditions.append(_SQL_TRUST_INTERNAL)

    if feature:
        conditions.append("feature = :feature")
        params["feature"] = feature
    if status:
        conditions.append("status = :status")
        params["status"] = status

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    return where, params


@router.get("/ai-monitor")
async def get_ai_monitor(
    limit: int = Query(50, ge=1, le=500),
    feature: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    _user=Depends(require_admin_or_super_admin),
):
    """
    Fetch Ollama activity for the website / end-user AI Monitor (public_web + app_authenticated).
    When AI_MONITOR_WEBSITE_ONLY is true (default), excludes internal/batch LLM rows.
    """
    from database import get_engine
    from sqlalchemy import text as sa_text

    engine = get_engine()
    where, params = _ai_monitor_where_clause(
        feature=feature, status=status, scope="website"
    )
    params = {**params, "limit": limit}

    try:
        with engine.connect() as conn:
            rows = conn.execute(
                sa_text(f"""
                    SELECT id, created_at, feature, model, prompt_summary,
                           request_text, response_text, duration_seconds,
                           eval_tokens, prompt_tokens, status, error_message
                    FROM ollama_activity_log
                    {where}
                    ORDER BY created_at DESC
                    LIMIT :limit
                """),
                params,
            ).mappings().all()

            count_params = {k: v for k, v in params.items() if k != "limit"}
            total = conn.execute(
                sa_text(f"SELECT COUNT(*) FROM ollama_activity_log {where}"),
                count_params,
            ).scalar()

            feature_counts = conn.execute(
                sa_text(f"""
                    SELECT feature, COUNT(*) as count,
                           AVG(duration_seconds) as avg_duration,
                           SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as errors
                    FROM ollama_activity_log
                    {where}
                    GROUP BY feature ORDER BY count DESC
                """),
                count_params,
            ).mappings().all()

        return {
            "entries": [dict(r) for r in rows],
            "total": total,
            "limit": limit,
            "feature_summary": [dict(r) for r in feature_counts],
            "website_only_filter": _ai_monitor_website_only_enabled(),
        }
    except Exception as e:
        logger.warning("AI Monitor query failed: %s", e)
        return {
            "entries": [],
            "total": 0,
            "limit": limit,
            "feature_summary": [],
            "website_only_filter": _ai_monitor_website_only_enabled(),
            "error": str(e)[:200],
        }


@router.get("/ai-monitor/internal")
async def get_ai_monitor_internal(
    limit: int = Query(50, ge=1, le=500),
    feature: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    _user=Depends(require_super_admin),
):
    """
    Internal / batch / untagged LLM activity (complement of website trust zones).
    Super admin only — may contain operational prompts.
    """
    from database import get_engine
    from sqlalchemy import text as sa_text

    engine = get_engine()
    where, params = _ai_monitor_where_clause(
        feature=feature, status=status, scope="internal"
    )
    params = {**params, "limit": limit}

    try:
        with engine.connect() as conn:
            rows = conn.execute(
                sa_text(f"""
                    SELECT id, created_at, feature, model, prompt_summary,
                           request_text, response_text, duration_seconds,
                           eval_tokens, prompt_tokens, status, error_message
                    FROM ollama_activity_log
                    {where}
                    ORDER BY created_at DESC
                    LIMIT :limit
                """),
                params,
            ).mappings().all()

            count_params = {k: v for k, v in params.items() if k != "limit"}
            total = conn.execute(
                sa_text(f"SELECT COUNT(*) FROM ollama_activity_log {where}"),
                count_params,
            ).scalar()

            feature_counts = conn.execute(
                sa_text(f"""
                    SELECT feature, COUNT(*) as count,
                           AVG(duration_seconds) as avg_duration,
                           SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as errors
                    FROM ollama_activity_log
                    {where}
                    GROUP BY feature ORDER BY count DESC
                """),
                count_params,
            ).mappings().all()

        return {
            "entries": [dict(r) for r in rows],
            "total": total,
            "limit": limit,
            "feature_summary": [dict(r) for r in feature_counts],
        }
    except Exception as e:
        logger.warning("AI Monitor internal query failed: %s", e)
        return {
            "entries": [],
            "total": 0,
            "limit": limit,
            "feature_summary": [],
            "error": str(e)[:200],
        }


