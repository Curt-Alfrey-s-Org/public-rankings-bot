-- Test Center PostgreSQL init (standalone instance: postgres-testcenter service).
-- 01: extensions. Full table bootstrap follows in 02-schema_testcenter_bootstrap.sql

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
