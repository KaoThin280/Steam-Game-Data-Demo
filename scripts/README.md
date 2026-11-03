# Script local và kiểm thử

Chạy từ thư mục gốc repository trên Windows PowerShell.

| Lệnh | Mục đích |
|---|---|
| `./scripts/start_local_stack.ps1` | Khởi động MCP, API rồi frontend; cần venv/node_modules sẵn |
| `./scripts/test_backend_unit.ps1` | Unit tests với dependency được kiểm soát |
| `./scripts/test_agent_local.ps1` | Smoke test với dịch vụ và tài khoản thật |
| `./scripts/test_agent_local.ps1 -ConversationSuite` | Hội thoại tiếng Việt/Anh nhiều lượt và chart |

Xem [cài đặt local](../docs/guides/local-development.md) và [testing](../docs/guides/testing.md) cho điều kiện, credential và giới hạn bằng chứng. Script local tạo secret tạm; không dùng thay cấu hình production. Smoke test tạo dữ liệu session/run và có thể sử dụng quota OpenRouter/E2B.
