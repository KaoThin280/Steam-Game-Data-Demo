# Schema database của dự án

## Phạm vi và nguồn đối chiếu

Các bảng bên dưới mô tả schema ứng dụng kỳ vọng theo [Steam models](../../back_end/app/models/steam.py), [user models](../../back_end/app/models/user.py) và [agent models](../../back_end/app/models/agent.py). Chưa truy vấn schema database live trong đợt rà soát này. Default/index/identity trong SQL cũ không tự chứng minh database đang có đúng các constraint đó.

**Lưu ý database mới:** `db_init_supabase.sql` và Alembic `0001_initial` vẫn là baseline cũ; xem phần migration ở cuối trước khi áp dụng. Số dòng dữ liệu phải truy vấn ở môi trường sử dụng, không lấy số ước lượng trong mô tả cũ làm KPI.

## Table of Contents

1. [Steam Database Schema](#1-steam-database-schema)
   - [Entity Relationship Overview](#entity-relationship-overview)
   - [Games Core Table](#games-core-table)
   - [Game Metadata Tables (Many-to-Many)](#game-metadata-tables)
   - [Users & Reviews Tables](#users--reviews-tables)
2. [User Authentication & Authorization Schema](#2-user-authentication--authorization-schema)
   - [Auth Tables](#auth-tables)
   - [Roles & Permissions Definition](#roles--permissions-definition)
   - [Quick Reference](#quick-reference)

---

## 1. Steam Database Schema <a id="1-steam-database-schema"></a>

### Entity Relationship Overview <a id="entity-relationship-overview"></a>

The schema utilizes a normalized structure for core entities to support efficient querying and indexing.

Main relationships:
- `games` **1—N** `reviews`
- `users` **1—N** `reviews`
- `games` **M—N** `languages` (via `game_languages`)
- `games` **M—N** `categories` (via `game_categories`)
- `games` **M—N** `genres` (via `game_genres`)

### Games Core Table <a id="games-core-table"></a>

#### 1.1 `games` — Core Game Information

The main table that stores one row per Steam game. *Note: Array-like metadata (languages, categories, genres) have been extracted into separate dimension tables.*

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `steam_appid` | `INTEGER` | `PRIMARY KEY` | Unique Steam application ID |
| `name` | `TEXT` | `NOT NULL` | Game name |
| `is_free` | `BOOLEAN` | `DEFAULT FALSE` | Whether the game is free to play |
| `required_age` | `INTEGER` | `DEFAULT 0` | Minimum required age |
| `release_date` | `DATE` | – | Game release date |
| `publishers` | `TEXT` | – | Comma-separated list of publishers |
| `developers` | `TEXT` | – | Comma-separated list of developers |
| `price_text` | `TEXT` | – | Formatted price string |
| `created_at` | `TIMESTAMPTZ` | `DEFAULT CURRENT_TIMESTAMP` | Record creation time |

Indexes trong baseline SQL (cần kiểm tra trên database triển khai): 
- `idx_games_name ON games(name)`
- `idx_games_is_free ON games(is_free)`

### Game Metadata Tables (Many-to-Many) <a id="game-metadata-tables"></a>

These tables handle the multi-valued attributes of games, allowing for proper indexing and statistical queries.

#### 1.2 Dimension Tables (`languages`, `categories`, `genres`)

| Table | Column | Type | Constraints | Description |
|-------|--------|------|-------------|-------------|
| **languages** | `id` | `SERIAL` | `PRIMARY KEY` | Surrogate key |
| | `name` | `TEXT` | `UNIQUE NOT NULL` | Language name |
| **categories**| `id` | `SERIAL` | `PRIMARY KEY` | Surrogate key |
| | `name` | `TEXT` | `UNIQUE NOT NULL` | Category name (e.g., Single-player) |
| **genres** | `id` | `SERIAL` | `PRIMARY KEY` | Surrogate key |
| | `name` | `TEXT` | `UNIQUE NOT NULL` | Genre name (e.g., Action) |

#### 1.3 Junction Tables

| Table | Column | Type | Constraints |
|-------|--------|------|-------------|
| **game_languages** | `steam_appid` | `INTEGER` | `PK`, `FK → games(steam_appid) ON DELETE CASCADE` |
| | `language_id` | `INTEGER` | `PK`, `FK → languages(id) ON DELETE CASCADE` |
| **game_categories**| `steam_appid` | `INTEGER` | `PK`, `FK → games(steam_appid) ON DELETE CASCADE` |
| | `category_id` | `INTEGER` | `PK`, `FK → categories(id) ON DELETE CASCADE` |
| **game_genres** | `steam_appid` | `INTEGER` | `PK`, `FK → games(steam_appid) ON DELETE CASCADE` |
| | `genre_id` | `INTEGER` | `PK`, `FK → genres(id) ON DELETE CASCADE` |

### Users & Reviews Tables <a id="users--reviews-tables"></a>

#### 1.4 `users` — Steam Users

Stores Steam user profiles based on review extraction.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `steamid` | `BIGINT` | `PRIMARY KEY` | 17-digit Steam ID |
| `personaname` | `TEXT` | – | Steam display name |
| `num_games_owned` | `INTEGER` | `DEFAULT 0` | Number of games owned |
| `created_at` | `TIMESTAMPTZ` | `DEFAULT CURRENT_TIMESTAMP` | Record creation time |

#### 1.5 `reviews` — User Reviews

Stores individual user reviews linked to specific games and users.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `recommendationid` | `BIGINT` | `PRIMARY KEY` | Steam recommendation ID |
| `steam_appid` | `INTEGER` | `NOT NULL`, `FK → games(steam_appid) ON DELETE CASCADE` | Reviewed game |
| `steamid` | `BIGINT` | `NOT NULL`, `FK → users(steamid) ON DELETE CASCADE` | Reviewer |
| `language` | `VARCHAR(20)` theo ORM | – | Language of the review |
| `review_text` | `TEXT` | – | Review body |
| `timestamp_created` | `TIMESTAMPTZ` | – | Timestamp of review creation |
| `timestamp_updated` | `TIMESTAMPTZ` | – | Timestamp of last update |
| `refunded` | `BOOLEAN` | `DEFAULT FALSE` | Whether the purchase was refunded |
| `received_for_free` | `BOOLEAN` | `DEFAULT FALSE` | Whether the game was received for free |
| `written_during_early_access` | `BOOLEAN` | `DEFAULT FALSE` | Written during early access |
| `primarily_steam_deck` | `BOOLEAN` | `DEFAULT FALSE` | Primarily played on Steam Deck |
| `playtime_at_review` | `INTEGER` | `DEFAULT 0` | Playtime at the moment of the review |
| `playtime_last_two_weeks` | `INTEGER` | `DEFAULT 0` | Playtime in the last 2 weeks |
| `playtime_forever` | `INTEGER` | `DEFAULT 0` | Total playtime in minutes |
| `created_at` | `TIMESTAMPTZ` | `DEFAULT CURRENT_TIMESTAMP` | DB record creation time |

Indexes trong baseline SQL (cần kiểm tra trên database triển khai): 
- `idx_reviews_appid ON reviews(steam_appid)`
- `idx_reviews_steamid ON reviews(steamid)`
- `idx_reviews_language ON reviews(language)`
- `idx_reviews_created ON reviews(timestamp_created)`

---

## 2. User Authentication & Authorization Schema <a id="2-user-authentication--authorization-schema"></a>

This schema implements **RBAC (Role-Based Access Control)** on top of the system. It uses a dedicated `app_users` table that is entirely separate from the Steam `users` table. Application users authenticate with a username/email and password, and are assigned one or more **roles**, each possessing specific **permissions**.

### Auth Tables <a id="auth-tables"></a>

#### 2.1 `roles` — System Roles

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `BIGINT` | `IDENTITY PRIMARY KEY` | Surrogate key |
| `role_name` | `TEXT` | `UNIQUE NOT NULL` | Role identifier |
| `description` | `TEXT` | – | Human-readable description |
| `created_at` | `TIMESTAMPTZ` | `DEFAULT CURRENT_TIMESTAMP` | Record creation time |

#### 2.2 `permissions` — System Permissions

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `BIGINT` | `IDENTITY PRIMARY KEY` | Surrogate key |
| `permission_name` | `TEXT` | `UNIQUE NOT NULL` | Permission identifier |
| `description` | `TEXT` | – | Human-readable description |
| `resource` | `TEXT` | – | Target resource (e.g., `games`, `users`) |
| `action` | `TEXT` | – | Allowed action (e.g., `read`, `write`) |
| `created_at` | `TIMESTAMPTZ` | `DEFAULT CURRENT_TIMESTAMP` | Record creation time |

#### 2.3 `role_permissions` — Role ↔ Permission Assignment

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `role_id` | `BIGINT` | `PK`, `FK → roles(id) ON DELETE CASCADE` | Role reference |
| `permission_id` | `BIGINT` | `PK`, `FK → permissions(id) ON DELETE CASCADE`| Permission reference |

#### 2.4 `app_users` — Application Accounts

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `BIGINT` | `IDENTITY PRIMARY KEY` | Surrogate key |
| `username` | `TEXT` | `UNIQUE NOT NULL` | Login name |
| `email` | `TEXT` | `UNIQUE NOT NULL` | Email address |
| `password_hash` | `TEXT` | `NOT NULL` | bcrypt-hashed password |
| `full_name` | `TEXT` | – | Display name |
| `is_active` | `BOOLEAN` | `DEFAULT TRUE` | Account enabled flag |
| `created_at` | `TIMESTAMPTZ` | `DEFAULT CURRENT_TIMESTAMP` | Account creation time |
| `last_login` | `TIMESTAMPTZ` | – | Last successful login |

#### 2.5 `user_roles` — User ↔ Role Assignment

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `user_id` | `BIGINT` | `PK`, `FK → app_users(id) ON DELETE CASCADE` | User reference |
| `role_id` | `BIGINT` | `PK`, `FK → roles(id) ON DELETE CASCADE` | Role reference |
| `assigned_at` | `TIMESTAMPTZ` | `DEFAULT CURRENT_TIMESTAMP` | Assignment time |

### Roles & Permissions Definition <a id="roles--permissions-definition"></a>

Script baseline seed bốn role; quyền thực tế còn tùy dữ liệu role/permission và dependency ở từng endpoint:

- **admin** – System administrator with full access.
- **analyst** – Read-only data analyst.
- **scientist** – Data scientist; read/write access.
- **viewer** – Tài khoản có role đọc cơ bản; không đồng nghĩa truy cập ẩn danh.

Default Permissions Matrix:
- **Games**: `games_read`, `games_write`, `games_delete`
- **Reviews**: `reviews_read`, `reviews_write`, `reviews_delete`
- **Users**: `users_read`, `users_write`, `users_delete`, `users_manage_roles`
- **System**: `system_admin`

### Quick Reference <a id="quick-reference"></a>

| # | Table | Purpose |
|---|-------|---------|
| 1 | `games` | Core game metadata records |
| 2 | `languages` / `categories` / `genres` | Dimension tables for multi-valued game attributes |
| 3 | `game_languages` / `game_categories` / `game_genres` | Junction tables resolving N:M game relationships |
| 4 | `users` | Steam user profiles |
| 5 | `reviews` | User reviews and playtime statistics |
| 6 | `roles` | RBAC roles definition |
| 7 | `permissions` | RBAC permissions definition |
| 8 | `role_permissions` | Junction table for Role ↔ Permission |
| 9 | `app_users` | Internal application accounts |
| 10 | `user_roles` | Junction table for App User ↔ Role |
| 11 | `refresh_tokens` | JWT refresh tokens with revoke support |
| 12 | `chat_histories` | AI chat conversation logs (role, content, session_id) |
| 13 | `ai_chart_history` | AI-generated chart configurations (Plotly specs, source queries, descriptions for caching/reuse) |

---


## 3 Auth token và dữ liệu AI

| Bảng | Khóa và nội dung | Vai trò |
|---|---|---|
| `refresh_tokens` | id; user_id FK app_users; token; expires_at; is_revoked; created_at | AuthService lưu SHA-256 digest trong cột token, không lưu refresh token plaintext mới |
| `chat_histories` | id; user_id FK; session_id TEXT; role; content; created_at | History của luồng chat legacy |
| `ai_chart_history` | id; user_id FK; session_id TEXT; chart_type/title; nhãn trục; config JSONB; source_query; description; created_at | Catalog/cache chart; tên bảng là số ít `history` |

`ai_chart_history.session_id` là text, không phải FK UUID tới agent_sessions. `config` lưu payload theo từng luồng; Agent Harness lưu chart cấu trúc cùng metadata cache. Không giả định mọi bản ghi cũ đều là Plotly figure hoặc đều tự bị xóa khi xóa phiên.

## 4 Agent Harness

```text
app_users -> agent_sessions -> agent_runs -> agent_events
app_users -> ai_chart_history
```

| Bảng | Cột quan trọng |
|---|---|
| `agent_sessions` | id UUID; user_id BIGINT FK; title TEXT; status active/archived; created_at, updated_at |
| `agent_runs` | id UUID; session_id UUID FK; input_text, output_text; status; current_step, max_steps; cancel_requested; error_code, error_message; created_at, started_at, completed_at, updated_at |
| `agent_events` | id BIGINT identity; run_id UUID FK; sequence; event_type; payload JSONB; created_at |

[supabase_agent_harness.sql](../../back_end/supabase_agent_harness.sql) thêm check trạng thái, unique `(run_id, sequence)` và partial unique index một run queued/running trên mỗi session. FK có cascade xóa. Schema có session status archived nhưng API chưa có endpoint archive riêng.

SQL bật RLS cho ba bảng agent; quyền của role backend phải phù hợp. API kiểm tra ownership, không có nghĩa mọi credential PostgreSQL có quyền giống API. Event được ứng dụng append nhưng không có cơ chế chống chỉnh sửa bất biến ở database.

## 5 Migration và database mới

| File | Phạm vi thật |
|---|---|
| [db_init_supabase.sql](../../back_end/db_init_supabase.sql) | Baseline auth/Steam/chat cũ; games còn metadata phẳng; chưa tạo đủ dimension/junction hiện tại và agent tables |
| [0001_initial.py](../../back_end/alembic/versions/0001_initial.py) | Migration baseline cũ; `alembic upgrade head` riêng không đủ để dựng toàn bộ schema hiện hành |
| [db_extra_tables.sql](../../back_end/db_extra_tables.sql) | Tạo refresh/chat/chart nếu chưa có; có cột description trong CREATE TABLE, nhưng không ALTER bảng chart đã tồn tại để thêm cột |
| [supabase_agent_harness.sql](../../back_end/supabase_agent_harness.sql) | Tạo bảng/index/RLS agent, yêu cầu có app_users trước |
| [db_readonly_user.sql](../../back_end/db_readonly_user.sql) | Role steam_readonly, allowlist SELECT và policy RLS cho các bảng Steam đã tồn tại; cần đặt LOGIN/password riêng |
| [diagnose_agent_data_visibility.sql](../../back_end/diagnose_agent_data_visibility.sql) và [fix_agent_data_visibility.sql](../../back_end/fix_agent_data_visibility.sql) | Chẩn đoán/sửa quyền nhìn thấy dữ liệu; đọc và duyệt trước khi chạy, không phải baseline schema |

Repository còn thiếu chuỗi migration đầy đủ cho schema chuẩn hóa hiện tại. Với database mới, cần bổ sung/review migration dimension/junction và cột chart thiếu, seed RBAC, rồi mới nạp dữ liệu và áp dụng harness/read-only. Với database đang có dữ liệu, so sánh catalog trước; `CREATE TABLE IF NOT EXISTS` không nâng cấp bảng cũ.

Thứ tự nạp hợp lý: games/users và dimension trước, junction/reviews sau, theo khóa ngoại. CSV nguồn có thể cần transform từ metadata phẳng; không copy nguyên lệnh import cũ vào schema đã chuẩn hóa.

## 6 Kiểm tra dữ liệu và quyền

Kiểm tra đủ bảng/cột/index, khóa chính duy nhất, FK review/junction, giá trị NULL/ngày, và số đếm theo role chính lẫn steam_readonly. Quyền SELECT và RLS đều ảnh hưởng dữ liệu nhìn thấy. SQL validator là regex kiểm tra SELECT/WITH, không thay thế kiểm tra grants thực tế.

`DATABASE_URL_READONLY` bắt buộc theo Settings; code không xác minh tên role trong URI là steam_readonly hoặc credential thực sự chỉ có quyền đọc. Cần xác minh trên database sau cấu hình. Xem [security](../operations/security.md).
