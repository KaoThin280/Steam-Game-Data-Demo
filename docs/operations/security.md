# Kiểm soát bảo mật và giới hạn hiện tại

Tài liệu ghi nhận những kiểm soát đọc được trong code, không chứng nhận hệ thống đã an toàn hoặc role/grants đã được cấu hình đúng trên database live.

## Kiểm soát đã có trong code

- Settings bắt buộc `DATABASE_URL_READONLY`; production kiểm tra độ dài/default JWT secret, độ dài MCP secret, không cho wildcard CORS và yêu cầu OpenRouter key. Kiểm tra độ dài không chứng minh entropy, cũng không chứng minh hai URL DB dùng hai role khác nhau.
- JWT kiểm tra claim theo [security.py](../../back_end/app/core/security.py). Refresh token mới lưu digest SHA-256, có rotation và revoke khi đổi mật khẩu.
- TLS database xác minh chứng chỉ mặc định; chỉ tắt khi `DB_SSL_VERIFY=False`.
- Session/run/chart kiểm tra sở hữu; context chart được API chèn vào gateway. Role gate của UI chat chưa được áp dụng tương đương tại API.
- SQL chỉ nhận SELECT/WITH qua validator và có giới hạn kết quả/timeout. Quyền SELECT allowlist nằm trong [db_readonly_user.sql](../../back_end/db_readonly_user.sql); phải áp dụng và kiểm tra thực tế. Regex không phải bộ phân tích SQL hoặc allowlist quyền hoàn chỉnh.
- Python chạy qua E2B và có bộ lọc pattern trước khi gửi; bộ lọc không thay sandbox hay network policy.
- Các route legacy mặc định tắt. MCP yêu cầu service secret, trừ trường hợp DEBUG với secret trống; giữ cổng này nội bộ.
- Có giới hạn bước, history, event và dữ liệu tool; một run active mỗi phiên theo partial unique index nếu migration đã áp dụng.

## Auth trình duyệt

Backend hỗ trợ cả cookie và Bearer, ưu tiên cookie access. Refresh token chỉ đặt trong httpOnly cookie. Frontend vẫn có logic lưu token và gate refresh dựa vào refreshToken trong store, nên cần sửa/kiểm thử contract. Không mô tả ứng dụng là chỉ dùng Bearer hoặc không có rủi ro CSRF. SameSite/CORS/httpOnly là các lớp bảo vệ khác nhau; cần đánh giá CSRF theo cách triển khai cookie thực tế.

## Việc cần xác minh hoặc bổ sung

| Phần | Công việc còn lại |
|---|---|
| Database | Role AI thực sự chỉ đọc bảng Steam; RLS và grants không bị quyền PUBLIC/role khác mở rộng |
| Tool catalog | Ba tool mô phỏng hiện vẫn có trong catalog; chưa có per-tool authorization |
| Trace và chart | Runtime còn lưu str(exc); cần redaction, retention, quyền DB và độ mới cache; event không bất biến ở DB |
| Multi-worker | Lease, heartbeat và idempotency cho replay; chưa có exactly-once |
| Deployment | Một process manager, health kiểm tra payload, test gate, rollback, log rotation |
| Secrets | BE_log.txt và logVPS.txt tồn tại local, được ignore và không tracked trong Git index đã kiểm tra; review trước khi chia sẻ log |
| DB admin | Công cụ riêng có quyền theo credential DB, ngoài RBAC website; chỉ dùng nội bộ |

Xem [báo cáo rà soát](../maintenance/documentation-audit.md) và [deployment](deployment.md). Sửa tài liệu không tự sửa các khoảng trống trong code hoặc cấu hình triển khai.
