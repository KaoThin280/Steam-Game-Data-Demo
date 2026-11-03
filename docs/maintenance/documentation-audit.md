# Kết quả rà soát tài liệu

Ngày đối chiếu: 01/11/2026. Phạm vi là tài liệu dự án Markdown và nội dung hai bản xuất Word, đối chiếu với source/config/SQL/test scripts trong checkout. Không truy cập database/VPS, không chạy migration/deploy, không xác nhận số liệu dataset hoặc benchmark. Log text và CV không phải tài liệu mô tả kiến trúc cần tổ chức lại.

## Nội dung đã sửa

| Nội dung cũ | Điều chỉnh |
|---|---|
| README chủ yếu giới thiệu bài nộp | Tổng quan sản phẩm, chức năng, thành phần và điểm vào tài liệu |
| Hai luồng chat legacy là luồng chính | Agent Harness hiện hành, REST frontend và JSON-RPC tool server tách riêng |
| Prompt nằm hết ở ai_service.py | Runtime/provider/MCP/router/config là các nguồn của harness |
| create_chart hỗ trợ pie/doughnut | Tool hiện tại hỗ trợ bar/line/scatter/area |
| Redis lưu hội thoại/cache sản phẩm | Rate limit; state và chart cache ở PostgreSQL |
| SQL/Alembic đủ dựng database mới | Nêu baseline cũ và phần schema/migration thiếu |
| DB read-only là tùy chọn | Settings yêu cầu URL; quyền thật vẫn phải xác minh |
| Fallback model tự hoạt động | Harness provider không dùng fallback setting |
| Khôi phục run an toàn exactly-once | Replay từ đầu, có nguy cơ lặp external call/chart write |
| MCP tương thích đầy đủ | Tập con tools/list, tools/call; lifecycle chưa đầy đủ |
| RAG cải thiện theo %/latency xác định | Đề xuất chưa triển khai; cần baseline/benchmark |
| RAM, quota, dataset/live state được khẳng định | Bỏ số chưa đo và xác nhận live chưa có bằng chứng |
| Mọi route cùng auth/rate-limit/error envelope | Mô tả theo route và handler thực tế |

## Sai lệch trong code còn tồn tại

Đợt này sửa tài liệu, không thay đổi behavior ứng dụng.

| Vấn đề | Bằng chứng | Ảnh hưởng / bước tiếp theo |
|---|---|---|
| Baseline schema chưa khớp ORM | [SQL](../../back_end/db_init_supabase.sql), [migration](../../back_end/alembic/versions/0001_initial.py), [models](../../back_end/app/models/steam.py) | Thiếu chuỗi migration dimension/junction, agent và nâng cấp chart; cần kiểm thử từ DB trống lẫn DB cũ |
| Refresh frontend/backend lệch contract | [api.ts](../../front_end/src/lib/api.ts), [auth.py](../../back_end/app/api/v1/auth.py) | FE kiểm tra refreshToken trong store, backend không trả nó trong JSON; cần chuyển client sang refresh cookie và test hết hạn token |
| Quyền UI/API chat khác nhau | [permissions.ts](../../front_end/src/utils/permissions.ts), [agent_rpc.py](../../back_end/app/api/v1/agent_rpc.py) | API chỉ yêu cầu active user + ownership; cần quyết định policy rồi đồng bộ |
| Timer sync không quản lý đủ hai process | [vps_sync.sh](../../deploy/vps_sync.sh) | Chỉ restart API, rsync có thể xóa runtime, kiểm tra requirements sau copy; không dùng mặc định |
| Health gate chỉ kiểm tra HTTP | [deploy.yml](../../.github/workflows/deploy.yml), [main.py](../../back_end/app/main.py) | HTTP 200 có thể là degraded; cần kiểm tra JSON và smoke dependencies |
| Logging rotation chưa gắn vào main | [main.py](../../back_end/app/main.py), [log_config.py](../../back_end/app/core/log_config.py) | Có helper chưa đồng nghĩa đã dùng; cần cấu hình rotation ngoài process hoặc gắn helper |
| Failure tools luôn xuất hiện | [mcp.py](../../back_end/app/agent_harness/mcp.py) | Chưa có chế độ chỉ bật trong test |
| Filter được nhận nhưng chưa áp dụng | [steam_service.py](../../back_end/app/services/steam_service.py) | genre/category ở GET games là no-op; cần nối dimension nếu muốn filter hoạt động |
| Lỗi run chưa được redact tổng quát | [runtime.py](../../back_end/app/agent_harness/runtime.py) | str(exc) được lưu vào run/event; không đồng nhất với redaction riêng của email |
| Có log text local được ignore | `BE_log.txt`, `logVPS.txt` | Không tracked trong Git index đã kiểm tra; không coi log local là bằng chứng deployment hiện tại hoặc đưa vào tài liệu công khai |

## Sắp xếp và phiên bản

Tài liệu chuyên đề được chuyển vào architecture/reference/guides/operations/learning/proposals/assessment. README thành phần giữ vai trò điểm vào. File tên cũ được thay bằng liên kết chuyển hướng khi phù hợp để không làm hỏng bookmark và tham chiếu trong code. Bản Word được đổi tên và giữ nguyên byte trong archive, không coi là bản cập nhật hiện hành.

Kiểm tra tài liệu gồm đích liên kết nội bộ, đối chiếu bảng route bằng AST và diff để bảo đảm thay đổi chỉ thuộc tài liệu. Đây không phải integration test ứng dụng.
