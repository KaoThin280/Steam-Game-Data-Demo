# Triển khai và vận hành

> Cập nhật 03/11/2026: workflow `deploy.yml` đã chuyển sang build Docker release thủ
> công sau unit tests, không còn SSH/venv tự deploy khi push. Xem
> [quy trình Docker VPS](docker-vps-migration.md) cho cơ chế mới. Các mô tả workflow
> SSH/nohup bên dưới là đường triển khai cũ, giữ để đối chiếu/rollback; chưa chứng minh
> VPS đã chuyển sang Docker. Native và Docker không chạy API đồng thời trên DB chung.

Phạm vi là các cơ chế có trong repository và điều kiện cần trước khi triển khai. Rà soát này không truy cập VPS, không áp dụng SQL và không xác minh deployment live. Không có bảo đảm mọi dịch vụ đều miễn phí hoặc tổng RAM dưới một ngưỡng cố định.

## Điều kiện trước triển khai

1. Đối chiếu database với [schema](../reference/database-schema.md), sao lưu và duyệt migration cần thiết. Baseline SQL/Alembic cũ chưa dựng đủ schema hiện tại.
2. Áp dụng bảng/index Agent Harness sau khi có app_users; cấu hình role read-only, password, grants và RLS. Kiểm tra role AI thấy dữ liệu Steam nhưng không đọc được bảng tài khoản/token/event.
3. Chuẩn bị môi trường theo [local development](../guides/local-development.md), dùng `DEBUG=False`, secret JWT/MCP riêng đủ mạnh, `DB_SSL_VERIFY=True` và CORS cụ thể.
4. Cấp credential/quota OpenRouter, E2B cho chức năng cần dùng. Provider hiện không chuyển fallback model chỉ vì có biến fallback trong .env.

## Backend VPS

API và MCP là hai process riêng. Khởi động MCP, kiểm tra read-only DB/tool discovery rồi mới khởi động API. Dùng một Uvicorn worker cho API vì bộ lập lịch run chưa có distributed lease.

| Phương án | Hiện trạng |
|---|---|
| GitHub Actions | [deploy.yml](../../.github/workflows/deploy.yml) SSH vào VPS, fetch/reset main, cài `back_end/venv`, kiểm tra .env, khởi động MCP và API bằng nohup |
| systemd | Mẫu hai unit trong [VPS services](vps-services.md); cần chỉnh workflow nếu chọn dùng |
| Docker Compose | [docker-compose.agent.yml](../../back_end/docker-compose.agent.yml) chạy hai service; không có PostgreSQL/Redis/E2B local trong stack này |
| Timer rsync cũ | [deploy/README](../../deploy/README.md); chưa phù hợp luồng hai process và có rủi ro xóa file runtime |

Workflow chạy khi push main có thay đổi backend/workflow hoặc được gọi thủ công. Nó dùng đường dẫn `~/my-project`, SSH username cố định trong YAML, secrets `VPS_IP`/`VPS_SSH_KEY`; cần chỉnh theo host. Đây không phải rolling deployment hay rollback tự động. Workflow test là job riêng, chưa có bước bắt buộc chờ test thành công trong deploy workflow.

MCP bind `127.0.0.1:8001`; API trong workflow bind `0.0.0.0:8000`. Nếu dùng Nginx/HTTPS, cấu hình host/firewall để chỉ public reverse proxy, không public MCP. [Mẫu Nginx](../../deploy/nginx/steam-api.conf) cần thay domain/chứng chỉ theo host và kiểm tra trước reload.

## Frontend

Thư mục build là `front_end/` với Next.js. Khi cấu hình hosting, đặt `NEXT_PUBLIC_API_URL=https://<api-host>/api/v1`; đây là URL công khai, không chứa secret. Backend CORS phải cho phép origin frontend. Vercel integration và tự deploy phụ thuộc cấu hình tài khoản hosting, không được chứng minh chỉ bằng file repository.

Login backend đặt cookie; phải kiểm thử qua đúng domain/HTTPS triển khai. Code frontend refresh hiện chưa đồng bộ contract cookie-only refresh token; xem [báo cáo rà soát](../maintenance/documentation-audit.md).

## Kiểm tra sau triển khai

- Kiểm tra health MCP và startup logs của API.
- Đọc JSON health API: `status`, `database`, `redis`. `curl --fail` không phát hiện HTTP 200 với status degraded; workflow hiện chỉ kiểm tra HTTP thành công.
- Login, `/auth/me`, refresh/logout; tạo phiên, hỏi số đếm, vẽ biểu đồ và mở lại history.
- Dùng môi trường thử nghiệm để kiểm tra hủy và restart/replay; xem [testing](../guides/testing.md).
- Kiểm tra từ bên ngoài rằng MCP không public; test role/grants trên database thật.

`/health` API không kiểm tra OpenRouter/E2B và không ping MCP mỗi lần; smoke test mới kiểm tra đường đi phân tích đầy đủ.

## Log và thông báo lỗi

`main.py` dùng logging console. Workflow chuyển stdout/stderr vào `mcp-server.log` và `uvicorn.log`. `core/log_config.py` có helper rotation nhưng không được main tự gọi; không khẳng định rotation đã bật.

Thông báo lỗi tùy chọn qua [error_notification_service.py](../../back_end/app/services/error_notification_service.py) xử lý lỗi 500, startup và run failed. Nó redacts/truncates context, nhờ model viết tóm tắt, dùng SMTP và fallback cục bộ khi cần. Cấu hình `ERROR_NOTIFICATIONS_ENABLED`, `ERROR_NOTIFICATION_TO`, `ERROR_NOTIFICATION_ENVIRONMENT`, `ERROR_NOTIFICATION_MIN_INTERVAL_SECONDS` và `SMTP_HOST/PORT/USERNAME/PASSWORD/FROM_EMAIL/STARTTLS` trong .env bảo vệ. Deduplication/delivery best-effort không phải hàng đợi email bền vững. Không bật hoặc gửi email chỉ để sửa tài liệu.

## Cập nhật và phục hồi

Chọn một cơ chế quản lý process; lưu commit và backup trước migration. Cài dependency trước restart, MCP trước API. Cần quy trình rollback riêng theo bản code/schema; không chạy timer rsync cũ song song với workflow. Thêm retention cho event, session, chart và log theo yêu cầu vận hành. Việc restart sẽ replay run đang dở, có thể tạo thêm lần gọi dịch vụ hoặc ghi chart.
