-- ============================================================================
-- Steam Game Data Demo - Database Schema (Supabase Free Tier)
-- ----------------------------------------------------------------------------
-- Aligned with SCHEMA_DOCUMENTATION.md:
--   - public.games     (Steam game metadata, flattened)
--   - public.users     (Steam reviewers)
--   - public.reviews   (Steam reviews)
--   - public.roles / public.permissions / public.role_permissions
--   - public.app_users / public.user_roles
--   - public.refresh_tokens  (auth)
--   - public.chat_histories  (AI agent sessions)
--   - public.ai_chart_history (Charting tool logs)
--
-- Designed to fit ~500MB Supabase free-tier storage for ~10,000 games
-- and ~169,000 reviews (according to the project spec).
-- ============================================================================

-- Ensure pgcrypto for gen_random_uuid (used by app_users.id default only if needed)
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ============================================================================
-- 1) ROLES & PERMISSIONS (RBAC)
-- ============================================================================
CREATE TABLE IF NOT EXISTS roles (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    role_name    TEXT UNIQUE NOT NULL,
    description  TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS permissions (
    id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    permission_name  TEXT UNIQUE NOT NULL,
    description      TEXT,
    resource         TEXT,
    action           TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS role_permissions (
    role_id        BIGINT NOT NULL REFERENCES roles(id)        ON DELETE CASCADE,
    permission_id  BIGINT NOT NULL REFERENCES permissions(id)  ON DELETE CASCADE,
    PRIMARY KEY (role_id, permission_id)
);

-- Seed default roles
INSERT INTO roles (role_name, description) VALUES
    ('admin',     'System administrator with full access.'),
    ('analyst',   'Read-only data analyst.'),
    ('scientist', 'Data scientist with read/write access (no delete).'),
    ('viewer',    'Guest visitor with basic read-only access.')
ON CONFLICT (role_name) DO NOTHING;

-- Seed default permissions
INSERT INTO permissions (permission_name, description, resource, action) VALUES
    ('games_read',          'Read game metadata',              'games',   'read'),
    ('games_write',         'Insert / update game metadata',   'games',   'write'),
    ('games_delete',        'Delete game metadata',            'games',   'delete'),
    ('reviews_read',        'Read user reviews',               'reviews', 'read'),
    ('reviews_write',       'Insert / update user reviews',    'reviews', 'write'),
    ('reviews_delete',      'Delete user reviews',             'reviews', 'delete'),
    ('users_read',          'Read reviewer profiles',          'users',   'read'),
    ('users_write',         'Insert / update reviewer profiles','users',  'write'),
    ('users_delete',        'Delete reviewer profiles',        'users',   'delete'),
    ('users_manage_roles',  'Manage application user roles',   'app_users','manage_roles'),
    ('system_admin',        'Full system administration',      'system',  'admin')
ON CONFLICT (permission_name) DO NOTHING;

-- Assign permission matrix
-- admin: everything
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.role_name = 'admin'
ON CONFLICT DO NOTHING;

-- analyst: read-only across games/reviews/users
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.role_name = 'analyst'
  AND p.permission_name IN (
    'games_read','reviews_read','users_read'
)
ON CONFLICT DO NOTHING;

-- scientist: read + write (no delete, no user-management)
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.role_name = 'scientist'
  AND p.permission_name IN (
    'games_read','games_write',
    'reviews_read','reviews_write',
    'users_read','users_write'
)
ON CONFLICT DO NOTHING;

-- viewer: basic read games + reviews
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.role_name = 'viewer'
  AND p.permission_name IN ('games_read','reviews_read')
ON CONFLICT DO NOTHING;

-- ============================================================================
-- 2) APPLICATION USERS (auth, RBAC)
-- ============================================================================
CREATE TABLE IF NOT EXISTS app_users (
    id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    username       TEXT UNIQUE NOT NULL,
    email          TEXT UNIQUE NOT NULL,
    password_hash  TEXT NOT NULL,
    full_name      TEXT,
    is_active      BOOLEAN NOT NULL DEFAULT TRUE,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_login     TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_app_users_email  ON app_users(email);
CREATE INDEX IF NOT EXISTS idx_app_users_active ON app_users(is_active);

CREATE TABLE IF NOT EXISTS user_roles (
    user_id     BIGINT NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
    role_id     BIGINT NOT NULL REFERENCES roles(id)     ON DELETE CASCADE,
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, role_id)
);

-- ============================================================================
-- 3) REFRESH TOKENS (revoke support for JWT)
-- ============================================================================
CREATE TABLE IF NOT EXISTS refresh_tokens (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id    BIGINT NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
    token      TEXT UNIQUE NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    is_revoked BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_refresh_user    ON refresh_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_refresh_expires ON refresh_tokens(expires_at);

-- ============================================================================
-- 4) STEAM GAMES (flattened metadata)
-- ----------------------------------------------------------------------------
-- Comma-separated TEXT for array-like fields (publishers, developers) only.
-- (2026-Q2) Cột CSV supported_languages / categories / genres đã được
-- loại bỏ để tiết kiệm storage. Nếu cần phân tích theo ngôn ngữ / category /
-- genre, bổ sung các bảng junction riêng sau.
-- ============================================================================
CREATE TABLE IF NOT EXISTS games (
    steam_appid          INTEGER PRIMARY KEY,
    name                 TEXT NOT NULL,
    is_free              BOOLEAN NOT NULL DEFAULT FALSE,
    required_age         INTEGER NOT NULL DEFAULT 0,
    release_date         DATE,
    publishers           TEXT,
    developers           TEXT,
    price_text           TEXT,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_games_name    ON games(name);
CREATE INDEX IF NOT EXISTS idx_games_is_free ON games(is_free);
CREATE INDEX IF NOT EXISTS idx_games_release ON games(release_date);

-- ============================================================================
-- 5) STEAM USERS (reviewers, from Steam public profile data)
-- ============================================================================
CREATE TABLE IF NOT EXISTS users (
    steamid         BIGINT PRIMARY KEY,
    personaname     TEXT,
    num_games_owned INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_users_personaname ON users(personaname);

-- ============================================================================
-- 6) REVIEWS
-- ============================================================================
CREATE TABLE IF NOT EXISTS reviews (
    recommendationid           BIGINT PRIMARY KEY,
    steam_appid                INTEGER NOT NULL REFERENCES games(steam_appid) ON DELETE CASCADE,
    steamid                    BIGINT  NOT NULL REFERENCES users(steamid)    ON DELETE CASCADE,
    language                   TEXT,
    review_text                TEXT,
    timestamp_created          TIMESTAMPTZ,
    timestamp_updated          TIMESTAMPTZ,
    refunded                   BOOLEAN NOT NULL DEFAULT FALSE,
    received_for_free          BOOLEAN NOT NULL DEFAULT FALSE,
    written_during_early_access BOOLEAN NOT NULL DEFAULT FALSE,
    primarily_steam_deck       BOOLEAN NOT NULL DEFAULT FALSE,
    playtime_at_review         INTEGER NOT NULL DEFAULT 0,
    playtime_last_two_weeks    INTEGER NOT NULL DEFAULT 0,
    playtime_forever           INTEGER NOT NULL DEFAULT 0,
    created_at                 TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_reviews_appid    ON reviews(steam_appid);
CREATE INDEX IF NOT EXISTS idx_reviews_steamid  ON reviews(steamid);
CREATE INDEX IF NOT EXISTS idx_reviews_language ON reviews(language);
CREATE INDEX IF NOT EXISTS idx_reviews_created  ON reviews(timestamp_created);
CREATE INDEX IF NOT EXISTS idx_reviews_voted    ON reviews(steam_appid, refunded);

-- ============================================================================
-- 7) AI CHAT HISTORY
-- ============================================================================
CREATE TABLE IF NOT EXISTS chat_histories (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id    BIGINT NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
    session_id TEXT NOT NULL,
    role       TEXT NOT NULL CHECK (role IN ('user','assistant','system','tool')),
    content    TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_chat_user_session ON chat_histories(user_id, session_id, created_at DESC);

-- ============================================================================
-- 8) AI CHART HISTORY (Charting tool: render config produced by the model)
-- ============================================================================
CREATE TABLE IF NOT EXISTS ai_chart_history (
    id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id        BIGINT NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
    session_id     TEXT NOT NULL,
    chart_type     TEXT NOT NULL,                -- 'bar','line','pie','scatter','area','radar'
    chart_title    TEXT,
    x_axis_label   TEXT,
    y_axis_label   TEXT,
    series_label   TEXT,
    config         JSONB NOT NULL,               -- chartjs-ready config (safe subset)
    source_query   TEXT,                        -- optional SQL the chart is based on
    created_at     TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_chart_user_session ON ai_chart_history(user_id, session_id, created_at DESC);

-- ============================================================================
-- 9) updated_at trigger helper
-- ============================================================================
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
DECLARE t TEXT;
BEGIN
    FOR t IN SELECT unnest(ARRAY['app_users'])
    LOOP
        EXECUTE format('DROP TRIGGER IF EXISTS trg_%I_set_updated_at ON %I', t, t);
        EXECUTE format('CREATE TRIGGER trg_%I_set_updated_at BEFORE UPDATE ON %I
                        FOR EACH ROW EXECUTE FUNCTION set_updated_at()', t, t);
    END LOOP;
END $$;

-- ============================================================================
-- 10) Verify
-- ============================================================================
SELECT 'Schema ready' AS status;
SELECT table_name,
       pg_size_pretty(pg_total_relation_size(quote_ident(table_name))) AS total_size
FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY pg_total_relation_size(quote_ident(table_name)) DESC;