# API hiện hành

Phạm vi: Product API trong `app.main`, prefix mặc định `/api/v1`. Bảng route được đối chiếu decorator và handler trong mã nguồn; request/response schema chi tiết nằm ở file nguồn được liên kết. Khi service chạy, dùng `/docs` hoặc `/openapi.json` để xem schema theo cấu hình thực tế.

## Xác thực và quyền

Login nhận JSON theo `UserLogin` và trả `access_token`, `token_type`, `expires_in`; access và refresh được đặt trong cookie httpOnly. Refresh token **không** trả trong JSON. Refresh/logout nhận refresh cookie hoặc Bearer refresh token qua dependency, không đọc `refresh_token` từ JSON body. Access dependency ưu tiên cookie rồi Bearer. Xem [auth.py](../../back_end/app/api/v1/auth.py), [schemas](../../back_end/app/schemas/user_schema.py), [dependencies](../../back_end/app/api/dependencies.py).

| Nhóm | Kiểm soát chính |
|---|---|
| Register/login | Không cần đăng nhập; rate limit auth |
| Profile | Tài khoản active |
| Đọc game/review | Role admin/scientist/analyst/viewer |
| Ghi/xóa game/review | Permission tương ứng; admin được bypass permission |
| Dashboard | Cả bốn role |
| Agent Harness | Tài khoản active, sở hữu session/run; chưa có role gate analyst tại API |
| Admin | `get_current_admin` |

Frontend đang kỳ vọng refresh token trong store trong khi backend chỉ đặt refresh cookie. Vì vậy không khẳng định auto-refresh end-to-end đã đúng; xem [báo cáo](../maintenance/documentation-audit.md).

## Danh sách route mặc định

Status code ghi theo decorator (mặc định 200), không bao gồm các lỗi phát sinh. Mỗi nhóm liên kết tới handler để tra query/body/response model.

### auth

Nguồn: [auth.py](../../back_end/app/api/v1/auth.py).

| Method | Path | Status | Handler |
|---|---|---|---|
| POST | `/api/v1/auth/register` | 201 | `register` |
| POST | `/api/v1/auth/login` | 200 | `login` |
| POST | `/api/v1/auth/refresh` | 200 | `refresh_token` |
| POST | `/api/v1/auth/logout` | 204 | `logout` |
| GET | `/api/v1/auth/me` | 200 | `get_me` |
| PUT | `/api/v1/auth/me` | 200 | `update_me` |
| PUT | `/api/v1/auth/me/password` | 204 | `change_password` |

### games

Nguồn: [games.py](../../back_end/app/api/v1/games.py).

| Method | Path | Status | Handler |
|---|---|---|---|
| GET | `/api/v1/games` | 200 | `list_games` |
| GET | `/api/v1/games/{steam_appid}` | 200 | `get_game` |
| POST | `/api/v1/games` | 201 | `upsert_game` |
| DELETE | `/api/v1/games/{steam_appid}` | 204 | `delete_game` |
| GET | `/api/v1/games/{steam_appid}/reviews` | 200 | `list_reviews` |
| POST | `/api/v1/games/{steam_appid}/reviews` | 201 | `create_review` |
| DELETE | `/api/v1/games/{steam_appid}/reviews/{recommendationid}` | 204 | `delete_review` |

### dashboard

Nguồn: [dashboard.py](../../back_end/app/api/v1/dashboard.py).

| Method | Path | Status | Handler |
|---|---|---|---|
| GET | `/api/v1/dashboard/overview` | 200 | `overview` |
| GET | `/api/v1/dashboard/top-games` | 200 | `top_games` |
| GET | `/api/v1/dashboard/genres` | 200 | `genre_distribution` |
| GET | `/api/v1/dashboard/years` | 200 | `year_distribution` |
| GET | `/api/v1/dashboard/languages` | 200 | `language_distribution` |

### agent_rpc

Nguồn: [agent_rpc.py](../../back_end/app/api/v1/agent_rpc.py).

| Method | Path | Status | Handler |
|---|---|---|---|
| POST | `/api/v1/agent-rpc/sessions` | 201 | `create_session` |
| GET | `/api/v1/agent-rpc/sessions` | 200 | `list_sessions` |
| GET | `/api/v1/agent-rpc/sessions/{session_id}` | 200 | `get_session` |
| PATCH | `/api/v1/agent-rpc/sessions/{session_id}` | 200 | `rename_session` |
| DELETE | `/api/v1/agent-rpc/sessions/{session_id}` | 204 | `delete_session` |
| POST | `/api/v1/agent-rpc/sessions/{session_id}/tasks` | 202 | `send_task` |
| GET | `/api/v1/agent-rpc/runs/{run_id}` | 200 | `get_run` |
| GET | `/api/v1/agent-rpc/runs/{run_id}/events` | 200 | `get_events` |
| GET | `/api/v1/agent-rpc/runs/{run_id}/stream` | 200 | `stream_events` |
| POST | `/api/v1/agent-rpc/runs/{run_id}/cancel` | 202 | `cancel_run` |

### admin

Nguồn: [admin.py](../../back_end/app/api/v1/admin.py).

| Method | Path | Status | Handler |
|---|---|---|---|
| GET | `/api/v1/admin/roles` | 200 | `list_roles` |
| GET | `/api/v1/admin/permissions` | 200 | `list_permissions` |
| GET | `/api/v1/admin/users` | 200 | `list_users` |
| GET | `/api/v1/admin/users/{user_id}` | 200 | `get_user` |
| PATCH | `/api/v1/admin/users/{user_id}` | 200 | `update_user` |
| POST | `/api/v1/admin/users/{user_id}/roles` | 200 | `assign_role` |
| DELETE | `/api/v1/admin/users/{user_id}/roles/{role_name}` | 200 | `revoke_role` |

### System

`GET /`, `/health`, `/ping`, `/agent-demo` được khai báo trong [main.py](../../back_end/app/main.py). FastAPI cung cấp thêm `/docs`, `/redoc`, `/openapi.json` và route hỗ trợ Swagger. `/ping` có rate limit; không phải tất cả endpoint đều có rate limit/auth. `/health` có thể trả 200 với `status="degraded"`; nó kiểm tra database chính và Redis, không xác nhận OpenRouter/E2B.

## Input và output của các API dữ liệu

| Thao tác | Input chính | Output / lưu ý |
|---|---|---|
| Register | username, email, password, confirm_password; full_name tùy chọn | UserOut; username 3–100 ký tự, password 8–128; mặc định role viewer |
| Login | email, password | Access token JSON và cookie; không trả refresh token JSON |
| PUT auth/me | email, full_name tùy chọn | Hồ sơ user hiện tại |
| PUT auth/me/password | old_password, new_password, confirm_new_password | 204; kiểm tra xác nhận và thu hồi refresh token |
| GET games | search, developer, publisher, is_free, year; sort_by release_date/name/required_age, sort_order asc/desc; page, page_size | items, total, page, page_size, total_pages; page_size 1–100, mặc định 20 |
| POST games | steam_appid, name; is_free, required_age, release_date, publishers, developers, price_text tùy chọn | Upsert game theo steam_appid, trả GameOut; không cập nhật junction metadata |
| GET game reviews | language, refunded, received_for_free, primarily_steam_deck, min_playtime_forever; page, page_size | ReviewListResponse; page_size 1–100 |
| POST game reviews | recommendationid, steam_appid, steamid và các trường ReviewCreate tùy chọn | ReviewOut; steam_appid body phải khớp URL |
| Dashboard overview | Không có body | total_games, total_reviews, free_games, paid_games, total_developers, total_languages |
| Dashboard distributions | limit theo endpoint | genres trả genre/count; years trả year/count; languages trả language/count |
| Dashboard top-games | limit | Danh sách GameOut sắp theo số review; không thêm trường total_reviews vào response |
| PATCH admin/users/{user_id} | is_active tùy chọn | Cập nhật trạng thái tài khoản; role có route riêng |
| POST admin/users/{user_id}/roles | role_name | Gán role theo contract router admin |

`genre` và `category` được route GET games chấp nhận nhưng SteamService hiện không áp dụng lọc. Không suy ra một query parameter hoạt động chỉ vì nó xuất hiện trong OpenAPI. Định nghĩa đầy đủ nằm trong [steam_schema.py](../../back_end/app/schemas/steam_schema.py) và [user_schema.py](../../back_end/app/schemas/user_schema.py).

Ví dụ request đọc dữ liệu: `GET /api/v1/games?search=portal&is_free=false&page=1&page_size=20&sort_by=name&sort_order=asc`. Đây là ví dụ cú pháp, không xác nhận dataset chứa game tương ứng.

## Contract Agent Harness

Ví dụ dưới đây chỉ minh họa body; thay `{session_id}` và `{run_id}` bằng UUID từ response.

| Thao tác | Body / query | Response chính |
|---|---|---|
| POST sessions | `{"title":"Phân tích Steam"}` hoặc `{}` | `session_id`, `status`, `created_at` |
| GET sessions | Không có body | Mảng tối đa 50 phiên theo updated_at giảm dần |
| GET sessions/{session_id} | UUID path | Phiên và tối đa 200 run theo created_at tăng dần |
| PATCH sessions/{session_id} | `{"title":"Tên mới"}` | Phiên đã đổi tên; title 1–200 ký tự, không trắng |
| DELETE sessions/{session_id} | Không có body | 204; 409 nếu còn run active |
| POST sessions/{session_id}/tasks | `{"message":"Có bao nhiêu game?"}` | 202, `run_id`, `session_id`, `status="queued"`; message 1–8000 ký tự |
| GET runs/{run_id} | UUID path | status, current_step, max_steps, output, error, cancel_requested |
| GET runs/{run_id}/events | `?after=0` | Tối đa 500 event có sequence lớn hơn cursor |
| GET runs/{run_id}/stream | Header `Last-Event-ID` tùy chọn | SSE có id, event, data; replay theo sequence |
| POST runs/{run_id}/cancel | Không có body | 202 và trạng thái hủy hoặc trạng thái terminal đã có |

Session đang có run queued/running từ chối task mới bằng 409. Đọc run/session không thuộc user trả 404. Xóa phiên cascade run/event; chart dùng session_id dạng text, không có FK tới agent_sessions để đảm bảo cascade chart.

Frontend hiện poll run/events. SSE đọc event từ PostgreSQL mỗi 0,75 giây; không stream từng token model. Client dùng Bearer phải có cách gửi Authorization khi kết nối SSE.

## Lỗi

- Validation mặc định của FastAPI trả `detail` với status 422.
- `HTTPException` trong router thường trả `detail` (ví dụ 404/409).
- `AppException` qua handler riêng trả `success`, `code`, `message`, `path`.
- Run/tool có trường lỗi riêng trong result/event; HTTP 202 chỉ xác nhận đã nhận task, không bảo đảm phân tích thành công.

Không giả định một error envelope duy nhất cho mọi endpoint.

## Route legacy và tool server

Khi `ENABLE_LEGACY_AI=True`, `main.py` mới đăng ký các router [ai_agent.py](../../back_end/app/api/v1/ai_agent.py), [chat.py](../../back_end/app/api/v1/chat.py), [data_files.py](../../back_end/app/api/v1/data_files.py), gồm các prefix `/api/v1/ai`, `/api/v1/chat`, `/api/v1/data-files`, `/api/v1/tables`. Chúng không phải contract chat mặc định và dùng cơ chế history/artifact cũ.

Tool server là app riêng: `GET /health`, `POST /mcp` trên cổng 8001. Không cộng hai route này vào Product API và không đưa MCP secret vào browser. Xem [catalog tool](agent-prompts-and-tools.md).
