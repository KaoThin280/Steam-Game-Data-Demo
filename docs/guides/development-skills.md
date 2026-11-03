# Skill dùng để phát triển dự án

Hai skill này hướng dẫn trợ lý lập trình làm việc trên repository; **không phải tool hoặc system prompt được nạp vào chatbot Steam lúc chạy**. Không cần thêm chúng vào OpenRouter hay MCP server của ứng dụng.

## Phạm vi

| Skill | Dùng khi | File nguồn |
|---|---|---|
| steam-ai-agent | Sửa vòng lặp model/tool, prompt, chart, history/cancellation/replay hoặc triển khai RAG | [SKILL.md](../../skills/steam-ai-agent/SKILL.md) |
| steam-backend | Phát triển REST API, auth/RBAC, query, migration, Redis và vận hành backend | [SKILL.md](../../skills/steam-backend/SKILL.md) |

Tác vụ giao nhau có thể dùng hướng dẫn của cả hai; không mặc định tạo nhiều agent hoặc sửa mọi phần được nêu trong skill. Các skill yêu cầu xác minh code hiện tại để tài liệu lịch sử không trở thành quy tắc lỗi thời.

## Cách giao việc

Ví dụ yêu cầu:

```text
Dùng $steam-ai-agent để triển khai milestone 1 ingestion trong đề xuất RAG.
Chỉ dùng corpus schema/metric đã duyệt, thêm kiểm thử ingest lặp và xóa nguồn.
```

```text
Dùng $steam-backend sửa bộ lọc genre/category cho GET /api/v1/games.
Giữ contract hiện tại và kiểm tra JOIN không nhân bản game hoặc sai tổng số.
```

```text
Dùng $steam-ai-agent kiểm tra lỗi hủy run: truy vết từ REST đến task,
gateway và sự kiện lưu trong database trước khi đề xuất sửa.
```

Nếu phiên làm việc chưa nhận tên skill, có thể yêu cầu đọc trực tiếp file SKILL.md trong repository. `agents/openai.yaml` chứa tên hiển thị và prompt gợi ý, không chứa credential.

## Quản lý bản nguồn

`skills/` trong repository là bản nguồn để review/commit cùng dự án. Bản dùng cá nhân nằm trong thư mục `skills` của Codex home, mỗi skill một thư mục cùng tên. Khi sửa bản nguồn, đồng bộ lại bản cài; hai bản không tự đồng bộ. Không copy đè skill cùng tên đã được tùy biến mà chưa so sánh diff.

Tài liệu nền gồm [kiến trúc](../architecture/system.md), [API](../reference/api.md), [database](../reference/database-schema.md), [testing](testing.md) và [thiết kế RAG](../proposals/rag-implementation.md). Skill chỉ dẫn cách chọn file và ra quyết định, tránh chép lại toàn bộ tài liệu kỹ thuật.
