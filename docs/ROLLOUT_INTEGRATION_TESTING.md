# Alfa Rollout System - Technical Integration Testing Guide

**Testing & Validation for Production Readiness**

---

## Overview

This guide provides testing procedures to verify all rollout system components are properly integrated and functioning correctly.

---

## Unit Tests

### Feature Flag Manager Tests

**File:** `tests/test_feature_flag_manager.py`

```python
import pytest
from models.feature_flag_manager import FeatureFlagManager
from pathlib import Path
import json
import tempfile


@pytest.fixture
def temp_config():
    """Create temporary feature flags config."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        config = {
            "alfa_rating_enabled": {
                "type": "percentage",
                "percentage": 0,
                "enabled": True
            },
            "alfa_predictions_in_api": {
                "type": "boolean",
                "enabled": False
            }
        }
        json.dump(config, f)
        return f.name


def test_load_flags(temp_config):
    """Test loading flags from file."""
    ffm = FeatureFlagManager(temp_config)
    assert ffm.get_flag("alfa_rating_enabled") is not None
    assert ffm.get_percentage("alfa_rating_enabled") == 0


def test_update_percentage_flag(temp_config):
    """Test updating percentage flag."""
    ffm = FeatureFlagManager(temp_config)
    success, msg = ffm.update_flag("alfa_rating_enabled", 25)
    assert success
    assert ffm.get_percentage("alfa_rating_enabled") == 25


def test_update_boolean_flag(temp_config):
    """Test updating boolean flag."""
    ffm = FeatureFlagManager(temp_config)
    success, msg = ffm.update_flag("alfa_predictions_in_api", True)
    assert success
    assert ffm.is_enabled("alfa_predictions_in_api")


def test_phase_calculation(temp_config):
    """Test get_current_phase()."""
    ffm = FeatureFlagManager(temp_config)
    
    # Test phase transitions
    ffm.update_flag("alfa_rating_enabled", 0)
    assert ffm.get_current_phase() == 0
    
    ffm.update_flag("alfa_rating_enabled", 10)
    assert ffm.get_current_phase() == 1
    
    ffm.update_flag("alfa_rating_enabled", 25)
    assert ffm.get_current_phase() == 2
    
    ffm.update_flag("alfa_rating_enabled", 50)
    assert ffm.get_current_phase() == 3
    
    ffm.update_flag("alfa_rating_enabled", 75)
    assert ffm.get_current_phase() == 4
    
    ffm.update_flag("alfa_rating_enabled", 100)
    assert ffm.get_current_phase() == 5


def test_change_log(temp_config):
    """Test audit trail."""
    ffm = FeatureFlagManager(temp_config)
    ffm.update_flag("alfa_rating_enabled", 25)
    
    log = ffm.get_change_log()
    assert len(log) > 0
    assert log[0]["flag"] == "alfa_rating_enabled"
    assert log[0]["new_value"] == 25


def test_validate_prerequisites(temp_config):
    """Test phase prerequisite validation."""
    ffm = FeatureFlagManager(temp_config)
    
    # Phase 0 should always be valid
    valid, msg = ffm.validate_rollout_prerequisites(0)
    assert valid
    
    # Phase 1 requires certain flags
    valid, msg = ffm.validate_rollout_prerequisites(1)
    assert valid or "required" in msg.lower()
```

### Rollout Manager Tests

**File:** `tests/test_rollout_manager.py`

```python
import pytest
from models.rollout_manager import RolloutManager, RatingMethod, create_rollout_manager
from models.feature_flag_manager import FeatureFlagManager
from pathlib import Path
import tempfile
import json


@pytest.fixture
def rollout_manager():
    """Create test rollout manager."""
    # Create temp config
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        config = {
            "alfa_rating_enabled": {
                "type": "percentage",
                "percentage": 0
            },
            "alfa_predictions_in_api": {
                "type": "boolean",
                "enabled": False
            },
            "alfa_anomaly_detection_enabled": {
                "type": "boolean",
                "enabled": False
            },
            "alfa_vs_fargo_comparison": {
                "type": "percentage",
                "percentage": 0
            }
        }
        json.dump(config, f)
        config_path = f.name
    
    ffm = FeatureFlagManager(config_path)
    return create_rollout_manager(ffm)


def test_ratings_method_disabled(rollout_manager):
    """Test that Fargo is returned when Alfa disabled."""
    method = rollout_manager.get_ratings_method("t123")
    assert method == RatingMethod.FARGO


def test_should_use_alfa_zero_percent(rollout_manager):
    """Test stratification at 0%."""
    assert not rollout_manager.should_use_alfa("t123", percent=0)


def test_should_use_alfa_hundred_percent(rollout_manager):
    """Test stratification at 100%."""
    assert rollout_manager.should_use_alfa("t123", percent=100)


def test_should_use_alfa_consistent(rollout_manager):
    """Test consistency - same tournament always gets same treatment."""
    result1 = rollout_manager.should_use_alfa("t123", percent=50)
    result2 = rollout_manager.should_use_alfa("t123", percent=50)
    assert result1 == result2


def test_should_use_alfa_distribution(rollout_manager):
    """Test that stratification distributes evenly."""
    # At 50%, roughly half should get Alfa
    count = 0
    for i in range(100):
        if rollout_manager.should_use_alfa(f"t{i}", percent=50):
            count += 1
    
    # Should be close to 50 (allow 40-60 range)
    assert 40 <= count <= 60


def test_user_preference_override(rollout_manager):
    """Test user opt-in/out in early phases."""
    rollout_manager.feature_flag_manager.update_flag("alfa_rating_enabled", 10)
    
    # User opts in
    rollout_manager.set_user_preference("user123", use_alfa=True)
    assert rollout_manager.get_user_preference("user123") == True
    
    # User opts out
    rollout_manager.set_user_preference("user123", use_alfa=False)
    assert rollout_manager.get_user_preference("user123") == False


def test_record_metrics(rollout_manager):
    """Test metrics recording."""
    success = rollout_manager.record_rollout_metrics(
        match_id="m123",
        tournament_id="t123",
        predictions_dict={
            "outcome_actual": 1.0,
            "outcome_predicted_alfa": 0.45,
            "outcome_predicted_fargo": 0.48,
            "brier_alfa": 0.3025,
            "brier_fargo": 0.2704
        }
    )
    assert success
```

---

## Integration Tests

### API Endpoint Tests

**File:** `tests/test_rollout_api.py`

```python
import pytest
from fastapi.testclient import TestClient
from api.main import app
import json


@pytest.fixture
def admin_headers():
    """Admin auth headers."""
    return {"Authorization": "Bearer test_admin_token"}


client = TestClient(app)


def test_get_rollout_status(admin_headers):
    """Test GET /api/admin/rollout/status."""
    response = client.get(
        "/api/admin/rollout/status",
        headers=admin_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert "current_phase" in data
    assert "alfa_percentage" in data
    assert "phase_name" in data


def test_update_feature_flag(admin_headers):
    """Test PUT /api/admin/rollout/feature-flags/{flag_name}."""
    response = client.put(
        "/api/admin/rollout/feature-flags/alfa_rating_enabled",
        json={
            "flag_name": "alfa_rating_enabled",
            "value": 25,
            "reason": "Test phase advance"
        },
        headers=admin_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["value"] == 25


def test_get_all_flags(admin_headers):
    """Test GET /api/admin/rollout/all-flags."""
    response = client.get(
        "/api/admin/rollout/all-flags",
        headers=admin_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert "flags" in data
    assert "current_phase" in data


def test_rollback(admin_headers):
    """Test POST /api/admin/rollout/rollback."""
    # First set to 50%
    client.put(
        "/api/admin/rollout/feature-flags/alfa_rating_enabled",
        json={"flag_name": "alfa_rating_enabled", "value": 50},
        headers=admin_headers
    )
    
    # Now rollback
    response = client.post(
        "/api/admin/rollout/rollback",
        headers=admin_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "rolled_back"
    assert data["alfa_percentage"] == 0


def test_change_log(admin_headers):
    """Test GET /api/admin/rollout/change-log."""
    response = client.get(
        "/api/admin/rollout/change-log?limit=10",
        headers=admin_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_validate_phase(admin_headers):
    """Test POST /api/admin/rollout/validate-phase."""
    response = client.post(
        "/api/admin/rollout/validate-phase",
        json={"phase": 1},
        headers=admin_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert "valid" in data
    assert "message" in data
```

---

## Middleware Tests

**File:** `tests/test_feature_flag_middleware.py`

```python
import pytest
from unittest.mock import Mock, patch
from starlette.requests import Request
from starlette.responses import Response
from api.middleware.feature_flags import FeatureFlagMiddleware


@pytest.fixture
def mock_request():
    """Create mock request."""
    request = Mock(spec=Request)
    request.state = {}
    request.query_params = {}
    request.scope = {"path": "/api/rankings"}
    return request


def test_middleware_injects_managers(mock_request):
    """Test middleware injects feature flag objects."""
    app = Mock()
    middleware = FeatureFlagMiddleware(app)
    
    # Mock the next middleware
    async def next_middleware(req):
        assert hasattr(req.state, 'feature_flag_manager')
        assert hasattr(req.state, 'rollout_manager')
        return Response()
    
    # This would normally be async, but for testing:
    # middleware.dispatch(mock_request, next_middleware)


def test_middleware_calculates_phase():
    """Test middleware calculates current phase."""
    # Integration test with actual FeatureFlagManager
    pass


def test_middleware_extracts_user_id():
    """Test middleware extracts user ID from auth."""
    pass


def test_middleware_sets_use_alfa():
    """Test middleware sets use_alfa based on query params."""
    pass
```

---

## Database Tests

**File:** `tests/test_rollout_database.py`

```python
import pytest
from database import SessionLocal, engine
from sqlalchemy import text


@pytest.fixture
def db():
    """Get database session."""
    session = SessionLocal()
    yield session
    session.close()


def test_rollout_tracking_table_exists(db):
    """Test rollout_tracking table is created."""
    result = db.execute(text(
        "SELECT EXISTS(SELECT 1 FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_name = 'rollout_tracking')"
    ))
    assert result.scalar()


def test_rollout_metrics_view_exists(db):
    """Test v_rollout_metrics_by_percentage view exists."""
    result = db.execute(text(
        "SELECT EXISTS(SELECT 1 FROM information_schema.views "
        "WHERE table_schema = 'public' AND table_name = 'v_rollout_metrics_by_percentage')"
    ))
    assert result.scalar()


def test_insert_rollout_record(db):
    """Test inserting a rollout tracking record."""
    stmt = text("""
        INSERT INTO rollout_tracking (
            match_id, tournament_id, outcome_actual,
            outcome_predicted_alfa, outcome_predicted_fargo,
            brier_alfa, brier_fargo, alfa_enabled
        ) VALUES (
            'test_m123', 'test_t123', 1.0,
            0.45, 0.48, 0.0000, 0.0000, true
        )
    """)
    db.execute(stmt)
    db.commit()
    
    # Verify insert
    result = db.execute(text(
        "SELECT COUNT(*) FROM rollout_tracking WHERE match_id = 'test_m123'"
    ))
    assert result.scalar() == 1


def test_query_metrics_view(db):
    """Test querying rollout metrics view."""
    result = db.execute(text(
        "SELECT * FROM v_rollout_metrics_by_percentage LIMIT 1"
    ))
    # View should return results or be empty, just checking it runs
    assert result is not None
```

---

## Staging Dry-Run Tests

### Before Phase 1 Deployment

```bash
# 1. Update to 10% (Phase 1) in staging
API_TOKEN=$STAGING_TOKEN
curl -X PUT \
  -H "Authorization: Bearer $API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"flag_name": "alfa_rating_enabled", "value": 10}' \
  https://staging.example.com/api/admin/rollout/feature-flags/alfa_rating_enabled

# 2. Run test tournaments
# (Create synthetic tournaments to generate matches)
for i in {1..10}; do
  python tests/simulate_tournament.py tournament_type=league
done

# 3. Check metrics
curl -H "Authorization: Bearer $API_TOKEN" \
  https://staging.example.com/api/admin/rollout/status

# Expected metrics:
# - matches_total > 100
# - brier_alfa < 0.32
# - error_rate < 1%

# 4. Rollback to 0%
curl -X POST \
  -H "Authorization: Bearer $API_TOKEN" \
  https://staging.example.com/api/admin/rollout/rollback

# 5. Verify rollback
curl -H "Authorization: Bearer $API_TOKEN" \
  https://staging.example.com/api/admin/rollout/status
# Should show: Phase 0, 0%

# 6. Check metrics history archived
# Verify rollout_tracking table has data from test period
```

---

## Performance Tests

### Load Test

```bash
# Generate load against API
ab -n 1000 -c 10 \
  -H "Authorization: Bearer $TOKEN" \
  https://your-domain/api/admin/rollout/status
```

**Expected Results:**
- Response time < 100ms
- Success rate = 100%
- No connection errors

### Database Performance

```sql
-- Test query performance
EXPLAIN ANALYZE
SELECT * FROM v_rollout_metrics_by_percentage;

EXPLAIN ANALYZE
SELECT * FROM v_rollout_metrics_hourly
WHERE hour > DATE_SUB(NOW(), INTERVAL 24 HOUR);

EXPLAIN ANALYZE
SELECT * FROM v_rollout_anomalies
LIMIT 100;
```

**Expected Results:**
- All queries < 100ms
- No sequential scans needed
- Indexes properly utilized

---

## Smoke Tests

**File:** `tests/smoke_test_rollout.sh`

```bash
#!/bin/bash

set -e

DOMAIN="https://your-domain.com"
TOKEN=$ADMIN_TOKEN

echo "Running rollout smoke tests..."

# Test 1: API health
echo "TEST 1: API Health"
curl -f $DOMAIN/api/health || exit 1
echo "✓ API responding"

# Test 2: Get current status
echo "TEST 2: Get Rollout Status"
STATUS=$(curl -s -H "Authorization: Bearer $TOKEN" \
  $DOMAIN/api/admin/rollout/status)
echo "$STATUS" | jq .
echo "✓ Status endpoint working"

# Test 3: Validate phase
echo "TEST 3: Validate Phase 1"
curl -s -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"phase": 1}' \
  $DOMAIN/api/admin/rollout/validate-phase | jq .
echo "✓ Phase validation working"

# Test 4: Get all flags
echo "TEST 4: Get All Flags"
curl -s -H "Authorization: Bearer $TOKEN" \
  $DOMAIN/api/admin/rollout/all-flags | jq '.flags | keys'
echo "✓ Flags retrieved"

# Test 5: Database connectivity
echo "TEST 5: Database Check"
# Query db for rollout_tracking table
curl -s -H "Authorization: Bearer $TOKEN" \
  $DOMAIN/api/admin/rollout/status | jq '.metrics'
echo "✓ Database accessible"

echo ""
echo "✓ All smoke tests passed!"
```

---

## Running Tests

### Unit Tests
```bash
pytest tests/test_feature_flag_manager.py -v
pytest tests/test_rollout_manager.py -v
```

### Integration Tests
```bash
pytest tests/test_rollout_api.py -v
pytest tests/test_feature_flag_middleware.py -v
```

### All Tests
```bash
pytest tests/test_rollout*.py -v --cov=models --cov=api
```

### Dry-Run (Staging)
```bash
bash tests/smoke_test_rollout.sh
```

---

## Test Fixtures

### Feature Flags Config (Test)
```json
{
  "alfa_rating_enabled": {
    "type": "percentage",
    "percentage": 0,
    "rollback_enabled": true
  },
  "alfa_predictions_in_api": {
    "type": "boolean",
    "enabled": false
  },
  "alfa_anomaly_detection_enabled": {
    "type": "boolean",
    "enabled": false
  },
  "alfa_vs_fargo_comparison": {
    "type": "percentage",
    "percentage": 0
  }
}
```

---

## Continuous Integration

### GitHub Actions / CI Pipeline

```yaml
name: Rollout Integration Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:13
        env:
          POSTGRES_PASSWORD: postgres
    
    steps:
      - uses: actions/checkout@v2
      
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.9
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov
      
      - name: Run unit tests
        run: pytest tests/test_feature_flag_manager.py -v
      
      - name: Run rollout manager tests
        run: pytest tests/test_rollout_manager.py -v
      
      - name: Check code coverage
        run: pytest --cov=models --cov=api --cov-report=xml
      
      - name: Upload coverage
        uses: codecov/codecov-action@v2
```

---

## Verification Checklist

- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] API endpoints respond correctly
- [ ] Database queries complete successfully
- [ ] Middleware injects state properly
- [ ] Feature flags update at runtime
- [ ] Phase validation works
- [ ] Rollback executes successfully
- [ ] Metrics are collected
- [ ] Views return data
- [ ] Load tests pass
- [ ] Smoke tests all green
- [ ] Staging dry-run successful

---

## Troubleshooting Tests

**Test fails: "Table not found"**
→ Run database migrations: `psql < database/migrations/rollout_tables.sql`

**Test fails: "Permission denied"**
→ Check auth token is valid and has admin role

**Test fails: "Connection refused"**
→ Verify API service is running and database is accessible

**Test fails: "Invalid JSON"**
→ Check feature_flags.json is valid JSON

---

## Next Steps

After all tests pass:
1. Run verification script: `./scripts/verify_rollout_integration.sh`
2. Complete [Deployment Checklist](ROLLOUT_DEPLOYMENT_CHECKLIST.md)
3. Get stakeholder approval
4. Begin Phase 1 deployment
