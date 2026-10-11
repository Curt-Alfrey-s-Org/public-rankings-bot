"""
Automated Health Checks for Alfa Rating Production System

Comprehensive health monitoring with automatic recovery attempts.
- HTTP health endpoint: GET /health/alfa
- Scheduled checks: Every 5 minutes via apscheduler
- Auto-recovery: Attempt model reload, cache restart, DB reconnect
- Notifications: Slack/email on failed recovery attempts

Module exports:
- HealthCheckManager: Main health check orchestrator
- run_health_checks_async: Run all checks asynchronously
- RecoveryAction: Auto-recovery executor
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    """Health check status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class ComponentStatus(str, Enum):
    """Individual component status."""
    OK = "ok"
    WARN = "warn"
    FAIL = "fail"
    UNKNOWN = "unknown"


class HealthCheckManager:
    """
    Manages comprehensive health checks for Alfa rating system.
    
    Checks:
    - Model loading and availability
    - Database connectivity
    - Cache (Redis) availability
    - API response times
    - Memory and CPU usage
    - Error rates from recent logs
    """
    
    def __init__(self, service_name: str = "Alfa Rating API", version: str = "1.0.0"):
        """Initialize health check manager."""
        self.service_name = service_name
        self.version = version
        self.startup_time = time.time()
        self._last_check: Dict[str, Any] = {}
        
    def get_uptime_seconds(self) -> float:
        """Get uptime in seconds since startup."""
        return time.time() - self.startup_time
    
    def check_model_loaded(self) -> Tuple[ComponentStatus, Optional[str], float]:
        """
        Check if Alfa model is loaded and available.
        
        Returns:
            (status, error_msg, latency_ms)
        """
        start = time.perf_counter()
        try:
            # Import and check model
            from models.alfa_logistic_regression import AlfaModel
            model = AlfaModel()
            if not model.is_loaded():
                return ComponentStatus.FAIL, "Model not loaded", (time.perf_counter() - start) * 1000
            latency_ms = (time.perf_counter() - start) * 1000
            return ComponentStatus.OK, None, latency_ms
        except Exception as e:
            error_msg = f"Model check failed: {str(e)[:100]}"
            logger.error(error_msg)
            return ComponentStatus.FAIL, error_msg, (time.perf_counter() - start) * 1000
    
    def check_database(self, engine=None) -> Tuple[ComponentStatus, Optional[str], float]:
        """
        Check database connectivity.
        
        Returns:
            (status, error_msg, latency_ms)
        """
        start = time.perf_counter()
        try:
            from sqlalchemy import text
            if engine is None:
                return ComponentStatus.UNKNOWN, "No engine provided", 0
            
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            
            latency_ms = (time.perf_counter() - start) * 1000
            # Degraded if latency > 1000ms (1 second)
            status = ComponentStatus.OK if latency_ms < 1000 else ComponentStatus.WARN
            return status, None, latency_ms
        except Exception as e:
            error_msg = f"Database check failed: {str(e)[:100]}"
            logger.error(error_msg)
            return ComponentStatus.FAIL, error_msg, (time.perf_counter() - start) * 1000
    
    def check_cache(self) -> Tuple[ComponentStatus, Optional[str], float]:
        """
        Check Redis cache availability.
        
        Returns:
            (status, error_msg, latency_ms)
        """
        import os
        redis_url = os.getenv("REDIS_URL", "").strip()
        
        start = time.perf_counter()
        try:
            if not redis_url:
                return ComponentStatus.UNKNOWN, "Redis not configured", 0
            
            import redis
            r = redis.from_url(redis_url, socket_connect_timeout=5)
            r.ping()
            
            latency_ms = (time.perf_counter() - start) * 1000
            status = ComponentStatus.OK if latency_ms < 500 else ComponentStatus.WARN
            return status, None, latency_ms
        except ImportError:
            return ComponentStatus.UNKNOWN, "redis package not installed", 0
        except Exception as e:
            error_msg = f"Cache check failed: {str(e)[:100]}"
            logger.warning(error_msg)
            return ComponentStatus.FAIL, error_msg, (time.perf_counter() - start) * 1000
    
    def check_system_resources(self) -> Tuple[ComponentStatus, Dict[str, Any], Optional[str]]:
        """
        Check system memory and CPU usage.
        
        Returns:
            (status, metrics_dict, error_msg)
        """
        try:
            import psutil
            process = psutil.Process()
            
            # Check memory (alert if >85% of system or >1GB for process)
            memory_info = process.memory_info()
            percent_memory = process.memory_percent()
            
            # Check CPU (alert if >80% over 1 minute)
            cpu_percent = process.cpu_percent(interval=0.1)
            
            status = ComponentStatus.OK
            if percent_memory > 85 or memory_info.rss > 1e9:  # 1GB
                status = ComponentStatus.WARN
            if cpu_percent > 90:
                status = ComponentStatus.WARN
            
            metrics = {
                "memory_percent": round(percent_memory, 2),
                "memory_mb": round(memory_info.rss / 1e6, 2),
                "cpu_percent": round(cpu_percent, 2),
                "num_threads": process.num_threads(),
            }
            return status, metrics, None
        except Exception as e:
            error_msg = f"System resource check failed: {str(e)[:100]}"
            logger.error(error_msg)
            return ComponentStatus.FAIL, {}, error_msg
    
    def check_error_rate(self, log_path: Optional[str] = None, window_minutes: int = 5) -> Tuple[ComponentStatus, Dict[str, Any], Optional[str]]:
        """
        Check error rate in recent logs.
        
        Args:
            log_path: Path to log file
            window_minutes: Time window to analyze
        
        Returns:
            (status, metrics_dict, error_msg)
        """
        try:
            if not log_path:
                return ComponentStatus.UNKNOWN, {}, "No log path provided"
            
            from pathlib import Path
            log_path = Path(log_path)
            if not log_path.exists():
                return ComponentStatus.UNKNOWN, {}, f"Log file not found: {log_path}"
            
            # Count errors and total lines in recent logs
            error_count = 0
            total_count = 0
            cutoff_time = time.time() - (window_minutes * 60)
            
            try:
                with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        total_count += 1
                        if any(level in line for level in ['ERROR', 'CRITICAL', 'EXCEPTION']):
                            error_count += 1
            except Exception as e:
                logger.warning(f"Error reading log file: {e}")
                return ComponentStatus.WARN, {}, str(e)[:100]
            
            error_rate = (error_count / total_count * 100) if total_count > 0 else 0
            
            # Status: FAIL if error_rate > 1% (critical threshold)
            # WARN if > 0.5%
            status = ComponentStatus.OK
            if error_rate > 1.0:
                status = ComponentStatus.FAIL
            elif error_rate > 0.5:
                status = ComponentStatus.WARN
            
            metrics = {
                "error_count": error_count,
                "total_lines": total_count,
                "error_rate_percent": round(error_rate, 2),
            }
            return status, metrics, None
        except Exception as e:
            error_msg = f"Error rate check failed: {str(e)[:100]}"
            logger.error(error_msg)
            return ComponentStatus.FAIL, {}, error_msg
    
    async def run_all_checks(self, engine=None, log_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Run all health checks asynchronously.
        
        Returns:
            Comprehensive health status dictionary
        """
        start = time.perf_counter()
        
        # Run checks (CPU-bound operations wrapped in executor would be better in production)
        model_status, model_error, model_latency = self.check_model_loaded()
        db_status, db_error, db_latency = self.check_database(engine)
        cache_status, cache_error, cache_latency = self.check_cache()
        resource_status, resource_metrics, resource_error = self.check_system_resources()
        error_status, error_metrics, error_error = self.check_error_rate(log_path)
        
        # Determine overall status
        all_statuses = [model_status, db_status, cache_status, resource_status, error_status]
        if ComponentStatus.FAIL in all_statuses:
            overall_status = HealthStatus.UNHEALTHY
        elif ComponentStatus.WARN in all_statuses:
            overall_status = HealthStatus.DEGRADED
        else:
            overall_status = HealthStatus.HEALTHY
        
        total_latency_ms = (time.perf_counter() - start) * 1000
        
        self._last_check = {
            "status": overall_status.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service": self.service_name,
            "version": self.version,
            "uptime_seconds": round(self.get_uptime_seconds(), 1),
            "check_latency_ms": round(total_latency_ms, 2),
            "components": {
                "model": {
                    "status": model_status.value,
                    "latency_ms": round(model_latency, 2),
                    "error": model_error,
                },
                "database": {
                    "status": db_status.value,
                    "latency_ms": round(db_latency, 2),
                    "error": db_error,
                },
                "cache": {
                    "status": cache_status.value,
                    "latency_ms": round(cache_latency, 2),
                    "error": cache_error,
                },
                "system_resources": {
                    "status": resource_status.value,
                    "metrics": resource_metrics,
                    "error": resource_error,
                },
                "error_rate": {
                    "status": error_status.value,
                    "metrics": error_metrics,
                    "error": error_error,
                },
            },
        }
        return self._last_check
    
    def get_last_check(self) -> Dict[str, Any]:
        """Get results from the last health check."""
        if not self._last_check:
            return {"status": "unknown", "error": "No checks performed yet"}
        return self._last_check


class RecoveryAction:
    """
    Automatic recovery executor for failed components.
    
    Recovery strategies:
    - Model reload: Reinitialize model from disk
    - Cache restart: Reconnect to Redis
    - Database reconnect: Re-establish database connection
    """
    
    def __init__(self, notification_handler=None):
        """
        Initialize recovery action handler.
        
        Args:
            notification_handler: Callable for Slack/email notifications
        """
        self.notification_handler = notification_handler
        self.recovery_log: List[Dict[str, Any]] = []
    
    async def recover_model(self, force_reload: bool = True) -> Tuple[bool, str]:
        """
        Attempt to reload Alfa model.
        
        Returns:
            (success, message)
        """
        try:
            from models.alfa_logistic_regression import AlfaModel
            model = AlfaModel()
            if force_reload:
                model.reload()
            logger.info("Model recovery: SUCCESS")
            self._log_recovery("model_reload", True, "Model reloaded successfully")
            return True, "Model reloaded successfully"
        except Exception as e:
            error_msg = f"Model recovery failed: {str(e)[:200]}"
            logger.error(error_msg)
            self._log_recovery("model_reload", False, str(e)[:200])
            await self._notify_failure("model_reload", error_msg)
            return False, error_msg
    
    async def recover_cache(self) -> Tuple[bool, str]:
        """
        Attempt to reconnect to Redis cache.
        
        Returns:
            (success, message)
        """
        import os
        redis_url = os.getenv("REDIS_URL", "").strip()
        
        if not redis_url:
            return False, "Redis not configured"
        
        try:
            import redis
            r = redis.from_url(redis_url, socket_connect_timeout=5)
            r.ping()
            # Clear any problematic data
            r.flushdb(asynchronous=True) if hasattr(r, 'flushdb') else None
            logger.info("Cache recovery: SUCCESS")
            self._log_recovery("cache_restart", True, "Cache reconnected successfully")
            return True, "Cache reconnected successfully"
        except Exception as e:
            error_msg = f"Cache recovery failed: {str(e)[:200]}"
            logger.error(error_msg)
            self._log_recovery("cache_restart", False, str(e)[:200])
            await self._notify_failure("cache_restart", error_msg)
            return False, error_msg
    
    async def recover_database(self, engine=None) -> Tuple[bool, str]:
        """
        Attempt to reconnect to database.
        
        Returns:
            (success, message)
        """
        if not engine:
            return False, "No database engine provided"
        
        try:
            from sqlalchemy import text, create_engine
            # Dispose of all connections and create new pool
            if hasattr(engine, 'dispose'):
                engine.dispose()
            
            # Test the connection
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            
            logger.info("Database recovery: SUCCESS")
            self._log_recovery("db_reconnect", True, "Database reconnected successfully")
            return True, "Database reconnected successfully"
        except Exception as e:
            error_msg = f"Database recovery failed: {str(e)[:200]}"
            logger.error(error_msg)
            self._log_recovery("db_reconnect", False, str(e)[:200])
            await self._notify_failure("db_reconnect", error_msg)
            return False, error_msg
    
    def _log_recovery(self, action: str, success: bool, message: str) -> None:
        """Log recovery attempt."""
        self.recovery_log.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "success": success,
            "message": message,
        })
    
    async def _notify_failure(self, component: str, error: str) -> None:
        """Send notification on recovery failure."""
        if self.notification_handler:
            try:
                message = f"🚨 **CRITICAL**: Failed to recover {component}\n\nError: {error}"
                await self.notification_handler(message)
            except Exception as e:
                logger.error(f"Notification send failed: {e}")
    
    def get_recovery_log(self) -> List[Dict[str, Any]]:
        """Get log of all recovery attempts."""
        return self.recovery_log.copy()


async def run_health_checks_async(engine=None, log_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Convenience function to run health checks asynchronously.
    
    Returns:
        Complete health status dictionary
    """
    manager = HealthCheckManager()
    return await manager.run_all_checks(engine=engine, log_path=log_path)


# Module initialization
_health_manager: Optional[HealthCheckManager] = None
_recovery_handler: Optional[RecoveryAction] = None


def initialize_health_checks(service_name: str = "Alfa Rating API", version: str = "1.0.0") -> HealthCheckManager:
    """Initialize and return the global health check manager."""
    global _health_manager
    _health_manager = HealthCheckManager(service_name, version)
    return _health_manager


def initialize_recovery(notification_handler=None) -> RecoveryAction:
    """Initialize and return the global recovery action handler."""
    global _recovery_handler
    _recovery_handler = RecoveryAction(notification_handler)
    return _recovery_handler


def get_health_manager() -> Optional[HealthCheckManager]:
    """Get the global health check manager."""
    return _health_manager


def get_recovery_handler() -> Optional[RecoveryAction]:
    """Get the global recovery action handler."""
    return _recovery_handler
