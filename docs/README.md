# Mục lục tài liệu

Tài liệu hiện hành được đối chiếu với mã nguồn trong repository ngày 01/11/2026. Các mô tả về triển khai là cấu hình hoặc hướng dẫn; chỉ log kiểm thử thực tế mới chứng minh dịch vụ hoạt động. Ví dụ request không phải dữ liệu truy vấn thực tế.

## Đọc theo nhu cầu

| Nhu cầu | Tài liệu | Phạm vi |
|---|---|---|
| Hiểu dự án làm gì | [Tổng quan](../README.md) | Mục tiêu, chức năng, thành phần, giới hạn |
| Chạy trên máy phát triển | [Local development](guides/local-development.md) | Điều kiện, môi trường, lệnh khởi động |
| Phát triển backend trong budget VPS 1 GB | [Docker local](guides/backend-docker-development.md) | API/MCP, Supabase/Upstash, giới hạn tài nguyên và quy trình kiểm thử |
| Điều hành và test backend local | [Sổ tay lệnh](guides/local-operations-runbook.md) | Cú pháp, tham số, health/log/RAM, smoke test và khôi phục VPS |
| Hiểu backend và luồng dữ liệu | [Kiến trúc hệ thống](architecture/system.md) | Request, lưu trữ, ranh giới dịch vụ |
| Hiểu một câu chat được xử lý thế nào | [Agent Harness](architecture/agent-harness.md) | History, model, tools, events, recovery |
| Chỉnh prompt và tool | [Prompt và tool](reference/agent-prompts-and-tools.md) | File nguồn, cấu hình, giới hạn |
| Tích hợp API | [API reference](reference/api.md) | Route hiện hành, auth, request, lỗi, legacy |
| Hiểu database | [Schema](reference/database-schema.md) | Steam, RBAC, agent, chart và độ lệch migration |
| Triển khai và kiểm tra dịch vụ | [Deployment](operations/deployment.md) | VPS, frontend, health, workflow |
| Chuyển VPS từ venv sang Docker | [Docker VPS migration](operations/docker-vps-migration.md) | Chuẩn bị GitHub, build release trên runner, chuyển đổi thủ công và rollback |
| Push bằng GitHub Desktop và cập nhật VPS | [Desktop → Actions → VPS](guides/github-desktop-to-vps.md) | File cần commit, conflict, workflow hiện tại và triển khai artifact |
| Cài systemd hoặc Compose | [VPS services](operations/vps-services.md) | Mẫu cấu hình hai process |
| Hiểu kiểm soát bảo mật | [Security](operations/security.md) | Kiểm soát trong code và giới hạn |
| Chạy kiểm thử | [Testing](guides/testing.md) | Unit, smoke, tiêu chí kiểm tra |
| Học từ code | [Lộ trình học](learning/backend-roadmap.md) | Bài học, thứ tự đọc, bài tập |
| Nghiên cứu mở rộng RAG | [Đề xuất RAG](proposals/rag.md) | Chưa triển khai, cách đánh giá |
| Chuẩn bị triển khai RAG | [Thiết kế RAG](proposals/rag-implementation.md) | Ingest, quyền, metadata, tích hợp, milestone và acceptance tests |
| Bắt đầu với file text và Pinecone | [Lần upload đầu tiên](guides/pinecone-first-upload.md) | File JSON mẫu, duyệt nội dung, kết nối, upload và search theo từng bước |
| Giao việc phát triển cho trợ lý | [Development skills](guides/development-skills.md) | Skill AI Agent và backend, phạm vi và cách sử dụng |
| Xem bài nộp đánh giá | [Agent Track](assessment/agent-track-submission.md) | Quyết định thiết kế và kịch bản demo |
| Xem thay đổi sau rà soát | [Kết quả rà soát](maintenance/documentation-audit.md) | Nội dung sửa và vấn đề code còn tồn tại |

README trong [backend](../back_end/README.md), [frontend](../front_end/README.md), [scripts](../scripts/README.md), [deploy](../deploy/README.md) và [db_admin](../db_admin/README.md) là điểm vào cho từng thành phần.

## Quy tắc tổ chức

- `architecture/`: mô tả hệ thống đã được triển khai trong code, kèm giới hạn.
- `reference/`: tra cứu contract API, schema, prompt và tool.
- `guides/`: thao tác local và kiểm thử; lệnh nêu rõ thư mục chạy.
- `operations/`: triển khai, vận hành và bảo mật.
- `learning/`: nội dung học; bài tập phải phân biệt với tính năng hiện có.
- `proposals/`: đề xuất chưa triển khai, không dùng làm mô tả hiện trạng.
- `assessment/`: tài liệu theo ngữ cảnh bài đánh giá.
- `archive/`: bản xuất cũ để đối chiếu, không dùng hướng dẫn vận hành.

Markdown là bản nguồn hiện hành. Hai bản Word cũ nằm trong [archive](archive/README.md); chúng chưa được xuất lại theo nội dung mới. Khi thay đổi route/model/tool, cập nhật tài liệu cùng thay đổi code. Không chép số dòng cố định hoặc kết quả benchmark chưa đo vào tài liệu.
