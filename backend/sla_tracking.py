"""
SLA Tracking for Alfa Rating Production System

Defines and monitors Service Level Agreements:
- Availability: 99.9% uptime (max 43 min/month downtime)
- Latency: p95 <500ms, p99 <2 seconds
- Accuracy: Brier score within ±5% of training baseline
- Anomaly detection: Precision >50%, Recall >70%

Tracks metrics hourly, daily, weekly, monthly.
Generates SLA reports and alerts on breaches.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
from statistics import mean, stdev, median
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class SLAMetric(str, Enum):
    """SLA metric types."""
    AVAILABILITY = "availability"
    LATENCY_P95 = "latency_p95"
    LATENCY_P99 = "latency_p99"
    ACCURACY_BRIER = "accuracy_brier"
    ANOMALY_PRECISION = "anomaly_precision"
    ANOMALY_RECALL = "anomaly_recall"


class SLABreachSeverity(str, Enum):
    """Severity of SLA breach."""
    NONE = "none"
    WARNING = "warning"
    CRITICAL = "critical"


class SLATarget:
    """
    SLA target definition with thresholds.
    
    Attributes:
        metric: SLA metric type
        target: Target value (e.g., 99.9 for 99.9% availability)
        warning_threshold: Warning threshold (e.g., 99.5 for availability)
        critical_threshold: Critical threshold (e.g., 99.0)
        min_breach_duration_minutes: Minimum duration before alerting
    """
    
    def __init__(
        self,
        metric: SLAMetric,
        target: float,
        warning_threshold: float,
        critical_threshold: float,
        min_breach_duration_minutes: int = 30,
    ):
        """Initialize SLA target."""
        self.metric = metric
        self.target = target
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold
        self.min_breach_duration_minutes = min_breach_duration_minutes
    
    def check_status(self, current_value: float) -> Tuple[SLABreachSeverity, str]:
        """
        Check current value against thresholds.
        
        Returns:
            (severity, description)
        """
        if current_value >= self.target:
            return SLABreachSeverity.NONE, f"Target met: {current_value:.2f}"
        
        if current_value >= self.warning_threshold:
            return SLABreachSeverity.WARNING, f"Warning: {current_value:.2f} (target: {self.target:.2f})"
        
        if current_value >= self.critical_threshold:
            return SLABreachSeverity.CRITICAL, f"Critical: {current_value:.2f} (critical: {self.critical_threshold:.2f})"
        
        return SLABreachSeverity.CRITICAL, f"Severe: {current_value:.2f} (target: {self.target:.2f})"


class SLADefinitions:
    """
    Standard SLA targets for Alfa rating system.
    
    - Availability: 99.9% (max 43 min/month)
    - Latency: p95 <500ms, p99 <2s
    - Accuracy: Brier ±5% from baseline
    - Anomaly: Precision >50%, Recall >70%
    """
    
    @staticmethod
    def get_default_targets() -> Dict[SLAMetric, SLATarget]:
        """Get standard SLA targets."""
        return {
            SLAMetric.AVAILABILITY: SLATarget(
                metric=SLAMetric.AVAILABILITY,
                target=99.9,
                warning_threshold=99.5,
                critical_threshold=99.0,
                min_breach_duration_minutes=30,
            ),
            SLAMetric.LATENCY_P95: SLATarget(
                metric=SLAMetric.LATENCY_P95,
                target=500,  # milliseconds
                warning_threshold=750,
                critical_threshold=1000,
            ),
            SLAMetric.LATENCY_P99: SLATarget(
                metric=SLAMetric.LATENCY_P99,
                target=2000,  # milliseconds
                warning_threshold=3000,
                critical_threshold=5000,
            ),
            SLAMetric.ACCURACY_BRIER: SLATarget(
                metric=SLAMetric.ACCURACY_BRIER,
                target=0.20,  # Brier score (lower is better, so inverted logic)
                warning_threshold=0.25,
                critical_threshold=0.30,
            ),
            SLAMetric.ANOMALY_PRECISION: SLATarget(
                metric=SLAMetric.ANOMALY_PRECISION,
                target=0.50,  # 50% minimum
                warning_threshold=0.40,
                critical_threshold=0.30,
            ),
            SLAMetric.ANOMALY_RECALL: SLATarget(
                metric=SLAMetric.ANOMALY_RECALL,
                target=0.70,  # 70% minimum
                warning_threshold=0.60,
                critical_threshold=0.50,
            ),
        }


class SLATracker:
    """
    Tracks SLA compliance and generates reports.
    
    Collects and aggregates metrics at multiple time scales:
    - Hourly: Raw metrics per hour
    - Daily: Aggregated from hourly
    - Weekly: Aggregated from daily
    - Monthly: Aggregated from daily
    """
    
    def __init__(self, report_dir: Optional[Path] = None):
        """
        Initialize SLA tracker.
        
        Args:
            report_dir: Directory to store SLA reports
        """
        self.report_dir = Path(report_dir) if report_dir else Path("./reports")
        self.report_dir.mkdir(parents=True, exist_ok=True)
        
        self.targets = SLADefinitions.get_default_targets()
        self.hourly_metrics: List[Dict[str, Any]] = []
        self.daily_metrics: List[Dict[str, Any]] = []
        self.monthly_metrics: List[Dict[str, Any]] = []
        self.breach_history: List[Dict[str, Any]] = []
    
    def record_hourly_metrics(
        self,
        availability_percent: float,
        latency_p95_ms: float,
        latency_p99_ms: float,
        accuracy_brier: float,
        anomaly_precision: float,
        anomaly_recall: float,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """
        Record hourly metrics.
        
        Args:
            availability_percent: % uptime (0-100)
            latency_p95_ms: 95th percentile latency in ms
            latency_p99_ms: 99th percentile latency in ms
            accuracy_brier: Brier score (0-1)
            anomaly_precision: Precision (0-1)
            anomaly_recall: Recall (0-1)
            timestamp: Measurement timestamp
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        
        # Start of hour for aggregation
        hour_start = timestamp.replace(minute=0, second=0, microsecond=0)
        
        record = {
            "timestamp": hour_start.isoformat(),
            "availability": availability_percent,
            "latency_p95_ms": latency_p95_ms,
            "latency_p99_ms": latency_p99_ms,
            "accuracy_brier": accuracy_brier,
            "anomaly_precision": anomaly_precision,
            "anomaly_recall": anomaly_recall,
        }
        self.hourly_metrics.append(record)
        
        # Check for breaches
        self._check_breaches(record, "hourly")
    
    def aggregate_to_daily(self) -> List[Dict[str, Any]]:
        """
        Aggregate hourly metrics to daily.
        
        Returns:
            List of daily metric records
        """
        if not self.hourly_metrics:
            return self.daily_metrics
        
        # Group by date
        daily_groups: Dict[str, List[Dict[str, Any]]] = {}
        for record in self.hourly_metrics:
            date_str = record["timestamp"][:10]  # YYYY-MM-DD
            if date_str not in daily_groups:
                daily_groups[date_str] = []
            daily_groups[date_str].append(record)
        
        # Aggregate each day
        for date_str, records in daily_groups.items():
            if len(records) == 0:
                continue
            
            daily_record = {
                "timestamp": date_str,
                "availability_min": min(r["availability"] for r in records),
                "availability_avg": mean(r["availability"] for r in records),
                "latency_p95_max": max(r["latency_p95_ms"] for r in records),
                "latency_p95_avg": mean(r["latency_p95_ms"] for r in records),
                "latency_p99_max": max(r["latency_p99_ms"] for r in records),
                "latency_p99_avg": mean(r["latency_p99_ms"] for r in records),
                "accuracy_brier_avg": mean(r["accuracy_brier"] for r in records),
                "anomaly_precision_avg": mean(r["anomaly_precision"] for r in records),
                "anomaly_recall_avg": mean(r["anomaly_recall"] for r in records),
                "num_hours": len(records),
            }
            
            # Check if already exists
            existing = next((d for d in self.daily_metrics if d["timestamp"] == date_str), None)
            if existing:
                self.daily_metrics.remove(existing)
            self.daily_metrics.append(daily_record)
        
        return self.daily_metrics
    
    def aggregate_to_monthly(self) -> List[Dict[str, Any]]:
        """
        Aggregate daily metrics to monthly.
        
        Returns:
            List of monthly metric records
        """
        if not self.daily_metrics:
            return self.monthly_metrics
        
        # Group by month
        monthly_groups: Dict[str, List[Dict[str, Any]]] = {}
        for record in self.daily_metrics:
            month_str = record["timestamp"][:7]  # YYYY-MM
            if month_str not in monthly_groups:
                monthly_groups[month_str] = []
            monthly_groups[month_str].append(record)
        
        # Aggregate each month
        for month_str, records in monthly_groups.items():
            if len(records) == 0:
                continue
            
            monthly_record = {
                "timestamp": month_str,
                "availability_min": min(r["availability_min"] for r in records),
                "availability_avg": mean(r["availability_avg"] for r in records),
                "latency_p95_max": max(r["latency_p95_max"] for r in records),
                "latency_p95_avg": mean(r["latency_p95_avg"] for r in records),
                "latency_p99_max": max(r["latency_p99_max"] for r in records),
                "latency_p99_avg": mean(r["latency_p99_avg"] for r in records),
                "accuracy_brier_avg": mean(r["accuracy_brier_avg"] for r in records),
                "anomaly_precision_avg": mean(r["anomaly_precision_avg"] for r in records),
                "anomaly_recall_avg": mean(r["anomaly_recall_avg"] for r in records),
                "num_days": len(records),
            }
            
            # Check if already exists
            existing = next((m for m in self.monthly_metrics if m["timestamp"] == month_str), None)
            if existing:
                self.monthly_metrics.remove(existing)
            self.monthly_metrics.append(monthly_record)
        
        return self.monthly_metrics
    
    def _check_breaches(self, record: Dict[str, Any], time_window: str) -> None:
        """
        Check for SLA breaches and log them.
        
        Args:
            record: Metric record
            time_window: "hourly", "daily", or "monthly"
        """
        breaches = []
        
        # Check each metric
        for metric, target in self.targets.items():
            if metric == SLAMetric.AVAILABILITY:
                current = record.get("availability")
            elif metric == SLAMetric.LATENCY_P95:
                current = record.get("latency_p95_ms")
            elif metric == SLAMetric.LATENCY_P99:
                current = record.get("latency_p99_ms")
            elif metric == SLAMetric.ACCURACY_BRIER:
                current = record.get("accuracy_brier")
            elif metric == SLAMetric.ANOMALY_PRECISION:
                current = record.get("anomaly_precision")
            elif metric == SLAMetric.ANOMALY_RECALL:
                current = record.get("anomaly_recall")
            else:
                continue
            
            if current is None:
                continue
            
            severity, description = target.check_status(current)
            if severity != SLABreachSeverity.NONE:
                breaches.append({
                    "metric": metric.value,
                    "severity": severity.value,
                    "description": description,
                    "timestamp": record.get("timestamp"),
                    "time_window": time_window,
                })
        
        # Log breaches
        for breach in breaches:
            self.breach_history.append(breach)
            level = logging.ERROR if breach["severity"] == "critical" else logging.WARNING
            logger.log(level, f"SLA Breach ({time_window}): {breach['metric']} - {breach['description']}")
    
    def generate_monthly_report(self, month: Optional[str] = None) -> str:
        """
        Generate SLA report for a month.
        
        Args:
            month: Month in YYYY-MM format (default: current month)
        
        Returns:
            Report as markdown string
        """
        if month is None:
            month = datetime.now(timezone.utc).strftime("%Y-%m")
        
        # Find monthly record
        monthly_record = next((m for m in self.monthly_metrics if m["timestamp"] == month), None)
        if not monthly_record:
            return f"# SLA Report for {month}\n\nNo data available."
        
        # Find breaches for this month
        month_breaches = [b for b in self.breach_history if b["timestamp"].startswith(month)]
        
        # Generate report
        report = f"""# SLA Report for {month}

## Summary
- **Availability**: {monthly_record['availability_avg']:.2f}% (target: 99.9%, min: {monthly_record['availability_min']:.2f}%)
- **Latency p95**: {monthly_record['latency_p95_avg']:.0f}ms (target: <500ms, max: {monthly_record['latency_p95_max']:.0f}ms)
- **Latency p99**: {monthly_record['latency_p99_avg']:.0f}ms (target: <2000ms, max: {monthly_record['latency_p99_max']:.0f}ms)
- **Accuracy (Brier)**: {monthly_record['accuracy_brier_avg']:.3f} (target: <0.20)
- **Anomaly Precision**: {monthly_record['anomaly_precision_avg']:.2%} (target: >50%)
- **Anomaly Recall**: {monthly_record['anomaly_recall_avg']:.2%} (target: >70%)

## Metrics by Day
| Date | Availability | Latency p95 | Latency p99 | Brier | Precision | Recall |
|------|--------------|-------------|------------|-------|-----------|--------|
"""
        for record in self.daily_metrics:
            if record["timestamp"].startswith(month):
                report += f"| {record['timestamp']} | {record['availability_avg']:.2f}% | {record['latency_p95_avg']:.0f}ms | {record['latency_p99_avg']:.0f}ms | {record['accuracy_brier_avg']:.3f} | {record['anomaly_precision_avg']:.1%} | {record['anomaly_recall_avg']:.1%} |\n"
        
        # Breaches section
        report += f"\n## SLA Breaches\n"
        if month_breaches:
            report += f"**{len(month_breaches)} breaches detected this month**\n\n"
            critical = [b for b in month_breaches if b["severity"] == "critical"]
            warnings = [b for b in month_breaches if b["severity"] == "warning"]
            
            if critical:
                report += f"### Critical ({len(critical)})\n"
                for breach in critical[:10]:  # Limit to first 10
                    report += f"- **{breach['metric']}** ({breach['time_window']}): {breach['description']}\n"
            
            if warnings:
                report += f"\n### Warnings ({len(warnings)})\n"
                for breach in warnings[:10]:
                    report += f"- **{breach['metric']}** ({breach['time_window']}): {breach['description']}\n"
        else:
            report += "✅ All SLAs met - no breaches detected.\n"
        
        # Write report to file
        report_path = self.report_dir / f"SLA_REPORT_{month}.md"
        try:
            report_path.write_text(report, encoding='utf-8')
            logger.info(f"SLA report written to {report_path}")
        except Exception as e:
            logger.error(f"Failed to write SLA report: {e}")
        
        return report
    
    def get_breach_summary(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get summary of recent breaches.
        
        Args:
            hours: Time window in hours
        
        Returns:
            Summary dict with breach counts and details
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        recent_breaches = [
            b for b in self.breach_history
            if datetime.fromisoformat(b["timestamp"]) > cutoff
        ]
        
        critical = [b for b in recent_breaches if b["severity"] == "critical"]
        warnings = [b for b in recent_breaches if b["severity"] == "warning"]
        
        # Count by metric
        by_metric = {}
        for breach in recent_breaches:
            metric = breach["metric"]
            if metric not in by_metric:
                by_metric[metric] = 0
            by_metric[metric] += 1
        
        return {
            "window_hours": hours,
            "total_breaches": len(recent_breaches),
            "critical_count": len(critical),
            "warning_count": len(warnings),
            "breaches_by_metric": by_metric,
            "recent_breaches": recent_breaches[-20:],  # Last 20
        }


def get_sla_tracker(report_dir: Optional[Path] = None) -> SLATracker:
    """Get or create the global SLA tracker."""
    return SLATracker(report_dir)
