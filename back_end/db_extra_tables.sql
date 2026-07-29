-- ============================================================================
-- Steam Game Data Demo - Extra tables (đã có sẵn trên Supabase)
-- ----------------------------------------------------------------------------
-- File này CHỈ chứa các bảng CHƯA có sẵn. Các bảng sau đã được tạo sẵn
-- (KHÔNG tạo lại trong file này):
--   app_users, games, permissions, reviews, role_permissions, roles,
--   user_roles, users
--
-- Nội dung file này:
--   1) public.refresh_tokens      (JWT refresh tokens, phục vụ revoke)
--   2) public.chat_histories      (lịch sử chat với AI Agent)
--   3) public.ai_chart_history    (lưu config Chart.js do model sinh ra)
--   4) updated_at trigger cho app_users (nếu bảng đã có updated_at thì bỏ qua)
--
-- Cách chạy: mở Supabase SQL Editor -> dán nội dung file này -> Run
-- ============================================================================

-- ============================================================================
-- 1) public.refresh_tokens
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
-- 2) public.chat_histories  (lịch sử chat AI Agent)
-- ============================================================================
CREATE TABLE IF NOT EXISTS chat_histories (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id    BIGINT NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
    session_id TEXT NOT NULL,
    role       TEXT NOT NULL CHECK (role IN ('user','assistant','system','tool')),
    content    TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_chat_user_session
    ON chat_histories(user_id, session_id, created_at DESC);

-- ============================================================================
-- 3) public.ai_chart_history  (Charting tool - config Chart.js do model sinh)
-- ============================================================================
CREATE TABLE IF NOT EXISTS ai_chart_history (
    id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id        BIGINT NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
    session_id     TEXT NOT NULL,
    chart_type     TEXT NOT NULL,                  -- bar | line | pie | doughnut | scatter | radar | area | polarArea
    chart_title    TEXT,
    x_axis_label   TEXT,
    y_axis_label   TEXT,
    series_label   TEXT,
    config         JSONB NOT NULL,                 -- Chart.js-ready config (safe subset)
    source_query   TEXT,                          -- optional SQL the chart is based on
    description    TEXT,                          -- NLP description for chart caching & reuse
    created_at     TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_chart_user_session
    ON ai_chart_history(user_id, session_id, created_at DESC);

-- ============================================================================
-- 4) Trigger tự động cập nhật updated_at cho app_users (idempotent)
-- ----------------------------------------------------------------------------
-- Nếu bảng app_users chưa có cột updated_at, bỏ qua phần này (không lỗi).
-- ============================================================================
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name   = 'app_users'
          AND column_name  = 'updated_at'
    ) THEN
        CREATE OR REPLACE FUNCTION set_updated_at()
        RETURNS TRIGGER AS $fn$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $fn$ LANGUAGE plpgsql;

        DROP TRIGGER IF EXISTS trg_app_users_set_updated_at ON app_users;
        CREATE TRIGGER trg_app_users_set_updated_at
        BEFORE UPDATE ON app_users
        FOR EACH ROW EXECUTE FUNCTION set_updated_at();
    END IF;
END $$;

-- ============================================================================
-- 5) Verify
-- ============================================================================
SELECT 'Extra tables ready' AS status;
SELECT table_name,
       pg_size_pretty(pg_total_relation_size(quote_ident(table_name))) AS total_size
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN ('refresh_tokens', 'chat_histories', 'ai_chart_history')
ORDER BY pg_total_relation_size(quote_ident(table_name)) DESC;