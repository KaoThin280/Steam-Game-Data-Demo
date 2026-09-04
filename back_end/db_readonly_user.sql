-- ============================================================================
-- Read-Only Database User for AI SQL Execution
-- ----------------------------------------------------------------------------
-- Creates a dedicated read-only user that can SELECT only the explicitly
-- allowlisted Steam data tables. It cannot read auth, RBAC or agent trace data.
--
-- Usage on Supabase:
--   1. Run this script in Supabase SQL Editor (as postgres superuser)
--   2. Set DATABASE_URL_READONLY in backend .env to use this user
--   3. Set DATABASE_URL_READONLY on the backend and redeploy
-- ============================================================================

-- 1) Create read-only role
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'steam_readonly') THEN
        CREATE ROLE steam_readonly
            NOLOGIN
            NOINHERIT
            CONNECTION LIMIT 5;
    END IF;
END
$$;

-- REQUIRED after replacing the placeholder locally, then execute separately:
-- ALTER ROLE steam_readonly LOGIN PASSWORD 'GENERATE_A_LONG_RANDOM_PASSWORD';

-- 2) Grant USAGE on schema
GRANT USAGE ON SCHEMA public TO steam_readonly;

-- 3) Reset broad grants from older versions of this script. The agent must not
-- read app_users, auth/refresh tokens, RBAC tables, or its own event traces.
REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM steam_readonly;
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM steam_readonly;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    REVOKE ALL ON TABLES FROM steam_readonly;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    REVOKE ALL ON SEQUENCES FROM steam_readonly;

-- 4) Explicit data-plane allowlist. Missing optional tables are skipped.
DO $$
DECLARE
    table_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'games', 'reviews', 'users', 'genres', 'categories', 'languages',
        'game_genres', 'game_categories', 'game_languages'
    ]
    LOOP
        IF to_regclass('public.' || table_name) IS NOT NULL THEN
            EXECUTE format('GRANT SELECT ON TABLE public.%I TO steam_readonly', table_name);
        END IF;
    END LOOP;
END $$;

-- 4b) Supabase tables may have RLS enabled. A table-level GRANT alone does
-- not make rows visible through RLS, so add SELECT-only policies for this
-- dedicated role. Do not give the role BYPASSRLS.
DO $$
DECLARE
    v_table_name text;
    v_policy_name text;
BEGIN
    FOREACH v_table_name IN ARRAY ARRAY[
        'games', 'reviews', 'users', 'genres', 'categories', 'languages',
        'game_genres', 'game_categories', 'game_languages'
    ]
    LOOP
        IF to_regclass('public.' || v_table_name) IS NOT NULL THEN
            v_policy_name := 'steam_readonly_select_' || v_table_name;
            IF NOT EXISTS (
                SELECT 1 FROM pg_policies p
                WHERE p.schemaname = 'public'
                  AND p.tablename = v_table_name
                  AND p.policyname = v_policy_name
            ) THEN
                EXECUTE format(
                    'CREATE POLICY %I ON public.%I FOR SELECT TO steam_readonly USING (true)',
                    v_policy_name,
                    v_table_name
                );
            END IF;
        END IF;
    END LOOP;
END $$;

-- 5) Revoke all write/schema permissions (defense-in-depth)
REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER
    ON ALL TABLES IN SCHEMA public FROM steam_readonly;

REVOKE CREATE ON SCHEMA public FROM steam_readonly;

-- 6) Verify the final allowlist
SELECT grantee, table_name, privilege_type
FROM information_schema.role_table_grants
WHERE grantee = 'steam_readonly' AND table_schema = 'public'
ORDER BY table_name, privilege_type;
