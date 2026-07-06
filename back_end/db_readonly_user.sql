-- ============================================================================
-- Read-Only Database User for AI SQL Execution
-- ----------------------------------------------------------------------------
-- Creates a dedicated read-only user that can only SELECT from all tables
-- in the public schema. This is defense-in-depth for the AI SQL execution
-- feature (ai_service.py / data_service.py).
--
-- Usage on Supabase:
--   1. Run this script in Supabase SQL Editor (as postgres superuser)
--   2. Set DATABASE_URL_READONLY in backend .env to use this user
--   3. Update session.py to use read-only connection for AI queries
-- ============================================================================

-- 1) Create read-only role
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'steam_readonly') THEN
        CREATE ROLE steam_readonly
            LOGIN
            NOINHERIT
            CONNECTION LIMIT 5
            PASSWORD 'CHANGE_ME_TO_A_STRONG_PASSWORD';
    END IF;
END
$$;

-- 2) Grant USAGE on schema
GRANT USAGE ON SCHEMA public TO steam_readonly;

-- 3) Grant SELECT on all existing tables
GRANT SELECT ON ALL TABLES IN SCHEMA public TO steam_readonly;

-- 4) Grant SELECT on all sequences
GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO steam_readonly;

-- 5) Default privileges for future tables
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    GRANT SELECT ON TABLES TO steam_readonly;

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    GRANT SELECT ON SEQUENCES TO steam_readonly;

-- 6) Revoke write permissions (defense-in-depth)
REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER
    ON ALL TABLES IN SCHEMA public FROM steam_readonly;

REVOKE CREATE, ALTER, DROP ON SCHEMA public FROM steam_readonly;

-- 7) Verify permissions
SELECT grantee, table_name, privilege_type
FROM information_schema.role_table_grants
WHERE grantee = 'steam_readonly' AND table_schema = 'public'
ORDER BY table_name, privilege_type;
