# Cài đặt và chạy local

Các lệnh PowerShell dưới đây chạy từ thư mục gốc repository, trừ khi có ghi chú. Đây là hướng dẫn khởi động, không phải biên bản chạy thành công.

## Điều kiện

- Python 3.12 theo môi trường CI; Node.js/npm để chạy Next.js.
- PostgreSQL có schema Steam đã chuẩn hóa, bảng tài khoản/RBAC, chart và Agent Harness. Đọc [schema và migration](../reference/database-schema.md) trước khi dùng database mới: script khởi tạo cũ chưa dựng đủ schema hiện tại.
- Kết nối Redis qua TLS, OpenRouter API key/model có quyền sử dụng; E2B key nếu dùng Python tool.

## Chuẩn bị dependency

```powershell
python -m venv back_end/.venv
./back_end/.venv/Scripts/python.exe -m pip install -r back_end/requirements.txt
./back_end/.venv/Scripts/python.exe -m pip install -r back_end/requirements-test.txt
Push-Location front_end
npm ci
Pop-Location
```

Tạo `back_end/.env` từ [mẫu backend](../../back_end/.env.example) nếu chưa có; giữ nguyên cấu hình riêng đã tồn tại. Các trường cần kiểm tra:

| Biến | Mục đích |
|---|---|
| `DATABASE_URL` | Kết nối chính cho dữ liệu ứng dụng |
| `DATABASE_URL_READONLY` | Kết nối role hạn chế cho AI; bắt buộc cả khi DEBUG |
| `REDIS_URL` | URL Redis TLS; có thể cấu hình HOST/PORT/PASSWORD thay thế |
| `OPENROUTER_API_KEY`, `OPENROUTER_MODEL` | Provider cho câu hỏi thật; model phải hỗ trợ tool calling |
| `E2B_API_KEY` | Python sandbox |
| `CORS_ORIGINS` | Ví dụ `["http://localhost:3000","http://127.0.0.1:3000"]` |
| `SECRET_KEY`, `MCP_SHARED_SECRET` | Bí mật JWT và giao tiếp dịch vụ khi khởi động thủ công |
| `MCP_SERVER_URL` | Mặc định `http://127.0.0.1:8001/mcp` |
| `BOOTSTRAP_ADMIN_EMAIL`, `BOOTSTRAP_ADMIN_PASSWORD` | Tùy chọn tạo admin; cần seed role admin trước |

Không dùng giá trị placeholder làm credential thật. `.env` đọc theo working directory backend; không cần đưa secret backend vào frontend.

## Chạy cả stack

```powershell
./scripts/start_local_stack.ps1
```

Script yêu cầu sẵn `back_end/.venv/Scripts/python.exe` và `front_end/node_modules`; không tự cài dependency. Nó đặt DEBUG, tạo secret tạm cho JWT/MCP, khởi động MCP rồi API và frontend. API bind `0.0.0.0`, MCP bind loopback; dùng script này trong môi trường phát triển tin cậy. `Ctrl+C` dừng các process script đã tạo. Dùng `-NoReload` khi kiểm tra hành vi restart không qua auto-reload.

Mở frontend ở `http://localhost:3000`; API docs ở `http://127.0.0.1:8000/docs`; demo backend ở `http://127.0.0.1:8000/agent-demo`. Log nằm ở `back_end/test_logs/`.

## Chạy thủ công

Mở hai terminal riêng, cùng working directory `back_end` và cùng `.env`. Terminal thứ nhất:

```powershell
./.venv/Scripts/python.exe -m uvicorn app.mcp_server:app --host 127.0.0.1 --port 8001
```

Sau khi MCP sẵn sàng, terminal thứ hai:

```powershell
./.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Frontend đọc `NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1` trong `front_end/.env.local`; chọn hostname nhất quán với cookie/CORS. Chạy `npm run dev` từ `front_end`. Trường URL phải chứa `/api/v1`.

## Kiểm tra và xử lý lỗi

Kiểm tra JSON `/health`, không chỉ HTTP 200: API trả `status="degraded"` khi database/Redis lỗi nhưng vẫn có thể trả HTTP 200. Health API không kiểm tra live OpenRouter/E2B/MCP sau startup. Thử đăng nhập, tạo session và chạy câu hỏi dữ liệu để kiểm tra đủ luồng.

| Triệu chứng | Kiểm tra |
|---|---|
| Startup thiếu read-only URL | Điền `DATABASE_URL_READONLY`, kiểm tra role/grants/RLS |
| MCP connection error | MCP chạy trước, đúng URL và cùng service secret |
| Bảng/column không tồn tại | Đối chiếu schema hiện tại; không chỉ chạy migration cũ |
| Đếm dữ liệu trả 0 bất thường | So sánh quyền và RLS của role chính/read-only |
| Trình duyệt 401 sau khi token hết hạn | Xem lỗi contract refresh còn tồn tại trong báo cáo rà soát |
| Model/tool lỗi | Kiểm tra event và credential/quota, không suy ra từ health |

Xem [kiểm thử](testing.md) cho unit và smoke test.
