# Sổ tay vận hành và kiểm thử backend Docker local

Ngày lập: 02/11/2026. Người dùng tự chạy các lệnh; tài liệu này không tự vận hành dịch vụ.

> Cập nhật 03/11/2026: người dùng đã kiểm tra frontend, đăng nhập, chat và tạo biểu đồ
> thành công. Workflow deploy đã được chuẩn bị đổi sang build Docker release thủ công;
> xem [chuyển VPS sang Docker](../operations/docker-vps-migration.md). Các cảnh báo push
> tự bật VPS trong tài liệu này áp dụng workflow SSH cũ cho tới khi bản mới được push.
> Lỗi redaction unit test cũ đã có bản sửa và regression tests; chờ suite đầy đủ trên CI.

## 1. Trạng thái đã xác nhận

Theo log `up` và `verify` người dùng cung cấp ngày 02/11/2026:

| Thành phần | Trạng thái | RAM tại thời điểm đo | RAM tối đa | CPU tối đa | OOM / restart |
|---|---|---:|---:|---:|---|
| API | Healthy | 99.47 MiB | 384 MiB | 0.12 core | false / 0 |
| MCP | Healthy | 70.11 MiB | 256 MiB | 0.08 core | false / 0 |

Backend đã khởi động, health probe của cả hai service đạt. API health kiểm tra database
chính và Redis; MCP health kiểm tra database read-only. Startup API còn khám phá tools
qua MCP. Tổng RAM snapshot khoảng 169.58 MiB, tổng trần 640 MiB.

Chưa có bằng chứng frontend, login/refresh, chat gọi model, chạy E2B, chart và tải đồng
thời đã đạt. Số RAM trên không phải đỉnh khi có tải; không phải toàn bộ RAM Docker Desktop.
`nanoCPUs=120000000` nghĩa là 0.12 core, không phải 12 core. CPU % trong stats là mức
đang sử dụng, không phải phần trăm riêng của quota 0.12/0.08.

Mô hình:

```text
Browser -> Next.js local :3000 -> API container :8000
                                 -> MCP container :8001 (chỉ mạng Docker)
API/MCP -> Supabase session pooler (TLS)
API     -> Upstash Redis (TLS), OpenRouter
MCP     -> E2B khi tool cần sandbox
```

## 2. Phạm vi và quy tắc trước khi chạy

- Local đang dùng chung Supabase/Upstash với website. Login có thể ghi refresh token;
  chat ghi session/run/event/chart; request có thể tăng bộ đếm Redis. Dừng container
  không hoàn tác các dữ liệu này.
- Chỉ chạy một API scheduler trên database dùng chung: dừng API VPS trước khi chạy
  API local; dừng local trước khi mở lại VPS. Website mất backend trong phiên thử này.
- Không push backend lên `main` khi thử local: workflow deploy có thể bật lại VPS.
- Không chạy migration, reset database, xóa game/review hoặc cấp quyền database rộng
  để sửa lỗi test. Dùng tài khoản test và session có tiền tố `LOCAL-TEST` khi test thủ công.
- Giữ một worker/API. Docker project: `steam-backend-local`; service: `api`, `mcp`.
- Container: `steam-backend-local-api-1`, `steam-backend-local-mcp-1`.
- Không chạy `start_local_stack.ps1` cùng Docker: script đó chạy thêm backend/MCP native.

Tất cả lệnh PowerShell bên dưới bắt đầu ở thư mục gốc, trừ nơi ghi rõ SSH/Linux:

```powershell
cd C:\Users\ACER\Desktop\PET_project\Steam-Game-Data-Demo
```

Nếu đổi port qua `BACKEND_LOCAL_PORT`, thay `8000` trong các URL ví dụ cho khớp.

## 3. Các lệnh điều hành thường dùng

Cú pháp script: `./scripts/backend_docker.ps1 [-Action] <action>`.
`Action` là chuỗi; mặc định `check`. Script chỉ nhận 7 giá trị sau:

| Lệnh (PowerShell) | Ý nghĩa / tác dụng | Điều không được suy ra |
|---|---|---|
| `./scripts/backend_docker.ps1 check` | Parse Compose, kiểm tra cấu hình; thành công thường im lặng | Chưa kiểm tra mật khẩu, mạng, quyền DB hoặc secret trong app |
| `./scripts/backend_docker.ps1 build` | Build image; tải/cài dependency khi cần | Chưa chạy API; build không chịu trần RAM runtime |
| `./scripts/backend_docker.ps1 up` | Build, chạy nền, MCP healthy rồi API; chờ tối đa 300 giây | Startup có thể phục hồi run và ghi DB |
| `./scripts/backend_docker.ps1 verify` | Probe cả hai service; in quota, OOM, restart, stats | Không phải smoke test AI hay load test; OOM/restart được in để người đọc đánh giá |
| `./scripts/backend_docker.ps1 stats` | Một snapshot CPU/RAM/network/PIDs | Không phải peak memory |
| `./scripts/backend_docker.ps1 logs` | Theo dõi 100 dòng cuối và log mới của cả hai service | Ctrl+C chỉ thoát xem log, không dừng backend |
| `./scripts/backend_docker.ps1 down` | Dừng/xóa container và network của project | Giữ image, file source/env; không xóa Supabase/Upstash; dữ liệu chỉ có trong container có thể mất |

Mỗi lần sửa code, `.env.docker.local`, Dockerfile hoặc CA: dùng `up` để áp dụng.
Không dùng riêng `restart` để nạp lại environment/image. Code không bind mount;
sửa file trên host chưa làm process trong container đổi ngay.

Để gọi Compose trực tiếp, định nghĩa mảng tham số trong phiên PowerShell hiện tại:

```powershell
$composeArgs = @('--project-name', 'steam-backend-local', '--env-file', '.\back_end\.env.docker.local', '-f', '.\back_end\compose.local.yml')
docker compose @composeArgs ps -a
```

| Tham số | Giá trị / tác dụng |
|---|---|
| `--project-name` | Chọn đúng stack, tránh điều khiển nhầm project |
| `--env-file` | File dùng nội suy biến Compose; service env_file nạp cấu hình app |
| `-f` | File Compose cần dùng |
| `ps -a` | Liệt kê cả container đang chạy và đã dừng |
| `up -d` | Chạy nền |
| `--build` | Build trước khi chạy |
| `--wait --wait-timeout 300` | Chờ running/healthy, giới hạn chờ 300 giây |
| `exec -T <service> ...` | Chạy lệnh trong container đang chạy, không cấp terminal TTY |
| `run --rm --no-deps -T <service> ...` | Container tạm, không bật dependency; tự xóa khi xong |

Không chia sẻ output `docker compose config` đầy đủ hoặc `docker inspect` đầy đủ:
chúng có thể chứa credential. Dùng `config --quiet` và các format chọn trường bên dưới.

## 4. Kiểm tra và chẩn đoán

### 4.1 Docker Engine

```powershell
docker version
docker compose version
```

Cần cả Client và Server trong `docker version`. Có CLI nhưng thiếu Server chưa chạy được container.

### 4.2 Health qua HTTP và nội bộ

```powershell
Invoke-RestMethod -Method Get -Uri 'http://127.0.0.1:8000/health' -TimeoutSec 15
docker compose @composeArgs exec -T mcp python -m app.healthcheck http://127.0.0.1:8001/health
```

`-Method Get`: đọc trạng thái; `-Uri`: endpoint; `-TimeoutSec 15`: giới hạn chờ phía client.
API cần `status=healthy`, `database=connected`, `redis=connected`. HTTP 200 với
`status=degraded` vẫn là lỗi phụ thuộc. MCP probe thành công thường không in gì;
`$LASTEXITCODE` bằng 0. MCP không có port host nên không mở localhost:8001 từ Windows.

### 4.3 Log mới và trạng thái process

```powershell
docker logs --since 5m --tail 80 steam-backend-local-mcp-1
docker logs --since 5m --tail 80 steam-backend-local-api-1
docker logs --follow --tail 50 steam-backend-local-api-1
docker inspect --format 'status={{.State.Status}} oomKilled={{.State.OOMKilled}} exitCode={{.State.ExitCode}} restarts={{.RestartCount}}' steam-backend-local-mcp-1
docker inspect --format '{{json .State.Health}}' steam-backend-local-mcp-1
```

`--since 5m`: chỉ 5 phút gần nhất; `--tail 80`: tối đa 80 dòng cuối; `--follow`: theo
dõi liên tục, Ctrl+C để thoát. Đổi tên container để kiểm tra API. `exitCode=143` thường
liên quan SIGTERM; bản thân nó không chứng minh OOM. `unhealthy` không nhất thiết process
đã thoát. Compose đang đặt `restart: no`, nên process chết không được tự bật lại.

### 4.4 Xem quota và đo trong lúc test

```powershell
docker inspect --format '{{.Name}} memory={{.HostConfig.Memory}} memorySwap={{.HostConfig.MemorySwap}} nanoCPUs={{.HostConfig.NanoCpus}}' steam-backend-local-api-1 steam-backend-local-mcp-1
docker stats steam-backend-local-api-1 steam-backend-local-mcp-1
```

`memory` tính bằng byte; `nanoCPUs / 1000000000` là số core. `memorySwap` bằng `memory`
nghĩa là không cấp thêm swap cho container. `docker stats` chạy liên tục; Ctrl+C thoát.
Theo dõi trước, trong và sau mỗi tác vụ; quota tổng không mô phỏng đầy đủ CPU burst,
network và overhead VPS. Trần RAM từng service riêng biệt, không tự mượn phần dư của nhau.

### 4.5 Kiểm tra URL mà không in mật khẩu

```powershell
docker compose @composeArgs run --rm --no-deps -T mcp python -c "import os; from urllib.parse import urlsplit; keys=['DATABASE_URL','DATABASE_URL_READONLY']; [(print(k, 'host=', urlsplit(os.getenv(k,'')).hostname, 'port=', urlsplit(os.getenv(k,'')).port)) for k in keys]"
```

Chỉ in host/port từ cấu hình mới; không khởi động server hoặc query DB. Cả hai URL local
phải dùng session pooler đã chọn, port 5432. Role chính và read-only vẫn khác nhau;
username pooler có dạng `<role>.<project-ref>`. `@` trong mật khẩu được encode thành
`%40`, giữ dấu `@` phân cách trước hostname. Hai biến `DATABASE_URL_IPV4`/`IPV6`
không thay thế tên biến ứng dụng thực sự đọc.

### 4.6 Bảng xử lý lỗi đã gặp

| Lỗi | Kiểm tra / hành động |
|---|---|
| Network is unreachable | Kiểm tra cả hai host, nhất là read-only còn dùng direct IPv6; local đã chuyển session pooler |
| self-signed certificate in certificate chain | Kiểm tra `back_end/certs/supabase-ca.crt`, Dockerfile COPY CA và `RUN update-ca-certificates` trước USER; build lại, giữ DB_SSL_VERIFY=True |
| Password authentication failed | Role, mật khẩu riêng của role, URL encoding; không đổi role read-only sang owner |
| Tenant or user not found | Host pooler, project ref, username `<role>.<ref>` |
| API chưa chạy, MCP unhealthy | Sửa MCP trước; API đang đợi dependency |
| 401 | Token hết hạn/khác SECRET_KEY, đăng nhập lại; không chia sẻ token |
| 403 | Kiểm tra role/permission tài khoản; không mở rộng quyền DB để né lỗi |
| 409 khi gửi chat | Session đang có run queued/running; chờ hoặc hủy run đó |
| 429 | Dừng gửi thêm, chờ cửa sổ rate limit; Upstash đang dùng chung |
| OOMKilled=true | Đo workload, peak RAM, payload trước khi đổi budget; không gọi thêm worker để sửa |
| Login được nhưng refresh lỗi ở browser | Kiểm tra cookie/CORS/hostname/HTTPS; xem phần frontend bên dưới |

CA phải lấy từ Supabase dashboard chính thức. Không đưa private key/password vào file cert.
Tham khảo: [Supabase SSL](https://supabase.com/docs/guides/platform/ssl-enforcement).

## 5. Thứ tự test tiếp theo

### Bước A — Baseline không gọi AI

```powershell
./scripts/backend_docker.ps1 verify
Start-Process 'http://127.0.0.1:8000/docs'
```

Mở Swagger để đọc endpoint/schema. `/docs` mở được chỉ chứng minh API trả HTTP,
không chứng minh truy vấn nghiệp vụ đúng. Lưu snapshot stats làm baseline.

### Bước B — Login và API đọc bằng PowerShell

Dùng tài khoản test đã tồn tại, có quyền xem game/dashboard. Đoạn này nhập mật khẩu
ẩn, không ghi trực tiếp vào lịch sử lệnh. Login ghi trạng thái xác thực vào DB thật.

```powershell
$baseUrl = 'http://127.0.0.1:8000'
$testEmail = Read-Host 'Email tai khoan test'
$securePassword = Read-Host 'Mat khau' -AsSecureString
$credential = [PSCredential]::new($testEmail, $securePassword)
$loginBody = @{email=$testEmail; password=$credential.GetNetworkCredential().Password} | ConvertTo-Json
try {
    $login = Invoke-RestMethod -Method Post -Uri "$baseUrl/api/v1/auth/login" -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes($loginBody)) -TimeoutSec 30
} finally {
    $loginBody = $null
    $credential = $null
    $securePassword = $null
}
$headers = @{Authorization="Bearer $($login.access_token)"}
Invoke-RestMethod -Uri "$baseUrl/api/v1/auth/me" -Headers $headers -TimeoutSec 30
Invoke-RestMethod -Uri "$baseUrl/api/v1/games?page=1&page_size=5" -Headers $headers -TimeoutSec 30
Invoke-RestMethod -Uri "$baseUrl/api/v1/dashboard/overview" -Headers $headers -TimeoutSec 30
```

`ContentType`: body JSON UTF-8; `Body`: email/password; `Headers`: access token, không
in/chụp biến này. `page=1`: trang đầu; `page_size=5`: lấy tối đa 5 game (API cho 1–100).
Đạt khi đúng user, đúng cấu trúc dữ liệu và không 5xx; đối chiếu số liệu với cùng
database/bộ lọc, không dùng số game ước lượng từ README.

Thử bỏ `-Headers` ở `/auth/me`: cần bị từ chối (401), không trả thông tin người dùng.
Không dùng endpoint POST/DELETE game/review để kiểm thử trên dữ liệu chung.

### Bước C — Smoke test agent trên Docker đang chạy

Chạy script có sẵn bằng một PowerShell riêng. Bắt buộc `-NoStartServer` để không
bật thêm backend native. Khi API healthy, nhánh này không yêu cầu `.venv` Python.

```powershell
./scripts/test_agent_local.ps1 -NoStartServer -BaseUrl 'http://127.0.0.1:8000' -Email 'THAY_BANG_EMAIL_TEST' -TimeoutSeconds 240 -SkipCancelTest
```

| Đầu vào | Ý nghĩa |
|---|---|
| `-NoStartServer` | Chỉ dùng server đang chạy; nếu không truy cập được thì báo lỗi |
| `-BaseUrl` | URL gốc, không thêm `/api/v1` |
| `-Email` | Email tài khoản test thực tế; thay placeholder |
| `-Password` | Script hỗ trợ nhưng nên bỏ để nhập ẩn; tránh mật khẩu trong history |
| `-TimeoutSeconds 240` | Giới hạn chờ run của script; không tăng timeout provider/backend |
| `-SkipCancelTest` | Bỏ bài hủy trong lượt đầu để kiểm tra luồng cơ bản |
| `-Task '...'` | Câu hỏi thay thế cho tác vụ mặc định |
| `-ConversationSuite` | Chạy bộ hội thoại nhiều lượt, nhiều session; nhiều lần gọi provider hơn |

Script có thể lấy mật khẩu từ `LOCAL_TEST_PASSWORD` trong environment hoặc `back_end/.env`
trước khi hỏi. Nó không tự đọc `.env.docker.local` cho thông tin tài khoản test.
Đảm bảo tài khoản thực tế phù hợp. Không cần publish cổng MCP cho nhánh `-NoStartServer`.

Test này ghi session/run/events/chart và tiêu thụ quota OpenRouter/E2B. Chạy một lần,
theo dõi stats ở terminal khác; không lặp tự động khi fail. Đạt khi script in:

```text
PASS: local backend agent smoke test completed.
```

Đọc thêm câu trả lời/tool events: PASS không chứng minh mọi số liệu AI đưa ra chính xác.
Nếu timeout, kiểm tra run/log trước khi gửi lại: run có thể còn chạy sau khi client ngừng chờ.

### Bước D — Hội thoại, biểu đồ, hủy và phân quyền

Sau smoke cơ bản, chạy bộ hội thoại:

```powershell
./scripts/test_agent_local.ps1 -NoStartServer -BaseUrl 'http://127.0.0.1:8000' -Email 'THAY_BANG_EMAIL_TEST' -TimeoutSeconds 240 -ConversationSuite
```

Với luồng mặc định, bỏ `-SkipCancelTest` để chạy thêm bài hủy. Quan sát cụ thể:

| Bài test | Thực hiện | Điều kiện đạt |
|---|---|---|
| Dữ liệu qua tool | Hỏi số game/review | Có tool events, số khớp truy vấn cùng DB |
| Chart | Yêu cầu biểu đồ game theo tháng, rồi mở lại lịch sử | Chart có dữ liệu/nhãn đúng, đọc lại được |
| E2B | Yêu cầu phép phân tích cần Python | Event thể hiện tool Python/E2B thực sự chạy, không chỉ trả văn bản |
| Hội thoại | Hỏi tiếp dựa trên câu trước | Giữ đúng context; session khác không lẫn lịch sử |
| Hủy | Gửi tác vụ test rồi hủy run của chính tài khoản | Trạng thái cancelled và event hủy; phân biệt trường hợp run đã xong trước lúc hủy |
| Hai tài khoản test | User B thử đọc session/run test của A bằng ID | 404 theo kiểm tra ownership hiện tại, không lộ nội dung |

Các endpoint để tra trong Swagger: `POST /api/v1/agent-rpc/sessions`,
`POST /sessions/{session_id}/tasks` (dưới `/api/v1/agent-rpc`, body `message`),
`GET /runs/{run_id}`, `GET /runs/{run_id}/events`, `POST /runs/{run_id}/cancel`.
ID phải lấy từ response thực tế, không đoán ID dữ liệu người dùng khác.

### Bước E — Frontend local và cookie

Mở terminal PowerShell mới:

```powershell
cd C:\Users\ACER\Desktop\PET_project\Steam-Game-Data-Demo\front_end
# Chỉ khi thiếu node_modules hoặc cần đồng bộ dependency theo lockfile:
# npm ci
$env:NEXT_PUBLIC_API_URL = 'http://localhost:8000/api/v1'
npm run dev -- --hostname localhost --port 3000
```

Mở `http://localhost:3000`; dùng nhất quán `localhost` cho cả browser và API để
tránh cookie thuộc host khác. Biến environment chỉ áp dụng terminal này; cần restart
Next.js sau khi đổi URL. Frontend chạy ngoài budget backend 640 MiB.

Thử login, games, dashboard, chat, chart; mở DevTools > Network kiểm tra request đi
tới API local. Thử reload trang, refresh token và logout. Không chia sẻ request có token.

Lưu ý code cookie đặt `Secure=true` khi DEBUG=false (Compose hiện tại). HTTP local
có thể có khác biệt xử lý Secure cookie tùy browser; Bearer API pass không chứng minh
refresh cookie pass. Nếu gặp vòng login/401, kiểm tra cookie trong DevTools, CORS và
hostname; để kiểm thử sát production cần HTTPS local. Không tự tắt DEBUG/security
toàn bộ chỉ để che lỗi cookie. Đây là điểm cần kiểm chứng, chưa được log health xác nhận.

### Bước F — Tài nguyên dưới tải nhỏ

Đầu tiên chạy tuần tự 10 request đọc, dùng `$baseUrl` và `$headers` từ bước B:

```powershell
$samples = foreach ($i in 1..10) {
    $watch = [Diagnostics.Stopwatch]::StartNew()
    $result = 'ok'
    try {
        $null = Invoke-RestMethod -Uri "$baseUrl/api/v1/games?page=1&page_size=5" -Headers $headers -TimeoutSec 30
    } catch { $result = 'failed' }
    $watch.Stop()
    [pscustomobject]@{Request=$i; Milliseconds=$watch.ElapsedMilliseconds; Result=$result}
    Start-Sleep -Seconds 2
}
$samples | Format-Table
```

Đây là đo tuần tự, không phải load test đồng thời. `1..10`: số request; `2`: khoảng
nghỉ; `TimeoutSec 30`: timeout mỗi request. Quan sát `docker stats` trong terminal khác.
Sau đó thử hai tài khoản, hai session riêng, gửi mỗi tài khoản một tác vụ và quan sát.
Không mở flood test trên database/Redis dùng chung; dừng khi 429, 5xx, RAM tăng kéo dài
hoặc provider lỗi. Không tuyên bố chịu tải VPS chỉ từ 10 request hoặc hai người dùng.

### Bước G — Restart có kiểm soát

Chỉ làm khi các run test đã kết thúc, không có tác vụ thật còn chạy:

```powershell
docker compose @composeArgs restart api
./scripts/backend_docker.ps1 verify
```

`restart api` kiểm tra vòng đời với cấu hình cũ, có thể ngắt kết nối; chờ startup rồi
verify lại nếu lần đầu chưa sẵn sàng. Mở lại session test, kiểm tra lịch sử còn trong DB.
Test recovery giữa run là bài nâng cao: có thể replay và gọi provider thêm; chưa chạy
trên DB chung trước khi xác nhận không có run thật. Không coi recovery là exactly-once.

## 6. Kết thúc phiên local và mở lại VPS

1. Chờ run hoàn tất hoặc hủy run test của mình.
2. PowerShell local:

```powershell
./scripts/backend_docker.ps1 down
docker compose @composeArgs ps -a
```

3. SSH vào VPS, kiểm tra process/port để tránh tạo trùng (không dùng lại PID cũ):

```bash
ps -eo pid,ppid,args | grep -E '[u]vicorn|[g]unicorn|[a]pp\.main|[a]pp\.mcp_server'
ss -ltnp | grep -E ':8000|:8001'
```

4. Chỉ khi không còn process chiếm hai port, dùng đường dẫn đã ghi trong workflow
   (kiểm tra lại nếu VPS đã đổi thư mục). Không git pull/reset/pip upgrade ở bước khôi phục:

```bash
cd ~/my-project/back_end
test -x ./venv/bin/python3 && test -f .env
```

Nếu kiểm tra trên thành công, chạy MCP trước:

```bash
nohup ./venv/bin/python3 -m uvicorn app.mcp_server:app --host 127.0.0.1 --port 8001 --workers 1 >> mcp-server.log 2>&1 &
curl --fail --silent --show-error http://127.0.0.1:8001/health
```

Nếu chưa sẵn sàng, chờ vài giây rồi curl lại; không chạy lặp lệnh nohup. Chỉ khi JSON
MCP báo `healthy`, khởi động API:

```bash
nohup ./venv/bin/python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1 >> uvicorn.log 2>&1 &
curl --fail --silent --show-error http://127.0.0.1:8000/health
```

`nohup`: giữ process khi SSH đóng; `>>`: nối log cũ; `2>&1`: gom stderr vào log;
`&`: chạy nền; `--workers 1`: một worker; MCP bind loopback, API bind các interface.
Kiểm tra JSON API healthy/database connected/redis connected, không chỉ exit code curl.
Nếu lỗi, đọc `tail -n 80 uvicorn.log` hoặc `tail -n 80 mcp-server.log`; không bật thêm process.
Cuối cùng thử website đang host. Không cần đổi `.env` VPS sang `.env.docker.local`.

## 7. Checklist và bằng chứng cần lưu

- [x] Build image, API/MCP healthy theo log người dùng.
- [x] Quota thực thi 384/256 MiB, 0.12/0.08 core; OOM false, restart 0 tại snapshot.
- [ ] Login và API đọc đúng dữ liệu/quyền.
- [ ] Smoke agent qua OpenRouter/tool; E2B có bằng chứng nếu dùng.
- [ ] Chart, lịch sử, nhiều lượt, cancel, ownership hai user.
- [ ] Browser login/reload/refresh/logout, CORS và Secure cookie.
- [ ] Đo RAM/CPU/latency dưới workload đại diện, không OOM/restart bất thường.
- [ ] Restart và đọc lại dữ liệu; VPS khôi phục sau khi local dừng.
- [ ] Trước merge/deploy: unit suite, schema compatibility, review diff và conflict Git.

Mẫu ghi kết quả (không ghi credential/token/nội dung riêng của người dùng):

| Thời gian | Commit/image | Bài test | Input không nhạy cảm | Kết quả mong đợi | Thực tế | RAM đỉnh quan sát | Lỗi/run ID test |
|---|---|---|---|---|---|---|---|
| ... | ... | ... | ... | ... | ... | ... | ... |

Lấy mã phiên bản mà không in environment:

```powershell
git rev-parse --short HEAD
git status --short
docker inspect --format '{{.Name}} image={{.Image}}' steam-backend-local-api-1 steam-backend-local-mcp-1
```

HEAD không đại diện đầy đủ source nếu working tree có chỉnh sửa; ghi kèm trạng thái đó.
Unit tests trước đây có 25/26 đạt, một lỗi cũ về redaction token chưa sửa; không gọi
suite là xanh hoàn toàn. Xem [hướng dẫn kiểm thử](testing.md) và [Docker development](backend-docker-development.md).
Script unit native cần Python/venv hoạt động; runtime image không mặc định có pytest.
