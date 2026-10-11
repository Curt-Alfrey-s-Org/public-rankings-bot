"""
Shared live-log infrastructure for long-running admin actions.

Pattern (mirrors the existing rebuild-website + scraper-run UX):

  1. Caller registers a job with `register_job(job_id, display_name)`. Jobs are keyed by a
     stable string and own a per-job log file path + a `threading.Lock` so two POSTs
     can't kick off the same job concurrently.
  2. The POST handler calls `start_background_action(job_id, runner)`. This truncates the
     log file, writes a header, spawns a daemon `threading.Thread` that holds the lock
     for the duration of `runner()`, and returns 200 immediately with `{"status": "started"}`.
  3. While `runner()` runs, every `logger.info / logger.warning` from the loggers listed
     in `LOG_HANDLER_TARGETS` lands in the per-job log file (a `logging.FileHandler` is
     attached for the duration via `attach_log_handler` — this is the standard "transient
     handler" pattern from the Python Logging Cookbook).
  4. The matching GET handler returns a `StreamingResponse` from `stream_log_file(...)`
     which tails the file, yields chunks as they arrive, and stops on either the
     "Done in" footer (written by `start_background_action`) or a hard timeout.

Doc refs:
  - Python logging: https://docs.python.org/3/howto/logging-cookbook.html
  - FastAPI streaming: https://fastapi.tiangolo.com/advanced/custom-response/#streamingresponse
  - nginx X-Accel-Buffering header (response-level buffering disable): https://nginx.org/en/docs/http/ngx_http_proxy_module.html
"""

from __future__ import annotations

import asyncio
import logging
import os
import threading
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator, Callable, Dict, Iterator, Optional

from fastapi.responses import StreamingResponse

from project_root import PROJECT_ROOT

logger = logging.getLogger(__name__)


# Loggers whose output is piped into the per-job log file while a background runner is
# active. Keep this set small and predictable so we don't accidentally capture unrelated
# request traffic. Add to this list with `register_log_target(name)` if a new module
# needs to emit into job logs.
LOG_HANDLER_TARGETS: list[str] = [
    "scrapers",
    "api.routes",
    "api.services",
    "database",
]


_LOG_FORMATTER = logging.Formatter(
    "[%(asctime)s] %(levelname)s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

# Marker the streaming endpoint watches for to signal "complete". Same string the
# rebuild-website + scraper-run helpers already write — keeps the front-end status
# detection (`content.includes('Done in')`) consistent across every job type.
_DONE_MARKER = "Done in"


class LiveLogJob:
    """
    Registration record for one long-running admin action.

    Args:
        job_id: stable url-safe identifier (e.g. "rebuild_website", "scraper_wpba",
                "load_wpba_pdf"). Used as the log filename suffix and for the URL.
        display_name: human-readable name written into the log header.
        log_file_template_env: optional environment variable name whose value is a
                Python format string with a `{job_id}` placeholder, used to override
                the default log path (production: `${PROJECT_ROOT}/logs/<job_id>.log`).
    """

    def __init__(
        self,
        job_id: str,
        display_name: str,
        log_file_template_env: str = "LIVE_LOG_FILE_TEMPLATE",
    ) -> None:
        self.job_id = job_id
        self.display_name = display_name
        self._log_file_template_env = log_file_template_env
        self.lock = threading.Lock()

    def log_path(self) -> Path:
        template = os.getenv(self._log_file_template_env, "").strip()
        if template:
            try:
                return Path(template.format(job_id=self.job_id))
            except (KeyError, IndexError):
                logger.warning(
                    "Invalid %s=%r; falling back to default path",
                    self._log_file_template_env,
                    template,
                )
        return PROJECT_ROOT / "logs" / f"{self.job_id}.log"


_REGISTRY: Dict[str, LiveLogJob] = {}
_REGISTRY_LOCK = threading.Lock()


def register_job(job_id: str, display_name: str) -> LiveLogJob:
    """Register a new long-running job. Idempotent — re-registering returns the same instance."""
    with _REGISTRY_LOCK:
        existing = _REGISTRY.get(job_id)
        if existing is not None:
            return existing
        job = LiveLogJob(job_id=job_id, display_name=display_name)
        _REGISTRY[job_id] = job
        return job


def get_job(job_id: str) -> Optional[LiveLogJob]:
    """Return the job for `job_id`, or None if it isn't registered."""
    return _REGISTRY.get(job_id)


def list_jobs() -> list[str]:
    return sorted(_REGISTRY.keys())


def register_log_target(logger_name: str) -> None:
    """Add a logger to the set whose output is captured into per-job log files."""
    if logger_name not in LOG_HANDLER_TARGETS:
        LOG_HANDLER_TARGETS.append(logger_name)


@contextmanager
def attach_log_handler(file_path: Path) -> Iterator[logging.FileHandler]:
    """
    Attach a `FileHandler(file_path)` to LOG_HANDLER_TARGETS for the duration of the
    context. Removes + closes the handler on exit so we don't leak file descriptors
    or duplicate output across runs (per Python Logging Cookbook's "transient handler"
    guidance).

    Each target logger is bumped to INFO if its effective level was higher (NOTSET or
    WARNING), so that `logger.info(...)` lines actually reach the handler regardless of
    the global root level.
    """
    file_path.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(str(file_path), mode="a", encoding="utf-8")
    handler.setLevel(logging.INFO)
    handler.setFormatter(_LOG_FORMATTER)
    targets = [logging.getLogger(name) for name in LOG_HANDLER_TARGETS]
    saved_levels: list[Optional[int]] = []
    for lg in targets:
        saved_levels.append(lg.level if lg.level != logging.NOTSET else None)
        if lg.level == logging.NOTSET or lg.level > logging.INFO:
            lg.setLevel(logging.INFO)
        lg.addHandler(handler)
    try:
        yield handler
    finally:
        try:
            handler.flush()
            handler.close()
        finally:
            for lg, original in zip(targets, saved_levels):
                lg.removeHandler(handler)
                if original is not None:
                    lg.setLevel(original)


def append_log_line(file_path: Path, line: str) -> None:
    """Append a single line to a job log file. Failures are logged, never raised."""
    try:
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(line if line.endswith("\n") else line + "\n")
    except OSError as e:
        logger.warning("Failed to append to live log %s: %s", file_path, e)


def _truncate_log(file_path: Path) -> None:
    """Truncate (or create) the per-job log file. Raises OSError on permission problems."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text("")


def _write_header(file_path: Path, display_name: str) -> None:
    append_log_line(file_path, "==========================================")
    append_log_line(file_path, f"  Rankings Bot — {display_name}")
    append_log_line(file_path, f"  Started at {datetime.utcnow().isoformat()}Z")
    append_log_line(file_path, "==========================================")


def start_background_action(
    job_id: str,
    runner: Callable[[], None],
    *,
    on_already_running: str = "in_progress",
) -> Dict[str, object]:
    """
    Truncate the job log, spawn a daemon thread that runs `runner()` while a
    `FileHandler` is attached, and return immediately. `runner` should raise on
    errors — the wrapper writes a `[CRASH]` line and the `Done in Xs` footer either
    way so the streaming UI always reaches a terminal state.

    Return shape (matches existing rebuild-website + scraper-run responses):
      - `status`: "started" | "already_running"
      - `job`:    job_id
      - `log_file`: stringified path
      - `message`: short human-readable summary
    """
    job = _REGISTRY.get(job_id)
    if job is None:
        raise ValueError(f"Unknown live-log job: {job_id!r}. Call register_job(...) first.")

    log_path = job.log_path()

    if job.lock.locked():
        return {
            "status": "already_running",
            "job": job_id,
            "log_file": str(log_path),
            "message": f"{job.display_name} is already running. Watch the live log.",
            "in_progress_marker": on_already_running,
        }

    try:
        _truncate_log(log_path)
    except OSError as exc:
        logger.exception("Could not truncate live log at %s", log_path)
        raise

    _write_header(log_path, job.display_name)

    def _bg() -> None:
        if not job.lock.acquire(blocking=False):
            append_log_line(log_path, f"[Skipped] {job.display_name} is already running in another worker.")
            return
        started = time.time()
        try:
            with attach_log_handler(log_path):
                try:
                    runner()
                    elapsed = int(time.time() - started)
                    append_log_line(
                        log_path,
                        f"\n[{datetime.utcnow().strftime('%H:%M:%S')}] {_DONE_MARKER} {elapsed}s.",
                    )
                except Exception as exc:  # noqa: BLE001 - capture any runner failure into the log
                    logger.exception("live-log job %s crashed: %s", job_id, exc)
                    elapsed = int(time.time() - started)
                    append_log_line(log_path, f"\n[CRASH] {exc!s}")
                    append_log_line(
                        log_path,
                        f"\n[{datetime.utcnow().strftime('%H:%M:%S')}] {_DONE_MARKER} {elapsed}s (with errors).",
                    )
        finally:
            job.lock.release()

    threading.Thread(
        target=_bg,
        name=f"live-log-{job_id}",
        daemon=True,
    ).start()
    logger.info("live-log job %s started in background; log=%s", job_id, log_path)

    return {
        "status": "started",
        "job": job_id,
        "log_file": str(log_path),
        "message": f"{job.display_name} started. Watch the live log for progress.",
    }


def _max_wait_seconds() -> int:
    raw = os.getenv("LIVE_LOG_STREAM_MAX_SEC", "1200").strip()
    try:
        n = int(raw, 10)
    except ValueError:
        logger.warning("Invalid LIVE_LOG_STREAM_MAX_SEC=%r; using 1200", raw)
        n = 1200
    return max(60, n)


async def _stream_log(job_id: str) -> AsyncGenerator[bytes, None]:
    job = _REGISTRY.get(job_id)
    if job is None:
        yield f"[Unknown job: {job_id}]\n".encode("utf-8")
        return

    log_path = job.log_path()
    yield f"[Connected - streaming {log_path.name} from {log_path.parent}/]\n".encode("utf-8")

    last_size = 0
    empty_file_notice_sent = False
    file_missing_ticks = 0
    max_wait_sec = _max_wait_seconds()
    loop = asyncio.get_running_loop()
    deadline = loop.time() + max_wait_sec

    while loop.time() < deadline:
        try:
            if log_path.is_file():
                with open(log_path, "rb") as f:
                    f.seek(last_size)
                    chunk = f.read()
                    if chunk:
                        last_size = f.tell()
                        yield chunk
                        if _DONE_MARKER.encode() in chunk:
                            return
                    elif (
                        last_size == 0
                        and log_path.stat().st_size == 0
                        and not empty_file_notice_sent
                    ):
                        yield b"[Log file is empty - waiting for output...]\n"
                        empty_file_notice_sent = True
            else:
                file_missing_ticks += 1
                if file_missing_ticks == 1:
                    yield (
                        f"[Waiting for log file at {log_path}... if this repeats, click "
                        "the action button first or check API write access to logs/ "
                        "(production: ./logs is bind-mounted to /app/logs).]\n"
                    ).encode("utf-8")
                elif file_missing_ticks % 40 == 0:
                    yield b"[Still waiting for log file...]\n"
        except (OSError, IOError) as e:
            logger.warning("Error reading live log %s: %s", log_path, e)
            yield f"\n[Log read error: {e!s}]\n".encode("utf-8", errors="replace")
            return
        await asyncio.sleep(0.5)

    yield (
        f"\n[Stream stopped after {max_wait_sec}s timeout - job may still be running on the server; "
        f"check {log_path}.]\n"
    ).encode("utf-8")


def stream_log_response(job_id: str) -> StreamingResponse:
    """
    Build a `StreamingResponse` for a registered job. Same headers we use for the
    rebuild-website stream so nginx flushes each chunk to the browser without buffering.

    Per nginx docs, `X-Accel-Buffering: no` disables proxy buffering for this single
    response (defense in depth — `proxy_buffering off` is also set in nginx.conf for
    `/api/`).
    """
    return StreamingResponse(
        _stream_log(job_id),
        media_type="text/plain; charset=utf-8",
        headers={
            "Cache-Control": "no-store",
            "X-Accel-Buffering": "no",
        },
    )
