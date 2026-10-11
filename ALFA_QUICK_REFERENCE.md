# ALFa Cold-Start & Anomaly Detection: Quick Reference

## 60-Second Overview

Two production-ready systems for Alfa billiards ratings:

1. **Cold-Start:** Blend measured rating with prior distribution → reduce new player variance by 11%
2. **Anomaly Detection:** 6 flags detect sandbagging, cheating, misclassification → flag 33% for review

All tested (23/23 passing), documented, and ready to integrate.

---

## Installation

No external dependencies beyond existing requirements. Just import:

```python
from models.alfa_cold_start import ColdStartEngine
from models.alfa_anomaly_detection import AnomalyDetector
```

---

## Cold-Start: 30 Seconds

**Adjust new player rating:**

```python
from models.alfa_cold_start import ColdStartEngine

engine = ColdStartEngine.from_defaults()  # Or compute from data

adjusted, stats = engine.bayesian_blend(
    measured_rating=480.0,
    games_played=5
)

print(f"Adjusted: {adjusted:.0f}")  # ~433 (pulled toward 400 prior)
```

**Compute custom priors:**

```python
fargo_ratings = [450, 500, 600, 650, 700, ...]
priors = ColdStartEngine.compute_priors_from_data(fargo_ratings)
engine = ColdStartEngine(priors)
```

---

## Anomaly Detection: 30 Seconds

**Detect suspicious player:**

```python
from models.alfa_anomaly_detection import AnomalyDetector, PlayerMatchHistory

detector = AnomalyDetector()

history = PlayerMatchHistory(
    player_id="player_123",
    rating=650.0,
    games=[
        {"opponent_rating": 550, "won": True, "is_break": False},
        {"opponent_rating": 551, "won": True, "is_break": False},
        # ... more games
    ]
)

flags = detector.detect_anomalies(history)

if flags.anomaly_score > 0.5:
    print(f"⚠️ Review {flags.player_id}")
    print(f"   Score: {flags.anomaly_score:.2f}")
    print(f"   Flags: {flags.flagged_count}")
```

---

## API Usage

### Cold-Start API

```python
engine = ColdStartEngine(priors)

# Main method
adjusted, stats = engine.bayesian_blend(measured_rating, games_played, estimated_skill)

# Returns:
# - adjusted: float (blended rating)
# - stats: {
#     'starter_rating': float,
#     'measured_rating': float,
#     'blended_rating': float,
#     'starter_weight': float,
#     'measured_weight': float,
#     'games_played': int,
#     'adjustment': float,  # +/- from measured
#   }

# Utility methods
starter = engine.starter_rating(estimated_skill)  # Get prior for skill level
convergence = engine.convergence_analysis(initial, true_rating, [5, 10, 20])
```

### Anomaly Detection API

```python
detector = AnomalyDetector()

# Main method
flags = detector.detect_anomalies(
    history: PlayerMatchHistory,
    league_division: str = None,
    expected_rating_range: (float, float) = None
)

# Returns: AnomalyFlags with:
# - .winning_weak_only: bool
# - .losing_strong_only: bool
# - .rating_league_mismatch: bool
# - .sudden_jump: bool
# - .high_variance: bool
# - .break_dominance_outlier: bool
# - .anomaly_score: float [0-1]
# - .severity_level: str ('low', 'medium', 'high')
# - .flagged_count: int
# - .as_dict(): dict (for serialization)

# Batch processing
from models.alfa_anomaly_detection import analyze_anomalies_batch

flags_list, stats = analyze_anomalies_batch(histories)
# stats: {
#     'total_players': int,
#     'flagged_players': int,
#     'low_severity': int,
#     'medium_severity': int,
#     'high_severity': int,
#     'avg_flags_per_player': float,
# }
```

---

## Integration Examples

### Example 1: Adjust Rating for Matchmaking

```python
from models.alfa_cold_start import ColdStartEngine

def get_game_rating(player_id: str) -> float:
    """Get rating for matchmaking (with cold-start adjustment)."""
    measured = db.get_player_rating(player_id)
    games = db.get_player_game_count(player_id)
    
    # Only adjust new players
    if games < 200:
        engine = ColdStartEngine.load_cached()
        adjusted, _ = engine.bayesian_blend(measured, games)
        return adjusted
    return measured
```

### Example 2: Flag Players for Review

```python
from models.alfa_anomaly_detection import AnomalyDetector, PlayerMatchHistory

def check_if_suspicious(player_id: str) -> bool:
    """Check if player should be reviewed."""
    detector = AnomalyDetector()
    history = build_history_from_db(player_id)
    flags = detector.detect_anomalies(history)
    
    if flags.severity_level in ["medium", "high"]:
        admin_queue.add({
            'player_id': player_id,
            'score': flags.anomaly_score,
            'flags': flags.flagged_count,
        })
        return True
    return False
```

### Example 3: Daily Maintenance Job

```python
import logging
from models.alfa_cold_start import ColdStartEngine
from models.alfa_anomaly_detection import analyze_anomalies_batch

logger = logging.getLogger(__name__)

def daily_maintenance():
    """Run daily: update priors and flag anomalies."""
    
    # 1. Update priors quarterly (or monthly)
    if should_update_priors():
        latest_fargos = db.get_all_current_fargos()
        priors = ColdStartEngine.compute_priors_from_data(latest_fargos)
        cache.store_priors(priors)
        logger.info("Updated cold-start priors")
    
    # 2. Check all players for anomalies
    all_histories = [db.build_match_history(p) for p in db.all_players()]
    flags_list, stats = analyze_anomalies_batch(all_histories)
    
    logger.info(f"Anomaly scan: {stats['flagged_players']} flagged, {stats['high_severity']} high")
    
    # 3. Queue high-severity for manual review
    for flags in flags_list:
        if flags.severity_level == "high":
            manual_review_queue.add(flags.as_dict())
```

---

## Configuration

### Cold-Start Thresholds

Edit `ColdStartEngine.BLEND_SCHEDULE`:

```python
BLEND_SCHEDULE = [
    (10, 0.80, 0.20),      # <10 games: aggressive blending
    (50, 0.50, 0.50),      # 10-50 games
    (200, 0.10, 0.90),     # 50-200 games
    (float('inf'), 0.00, 1.00),  # 200+ games: no adjustment
]
```

### Anomaly Thresholds

Edit `AnomalyDetector` class constants:

```python
WEAK_THRESHOLD = -50                    # "Weak" = 50+ pts below
WEAK_ONLY_WINRATE_THRESHOLD = 0.80     # Flag if 80%+ wins vs weak
STRONG_THRESHOLD = 50                   # "Strong" = 50+ pts above
STRONG_ONLY_LOSSRATE_THRESHOLD = 0.80  # Flag if 80%+ losses vs strong
SUDDEN_JUMP_THRESHOLD = 40              # Flag for +40 pts
SUDDEN_JUMP_WINDOW = 5                  # In how many games
HIGH_VARIANCE_THRESHOLD = 0.35          # Win% std dev
BREAK_DOMINANCE_THRESHOLD = 0.75        # Break win rate %
```

---

## Testing

**Run all tests:**

```bash
pytest tests/test_alfa_cold_start_and_anomaly.py -v
```

**Run specific test:**

```bash
pytest tests/test_alfa_cold_start_and_anomaly.py::TestColdStartEngine::test_bayesian_blend_few_games -v
```

**Full evaluation (warning: takes ~2 min):**

```bash
python3 test_alfa_systems.py
```

---

## Common Tasks

### Task: Adjust rating for tournament registration

```python
def register_player(name: str, fargo: float, games: int):
    engine = ColdStartEngine.load_cached()
    
    if games < 50:
        adjusted, stats = engine.bayesian_blend(fargo, games)
        print(f"New player: {fargo} → {adjusted} (adjusted)")
        return adjusted
    return fargo
```

### Task: Monitor high-risk players

```python
def get_review_list() -> list:
    detector = AnomalyDetector()
    all_histories = [... build all histories ...]
    flags_list, stats = analyze_anomalies_batch(all_histories)
    
    return sorted(
        [f for f in flags_list if f.severity_level == "high"],
        key=lambda x: -x.anomaly_score
    )
```

### Task: Export metrics

```python
import json

def export_system_metrics():
    # Cold-start metrics
    cs_data = {
        'priors': cached_priors.to_dict(),
        'last_updated': datetime.now().isoformat(),
    }
    
    # Anomaly metrics
    all_histories = [...]
    _, anomaly_stats = analyze_anomalies_batch(all_histories)
    
    report = {
        'cold_start': cs_data,
        'anomalies': anomaly_stats,
        'timestamp': datetime.now().isoformat(),
    }
    
    with open('metrics.json', 'w') as f:
        json.dump(report, f, indent=2)
```

---

## Troubleshooting

**Q: Cold-start adjustment seems too aggressive**
- ✅ Reduce starter_weight for your game count tier
- ✅ Increase starter weight only for <10 games

**Q: Too many false positives in anomaly detection**
- ✅ Increase WEAK_ONLY_WINRATE_THRESHOLD from 0.80 → 0.85
- ✅ Increase SUDDEN_JUMP_THRESHOLD from 40 → 50
- ✅ Increase min games requirement from 5 → 10

**Q: Players complain about rating adjustment**
- ✅ Explain: "New players have noisy ratings; we blend with skill category average"
- ✅ Show: "This helps find fair matches faster"
- ✅ Point out: Adjustment disappears by 200 games

**Q: Anomalies detected seem wrong**
- ✅ Check PlayerMatchHistory.games structure
- ✅ Verify opponent_rating and is_break fields
- ✅ Look at flagged_count and anomaly_score, not individual flags

---

## Performance

- **Cold-start blend:** <1ms per adjustment
- **Anomaly detection:** <10ms per player
- **Batch processing:** ~50ms for 1000 players

---

## Files to Know

| File | Purpose |
|------|---------|
| `models/alfa_cold_start.py` | Core cold-start system |
| `models/alfa_anomaly_detection.py` | Core anomaly detection |
| `tests/test_alfa_cold_start_and_anomaly.py` | 23 passing unit tests |
| `docs/ALFA_COLD_START_IMPLEMENTATION.md` | Full implementation guide |
| `test_alfa_systems.py` | Full evaluation script |
| `reports/ALFA_COLD_START_ANOMALY_SUMMARY.md` | Evaluation results |

---

## Getting Help

- **Implementation details:** See `docs/ALFA_COLD_START_IMPLEMENTATION.md`
- **Code examples:** See `tests/test_alfa_cold_start_and_anomaly.py`
- **Evaluation results:** See `reports/ALFA_COLD_START_ANOMALY_SUMMARY.md`
- **API signatures:** See module docstrings

---

Last updated: February 16, 2026
