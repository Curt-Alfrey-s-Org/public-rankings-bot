# Rankings Bot Authentication Refactoring - Summary

## Objective
Refactor the Rankings Bot login system to **remove guest/public access** and only allow **players, directors, and admin accounts**.

## Changes Completed

### 1. Backend Authentication System

#### File: [api/auth.py](api/auth.py)
**Changes:**
- **Removed:** `"guest"` role from `Role` type definition
- **Added:** `"player"` role to `Role` type definition
- Updated `Role = Literal["guest", "admin", "director"]` → `Role = Literal["player", "admin", "director"]`
- Updated role validation in `get_current_user()` to recognize `"player"` instead of `"guest"`
- Added three new functions for player credential validation:
  - `get_player_username()` - Returns PLAYER_USERNAME env var (default: "player")
  - `get_player_password_hash()` - Returns PLAYER_PASSWORD_HASH env var if set
  - `check_player_password()` - Validates player credentials against PLAYER_USERNAME and PLAYER_PASSWORD env vars
- Updated module docstring to reflect new roles

#### File: [api/routes/auth.py](api/routes/auth.py)
**Changes:**
- Added import: `check_player_password`
- **Removed:** `/auth/guest` endpoint
- **Added:** `/auth/player` endpoint (POST)
  - Requires username and password credentials
  - Returns JWT token with role: `"player"`
- Updated endpoints documentation in module docstring

### 2. Frontend Authentication

#### File: [frontend/src/api/auth.ts](frontend/src/api/auth.ts)
**Changes:**
- Updated module comment from "login (admin), director, guest, me" → "login (admin), director, player, me"
- **Removed:** `guest()` method that made unauthenticated POST to `/auth/guest`
- **Added:** `playerLogin(username: string, password: string)` method
  - Makes authenticated POST request to `/auth/player` with credentials
  - Returns TokenResponse with bearer token and role

#### File: [frontend/src/contexts/AuthContext.tsx](frontend/src/contexts/AuthContext.tsx)
**Changes:**
- Updated `AuthContextValue` interface:
  - Removed: `guestLogin: () => Promise<void>`
  - Added: `playerLogin: (username: string, password: string) => Promise<void>`
  - Added: `isPlayer: boolean` helper property
- Replaced `guestLogin` callback with `playerLogin` callback in `AuthProvider`
- Updated computed properties:
  - Added: `isPlayer: user?.role === 'player'`
- Updated useMemo dependency array to include `playerLogin`

### 3. Docker Configuration

#### File: [docker-compose.yml](Rankings-Bot/docker-compose.yml)
**Changes:**
- Added environment variables for all three roles:
  ```yaml
  - ADMIN_USERNAME=admin
  - ADMIN_PASSWORD=admin123
  - DIRECTOR_USERNAME=director
  - DIRECTOR_PASSWORD=director123
  - PLAYER_USERNAME=player
  - PLAYER_PASSWORD=player123
  ```

## Test Results

### Authentication Endpoints
| Endpoint | Method | Credentials | Status | Response Role |
|----------|--------|-------------|--------|---------------|
| `/api/auth/login` | POST | admin/admin123 | ✓ Working | `admin` |
| `/api/auth/director` | POST | director/director123 | ✓ Working | `director` |
| `/api/auth/player` | POST | player/player123 | ✓ Working | `player` |
| `/api/auth/guest` | POST | (none) | ✗ Removed | "Method Not Allowed" |

### JWT Token Validation
- Player token payload contains correct role: `"role": "player"`
- `/api/auth/me` endpoint correctly returns player role
- Token expiration: 7 days (604800 seconds)

## Access Control

### Before Refactoring
- **Guest:** View-only access, no credentials required
- **Player:** N/A
- **Director:** Data input access, requires credentials
- **Admin:** Full access, requires credentials

### After Refactoring
- **Guest:** ✗ Removed (no unauthenticated access)
- **Player:** ✓ Added - Read-only access, requires credentials (username/password)
- **Director:** ✓ Unchanged - Data input access, requires credentials
- **Admin:** ✓ Unchanged - Full access, requires credentials

## Access Requirements

### Protected Endpoints
All existing role-based access controls remain functional:
- `@Depends(require_admin)` - Admin role only
- `@Depends(require_director_or_admin)` - Director or Admin roles
- `@Depends(get_current_user)` - Any authenticated user (player, director, or admin)

### Default Credentials
```
Player:    player / player123
Director:  director / director123
Admin:     admin / admin123
```

## Security Improvements

1. **No Guest Access:** Removed public/unauthenticated access to the rankings bot
2. **Required Authentication:** All users must authenticate with valid credentials
3. **Role-Based Access:** Clear separation between players, directors, and administrators
4. **JWT Tokens:** 7-day expiring JWT tokens with role-based claims

## Deployment

### Docker Image Rebuild
```bash
cd /home/ansible/rankings-bot
sudo docker-compose down
sudo docker-compose build --no-cache
sudo docker-compose up -d
```

### Container Status
- **Image:** rankings-bot_rankings-bot-api:latest
- **Container:** rankings-bot-api
- **Port:** 127.0.0.1:8003 (host) → 8000 (container)
- **Status:** ✓ Running

## Migration Notes

### For Existing Users
- **Previous Guest Users:** Must now login with player credentials or upgrade to director/admin roles
- **Frontend:** No more "Guest Login" button - replaced with "Player Login" requiring credentials
- **Stored Tokens:** Old guest tokens will be invalid; users must re-login with player credentials

### For Developers
- Role enum changed from `["guest", "admin", "director"]` to `["player", "admin", "director"]`
- API endpoint `/api/auth/guest` removed
- New endpoint `/api/auth/player` for authenticated read-only users

## Files Modified
1. `/home/ansible/rankings-bot/api/auth.py` ✓
2. `/home/ansible/rankings-bot/api/routes/auth.py` ✓
3. `/home/ansible/rankings-bot/frontend/src/api/auth.ts` ✓
4. `/home/ansible/rankings-bot/frontend/src/contexts/AuthContext.tsx` ✓
5. `/home/ansible/rankings-bot/docker-compose.yml` ✓

## Verification
All auth endpoints tested and working correctly:
- ✓ Player login successful
- ✓ Director login successful
- ✓ Admin login successful
- ✓ Guest login removed and returns "Method Not Allowed"
- ✓ JWT tokens contain correct roles
- ✓ `/api/auth/me` endpoint validates correctly

---
**Completed:** 2025-02-05
**Status:** ✓ Production Ready
