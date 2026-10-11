# User Management & Security System Implementation

## Overview
Comprehensive user management system for Rankings-Bot enabling:
- Bulk user creation from Fargo player data with auto-generated secure credentials
- User profile customization (display name / nickname, email)
- Login security monitoring with IP address tracking
- Account lockout enforcement (5 failed attempts = 30-minute lock)
- CSV export for distribution to WPA/WPBA presidents

---

## Backend Components

### 1. LoginAttempt Model (`api/models/login_attempt.py`)
Tracks all login attempts (success and failure) with IP addresses for security analysis.

**Fields:**
- `id` (Integer, Primary Key)
- `user_id` (Foreign Key to User, nullable)
- `username` (String) - Username attempted
- `ip_address` (String) - Client IP address
- `success` (Boolean) - Login succeeded or failed
- `failure_reason` (String, nullable) - Reason if failed: "invalid_password", "account_locked", "invalid_user"
- `timestamp` (DateTime) - When attempt occurred

**Indexes:**
- `(user_id, timestamp)` - Query attempts by user
- `(ip_address, timestamp)` - Query attempts by IP
- `(username, timestamp)` - Query attempts by username

---

### 2. User Model Updates (`api/models/user.py`)
Enhanced with profile customization fields.

**New Fields:**
- `nickname` (String, 100 chars, nullable) - Display name shown to other players
- `email` (String, nullable) - Changed from required to optional (set on first login)

**Removed Requirement:**
- Email is no longer required at account creation (bulk-created users set email on first login)

---

### 3. Bulk User Service (`api/services/bulk_user_service.py`)
Converts Fargo player data into ranked user accounts.

**Functions:**

#### `generate_unique_username(name: str, db: Session) -> str`
Creates the username from the player's **Fargo name** so operators can hand a player
their Fargo name as the first-login credential:
1. Uses the Fargo name as-is, trimmed with internal whitespace collapsed and case
   preserved (e.g., "Shane Van Boening")
2. Appends a numeric suffix only on a true duplicate name (e.g., "John Smith 2")

Login lookups are case/whitespace-insensitive (`api.auth.get_user_by_username`), so the
handed-out name works regardless of how the player types it.

**Returns:** Username equal to the Fargo name (with numeric suffix on collision)

#### `generate_password() -> str`
Generates 12-character secure password with:
- Uppercase letters (2-3)
- Lowercase letters (3-4)
- Digits (2-3)
- Special symbols [!@#$%] (1-2)

**Example:** "X9#kL2@mP5!"

#### `create_bulk_users_from_fargo(fargo_players: List[dict], db: Session) -> tuple`
Creates User records from Fargo player data.

**Input Format:**
```python
[
  {"name": "John Smith", "fargo_rating": 800, "state": "CA", "fargo_id": 12345},
  {"name": "Jane Doe", "fargo_rating": 750, "state": "NY", "fargo_id": 12346},
]
```

**Returns:**
```python
(
  created_users=[...],  # List of created User objects with generated passwords
  errors=[...]          # List of {"player": {...}, "error": "reason"}
)
```

#### `export_users_csv(users: List[User]) -> str`
Converts user list to CSV string.

**Format:**
```
username,password,name,fargo_rating,state,fargo_id
john_smith,X9#kL2@mP5!,John Smith,800,CA,12345
jane_doe,Y8@kM3#oQ6!,Jane Doe,750,NY,12346
```

---

### 4. Login Tracking Service (`api/services/login_tracking_service.py`)
Backend for login attempt tracking and account lockout enforcement.

**Functions:**

#### `record_login_attempt(db, username, ip_address, success, failure_reason, user_id)`
Records login attempt to LoginAttempt table.

#### `check_and_update_failed_attempts(db, user, ip_address, max_attempts=5, lockout_minutes=30) -> bool`
Increments failed attempt counter and locks account after max_attempts.

**Returns:** True if account is now locked, False otherwise

**Lockout Logic:**
- Increments `User.failed_login_attempts` counter
- Sets `User.account_locked_until = now + 30 minutes` after 5 failures
- Locks in database immediately (not time-based)

#### `reset_failed_attempts(db, user) -> None`
Clears failed attempts counter and removes lockout after successful login.

#### `is_account_locked(user) -> bool`
Checks if `account_locked_until > datetime.utcnow()`

#### `get_account_lock_info(user) -> dict`
Returns:
```python
{
  "is_locked": bool,
  "locked_until": datetime or None,
  "minutes_remaining": int or None
}
```

#### `get_user_login_history(db, user_id, hours=24, limit=20) -> List[LoginAttempt]`
Retrieves recent login attempts for user.

---

### 5. Admin Security Routes (`api/routes/admin_security.py`)
Four admin endpoints for bulk user management and security monitoring.

#### `POST /api/admin/users/bulk-create` (super_admin only)
Create multiple users from Fargo player data and get CSV export.

**Request:**
```python
{
  "players": [
    {"name": "John Smith", "fargo_rating": 800, "state": "CA", "fargo_id": 12345},
    {"name": "Jane Doe", "fargo_rating": 750, "state": "NY", "fargo_id": 12346},
  ]
}
```

**Response:**
```python
{
  "created_count": 2,
  "error_count": 0,
  "users": [
    {
      "username": "john_smith",
      "password": "X9#kL2@mP5!",
      "name": "John Smith",
      "fargo_rating": 800,
      "state": "CA",
      "fargo_id": 12345
    },
    ...
  ],
  "errors": [],
  "csv_data": "username,password,name,...\njohn_smith,X9#kL2@mP5!,..."
}
```

#### `GET /api/admin/login-attempts` (admin+)
View login attempts with IP addresses, filtered by time and status.

**Query Parameters:**
- `hours: int` (default 24) - Show attempts from last N hours (1-168)
- `failed_only: bool` (default false) - Show only failed attempts
- `limit: int` (default 100) - Max results

**Response:**
```python
{
  "total": 150,
  "attempts": [
    {
      "id": 1,
      "username": "jsmith",
      "ip_address": "198.51.100.103",
      "success": false,
      "failure_reason": "invalid_password",
      "timestamp": "2024-01-15T10:30:00Z"
    },
    ...
  ]
}
```

#### `GET /api/admin/users/{username}/security` (admin+)
View security status of specific user: failed attempts, lock status, recent IPs, attempt history.

**Response:**
```python
{
  "username": "jsmith",
  "failed_attempts": 3,
  "is_locked": false,
  "locked_until": null,
  "minutes_remaining": null,
  "recent_ips": ["198.51.100.103", "198.51.100.104"],
  "recent_attempts": [
    {
      "ip_address": "198.51.100.103",
      "success": false,
      "timestamp": "2024-01-15T10:30:00Z",
      "failure_reason": "invalid_password"
    },
    ...
  ]
}
```

#### `POST /api/admin/users/{username}/unlock` (super_admin only)
Manually unlock locked user account.

**Response:**
```python
{
  "message": "Account unlocked successfully",
  "username": "jsmith",
  "is_locked": false
}
```

---

### 6. Profile Routes (`api/routes/profile.py`)
User profile customization endpoints.

#### `PUT /api/profile/nickname`
Update user's display nickname (shown in rankings).

**Request:**
```python
{"nickname": "Johnny"}
```

#### `PUT /api/profile/email`
Update user's email address (required for password reset).

**Request:**
```python
{"email": "john@example.com"}
```

#### `GET /api/me`
Get current user's profile information.

**Response:**
```python
{
  "username": "john_smith",
  "nickname": "Johnny",
  "email": "john@example.com",
  "role": "user"
}
```

---

### 7. Auth Endpoint Updates (`api/routes/auth.py`)
Enhanced login endpoint with security tracking.

**POST /login**
- Checks if account is locked (returns 423 status)
- Records failed attempts with IP and reason
- Locks account after 5 failures for 30 minutes
- Records successful login with IP to LoginAttempt table
- Resets failed counter on success
- Full IP address logging for security analysis

---

## Frontend Components

### 1. LoginAttemptsMonitor (`frontend/src/features/admin/components/LoginAttemptsMonitor.tsx`)
Real-time monitoring of failed login attempts with IP addresses.

**Features:**
- Auto-refresh every 30 seconds
- Filter by time range (1-168 hours)
- Filter by failed attempts only
- Display stats: total, successful, failed, unique IPs
- Table showing: username, IP, status, reason, timestamp

### 2. UserSecurityStatus (`frontend/src/features/admin/components/UserSecurityStatus.tsx`)
View security info for specific user and manually unlock if needed.

**Features:**
- Failed attempts counter
- Lock status with countdown timer
- Recent IP addresses list
- Recent attempt history (last 24h)
- Manual unlock button (super_admin only)

### 3. BulkUserCreator (`frontend/src/features/admin/components/BulkUserCreator.tsx`)
Import players from Fargo and generate user accounts with secure passwords.

**Features:**
- CSV input field with instructions
- Format: name, fargo_rating, state, fargo_id
- Shows created users in table
- Shows errors in separate section
- Download CSV button (username, password, name, rating, state)
- Import another batch option

### 4. ProfilePage (`frontend/src/features/user/pages/ProfilePage.tsx`)
User profile customization page.

**Features:**
- Display username (read-only)
- Set display name (nickname)
- Set email address (required for password reset)
- Show role and current values
- Save buttons with loading states
- Success/error messages

### 5. AdminSecurityDashboard (`frontend/src/features/admin/pages/AdminSecurityDashboard.tsx`)
Central admin dashboard with three tabs:
1. **Bulk User Import** - Create users from Fargo data, export CSV
2. **Login Monitoring** - View failed attempts with IP tracking
3. **User Security** - Search user and view/manage security status

---

## Workflow: Creating & Distributing Users

### Step 1: Admin Imports Players
1. Go to **Admin Security Dashboard** → **Bulk User Import**
2. Paste Fargo player data (name, rating, state, ID)
3. Click **Create Users**
4. Review created users in table
5. Click **Download CSV**

### Step 2: CSV Distribution Format
**Distribute to WPA/WPBA Presidents:**
```
username,password,name,fargo_rating,state,fargo_id
john_smith,X9#kL2@mP5!,John Smith,800,CA,12345
jane_doe,Y8@kM3#oQ6!,Jane Doe,750,NY,12346
```

**IMPORTANT**: Passwords are temporary. Users must:
1. Log in with provided username and password
2. Set their email address (required)
3. Change password to something they remember

### Step 3: First Login Experience
1. Player logs in with username + temporary password
2. Prompted to set email (required for password reset)
3. Prompted to choose new password
4. Redirected to profile page to set nickname if desired
5. Account ready for use

### Step 4: Ongoing Security Management
**Admin monitors login attempts:**
- Go to **Login Monitoring** tab
- See failed attempts by IP address
- Check for suspicious activity
- Filter by time range

**Admin checks user security status:**
- Go to **User Security** tab
- Search for username
- View failed attempts counter and lock status
- Manually unlock if needed
- See recent IPs and attempt history

---

## Security Features

### Account Lockout
- **Trigger:** 5 consecutive failed login attempts
- **Duration:** 30 minutes
- **Status Code:** 423 (Locked)
- **Manual Unlock:** Super admin can unlock immediately via API
- **Reset:** Successful login clears counter

### IP Address Logging
- **Tracked:** Every login attempt (success & failure)
- **Source:** X-Real-IP, X-Forwarded-For header, or direct connection
- **Use Cases:**
  - Detect brute-force attacks from single IP
  - Track legitimate attempts from multiple IPs
  - Admin security analysis

### Rate Limiting
- **Global:** 10 login attempts per 15 minutes per IP
- **Returns:** 429 status with Retry-After header
- **Brute-force Protection:** Prevents automated attacks

### Email Required
- Profile can set email before first login (or after)
- Email optional initially (for bulk-created users)
- Required for password reset functionality

---

## Database Migrations (PostgreSQL)

### New Table: login_attempt
Created **automatically** by SQLAlchemy on app startup. The table definition:

```sql
-- Created automatically by api/models/login_attempt.py via create_all()
CREATE TABLE login_attempt (
  id SERIAL PRIMARY KEY,
  user_id INTEGER REFERENCES "user"(id) ON DELETE SET NULL,
  username VARCHAR(100) NOT NULL,
  ip_address VARCHAR(45) NOT NULL,
  success BOOLEAN NOT NULL,
  failure_reason VARCHAR(100),
  timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes created automatically by SQLAlchemy model
CREATE INDEX idx_login_attempt_user_id_timestamp 
  ON login_attempt(user_id, timestamp DESC);
CREATE INDEX idx_login_attempt_ip_address_timestamp 
  ON login_attempt(ip_address, timestamp DESC);
CREATE INDEX idx_login_attempt_username_timestamp 
  ON login_attempt(username, timestamp DESC);
```

### Updated Table: user
You **must run these ALTER statements manually** before deploying:

```sql
-- Make email nullable for bulk-created users
ALTER TABLE "user" ALTER COLUMN email DROP NOT NULL;

-- Add nickname column for display name customization
ALTER TABLE "user" ADD COLUMN nickname VARCHAR(100) NULL;
```

**Execute in PostgreSQL:**
```bash
psql -U postgres -d rankings_bot
```

Then paste:
```sql
ALTER TABLE "user" ALTER COLUMN email DROP NOT NULL;
ALTER TABLE "user" ADD COLUMN nickname VARCHAR(100) NULL;
```

**Verify with:**
```
\d "user"
```

Expected output shows:
- `email` column: nullable (no `NOT NULL`)
- `nickname` column: new column added

---

## Development Notes

### Environment Setup
Already configured in `.env.example`:
- Redis: `redis://redis:6379/0` (for Celery)
- Database: `postgresql://...` (existing)

### Rate Limiting
Uses `check_login_rate_limit(ip)` from `api.rate_limiter`:
- 10 attempts per 15 minutes per IP
- Returns (allowed: bool, wait_time: float)

### Thread Safety
- All database operations wrapped in try/except
- Rollback on error to prevent partial updates
- LoginAttempt records created immediately (fire-and-forget)

### Backward Compatibility
- Email field: nullable, defaults to None for bulk-created users
- Existing users unaffected (email stays as-is)
- Login endpoint: drop-in replacement with added security

---

## API Integration Checklist

- [x] LoginAttempt model (ORM with IP tracking)
- [x] User model updates (email optional, nickname)
- [x] Bulk user service (username generation, password generation, CSV export)
- [x] Admin security routes (bulk create, monitoring, unlock)
- [x] Login tracking service (lockout logic, attempt recording)
- [x] Auth endpoint updates (integrated security tracking)
- [x] Profile routes (nickname, email endpoints)
- [x] All routes imported and registered in main.py
- [x] No syntax errors (verified with get_errors)

---

## Testing Commands

### Create Users from CSV
```bash
curl -X POST http://localhost:8003/api/admin/users/bulk-create \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "players": [
      {"name": "John Smith", "fargo_rating": 800, "state": "CA", "fargo_id": 12345},
      {"name": "Jane Doe", "fargo_rating": 750, "state": "NY", "fargo_id": 12346}
    ]
  }'
```

### View Login Attempts (24h)
```bash
curl http://localhost:8003/api/admin/login-attempts?hours=24 \
  -H "Authorization: Bearer $TOKEN"
```

### View User Security Status
```bash
curl http://localhost:8003/api/admin/users/john_smith/security \
  -H "Authorization: Bearer $TOKEN"
```

### Unlock User Account
```bash
curl -X POST http://localhost:8003/api/admin/users/john_smith/unlock \
  -H "Authorization: Bearer $TOKEN"
```

### Update Profile Nickname
```bash
curl -X PUT http://localhost:8003/api/profile/nickname \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"nickname": "Johnny"}'
```

---

## Troubleshooting

### Password Not Generated
- Ensure `secrets` module available (standard library)
- Check character set includes uppercase, lowercase, digits, symbols

### Account Locked After First Login
- Check if timestamp format is correct (UTC)
- Ensure `datetime.utcnow()` is used consistently
- Check if admin can manually unlock via API

### CSV Export Empty
- Verify users created successfully (check response "created_count")
- Ensure export function iterates over all users
- Check CSV delimiter (should be comma)

### Email Update Failed
- Check email format validation (EmailStr)
- Verify email not already in use by another user
- Ensure user authenticated (Bearer token valid)

---

## Summary

This implementation provides a complete user management and security system:
1. **Bulk User Creation**: Auto-generate secure accounts from Fargo data
2. **CSV Export**: Distribute to WPA/WPBA presidents in standard format
3. **Profile Customization**: Email and display name management
4. **Login Security**: 5-attempt lockout with 30-minute enforced lock
5. **IP Tracking**: Monitor locations and detect suspicious activity
6. **Admin Dashboard**: Real-time monitoring and manual unlock capability

All components are production-ready with proper error handling, rate limiting, and audit logging.
