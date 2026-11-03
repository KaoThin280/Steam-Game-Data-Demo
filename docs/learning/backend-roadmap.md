# Lộ trình học backend qua Steam Game Data Demo

Dành cho người đã biết Python cơ bản và muốn hiểu dự án từ HTTP/database đến vòng lặp AI. Mỗi chặng gồm kiến thức, code cần đọc và một bài thực hành; bài tập là đề xuất, chưa phải chức năng đã có.

## 1 Hiểu luồng request

Học HTTP method, status code, JSON, client/server, REST và dependency injection. Đọc [main.py](../../back_end/app/main.py), [games.py](../../back_end/app/api/v1/games.py), rồi [steam_service.py](../../back_end/app/services/steam_service.py). Theo một request danh sách game từ router tới query và response. Phân biệt lỗi validation 422, xác thực 401, phân quyền 403 và không tìm thấy 404.

Bài tập: mô tả input, output và từng bước của `GET /api/v1/games`; thử đổi bộ lọc và phân trang trên database thử nghiệm.

## 2 Python cho backend

Học type hint, Pydantic, async/await, context manager, exception và package/import. Đọc [schemas](../../back_end/app/schemas), [db/session.py](../../back_end/app/db/session.py). Async giúp process chờ I/O mà vẫn xử lý công việc khác, không tự tăng tốc CPU hoặc bảo đảm một mức tải.

Bài tập: viết một hàm async gọi hai dependency giả lập và xử lý timeout. Phân biệt session database với phiên chat.

## 3 SQL và mô hình dữ liệu

Học khóa chính/ngoại, JOIN, GROUP BY, CTE, NULL, index, transaction; sau đó đọc ORM trong [models](../../back_end/app/models) cùng [schema](../reference/database-schema.md). `users` là người review Steam, `app_users` là tài khoản website. Một game nhiều genre nên JOIN có thể nhân số dòng; xác định metric trước khi COUNT.

Bài tập: viết query số game theo genre và tháng; đối chiếu số tổng, kiểm tra NULL và trùng khóa. Học Alembic như cơ chế quản lý migration, nhưng không giả định migration cũ trong repo dựng đủ schema hiện hành.

## 4 Auth và phân quyền

Đọc [security.py](../../back_end/app/core/security.py), [auth_service.py](../../back_end/app/services/auth_service.py), [dependencies.py](../../back_end/app/api/dependencies.py). Password được hash, không phải mã hóa để giải ngược. JWT có payload được mã hóa biểu diễn base64url và chữ ký; chữ ký không che nội dung payload. Refresh token được lưu dạng digest để kiểm tra/thu hồi.

Theo luồng login -> access cookie/Bearer -> current user -> role/permission. Cookie httpOnly hạn chế JavaScript đọc token, không loại bỏ mọi tác động XSS hoặc CSRF. Đọc [API](../reference/api.md) để biết contract refresh hiện tại và phần frontend chưa đồng bộ.

Bài tập: kiểm tra hai tài khoản không được xem session của nhau; phân biệt kiểm soát UI và kiểm soát API.

## 5 Redis và trạng thái bền vững

Đọc [rate_limit.py](../../back_end/app/core/rate_limit.py): key theo user/IP và bucket, tăng bộ đếm và TTL. Redis hiện dùng rate limit, còn session/run/event lưu PostgreSQL. JWT không có nghĩa toàn bộ hệ thống stateless: vẫn có refresh-token revocation và tác vụ trong process.

Bài tập: diễn giải lần request nào bị 429 ở một bucket thử nghiệm. Cache và message broker là chủ đề học tiếp, không phải thành phần agent đã có trong repo.

## 6 Agent và tool calling

Đọc theo thứ tự [types.py](../../back_end/app/agent_harness/types.py), [runtime.py](../../back_end/app/agent_harness/runtime.py), [provider.py](../../back_end/app/agent_harness/provider.py), [mcp.py](../../back_end/app/agent_harness/mcp.py), [agent_rpc.py](../../back_end/app/api/v1/agent_rpc.py).

```text
câu hỏi -> API lưu run -> dựng history -> model
        -> tool call -> gateway -> tool server -> SQL/E2B
        -> tool result -> model -> câu trả lời -> lưu kết quả
```

Học lần lượt RPC là mô hình gọi thủ tục từ xa, JSON-RPC là định dạng message, MCP bổ sung ngữ nghĩa khám phá/gọi tool và vòng đời. Trong repo, frontend dùng REST; gateway tới tool server dùng tập con JSON-RPC theo MCP. Provider dùng function calling, không dùng giao thức text `Response to user / Request system / Code` của tài liệu cũ.

Bài tập: đọc một event trace và chỉ ra ai quyết định gọi tool, ai chạy SQL, dữ liệu nào gửi model. Sau đó thử timeout, max steps, cancellation và replay trên môi trường thử nghiệm. Không đồng nhất lưu event với checkpoint hoặc exactly-once.

## 7 Triển khai và kiểm thử

Đọc [local development](../guides/local-development.md), [testing](../guides/testing.md), [deployment](../operations/deployment.md). Hiểu hai process API/MCP, một worker API, biến môi trường, startup dependency, reverse proxy và health check. Đo RAM/latency trước khi kết luận cấu hình đáp ứng tải; không suy ra chi phí từ số người dùng đơn thuần.

Bài tập: chạy unit tests, mô tả test giả lập phần nào; sau đó chạy smoke với dịch vụ thật nếu có credential. Ghi bằng chứng và phân biệt kiểm tra tĩnh với runtime.

## 8 Hướng nâng cao

Sau khi giải thích được một request từ đầu tới cuối, nghiên cứu lease/heartbeat cho worker, idempotency, event retention, phân quyền tool, kiểm thử migration và [đề xuất RAG](../proposals/rag.md). Mỗi thay đổi cần yêu cầu cụ thể và test cho hành vi mới; không cần học hết mọi framework trước khi hiểu dự án.
