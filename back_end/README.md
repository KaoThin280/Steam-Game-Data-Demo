# Backend

Backend gồm Product API FastAPI (`app.main`, cổng 8000) và tool server nội bộ (`app.mcp_server`, cổng 8001). API xử lý auth, game/review, dashboard và Agent Harness; tool server thực thi SQL phân tích, chart và Python qua E2B.

| Thư mục | Nội dung |
|---|---|
| `app/api/v1/` | Route REST; agent_rpc là chat hiện hành |
| `app/agent_harness/` | Runtime, provider, gateway, store và interface |
| `app/models/`, `app/schemas/` | ORM và request/response schemas |
| `app/services/` | Auth, dữ liệu Steam, E2B, email và các service AI legacy |
| `app/core/`, `app/db/` | Cấu hình, security, rate limit, kết nối |
| `tests/` | Unit tests có dependency kiểm soát |

## Hướng dẫn

- [Cài đặt và chạy local](../docs/guides/local-development.md)
- [API reference](../docs/reference/api.md)
- [Kiến trúc Agent Harness](../docs/architecture/agent-harness.md)
- [Schema và giới hạn migration](../docs/reference/database-schema.md)
- [Kiểm thử](../docs/guides/testing.md)
- [Triển khai](../docs/operations/deployment.md), [systemd/Compose](../docs/operations/vps-services.md), [security](../docs/operations/security.md)

Khởi động MCP trước API. Dùng một API worker; không khẳng định script SQL baseline dựng đủ database mới. `ENABLE_LEGACY_AI=False` mặc định tắt các route AI/chat/file cũ. Quay lại [mục lục tài liệu](../docs/README.md).
