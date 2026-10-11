#!/usr/bin/env python3
"""
Centralized Log Management System for market-pie5-bot
Consolidates logging from multiple sources. JSON/file storage only (no SQLite).
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class LogManager:
    """
    Unified logging system that consolidates logs from different sources
    and provides storage in JSON format (no database).
    """

    def __init__(self, log_dir: str = "logs", db_name: str = "trading_logs"):
        """
        Initialize the log manager.

        Args:
            log_dir: Directory to store log files
            db_name: Base name for log files (no SQLite; used as prefix for JSON)
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        self.db_name = db_name
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    def log_trade(self, trade_data: Dict[str, Any], session_id: Optional[str] = None):
        """Log a trade to JSON storage."""
        if session_id is None:
            session_id = self.session_id
        if "timestamp" not in trade_data:
            trade_data["timestamp"] = datetime.now().isoformat()
        json_file = self.log_dir / f"trades_{session_id}.json"
        self._append_to_json(json_file, trade_data)

    def log_system_event(self, level: str, message: str, metadata: Optional[Dict] = None):
        """Log a system event to JSON."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "message": message,
            "metadata": metadata or {},
        }
        json_file = self.log_dir / f"system_{self.session_id}.json"
        self._append_to_json(json_file, log_entry)

    def log_backtest_result(self, backtest_data: Dict[str, Any]):
        """Log backtest results to JSON."""
        backtest_data.setdefault("timestamp", datetime.now().isoformat())
        json_file = self.log_dir / f"backtest_{self.session_id}.json"
        self._save_to_json(json_file, backtest_data)

    def log_performance_metric(self, metric_name: str, metric_value: float, metadata: Optional[Dict] = None):
        """Log a performance metric to JSON."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "metric_name": metric_name,
            "metric_value": metric_value,
            "metadata": metadata or {},
        }
        json_file = self.log_dir / f"performance_{self.session_id}.json"
        self._append_to_json(json_file, entry)

    def merge_trade_history(self, trade_history: List[Dict]) -> int:
        """Merge existing trade history into the log system."""
        for trade in trade_history:
            self.log_trade(trade)
        return len(trade_history)

    def get_trades(self, session_id: Optional[str] = None, symbol: Optional[str] = None,
                   start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Dict]:
        """Retrieve trades from JSON files with optional filters."""
        sid = session_id or self.session_id
        json_file = self.log_dir / f"trades_{sid}.json"
        if not json_file.exists():
            return []
        rows = self._read_json_lines(json_file)
        if symbol:
            rows = [r for r in rows if r.get("symbol") == symbol]
        if start_date:
            rows = [r for r in rows if (r.get("timestamp") or "") >= start_date]
        if end_date:
            rows = [r for r in rows if (r.get("timestamp") or "") <= end_date]
        return sorted(rows, key=lambda r: r.get("timestamp", ""))

    def get_backtest_results(self, session_id: Optional[str] = None) -> List[Dict]:
        """Retrieve backtest results from JSON."""
        sid = session_id or self.session_id
        json_file = self.log_dir / f"backtest_{sid}.json"
        if not json_file.exists():
            return []
        try:
            data = json.loads(json_file.read_text())
            return [data] if isinstance(data, dict) else data
        except Exception as e:
            logger.warning("Failed to parse backtest JSON file '%s': %s", json_file, e)
            return []

    def _append_to_json(self, file_path: Path, data: Dict):
        """Append data to a JSON file as a new line."""
        with open(file_path, "a") as f:
            f.write(json.dumps(data, default=str) + "\n")

    def _read_json_lines(self, file_path: Path) -> List[Dict]:
        """Read newline-delimited JSON lines."""
        out = []
        if not file_path.exists():
            return out
        with open(file_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except Exception as e:
                    logger.debug("Skipping invalid JSON log line in '%s': %s", file_path, e)
        return out

    def _save_to_json(self, file_path: Path, data: Dict):
        """Save data to a JSON file (overwrite)."""
        with open(file_path, "w") as f:
            json.dump(data, f, indent=2, default=str)


if __name__ == "__main__":
    print("Log Manager Example Usage (JSON only)")
    print("=" * 60)
    log_manager = LogManager()
    trade = {
        "symbol": "AAPL",
        "action": "BUY",
        "quantity": 10.0,
        "price": 150.0,
        "is_win": True,
        "pnl": 50.0,
        "pnl_percent": 3.33,
        "exit_reason": "trailing_stop",
        "strategy": "momentum",
    }
    log_manager.log_trade(trade)
    print(f"✓ Logged trade: {trade['symbol']} {trade['action']}")
    log_manager.log_system_event("INFO", "Trading bot started", {"version": "1.0"})
    print("✓ Logged system event")
    backtest = {
        "initial_capital": 10000.0,
        "final_capital": 11000.0,
        "total_pnl": 1000.0,
        "roi": 0.10,
        "total_trades": 50,
        "winning_trades": 30,
        "losing_trades": 20,
        "win_rate": 0.60,
    }
    log_manager.log_backtest_result(backtest)
    print("✓ Logged backtest result")
    trades = log_manager.get_trades()
    print(f"\n✓ Retrieved {len(trades)} trades")
    print("\nLog files in 'logs' directory:")
    for file in log_manager.log_dir.glob("*"):
        print(f"  - {file.name}")
