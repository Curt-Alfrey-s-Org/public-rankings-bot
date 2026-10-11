# What each role can do

Users can have **multiple roles** (e.g. player + director + admin). Permissions are additive: if you have the role, you can do that role’s actions.

---

## Player

- Log in and use the app.
- View **own** player performance (stats, history, tournaments) when their account is linked to a player name in rankings.
- View rankings, leaderboard, tournament history, head-to-head (own data).
- Use AI Coach (pointers-only unless they also have admin).

**Does not:** Create tournaments, create players, manage users, or see other players’ performance.

---

## Director

Everything **Player** can do, plus:

- Create and edit **tournaments**.
- Create players (from ranking or manual).
- Data input (enter results, run events).
- Manage tournament definitions, Fargo sync for director use.
- Access Data Input, Tournament Wizard, Player Management (create/dedupe).

**Does not:** Manage user accounts, change roles, rebuild website, Covert Ops, or see all players’ performance.

---

## Admin

Everything **Director** can do, plus:

- **User management:** List users, create users, update user roles (admin, director, moderator, user — not super_admin).
- **App management:** Rebuild website, rebuild all images, view rebuild log.
- **Rankings:** Refresh rankings, backup, verify-and-populate.
- **Visibility:** See **all** player performance (not just own).
- **AI Coach:** Full analysis (not just pointers).
- **Covert Ops:** Recon and admin-only tools.
- **Appearance:** Set default avatar/background for the site.
- **Settings:** Admin Settings, Health/Logs.

**Does not:** Create or assign **super_admin** (super_admin only).

---

## Super admin

Everything **Admin** can do, plus:

- Create and assign **super_admin** role (other super_admins).
- Bootstrap / first-user setup (e.g. from env).

---

## Moderator

Exists in the DB; currently treated like **director** for permissions (director-or-admin checks). Can be given distinct capabilities later (e.g. moderate content, no tournament create).

---

## Quick reference

| Capability                     | Player | Director | Admin | Super admin |
|--------------------------------|--------|----------|--------|-------------|
| View own performance           | ✅     | ✅       | ✅     | ✅          |
| View all players’ performance  | ❌     | ❌       | ✅     | ✅          |
| Create / edit tournaments      | ❌     | ✅       | ✅     | ✅          |
| Create players                 | ❌     | ✅       | ✅     | ✅          |
| Data input                     | ❌     | ✅       | ✅     | ✅          |
| User management                | ❌     | ❌       | ✅*    | ✅          |
| Rebuild website / images       | ❌     | ❌       | ✅     | ✅          |
| Covert Ops                     | ❌     | ❌       | ✅     | ✅          |
| Create super_admin             | ❌     | ❌       | ❌     | ✅          |

\* Admin can set roles: user, director, moderator, admin (not super_admin).
