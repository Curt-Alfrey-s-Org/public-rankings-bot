"""
Background task tracking for long-running operations like Fargo sync.
Stores current task status in memory so UI can poll for updates.
"""

import logging
from typing import Optional
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """Task execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class BackgroundTask:
    """Represents a single background task."""
    
    def __init__(self, task_id: str, task_name: str):
        self.task_id = task_id
        self.task_name = task_name
        self.status = TaskStatus.PENDING
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.message = "Pending..."
        self.error: Optional[str] = None
        self.result: Optional[dict] = None
    
    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            "task_id": self.task_id,
            "task_name": self.task_name,
            "status": self.status.value,
            "message": self.message,
            "error": self.error,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "result": self.result,
        }


class BackgroundTaskManager:
    """Simple in-memory task manager."""
    
    def __init__(self):
        self._tasks: dict[str, BackgroundTask] = {}
        self._current_task: Optional[BackgroundTask] = None
    
    def start_task(self, task_id: str, task_name: str) -> BackgroundTask:
        """Mark task as started."""
        task = BackgroundTask(task_id, task_name)
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.utcnow()
        task.message = f"Running {task_name}..."
        self._tasks[task_id] = task
        self._current_task = task
        logger.info(f"Task started: {task_id} - {task_name}")
        return task
    
    def complete_task(self, task_id: str, message: str = "Completed", result: Optional[dict] = None):
        """Mark task as completed."""
        task = self._tasks.get(task_id)
        if task:
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.utcnow()
            task.message = message
            task.result = result
            if self._current_task and self._current_task.task_id == task_id:
                self._current_task = None
            logger.info(f"Task completed: {task_id}")
    
    def fail_task(self, task_id: str, error: str):
        """Mark task as failed."""
        task = self._tasks.get(task_id)
        if task:
            task.status = TaskStatus.FAILED
            task.completed_at = datetime.utcnow()
            task.error = error
            task.message = f"Failed: {error}"
            if self._current_task and self._current_task.task_id == task_id:
                self._current_task = None
            logger.error(f"Task failed: {task_id} - {error}")
    
    def get_task(self, task_id: str) -> Optional[BackgroundTask]:
        """Get task by ID."""
        return self._tasks.get(task_id)
    
    def get_current_task(self) -> Optional[BackgroundTask]:
        """Get currently running task."""
        # If current task is completed/failed, clear it
        if self._current_task and self._current_task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
            self._current_task = None
        return self._current_task
    
    def get_all_tasks(self, limit: int = 50) -> list[BackgroundTask]:
        """Get all tasks (reverse chronological, most recent first)."""
        tasks = sorted(self._tasks.values(), key=lambda t: t.started_at or datetime.utcnow(), reverse=True)
        return tasks[:limit]
    
    def get_tasks_by_status(self, status: TaskStatus) -> list[BackgroundTask]:
        """Get all tasks with a specific status."""
        return [t for t in self._tasks.values() if t.status == status]
    
    def clear_old_tasks(self, max_age_hours: int = 24) -> int:
        """Remove tasks older than max_age_hours. Returns count removed."""
        from datetime import timedelta, datetime
        cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)
        to_delete = [
            task_id for task_id, task in self._tasks.items()
            if task.completed_at and task.completed_at < cutoff
        ]
        for task_id in to_delete:
            del self._tasks[task_id]
        return len(to_delete)


# Global task manager instance
_task_manager = BackgroundTaskManager()


def get_task_manager() -> BackgroundTaskManager:
    """Get the global task manager."""
    return _task_manager
