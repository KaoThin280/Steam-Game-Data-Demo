# Kiến trúc hệ thống

Tài liệu mô tả quan hệ giữa web, API, database và dịch vụ AI. Chi tiết vòng lặp agent nằm trong [Agent Harness](agent-harness.md).

## Thành phần và trách nhiệm

| Thành phần | Điểm vào trong code | Trách nhiệm |
|---|---|---|
| Frontend | [app](../../front_end/src/app), [API client](../../front_end/src/lib/api.ts) | Trang game, dashboard, chat, admin; gọi REST và poll events |
| Product API | [main.py](../../back_end/app/main.py) | Auth, Steam REST API, quản lý session/run, lifespan |
| Agent Harness | [agent_harness](../../back_end/app/agent_harness) | Điều phối model, tool, trạng thái và event |
| Tool server | [mcp_server.py](../../back_end/app/mcp_server.py) | JSON-RPC HTTP nội bộ, kiểm tra service secret, thực thi tool |
| PostgreSQL | [models](../../back_end/app/models), [db/session.py](../../back_end/app/db/session.py) | Steam data, tài khoản, token digest, agent state, chart |
| Redis | [rate_limit.py](../../back_end/app/core/rate_limit.py) | Bộ đếm rate limit; không phải memory hội thoại hay hàng đợi agent |
| E2B | [e2b_service.py](../../back_end/app/services/e2b_service.py) | Chạy Python trong sandbox ngoài VPS |
| DB admin nội bộ | [app.py](../../db_admin/app.py) | Truy cập DB trực tiếp theo quyền credential riêng, ngoài RBAC website |

## Request dữ liệu thông thường

```text
Browser -> Axios -> /api/v1/games hoặc /dashboard
        -> dependency xác thực / quyền
        -> SteamService -> SQLAlchemy -> PostgreSQL
        <- JSON <- frontend render bảng / Chart.js
```

Game và review có endpoint ghi/xóa với permission riêng. Dashboard dùng truy vấn tổng hợp. Không có bằng chứng trong SteamService hiện tại về cache dashboard bằng Redis; biến `REDIS_TTL` không chứng minh cache đã được dùng.

## Request chat

```text
Browser -> /agent-rpc/sessions/{id}/tasks -> PostgreSQL lưu run queued
        <- 202 và run_id
API asyncio task -> lấy lịch sử completed -> AgentRuntime -> OpenRouter
AgentRuntime -> HTTPMCPGateway -> :8001/mcp -> PostgreSQL read-only / E2B
Tool result -> AgentRuntime -> OpenRouter -> câu trả lời
RunStore -> PostgreSQL lưu trạng thái và events
Browser -> poll run/events -> hiển thị câu trả lời và Plotly chart
```

Chart được lưu ở `ai_chart_history` bằng kết nối database chính. Truy vấn SQL do model cung cấp dùng kết nối `DATABASE_URL_READONLY`. Đây là hai mục đích khác nhau dù cùng máy chủ PostgreSQL.

## Khởi động và dừng

`main.lifespan` kiểm tra kết nối database chính, database read-only, khám phá tool qua MCP, kết nối Redis, thử bootstrap admin rồi tìm run bị gián đoạn. Lỗi ở chuỗi kiểm tra chính làm startup thất bại; bootstrap admin có cơ chế ghi log và bỏ qua lỗi riêng. Vì vậy phải khởi động MCP trước API.

Khi dừng, API ngắt tác vụ đang chạy rồi đóng Redis/database. Không có worker queue độc lập. Dùng nhiều API worker có thể lập lịch trùng run; lưu trạng thái trong database chưa đủ để có điều phối phân tán.

## Xác thực và quyền

Backend nhận access token từ cookie httpOnly trước, rồi mới tới Bearer header. Login trả access token trong JSON và đặt cookie cho access/refresh; refresh token không được trả trong JSON. Frontend gửi cookie qua `withCredentials` và có Bearer từ store.

Quyền UI không hoàn toàn đồng nhất với API: UI chat giới hạn analyst/scientist/admin, nhưng `agent_rpc.py` chỉ yêu cầu tài khoản active và kiểm tra sở hữu tài nguyên. Dashboard API cho cả bốn role. Xem [API](../reference/api.md) và [các sai lệch còn tồn tại](../maintenance/documentation-audit.md) trước khi suy ra quyền từ thanh điều hướng.

## Phần cũ và phần dự kiến

`ai_service.py`, `agentic_workflow.py` và các router `/ai`, `/chat`, `/data-files`, `/tables` thuộc luồng legacy, chỉ đăng ký khi `ENABLE_LEGACY_AI=True`. Không dùng chúng để giải thích luồng chat mặc định. RAG/vector retrieval và worker có lease là hướng mở rộng, chưa phải thành phần hiện hành.
