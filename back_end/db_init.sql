-- ============================================================================
-- Steam Game Data - Database Schema (Aiven PostgreSQL - Free Tier)
-- ----------------------------------------------------------------------------
-- Tối ưu cho 1GB storage:
--   - ~150.000 app_id (GameMeta)
--   - ~20 reviews/app (khoảng 3.000.000 reviews)
--   - 1 schema "steam" tách riêng để dễ quản lý/drop
--
-- Cách chạy (một trong 2):
--   1) psql:   psql "host=... port=... user=avnadmin dbname=defaultdb sslmode=require" -f db_init.sql
--   2) Aiven console -> Query Editor -> dán nội dung file này
-- ============================================================================

-- Tạo schema riêng (gọn, dễ quản lý)
CREATE SCHEMA IF NOT EXISTS steam;
SET search_path TO steam, public;

-- ============================================================================
-- 1) BẢNG USERS (Auth, phân quyền)
-- ============================================================================
CREATE TABLE IF NOT EXISTS users (
    id              BIGSERIAL PRIMARY KEY,
    email           VARCHAR(255) UNIQUE NOT NULL,
    username        VARCHAR(100) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    full_name       VARCHAR(255),
    avatar_url      VARCHAR(500),
    role            VARCHAR(20) NOT NULL DEFAULT 'user'
                        CHECK (role IN ('admin', 'user', 'premium')),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    is_verified     BOOLEAN NOT NULL DEFAULT FALSE,
    last_login_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_users_role     ON users(role);
CREATE INDEX IF NOT EXISTS idx_users_active   ON users(is_active);

-- ============================================================================
-- 2) BẢNG REFRESH TOKENS (lưu DB để revoke)
-- ============================================================================
CREATE TABLE IF NOT EXISTS refresh_tokens (
    id         BIGSERIAL PRIMARY KEY,
    user_id    BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token      VARCHAR(500) UNIQUE NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    is_revoked BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_refresh_user     ON refresh_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_refresh_expires  ON refresh_tokens(expires_at);

-- ============================================================================
-- 3) BẢNG CHAT_HISTORIES (AI Agent)
-- ============================================================================
CREATE TABLE IF NOT EXISTS chat_histories (
    id         BIGSERIAL PRIMARY KEY,
    user_id    BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_id VARCHAR(100) NOT NULL,
    role       VARCHAR(20) NOT NULL CHECK (role IN ('user','assistant','system')),
    content    TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_chat_user_session ON chat_histories(user_id, session_id, created_at DESC);

-- ============================================================================
-- 4) BẢNG GAME_META (metadata game)
-- ----------------------------------------------------------------------------
-- Tối ưu: chỉ giữ field thực sự dùng. Ảnh/JSON thô lưu trong raw_data (JSONB).
-- Ước tính ~150K dòng:
--   - id BIGSERIAL 8B
--   - app_id 4B
--   - name 500B
--   - dev/pub 255B mỗi
--   - arrays ~ 200B
--   - raw_data JSONB (gzip) ~ 1-2KB
-- Tổng ~ 1.2-1.5KB/dòng -> ~ 220MB cho 150K dòng. OK với 1GB.
-- ============================================================================
CREATE TABLE IF NOT EXISTS game_metas (
    id              BIGSERIAL PRIMARY KEY,

    -- Steam identifiers
    app_id          INTEGER UNIQUE NOT NULL,
    name            VARCHAR(500) NOT NULL,

    -- Mô tả (HTML thường khá dài -> Text)
    short_description    TEXT,
    detailed_description TEXT,
    about_the_game       TEXT,

    -- Hình ảnh / website
    header_image    VARCHAR(500),
    capsule_image   VARCHAR(500),
    capsule_imagev5 VARCHAR(500),
    website         VARCHAR(500),

    -- Dev / Pub (chỉ lấy 1 - không lưu mảng)
    developer       VARCHAR(255),
    publisher       VARCHAR(255),

    -- Thể loại (lưu mảng text gọn)
    genres          VARCHAR(100)[],
    categories      VARCHAR(100)[],
    tags            VARCHAR(100)[],

    -- Nền tảng
    windows         BOOLEAN NOT NULL DEFAULT FALSE,
    mac             BOOLEAN NOT NULL DEFAULT FALSE,
    linux           BOOLEAN NOT NULL DEFAULT FALSE,

    -- Ngày phát hành
    release_date    TIMESTAMPTZ,
    coming_soon     BOOLEAN NOT NULL DEFAULT FALSE,

    -- Giá
    price_initial       NUMERIC(12,2),
    price_final         NUMERIC(12,2),
    currency            VARCHAR(10),
    discount_percent    SMALLINT,
    is_free             BOOLEAN NOT NULL DEFAULT FALSE,

    -- Đánh giá
    total_reviews       INTEGER NOT NULL DEFAULT 0,
    total_positive      INTEGER NOT NULL DEFAULT 0,
    total_negative      INTEGER NOT NULL DEFAULT 0,
    review_score        SMALLINT,
    review_score_desc   VARCHAR(50),
    positive_percent    REAL,

    -- Yêu cầu hệ thống
    pc_requirements_min     JSONB,
    pc_requirements_rec     JSONB,
    mac_requirements_min    JSONB,
    linux_requirements_min  JSONB,

    -- Khác
    supported_languages    VARCHAR(50)[],
    full_audio_languages   VARCHAR(50)[],
    screenshots            VARCHAR(500)[],
    movies                 VARCHAR(500)[],

    -- Toàn bộ dữ liệu gốc (backup)
    raw_data           JSONB,

    -- Age rating
    required_age       SMALLINT NOT NULL DEFAULT 0,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_game_metas_name         ON game_metas(name);
CREATE INDEX IF NOT EXISTS idx_game_metas_developer    ON game_metas(developer);
CREATE INDEX IF NOT EXISTS idx_game_metas_publisher    ON game_metas(publisher);
CREATE INDEX IF NOT EXISTS idx_game_metas_release      ON game_metas(release_date);
CREATE INDEX IF NOT EXISTS idx_game_metas_total_rev    ON game_metas(total_reviews DESC);
CREATE INDEX IF NOT EXISTS idx_game_metas_pos_pct      ON game_metas(positive_percent DESC);
CREATE INDEX IF NOT EXISTS idx_game_metas_price        ON game_metas(price_final);
CREATE INDEX IF NOT EXISTS idx_game_metas_is_free      ON game_metas(is_free);
-- GIN cho tìm trong mảng
CREATE INDEX IF NOT EXISTS idx_game_metas_genres_gin   ON game_metas USING GIN(genres);
CREATE INDEX IF NOT EXISTS idx_game_metas_cats_gin     ON game_metas USING GIN(categories);
CREATE INDEX IF NOT EXISTS idx_game_metas_tags_gin     ON game_metas USING GIN(tags);

-- ============================================================================
-- 5) BẢNG GAME_REVIEWS
-- ----------------------------------------------------------------------------
-- Ước tính 150K games * 20 reviews = 3.000.000 reviews.
-- Mỗi dòng ~ 0.5-1KB (review text thường < 1KB) -> 1.5-3GB
-- -> CẦN CẮT TỈA raw_data và content_text để vừa 1GB.
-- Gợi ý: chỉ lưu review_text (Text, sẽ TOAST ra ngoài) + các index.
-- Ảnh hưởng ~ 1-2KB text/review -> 3-6GB (vẫn lớn)
-- => TỐI ƯU:
--   - Không lưu raw_data JSONB (chỉ lưu các trường cần thiết)
--   - review_text để Text (TOAST tự động nén)
--   - index gọn
-- ============================================================================
CREATE TABLE IF NOT EXISTS game_reviews (
    id              BIGSERIAL PRIMARY KEY,
    game_id         BIGINT NOT NULL REFERENCES game_metas(id) ON DELETE CASCADE,

    recommendation_id VARCHAR(100) UNIQUE,  -- Dùng để chống trùng lặp

    -- Nội dung
    review_text     TEXT,
    language        VARCHAR(10),

    -- Đánh giá
    voted_up        BOOLEAN NOT NULL,
    votes_up        INTEGER NOT NULL DEFAULT 0,
    votes_funny     INTEGER NOT NULL DEFAULT 0,
    comment_count   INTEGER NOT NULL DEFAULT 0,

    -- Ngữ cảnh mua hàng
    steam_purchase        BOOLEAN NOT NULL DEFAULT FALSE,
    received_for_free     BOOLEAN NOT NULL DEFAULT FALSE,
    written_during_early_access BOOLEAN NOT NULL DEFAULT FALSE,
    primarily_steam_deck  BOOLEAN NOT NULL DEFAULT FALSE,
    refunded              BOOLEAN NOT NULL DEFAULT FALSE,

    -- Thông tin người review
    author_steamid          VARCHAR(50),
    author_personaname      VARCHAR(100),  -- Tên hiển thị
    author_num_games_owned  INTEGER,
    author_num_reviews      INTEGER,
    author_playtime_forever      INTEGER,   -- phút
    author_playtime_at_review    INTEGER,   -- phút
    author_playtime_last_two_weeks INTEGER DEFAULT 0,

    -- Thời gian
    timestamp_created    TIMESTAMPTZ,
    timestamp_updated    TIMESTAMPTZ,
    app_release_date     TIMESTAMPTZ,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_reviews_game_id     ON game_reviews(game_id);
CREATE INDEX IF NOT EXISTS idx_reviews_voted_up    ON game_reviews(voted_up);
CREATE INDEX IF NOT EXISTS idx_reviews_language    ON game_reviews(language);
CREATE INDEX IF NOT EXISTS idx_reviews_author      ON game_reviews(author_steamid);
CREATE INDEX IF NOT EXISTS idx_reviews_created     ON game_reviews(timestamp_created DESC);
CREATE INDEX IF NOT EXISTS idx_reviews_game_voted  ON game_reviews(game_id, voted_up);
CREATE INDEX IF NOT EXISTS idx_reviews_playtime    ON game_reviews(author_playtime_forever DESC);

-- ============================================================================
-- 6) TRIGGER cập nhật updated_at tự động
-- ============================================================================
CREATE OR REPLACE FUNCTION steam.set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
DECLARE t TEXT;
BEGIN
    FOR t IN SELECT unnest(ARRAY['users','refresh_tokens','chat_histories','game_metas','game_reviews'])
    LOOP
        EXECUTE format('DROP TRIGGER IF EXISTS trg_%I_set_updated_at ON steam.%I', t, t);
        EXECUTE format('CREATE TRIGGER trg_%I_set_updated_at BEFORE UPDATE ON steam.%I
                        FOR EACH ROW EXECUTE FUNCTION steam.set_updated_at()', t, t);
    END LOOP;
END $$;

-- ============================================================================
-- 7) (Tuỳ chọn) Seed admin đầu tiên
-- ----------------------------------------------------------------------------
-- Mật khẩu "Admin@123" hash bằng bcrypt (12 rounds).
-- Hash được tạo từ script create_admin.py
-- ============================================================================
-- INSERT INTO steam.users (email, username, hashed_password, full_name, role, is_active, is_verified)
-- VALUES ('admin@steam.local', 'admin', '<bcrypt-hash>', 'Administrator', 'admin', TRUE, TRUE);

-- ============================================================================
-- 8) Kiểm tra
-- ============================================================================
SELECT 'Schema steam created' AS status;
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'steam'
ORDER BY table_name;
