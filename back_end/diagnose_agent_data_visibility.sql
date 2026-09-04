-- Run this whole file in Supabase SQL Editor as the postgres/project owner.
-- It does not modify data or permissions.

-- 1) Confirm which database/project the SQL Editor is connected to.
SELECT
    current_database() AS database_name,
    current_user AS executing_user,
    current_schema() AS schema_name,
    inet_server_addr() AS server_address;

-- 2) Count as the owner (what Table Editor normally sees).
SELECT
    (SELECT count(*) FROM public.games) AS games_as_owner,
    (SELECT count(*) FROM public.reviews) AS reviews_as_owner;

-- 3) Check table grants and RLS configuration.
SELECT
    c.relname AS table_name,
    c.relrowsecurity AS rls_enabled,
    c.relforcerowsecurity AS rls_forced,
    has_table_privilege('steam_readonly', c.oid, 'SELECT') AS readonly_has_select
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public'
  AND c.relname IN (
      'games', 'reviews', 'users', 'genres', 'categories', 'languages',
      'game_genres', 'game_categories', 'game_languages'
  )
ORDER BY c.relname;

-- 4) Show policies and the roles to which they apply.
SELECT schemaname, tablename, policyname, permissive, roles, cmd, qual
FROM pg_policies
WHERE schemaname = 'public'
  AND tablename IN (
      'games', 'reviews', 'users', 'genres', 'categories', 'languages',
      'game_genres', 'game_categories', 'game_languages'
  )
ORDER BY tablename, policyname;

-- Supabase's SQL Editor role is not necessarily a member of custom login
-- roles, so SET ROLE steam_readonly can fail even though that login works.
-- Verify the effective row count through the backend connection instead.
SELECT
    has_schema_privilege('steam_readonly', 'public', 'USAGE') AS has_schema_usage,
    has_table_privilege('steam_readonly', 'public.games', 'SELECT') AS can_select_games,
    has_table_privilege('steam_readonly', 'public.reviews', 'SELECT') AS can_select_reviews;
