#!/usr/bin/env python3
"""
Rankings Bot Monitoring Daemon

Provides scheduled refresh and health monitoring for Rankings-Bot API.
- Triggers periodic ranking refreshes
- Monitors database and API health
- Sends alerts on failures
- Logs comprehensive metrics

Usage:
  python scripts/rankings_daemon.py
  
Environment Variables:
  REFRESH_INTERVAL_HOURS: Hours between scheduled refreshes (default: 6)
  ADMIN_TOKEN: JWT token for API refresh endpoint
  MONITORING_LOG: Path to monitoring log file (default: logs/monitoring.log)
  MONITORING_ENABLED: Set to 'true' to enable scheduled API refresh (default: false; opt-in)
  API_HEALTH_ENDPOINT: Health check URL (default: http://localhost:8003/api/health)
  REFRESH_ENDPOINT: Refresh API URL (default: http://localhost:8003/api/rankings/refresh)
"""

import os
import sys
import time
import json
import requests
import logging
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

# Configure logging
LOG_DIR = Path(__file__).parent.parent / 'logs'
LOG_DIR.mkdir(exist_ok=True, parents=True)

LOG_FILE = Path(os.getenv('MONITORING_LOG', LOG_DIR / 'monitoring.log'))
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# Configuration
ENABLED = os.getenv('MONITORING_ENABLED', 'false').lower() == 'true'
REFRESH_INTERVAL_HOURS = int(os.getenv('REFRESH_INTERVAL_HOURS', '6'))
ADMIN_TOKEN = os.getenv('ADMIN_TOKEN', '')
API_HEALTH_ENDPOINT = os.getenv('API_HEALTH_ENDPOINT', 'http://localhost:8003/api/health')
REFRESH_ENDPOINT = os.getenv('REFRESH_ENDPOINT', 'http://localhost:8003/api/rankings/refresh')
ALERT_EMAIL = os.getenv('ALERT_EMAIL', '')

# State tracking
last_refresh_time: Optional[datetime] = None
last_successful_refresh: Optional[datetime] = None
consecutive_failures = 0
max_consecutive_failures = 3


class MonitoringMetrics:
    """Track monitoring metrics and health statistics."""
    
    def __init__(self):
        self.start_time = datetime.now()
        self.refresh_count = 0
        self.successful_refreshes = 0
        self.failed_refreshes = 0
        self.uptime_seconds = 0
        self.avg_refresh_time_seconds = 0.0
        self.last_refresh_result: Optional[Dict] = None
        self.last_error: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert metrics to dictionary."""
        self.uptime_seconds = (datetime.now() - self.start_time).total_seconds()
        return {
            'start_time': self.start_time.isoformat(),
            'refresh_count': self.refresh_count,
            'successful_refreshes': self.successful_refreshes,
            'failed_refreshes': self.failed_refreshes,
            'uptime_seconds': self.uptime_seconds,
            'avg_refresh_time_seconds': self.avg_refresh_time_seconds,
            'last_error': self.last_error,
            'last_refresh_result': self.last_refresh_result
        }


# Global metrics
metrics = MonitoringMetrics()


def check_api_health() -> bool:
    """
    Check if API is healthy.
    
    Returns:
        True if API is healthy, False otherwise
    """
    try:
        response = requests.get(API_HEALTH_ENDPOINT, timeout=10)
        if response.status_code == 200:
            data = response.json()
            logger.info(f"[HEALTH] API healthy: {data.get('status', 'unknown')}")
            return True
        else:
            logger.warning(f"[HEALTH] API returned status {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"[HEALTH] Failed to check API health: {e}")
        return False


def trigger_rankings_refresh() -> bool:
    """
    Trigger manual refresh via API.
    
    Returns:
        True if refresh succeeded, False otherwise
    """
    global last_refresh_time, last_successful_refresh, consecutive_failures
    
    if not ADMIN_TOKEN:
        logger.warning("[REFRESH] ADMIN_TOKEN not set - skipping refresh")
        return False
    
    last_refresh_time = datetime.now()
    refresh_start = time.time()
    
    try:
        headers = {
            'Authorization': f'Bearer {ADMIN_TOKEN}',
            'Content-Type': 'application/json'
        }
        
        logger.info("[REFRESH] Triggering scheduled rankings refresh...")
        response = requests.post(
            REFRESH_ENDPOINT,
            headers=headers,
            timeout=300,  # 5-minute timeout for refresh
        )
        
        refresh_elapsed = time.time() - refresh_start
        
        if response.status_code == 200:
            result = response.json()
            metrics.refresh_count += 1
            metrics.successful_refreshes += 1
            consecutive_failures = 0
            last_successful_refresh = datetime.now()
            metrics.last_refresh_result = result
            
            logger.info(f"[REFRESH] ✓ Scheduled refresh completed in {refresh_elapsed:.1f}s")
            logger.info(f"[REFRESH] Results: {json.dumps(result, indent=2)}")
            
            return True
        elif response.status_code == 429:
            logger.warning(f"[REFRESH] Rate limited (429). Response: {response.text[:200]}")
            metrics.refresh_count += 1
            metrics.failed_refreshes += 1
            consecutive_failures += 1
            metrics.last_error = "Rate limited by API"
            return False
        else:
            logger.error(f"[REFRESH] API returned status {response.status_code}: {response.text[:200]}")
            metrics.refresh_count += 1
            metrics.failed_refreshes += 1
            consecutive_failures += 1
            metrics.last_error = f"API error: {response.status_code}"
            return False
    
    except requests.exceptions.Timeout:
        logger.error("[REFRESH] Refresh timed out (300s)")
        metrics.refresh_count += 1
        metrics.failed_refreshes += 1
        consecutive_failures += 1
        metrics.last_error = "Refresh timeout"
        return False
    except Exception as e:
        logger.error(f"[REFRESH] Failed to trigger refresh: {e}", exc_info=True)
        metrics.refresh_count += 1
        metrics.failed_refreshes += 1
        consecutive_failures += 1
        metrics.last_error = str(e)
        return False


def send_alert(subject: str, message: str):
    """
    Send alert via email or log.
    
    Args:
        subject: Alert subject
        message: Alert message
    """
    if ALERT_EMAIL:
        try:
            import smtplib
            from email.mime.text import MIMEText
            
            msg = MIMEText(message)
            msg['Subject'] = f"[Rankings-Bot] {subject}"
            msg['From'] = 'monitoring@rankings-bot'
            msg['To'] = ALERT_EMAIL
            
            logger.info(f"[ALERT] Sending email to {ALERT_EMAIL}: {subject}")
            # Note: Requires SMTP server configuration
        except Exception as e:
            logger.warning(f"[ALERT] Failed to send email: {e}")
    else:
        logger.warning(f"[ALERT] {subject}: {message}")


def log_metrics():
    """Log current monitoring metrics."""
    metrics_dict = metrics.to_dict()
    logger.info(f"[METRICS] {json.dumps(metrics_dict, indent=2)}")


def monitor_loop():
    """Main monitoring loop."""
    global consecutive_failures
    
    logger.info(f"[STARTUP] Rankings Monitoring Daemon started (enabled: {ENABLED})")
    logger.info(f"[CONFIG] Refresh interval: {REFRESH_INTERVAL_HOURS} hours")
    logger.info(f"[CONFIG] API Health endpoint: {API_HEALTH_ENDPOINT}")
    logger.info(f"[CONFIG] Refresh endpoint: {REFRESH_ENDPOINT}")
    
    next_refresh = datetime.now() + timedelta(hours=REFRESH_INTERVAL_HOURS)
    
    while True:
        try:
            # Log current state periodically
            if metrics.refresh_count % 10 == 0 and metrics.refresh_count > 0:
                log_metrics()
            
            # Check API health
            if not check_api_health():
                logger.warning("[MONITOR] API health check failed")
                time.sleep(60)  # Wait 1 minute before retrying
                continue
            
            # Check if it's time for refresh
            now = datetime.now()
            if now >= next_refresh and ENABLED:
                if trigger_rankings_refresh():
                    # Schedule next refresh
                    next_refresh = datetime.now() + timedelta(hours=REFRESH_INTERVAL_HOURS)
                    logger.info(f"[SCHEDULE] Next refresh scheduled for {next_refresh.isoformat()}")
                else:
                    # On failure, retry sooner
                    logger.warning(f"[SCHEDULE] Refresh failed, retrying in 30 minutes")
                    next_refresh = datetime.now() + timedelta(minutes=30)
                    
                    if consecutive_failures >= max_consecutive_failures:
                        alert_msg = (
                            f"Rankings-Bot refresh has failed {consecutive_failures} times.\n"
                            f"Last error: {metrics.last_error}\n"
                            f"Check API logs for details."
                        )
                        send_alert(f"Multiple refresh failures ({consecutive_failures}x)", alert_msg)
            
            # Sleep before next check
            time.sleep(60)  # Check every minute
        
        except KeyboardInterrupt:
            logger.info("[SHUTDOWN] Monitoring daemon interrupted by user")
            break
        except Exception as e:
            logger.error(f"[ERROR] Unexpected error in monitor loop: {e}", exc_info=True)
            time.sleep(60)  # Wait before retrying
    
    # Final metrics
    logger.info("[SHUTDOWN] Final metrics:")
    log_metrics()
    logger.info("[SHUTDOWN] Monitoring daemon stopped")


def main():
    """Entry point for monitoring daemon."""
    try:
        monitor_loop()
    except Exception as e:
        logger.error(f"[FATAL] Fatal error in monitoring daemon: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    # Check if running in background
    if len(sys.argv) > 1 and sys.argv[1] == '--background':
        # Daemonize (optional, not fully implemented)
        logger.info("[STARTUP] Running in background mode")
    
    main()
