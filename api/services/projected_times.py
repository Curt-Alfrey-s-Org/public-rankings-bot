"""
Projected match times: estimate when matches will start/end from avg duration.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional


DEFAULT_AVG_DURATION_MINUTES = 30


def _parse_iso(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _to_iso(dt: datetime) -> str:
    return dt.isoformat()


def compute_projected_times(
    matches: List[Dict],
    tournament_date: Optional[str] = None,
    default_start_hour: int = 9,
) -> List[Dict]:
    """
    Add projected_start_time and projected_end_time to each match.
    Uses avg duration from completed matches; round 1 uses scheduled_time or tournament_date.
    """
    if not matches:
        return []

    # Compute avg duration from completed matches with both started_at and completed_at
    durations = []
    for m in matches:
        if m.get("status") != "completed":
            continue
        start = _parse_iso(m.get("started_at"))
        end = _parse_iso(m.get("completed_at"))
        if start and end and end > start:
            durations.append((end - start).total_seconds() / 60)
    avg_minutes = sum(durations) / len(durations) if durations else DEFAULT_AVG_DURATION_MINUTES

    # Base time for round 1: tournament date at default hour, or first scheduled match
    base_date = tournament_date or "2026-01-01"
    try:
        base_dt = datetime.fromisoformat(base_date)
    except (ValueError, TypeError):
        base_dt = datetime(2026, 1, 1)
    if base_dt.hour == 0 and base_dt.minute == 0:
        base_dt = base_dt.replace(hour=default_start_hour, minute=0, second=0, microsecond=0)

    # Group by (bracket_type, round_number)
    by_round: Dict[tuple, List[Dict]] = {}
    for m in matches:
        key = (m.get("bracket_type") or "winners", m.get("round_number") or 1)
        if key not in by_round:
            by_round[key] = []
        by_round[key].append(m)

    # Sort rounds: winners 1,2,3... then losers, then grand_final
    def round_key(item):
        bt, rn = item[0]
        order = {"winners": 0, "losers": 100, "grand_final": 200}.get(bt, 0)
        return (order, rn)

    sorted_rounds = sorted(by_round.items(), key=round_key)

    # Track projected_end per match_id for dependency resolution
    proj_end: Dict[str, datetime] = {}

    for (bracket_type, round_num), round_matches in sorted_rounds:
        sorted_matches = sorted(round_matches, key=lambda x: x.get("match_number", 0))

        if round_num == 1:
            # Round 1: use scheduled_time or stagger from base
            for i, m in enumerate(sorted_matches):
                mid = m.get("match_id", "")
                sched = _parse_iso(m.get("scheduled_time"))
                if sched:
                    start = sched
                else:
                    start = base_dt + timedelta(minutes=i * avg_minutes * 0.5)
                end = start + timedelta(minutes=avg_minutes)
                proj_end[mid] = end
                m["projected_start_time"] = _to_iso(start)
                m["projected_end_time"] = _to_iso(end)
        else:
            # Round N: start when preceding matches (round N-1, same bracket) would complete
            prev_key = (bracket_type, round_num - 1)
            prev_matches = by_round.get(prev_key, [])
            prev_sorted = sorted(prev_matches, key=lambda x: x.get("match_number", 0))

            # Single elim: round N match k needs round N-1 matches 2k-1 and 2k
            for i, m in enumerate(sorted_matches):
                mid = m.get("match_id", "")
                idx1 = 2 * i
                idx2 = 2 * i + 1
                latest_end = base_dt
                if prev_sorted:
                    for idx in (idx1, idx2):
                        if idx < len(prev_sorted):
                            pm = prev_sorted[idx]
                            pend = proj_end.get(pm.get("match_id"))
                            if pend and pend > latest_end:
                                latest_end = pend
                start = latest_end + timedelta(minutes=5)
                end = start + timedelta(minutes=avg_minutes)
                proj_end[mid] = end
                m["projected_start_time"] = _to_iso(start)
                m["projected_end_time"] = _to_iso(end)

    return matches
