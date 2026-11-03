# Phát triển backend local với ngân sách VPS 1 GB

## Mô hình chạy

```text
Frontend local :3000
  -> 127.0.0.1:8000 -> container API (app.main:app, 1 worker)
                         -> container MCP :8001 (app.mcp_server:app, 1 worker)
                         -> Supabase PostgreSQL qua TLS
                         -> Upstash Redis qua TLS
                         -> OpenRouter / E2B
```

PostgreSQL và Redis không chạy trong Docker local. MCP không publish port ra host.
VPS tiếp tục dùng hai entrypoint Python trên qua workflow SSH/venv hiện có.
Không cần chuyển VPS sang Docker để dùng môi trường phát triển này.

## Ngân sách tài nguyên

Giả định khởi điểm: VM có 1 GiB RAM. Người dùng xác nhận 1 GB; chưa đo MemTotal,
dịch vụ nền hoặc xác minh machine type trên VPS.

| Thành phần | Giới hạn RAM | Giới hạn CPU |
|---|---:|---:|
| API | 384 MiB | 0.12 CPU |
| MCP | 256 MiB | 0.08 CPU |
| Tổng ứng dụng | 640 MiB | 0.20 CPU |
| Chừa cho OS, Docker, dịch vụ nền và dự phòng | khoảng 384 MiB | phải đo lại |

Đây là budget kiểm thử, không phải số đo overhead. Nếu VM là e2-micro, Google mô tả
CPU duy trì tương đương 0.25 core và có burst; nhìn thấy 2 vCPU không có nghĩa được
dùng 2 core liên tục. Giới hạn 0.20 ở đây là lựa chọn kiểm thử bảo thủ, không mô phỏng
đúng cơ chế burst, CPU vật lý hay độ trễ mạng của GCP.

Nguồn: [GCP E2 shared-core](https://docs.cloud.google.com/compute/docs/general-purpose-machines#sharedcore),
[Docker Compose resource limits](https://docs.docker.com/reference/compose-file/services/).

`memswap_limit` bằng `mem_limit` để container không dùng swap che giấu thiếu RAM.
Tổng hai hard cap là 640 MiB nhưng mỗi service có trần riêng, không tự mượn phần trống
của service kia. Docker Desktop/WSL trên Windows vẫn dùng thêm RAM ngoài budget này.
Giới hạn áp dụng lúc chạy container, không giới hạn quá trình build image.
Không dùng reload khi đo; reloader sinh thêm process và làm sai phép so sánh với VPS.

Chạy các lệnh chỉ đọc trên VPS để hiệu chỉnh (không cần dừng dịch vụ):

```bash
free -m
ps -eo pid,comm,rss,%cpu --sort=-rss | head -20
vmstat 1 10
python3 --version
# Chỉ khi VPS có Docker:
docker stats --no-stream
```

Đo cả lúc rảnh và tải thực tế. Không lấy MemAvailable khi backend đang chạy rồi trừ
backend thêm lần nữa; RSS các process cũng có trang dùng chung. Chọn budget theo
đỉnh ứng dụng, tải nền, MemAvailable và khoảng dự phòng, không theo một snapshot duy nhất.
Nếu VPS chạy venv như workflow hiện tại thì không có overhead Docker cho ứng dụng đó.

## Cấu hình local riêng

Từ thư mục gốc, sao chép một lần nếu file local chưa tồn tại:

```powershell
Copy-Item back_end/.env.docker.example back_end/.env.docker.local
```

Điền Supabase URL chính và URL role read-only của **môi trường dev**, Upstash dev,
OpenRouter/E2B và hai secret ngẫu nhiên riêng. File `.env.docker.local` được Git và
Docker build context bỏ qua. Không sao chép nguyên `.env` production.
Nên dùng Supabase project riêng; không chạy PostgreSQL local.
Môi trường dev cần schema và dữ liệu mẫu phù hợp; container không tự tạo/migrate schema.
Xem [database schema](../reference/database-schema.md) trước khi chuẩn bị database.

Lý do không dùng chung production: startup API có `recover_orphaned_runs()`;
local có thể nhận các run chưa hoàn tất của VPS. Login, chat, chart và endpoint ghi
cũng thay đổi database. Upstash dùng chung có thể làm rate limit giữa hai môi trường
ảnh hưởng nhau. Docker chỉ cô lập process, không cô lập dữ liệu dịch vụ bên ngoài.

Tạo secret bằng Python hoặc trình quản lý mật khẩu, ví dụ chạy hai lần:

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

Giữ `DEBUG=false` để chạy validation giống production. Dùng model IDs đã xác minh
trên VPS nếu cần so sánh hành vi. Compose tắt email thông báo lỗi và bootstrap admin.

## Vòng lặp phát triển

Bật Docker Desktop với Linux containers, rồi chạy từ thư mục gốc:

```powershell
./scripts/backend_docker.ps1 check
./scripts/backend_docker.ps1 up
./scripts/backend_docker.ps1 verify
./scripts/backend_docker.ps1 stats
./scripts/backend_docker.ps1 logs
```

`up` build image và đợi health; sau mỗi lần sửa code, chạy lại `up` để build/recreate.
Image không bind-mount source: bản đang chạy chỉ đổi khi rebuild. Frontend chạy riêng
bằng `npm run dev`, với `NEXT_PUBLIC_API_URL=http://127.0.0.1:8000/api/v1`.
API docs: `http://127.0.0.1:8000/docs`.

`verify` kiểm tra JSON `status=healthy` của cả hai service, in giới hạn thực thi,
OOM flag, số restart và snapshot tài nguyên. HTTP 200 chứa `degraded` không đạt.
Health chỉ chứng minh kết nối phụ thuộc được kiểm tra, không chứng minh mọi tính năng.
Script không gọi AI, gửi email hoặc tự chạy migration.

```powershell
./scripts/backend_docker.ps1 down
```

Không dùng `scripts/start_local_stack.ps1` đồng thời với Docker vì trùng cổng và
có thể tạo thêm API scheduler. Stack mới có project name riêng `steam-backend-local`.

Nếu cần thay budget sau khi đo, thêm các biến Compose vào `.env.docker.local`:

```dotenv
API_MEMORY_LIMIT=384m
MCP_MEMORY_LIMIT=256m
API_CPU_LIMIT=0.12
MCP_CPU_LIMIT=0.08
BACKEND_LOCAL_PORT=8000
```

## Tổ chức code khi thêm chức năng

Giữ kiến trúc backend theo module trong một ứng dụng; mỗi tính năng REST không cần
một container riêng. API và MCP là hai process có trách nhiệm khác nhau.

| Vị trí | Trách nhiệm khi thêm tính năng |
|---|---|
| `app/api/v1/<feature>.py` | HTTP input, dependency auth/RBAC, status/response |
| `app/schemas/<feature>.py` | Contract request/response, validation |
| `app/services/<feature>_service.py` | Quy tắc nghiệp vụ và orchestration |
| `app/models/` + migration | Mapping và thay đổi schema có kế hoạch nâng cấp |
| `app/api/router.py` | Đăng ký feature router vào API chung |
| `app/agent_harness/` | Luồng model/tool; không nhét nghiệp vụ REST vào đây |
| `app/main.py` | Khởi tạo app, middleware, lifespan và health |
| `tests/` | Regression tests cho hành vi và contract |

Luồng: request -> router -> schema/auth -> service -> database -> response.
Giữ đường dẫn `/api/v1/...`, auth và response cũ khi refactor. Thay đổi phá contract
phải có kế hoạch chuyển đổi frontend. Route legacy chỉ import khi bật cờ tương ứng.
Không thêm query, tải model hoặc gọi mạng tại thời điểm import module.
Một API worker được giữ vì agent scheduler/cancel còn quản lý task trong process.

## Điều kiện trước khi deploy

1. Unit/regression tests qua; schema mới có đường nâng cấp từ schema VPS hiện tại.
2. Build và khởi động hai container thành công trong budget; không OOM/restart.
3. Thử login/refresh, games/dashboard, chat/tool/chart và cancel/restart trên Supabase dev.
4. Đo dưới tải đại diện (số user đồng thời và dữ liệu đủ lớn), theo dõi RAM đỉnh,
   CPU, latency và lỗi. Một health check xanh không đủ chứng minh chịu tải.
5. Kiểm tra Python/dependency versions giữa image (3.12) và VPS. Một số dependencies
   đang dùng khoảng phiên bản mở; build khác ngày chưa bảo đảm có cùng dependency set.
6. Xử lý conflict Git có sẵn và review diff trước merge main. Workflow deploy hiện
   chạy khi push main có thay đổi backend, chưa phụ thuộc vào kết quả workflow unit tests.
   Không coi CI đang chặn deploy lỗi; chỉ merge bản đã kiểm thử. Chưa chỉnh pipeline VPS.

Entry point VPS vẫn là `app.main:app` và `app.mcp_server:app`; local dùng service DNS
`http://mcp:8001/mcp`, VPS dùng loopback `http://127.0.0.1:8001/mcp` trong môi trường riêng.
Các file này chuẩn bị quy trình tương thích; cần runtime smoke/load và kiểm tra VPS
thật trước khi kết luận triển khai sẽ chạy bình thường.

## Kết quả kiểm tra ban đầu ngày 02/11/2026

- Compose parse thành công; tổng memory cap 671088640 bytes (640 MiB), MCP không
  publish port, API bind loopback. PowerShell script qua kiểm tra cú pháp.
- Python 3.12: 25/26 unit tests đạt, bao gồm 8 tests mới cho router và health probe.
  Test cũ `test_redact_text_removes_credentials_and_tokens` thất bại vì chuỗi
  `Authorization=Bearer ...` vẫn để lại token. Source/test tương ứng không thay đổi
  so với Git HEAD; đây là lỗi còn tồn tại, chưa sửa trong phạm vi này.
- Chưa build/run Docker, chưa đo RAM/CPU dưới tải, chưa truy cập VPS hoặc database thật.
  Docker CLI có sẵn nhưng Engine chưa hoạt động; lệnh start không tìm thấy cài đặt
  Docker Desktop hợp lệ. `.venv` cũ cũng trỏ tới Python không còn khả dụng; kiểm thử
  đã dùng dependency tạm với Python 3.12 thay cho `.venv` đó.

### Cập nhật sau khi người dùng tự chạy Docker ngày 02/11/2026

Người dùng đã cung cấp log build và `verify` thành công: API/MCP đều Healthy,
OOMKilled=false, restart=0. RAM snapshot lần lượt 99.47/70.11 MiB trong trần
384/256 MiB; quota CPU 0.12/0.08 core. Docker Engine hiện đã hoạt động theo bằng
chứng này; ghi nhận thiếu Engine ở trên là trạng thái trước đó.

Local đã dùng session pooler cho cả hai URL Supabase và cài CA chính thức vào image,
giữ DB_SSL_VERIFY=True. Người dùng chọn dùng chung Supabase/Upstash với VPS vì giới hạn
số database; phải quản lý phiên chạy local/VPS để tránh hai API scheduler cùng hoạt động.
Chưa có bằng chứng test chức năng/tải hoàn tất. Xem [sổ tay vận hành và test](local-operations-runbook.md)
để thực hiện các bước tiếp theo và khôi phục VPS sau phiên thử.
