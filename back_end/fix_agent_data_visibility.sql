-- Run in Supabase SQL Editor as the postgres/project owner.
-- Purpose: let steam_readonly SELECT the global Steam catalogue through RLS.
-- It does NOT grant access to app_users, auth/RBAC, tokens, or agent traces.

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
            EXECUTE format(
                'GRANT SELECT ON TABLE public.%I TO steam_readonly',
                v_table_name
            );

            -- A GRANT is not enough when RLS is enabled. Add a SELECT-only,
            -- role-specific policy without giving the role BYPASSRLS.
            v_policy_name := 'steam_readonly_select_' || v_table_name;
            IF NOT EXISTS (
                SELECT 1
                FROM pg_policies p
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

-- SQL Editor cannot reliably SET ROLE to a custom login on Supabase hosted.
-- Verify grants/policies here, then verify the row count using the backend's
-- real DATABASE_URL_READONLY connection.
SELECT
    has_schema_privilege('steam_readonly', 'public', 'USAGE') AS has_schema_usage,
    has_table_privilege('steam_readonly', 'public.games', 'SELECT') AS can_select_games,
    has_table_privilege('steam_readonly', 'public.reviews', 'SELECT') AS can_select_reviews;

SELECT tablename, policyname, roles, cmd, qual
FROM pg_policies
WHERE schemaname = 'public'
  AND policyname LIKE 'steam_readonly_select_%'
ORDER BY tablename;
