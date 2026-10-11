"""
Backup Management Routes
Allows admins to list, create, and restore database backups
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
from pathlib import Path
import subprocess
import logging
import os
from datetime import datetime

from api.auth import require_admin
from api.services.live_log import (
    get_job,
    register_job,
    start_background_action,
    stream_log_response,
)
from api.services.live_topics import Topic
from api.services.live_updates import notify_data_changed
from project_root import PROJECT_ROOT

router = APIRouter(prefix="/api/backups", tags=["backups"])
logger = logging.getLogger(__name__)
register_job("system_backup", "Create system backup")
BACKUP_DIR = PROJECT_ROOT / "backups"
BACKUP_SCRIPT = PROJECT_ROOT / "scripts" / "backup_postgres.sh"
RESTORE_SCRIPT = PROJECT_ROOT / "scripts" / "restore_from_backup.sh"


class BackupInfo(BaseModel):
    filename: str
    size_mb: float
    created: str
    age_days: int


class BackupListResponse(BaseModel):
    total: int
    backups: List[BackupInfo]


class RestoreRequest(BaseModel):
    backup_filename: str
    confirm: bool = False


def get_backup_files() -> List[BackupInfo]:
    """Get list of available backup files with metadata."""
    if not BACKUP_DIR.exists():
        return []
    
    backups = []
    now = datetime.now()
    
    for backup_file in sorted(BACKUP_DIR.glob("rankings_*.dump"), reverse=True):
        stat = backup_file.stat()
        created = datetime.fromtimestamp(stat.st_mtime)
        age = (now - created).days
        
        backups.append(BackupInfo(
            filename=backup_file.name,
            size_mb=round(stat.st_size / (1024 * 1024), 2),
            created=created.strftime("%Y-%m-%d %H:%M:%S"),
            age_days=age
        ))
    
    return backups


@router.get("/list", response_model=BackupListResponse)
async def list_backups(_admin: dict = Depends(require_admin)):
    """List all available database backups (Admin only)."""
    try:
        backups = get_backup_files()
        return BackupListResponse(total=len(backups), backups=backups)
    except Exception as e:
        logger.error(f"Error listing backups: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/create")
async def create_backup(_admin: dict = Depends(require_admin)):
    """Create a new database backup (Admin only).

    Spawns the backup script via the shared live-log infrastructure so the operator
    can watch progress at GET /api/backups/create/log. The script's stdout+stderr
    are appended to ``logs/system_backup.log``; any non-zero exit code is raised
    and surfaces as a ``[CRASH]`` line in the live log followed by ``Done in Xs
    (with errors)``.
    """
    if not BACKUP_SCRIPT.exists():
        raise HTTPException(status_code=500, detail="Backup script not found")

    def _runner() -> None:
        job = get_job("system_backup")
        if job is None:
            raise RuntimeError("system_backup job not registered")
        log_path = job.log_path()
        logger.info("Spawning %s; output -> %s", BACKUP_SCRIPT, log_path)
        with open(log_path, "a", encoding="utf-8") as logf:
            proc = subprocess.run(
                [str(BACKUP_SCRIPT)],
                cwd=str(PROJECT_ROOT),
                stdout=logf,
                stderr=subprocess.STDOUT,
                timeout=300,
                check=False,
            )
        logger.info("Backup script exit=%s", proc.returncode)
        if proc.returncode != 0:
            raise RuntimeError(f"Backup script exited with code {proc.returncode}")
        try:
            notify_data_changed(
                Topic.BACKUPS.value,
                message="System backup created",
            )
        except Exception as e:
            logger.warning("notify_data_changed failed (system backup): %s", e)

    return start_background_action("system_backup", _runner)


@router.get("/create/log")
async def stream_create_backup_log(_admin: dict = Depends(require_admin)):
    """Stream the live log for the most recent Create system backup run."""
    return stream_log_response("system_backup")


@router.post("/restore")
async def restore_backup(
    request: RestoreRequest,
    _admin: dict = Depends(require_admin)
):
    """
    Restore database from backup (Admin only).
    ⚠️ WARNING: This will terminate all connections and restore the database.
    Requires confirm=true to proceed.
    """
    if not request.confirm:
        raise HTTPException(
            status_code=400,
            detail="Restore not confirmed. Set 'confirm: true' to proceed."
        )
    
    backup_path = BACKUP_DIR / request.backup_filename
    if not backup_path.exists():
        raise HTTPException(status_code=404, detail="Backup file not found")
    
    if not RESTORE_SCRIPT.exists():
        raise HTTPException(status_code=500, detail="Restore script not found")
    
    try:
        # Run restore script (this will drop/recreate database)
        # Automated restore requires shell access; return manual instructions
        return {
            "message": "Restore initiated",
            "warning": "Database restore requires manual confirmation",
            "instructions": [
                "SSH into the server",
                f"Run: cd {PROJECT_ROOT}",
                f"Run: ./scripts/restore_from_backup.sh backups/{request.backup_filename}",
                "Type 'YES' to confirm",
                "Restart API: sudo systemctl restart rankings-bot-api"
            ],
            "backup_file": str(backup_path)
        }
    except Exception as e:
        logger.error(f"Restore error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/download/{filename}")
async def download_backup(
    filename: str,
    _admin: dict = Depends(require_admin)
):
    """Download a backup file (Admin only)."""
    backup_path = BACKUP_DIR / filename
    
    # Security: prevent path traversal
    if not backup_path.resolve().parent == BACKUP_DIR.resolve():
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    if not backup_path.exists():
        raise HTTPException(status_code=404, detail="Backup not found")
    
    return FileResponse(
        path=str(backup_path),
        filename=filename,
        media_type="application/octet-stream"
    )


@router.delete("/delete/{filename}")
async def delete_backup(
    filename: str,
    _admin: dict = Depends(require_admin)
):
    """Delete a backup file (Admin only)."""
    backup_path = BACKUP_DIR / filename
    
    # Security: prevent path traversal
    if not backup_path.resolve().parent == BACKUP_DIR.resolve():
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    if not backup_path.exists():
        raise HTTPException(status_code=404, detail="Backup not found")
    
    try:
        backup_path.unlink()
        logger.info(f"Deleted backup: {filename}")
        try:
            # No filename on the public SSE channel.
            notify_data_changed(
                Topic.BACKUPS.value,
                message="Backup deleted",
            )
        except Exception as e:
            logger.warning("notify_data_changed failed (delete backup): %s", e)
        return {"message": f"Backup {filename} deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting backup: {e}")
        raise HTTPException(status_code=500, detail=str(e))
