# Roles and Permissions

**→ [What each role can do (ROLE_CAPABILITIES.md)](ROLE_CAPABILITIES.md)** — list of capabilities per role (player, director, admin, super_admin).

This doc describes how roles work today and how to align with standard permission models (e.g. Discord, Rust) where **directors can also be players** and **players have a distinct player role**.

## Current state

- **Single role per user:** Each user has one `role` in the database: `user`, `director`, `moderator`, `admin`, or `super_admin`.
- **No explicit "player" role:** Whether someone is "a player" is inferred by **username**: if your login username appears as `player_name` in rankings/players data, you can access your own player performance. There is no `player` role in the DB.
- **Director vs player:** Today a director is never explicitly marked as "also a player." They get director capabilities (create tournaments, etc.) and, if their username matches a player name, they also get "own player" access—but that’s by name match, not by role.

So **today:** directors can effectively be "players" only if their username exists in the player/rankings data. There is no separate "player" role; "player" is implicit.

## What you want (and how it matches standards)

- **Directors may also be players** (have both director and player).
- **Players have a player role** and do **not** have director role (unless they are director+player).
- **Standards:** Discord and games like Rust use **multiple roles per user** and **additive permissions**: a user has a set of roles, and each permission is "user has **any** of these roles."

That maps to:

| Concept        | Discord/Rust style        | This app (goal)                    |
|----------------|---------------------------|------------------------------------|
| Roles          | User has many roles       | User can have director and/or player |
| Permission     | "Can do X" = has role A or B | "Can manage events" = director \| admin \| super_admin; "Is a player" = has player |
| Director+player| User has [Director, Player] | Director who is also a player has both roles |

## Two ways to get there

### Option A: Multiple roles per user (Discord-style, recommended for clarity)

- Add a **roles** model: e.g. `user_roles` table `(user_id, role)` with values like `player`, `director`, `moderator`, `admin`, `super_admin`. A user can have several rows (e.g. one for `director`, one for `player`).
- **Permissions:** Implement helpers like `user_has_role(user, "director")` and `user_has_role(user, "player")`. Existing checks become "has director or admin or super_admin" and "has player" where needed.
- **JWT:** Either put a list of roles in the token (e.g. `roles: ["director","player"]`) or keep a single "primary" role for backward compatibility and add a separate `is_player` claim derived from roles.
- **Migration:** Add `user_roles`, backfill from current `users.role` (one row per user with their current role), then add `player` role for users who are players (e.g. username in players/rankings or a new "link to player" flag). Optionally keep `users.role` as "primary" for display or legacy.

**Pros:** Clear, scalable, matches Discord/Rust; easy to add more roles later.  
**Cons:** Bigger change (new table, all permission checks updated, login/me response changed).

### Option B: Single staff role + "is player" flag (simpler)

- Keep **one** `role` on `users` for **staff level**: `user`, `director`, `moderator`, `admin`, `super_admin`.
- Add **`is_player`** boolean (or a `player_id` FK to your players table if you have one). "Is a player" = `is_player` is true (or user has a linked player record).
- **Director who is also a player:** `role = director` and `is_player = true`. **Player only:** `role = user` and `is_player = true`.
- Permissions stay as today for staff; for "can view own performance" / "is a player" you use `is_player` (or link to player) instead of only username match.

**Pros:** Small schema change, minimal code changes.  
**Cons:** Only two "dimensions" (staff role + player). Adding more dimensions (e.g. "referee") would need more flags or a move to Option A.

## Recommendation

- If you want **one clear "player" role** and the ability to have **director + player** (and later more combinations), **Option A (multiple roles)** is the right long-term model and matches Discord/Rust.
- If you only need "directors can be players" and "players are non-directors unless they’re also directors," **Option B** is enough and is quicker to ship.

## Summary

| Question | Current state | With Option A | With Option B |
|----------|----------------|----------------|----------------|
| Do directors have a "player" role? | No; only if username matches player | Yes; user can have both director and player roles | Yes; director with `is_player=true` |
| Do players have a player role? | No; inferred by username | Yes; explicit `player` role | Yes; `is_player` (or player link) |
| Standards (Discord/Rust-style)? | Single role, no player role | Yes; multiple roles, additive permissions | Partial; two dimensions only |

Implementing Option A requires a migration (e.g. `user_roles`), backfill, and updating auth + permission checks. Implementing Option B requires adding `is_player` (and optionally a player link) and using it wherever "is this user a player?" is needed.
