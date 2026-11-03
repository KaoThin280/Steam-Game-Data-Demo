# Kiểm thử và đánh giá kết quả

Tài liệu mô tả các kiểm tra hiện có và tiêu chí chạy thử. Việc có test trong repository không đồng nghĩa test đã chạy thành công trên môi trường đang dùng.

## Unit tests

Từ thư mục gốc trên PowerShell:

```powershell
./scripts/test_backend_unit.ps1
```

[tests](../../back_end/tests) bao gồm runtime, MCP contract, chuẩn hóa database URL và thông báo lỗi. Các dependency được kiểm soát hoặc giả lập để kiểm tra logic; không chứng minh credential, SQL migration hay quyền database thật. [CI](../../.github/workflows/backend-agent-tests.yml) chạy backend tests với Python 3.12.

## Smoke test với dịch vụ thật

```powershell
./scripts/test_agent_local.ps1
./scripts/test_agent_local.ps1 -ConversationSuite
```

Cần môi trường trong [local development](local-development.md) và tài khoản test. Script đọc `LOCAL_TEST_EMAIL`, `LOCAL_TEST_PASSWORD` từ cấu hình local hoặc tham số nhập; có thể khởi động backend/MCP khi cần. Test tạo session/run thật và gọi provider, nên có thể dùng quota dịch vụ và ghi dữ liệu thử nghiệm.

Conversation suite thực hiện hội thoại nhiều lượt tiếng Việt/Anh, yêu cầu câu hỏi dữ liệu có tool events, kiểm tra chart và đọc lại history. Đây không phải load test hoặc bộ đánh giá độ chính xác bao phủ mọi câu hỏi.

## Kiểm tra thủ công

| Tình huống | Điều cần quan sát |
|---|---|
| Đăng nhập và hết hạn token | Login, `/auth/me`, refresh cookie, logout; theo dõi 401 và store frontend |
| Câu hỏi tổng số game | Có tool phù hợp; đối chiếu số với SQL cùng database/role |
| Biểu đồ theo tháng | Đúng kiểu, khoảng thời gian, thứ tự và nhãn trục; mở lại session vẫn thấy chart |
| Hủy tác vụ | Run cancelled được lưu; ghi nhận tác vụ ngoài process có thể chưa dừng ngay |
| Restart API | Run có `run.recovered`, được replay; không khẳng định exactly-once |
| Hai user | Không đọc/sửa/xóa session hoặc chart của user khác |
| SQL đọc bảng auth | Role thực tế phải từ chối; regex validator riêng không đủ |
| Database mới | Đối chiếu đủ bảng/cột/index và chạy API/dashboard, không chỉ `SELECT 1` |

## Kiểm tra frontend

Từ `front_end/`: `npm run type-check`, `npm run lint`, `npm run build`. Các lệnh này kiểm tra code/build; cần mở UI để xác nhận auth, polling và render chart thực tế.

## Ghi lại bằng chứng

Lưu commit, môi trường, lệnh, thời gian, exit code, số test và kết quả quan sát. Phân biệt rõ kiểm tra tĩnh, unit, integration và load test; không gán latency/độ chính xác ước lượng thành kết quả đo. `scripts/EVALUATION.md` cũ mô tả chat legacy và đã được thay bằng tài liệu này. `scripts/test_e2e.py` tồn tại local nhưng được ignore; script này nhắm luồng legacy, không thuộc bộ test harness hiện hành.
