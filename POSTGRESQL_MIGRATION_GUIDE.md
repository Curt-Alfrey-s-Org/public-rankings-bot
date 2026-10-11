# PostgreSQL Migration Guide - User Management System

## Overview

This guide explains how to migrate your PostgreSQL database to support the new user management and security features.

## Before You Start

- **Database:** PostgreSQL (required)
- **Backup:** Take a backup of your database before migrations
- **Access:** You'll need PostgreSQL superuser or equivalent access
- **Downtime:** Minimal - ALTER TABLE operations are fast

## Migration Strategy

### Tables to Create (Automatic)
- `login_attempt` - Created automatically by SQLAlchemy's `create_all()` when app starts
  - No manual SQL needed
  - Includes automatic indexes

### Columns to Add (Manual)
- `user.nickname` - Display name for rankings
- `user.email` - Make nullable (was required, now optional)

## Step 1: Backup Your Database

```bash
# Create a backup before migration
pg_dump -U postgres rankings_bot > backup_before_migration.sql

# Verify backup
ls -lh backup_before_migration.sql
```

## Step 2: Run ALTER TABLE Statements

Connect to PostgreSQL:

```bash
psql -U postgres -d rankings_bot
```

Then execute:

```sql
-- Step 1: Make email nullable (allows NULL for bulk-created users)
ALTER TABLE "user" ALTER COLUMN email DROP NOT NULL;

-- Step 2: Add nickname column (display name for rankings)
ALTER TABLE "user" ADD COLUMN nickname VARCHAR(100) NULL;
```

**Verify the changes:**

```sql
-- Check the user table has been updated correctly
\d "user"
```

You should see:
```
 Attribute       |          Type          | Nullable | Default
-----------------+------------------------+----------+---------
 id              | integer                | not null | 
 username        | character varying(100) | not null | 
 email           | character varying(255) |          | 
 nickname        | character varying(100) |          | 
 password_hash   | character varying      | not null | 
 ...
```

Note:
- `email` column now shows empty under "Nullable" (it's nullable)
- `nickname` column is new and nullable

## Step 3: Verify login_attempt Table (Post-Deployment)

After deploying the app, the `login_attempt` table will be created automatically.

Check that it exists:

```bash
psql -U postgres -d rankings_bot -c "\dt login_attempt"
```

You should see:
```
           List of relations
 Schema |       Name       | Type  | Owner
--------+------------------+-------+-------
 public | login_attempt    | table | postgres
```

If not, check the API logs for errors:
```bash
docker-compose logs api
```

## Step 4: Verify Data

Check that tables have the correct structure:

```sql
-- Verify user table modifications
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'user' AND column_name IN ('email', 'nickname');
```

Expected output:
```
 column_name | data_type           | is_nullable
-------------+---------------------+-------------
 email       | character varying   | YES
 nickname    | character varying   | YES
```

## Rollback Plan

If something goes wrong, you can rollback:

```bash
# Restore from backup
psql -U postgres -d rankings_bot < backup_before_migration.sql
```

Or manually revert:

```sql
-- Remove nickname column
ALTER TABLE "user" DROP COLUMN nickname;

-- Make email required again
ALTER TABLE "user" ALTER COLUMN email SET NOT NULL;

-- Drop login_attempt table (if auto-created)
DROP TABLE IF EXISTS login_attempt CASCADE;
```

## Troubleshooting

### "relation 'user' does not exist"

The `user` table name might be quoted differently. Try:

```sql
-- List all tables to find the exact name
\dt

-- Then use the correct name
\d your_actual_table_name
```

### "column 'email' of relation 'user' is already nullable"

This means the migration was already applied. This is OK - no action needed.

### "column 'nickname' already exists"

The migration was already applied. This is OK - no action needed.

### "ALTER TABLE permission denied"

You need superuser or table owner permissions:

```bash
# Run as superuser
psql -U postgres -d rankings_bot
```

Or grant permissions:

```sql
-- As superuser, grant to your user
GRANT ALTER ON TABLE "user" TO your_username;
```

## Post-Migration Verification

Run these checks to verify everything is working:

```sql
-- 1. Check user table structure
\d "user"

-- 2. Verify email is nullable
SELECT COUNT(*) FROM "user" WHERE email IS NULL;

-- 3. Verify nickname column exists
SELECT COUNT(nickname) FROM "user";

-- 4. After deployment, check login_attempt table
\dt login_attempt

-- 5. Verify indexes on login_attempt exist
\di login_attempt*
```

## Performance Notes

- `ALTER TABLE` operations are fast (< 1 second)
- Adding nullable columns doesn't require table rewrite
- Indexes on `login_attempt` are created by SQLAlchemy automatically

## Timeline

| Step | Time | Action |
|------|------|--------|
| 1 | 2 min | Backup database |
| 2 | 1 min | Run ALTER statements |
| 3 | Immediate | Deploy new app code |
| 4 | 5 sec | Verify tables (app creates login_attempt) |
| 5 | 5 min | Run verification queries |

**Total:** ~10 minutes

## Support

If you encounter issues:

1. Check the API logs: `docker-compose logs api`
2. Verify database connectivity: `psql -U postgres -d rankings_bot`
3. Review this guide's troubleshooting section
4. Inspect the database directly for any schema mismatches

---

**Version:** 1.0 (February 2026)  
**Database:** PostgreSQL 12+  
**Last Updated:** During User Management System Deployment
