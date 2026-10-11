# Database Schema and Code Fixes - February 21, 2026

## Summary
Fixed database schema issues and code compatibility problems that prevented tournament endpoints from functioning.

## Database Schema Updates (Manual SQL)

Applied directly to `rankings.db`:

```sql
ALTER TABLE tournaments ADD COLUMN is_test_tournament BOOLEAN DEFAULT 0;
ALTER TABLE tournaments ADD COLUMN tables_available INTEGER;
```

**Alembic version**: Database shows version `008`, but migrations 021+ not applied via alembic due to configuration issues.

## Code Changes

### 1. **database/db_manager.py** - Fixed Row Factory
- **Issue**: `dict(row)` failing with "cannot convert dictionary update sequence" error
- **Fix**: Added `conn.row_factory` to `get_connection()` method
- **Impact**: Enables dict conversion for all database queries

```python
def get_connection(self):
    """Get database connection with row_factory for dict-like access"""
    conn = connect(self.db_path)
    conn.row_factory = Row
    return conn
```

### 2. **api/tournament_manager.py** - Fixed Initialization
- **Issue**: `DatabaseManager.__init__() got an unexpected keyword argument 'engine'`
- **Fix**: Changed from `engine` parameter to `db_path` parameter
- **Impact**: TournamentManager now properly initializes DatabaseManager

```python
def __init__(self, db_path: str):
    from database.db_manager import DatabaseManager
    self._db_manager = DatabaseManager(db_path=db_path)
```

### 3. **api/routes/tournaments.py** - Added Missing Imports
- **Issue**: `NameError: name 'Depends' is not defined` and missing auth import
- **Fix**: Added `Depends` to FastAPI imports and `require_director_or_admin` from api.auth
- **Impact**: DELETE endpoint and other authenticated endpoints now have required dependencies

```python
from fastapi import APIRouter, HTTPException, status, Depends
from api.tournament_manager import TournamentManager
from api.auth import require_director_or_admin
```

### 4. **api/routes/auth_v1.py** - Disabled Broken Endpoint
- **Issue**: ImportError for non-existent functions: `ensure_super_admin_bootstrap`, `ensure_default_users_bootstrap`, `authenticate_user`
- **Fix**: Commented out missing imports and stubbed endpoint to return construction message
- **Impact**: Prevents API startup crash; mobile auth endpoint temporarily disabled
- **TODO**: Implement missing auth functions or remove endpoint

### 5. **alembic.ini** - Configuration Cleanup
- **Changes**: 
  - Added proper `[alembic]` section with `script_location` and `file_template`
  - Changed `[sqlalchemy]` section for database URL
  - Removed duplicate sections that caused parser errors
- **Status**: Alembic still has issues with migration file format (missing `revision` variable declarations)

### 6. **alembic/env.py** - URL Configuration Fix
- **Fix**: Updated URL reading logic to properly handle `[sqlalchemy]` section:
```python
sqlalchemy_section = config.get_section('sqlalchemy')
if sqlalchemy_section and sqlalchemy_section.get('sqlalchemy.url'):
    config.set_main_option('sqlalchemy.url', sqlalchemy_section.get('sqlalchemy.url'))
```

## Known Issues (Not Fixed)

1. **Alembic migrations not running**: Migration files lack proper `revision` variable declarations
2. **Auth v1 endpoint non-functional**: Missing authentication helper functions
3. **Additional import errors**: Some modules may reference non-existent functions (e.g., `get_current_user_object`)
4. **Database migration tracking**: Stuck at version 008, manually applied columns from 021

## Testing Status

- ✅ Database schema updated (columns verified)
- ✅ Code compiles without import errors for core tournament routes
- ⚠️ API container startup not yet verified
- ❌ Tournament endpoints not yet tested with updated schema
- ❌ Alembic migrations not functional

## Deployment Notes

**Before deploying**:
1. Verify all containers can start successfully
2. Test tournament CRUD endpoints with new schema
3. Consider implementing missing auth_v1 functions or removing endpoint
4. Fix alembic migration system or continue with manual SQL updates

**Database backup recommended** before applying to production.

## Next Steps

1. Complete API container startup debugging
2. Test tournament list/create/edit/delete endpoints
3. Implement or remove auth_v1 functions
4. Fix alembic migration system for future schema changes
5. Deploy and verify in production environment
