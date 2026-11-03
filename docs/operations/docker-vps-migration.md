# Đưa backend Docker lên VPS 1 GB

Cập nhật 03/11/2026. Tài liệu và cấu hình đã chuẩn bị; người dùng tự chạy lệnh.
Chưa chuyển VPS sang Docker. Người dùng đã xác nhận local chạy frontend, login,
chat và chart thành công; chưa có bằng chứng load test hay rollout production.

## 1. Những việc phải xử lý trước khi push

1. Đổi mật khẩu từng xuất hiện trực tiếp trong `scripts/test_e2e.py`,
   `db_admin/config.py`, `db_admin/.env.example`. Kiểm tra phát hiện giá trị trong script
   test trùng mật khẩu database local. Đổi cả credential có dùng lại cùng giá trị:
   database role liên quan, tài khoản test và admin nếu áp dụng. Cập nhật `.env` VPS,
   `.env.docker.local`, và cấu hình admin riêng; không gửi giá trị vào chat.
   Mã đã bỏ credential trực tiếp, nhưng lịch sử Git vẫn có thể chứa chúng.
   Rà soát GitHub secret scanning và lịch sử sau khi rotate; không force-push/xóa lịch sử
   tùy tiện. Audit ở đây là kiểm tra mẫu và đối chiếu secret local, không bảo đảm toàn
   bộ lịch sử sạch.
2. Resolve conflict `Instruction4Agent.md`. Bản trong working tree là hướng dẫn mới;
   để giữ bản đó, người dùng có thể chạy `git add -- Instruction4Agent.md` sau khi đọc.
   Không chạy `git checkout --theirs` hoặc `git rm` nếu muốn giữ nội dung local.
3. Xác định URL backend công khai và proxy hiện tại. URL `localhost:8000` chỉ là local.
   Chưa biết URL production thì chỉ có thể chuẩn bị release, chưa xác nhận website
   truy cập được sau rollout. Xem mục 3.
4. Tests đầy đủ phải đạt trước tạo artifact. Lỗi redaction cũ đã sửa thứ tự xử lý
   Bearer trước assignment và thêm regression cases; cần kết quả CI của commit mới.

### Kiểm tra và stage bằng PowerShell ở thư mục dự án

```powershell
git status --short
git diff --name-only --diff-filter=U
git check-ignore back_end/.env back_end/.env.docker.local back_end/.env.production front_end/.env.local db_admin/.env
git ls-files -- '*.env' '*.env.local' '*.env.production'
```

`check-ignore` phải hiện các file cấu hình thật; `ls-files` không được hiện credential
thật đang tracked. `.gitignore` không tự untrack file đã có trong index.
File CA `back_end/certs/supabase-ca.crt` là certificate công khai, cần đưa lên cùng
Dockerfile; không upload private key. `.env*.example` chỉ chứa placeholder.

Sau khi đọc và chọn giữ bản Instruction4Agent local:

```powershell
git add -- Instruction4Agent.md
git add -A
git diff --cached --check
git diff --cached --name-status
git diff --name-only --diff-filter=U
```

Chỉ commit khi hết conflict, đã rà soát staged diff và credential được loại bỏ.
Đặc biệt stage lại cả ba file đã bỏ mật khẩu; index cũ không tự cập nhật theo working tree.
Không commit `.env.production`, `.env.docker.local`, log, image tar hoặc dependency cache.
Các tài liệu Word trong `docs/archive` là bản lịch sử, có thể giữ nhưng không bắt buộc
cho deploy. Source/code/docs/cert/Compose mới cần được stage đầy đủ.

```powershell
git commit -m "Prepare Docker production release and deployment guide"
git push origin main
```

Nếu Git yêu cầu xử lý merge/rebase đang dở, hoàn tất theo trạng thái Git thay vì force-push.
Các lệnh này do người dùng chạy, chưa được trợ lý thực hiện.

## 2. Cơ chế deploy mới

`.github/workflows/deploy.yml` đã đổi từ SSH/venv tự động sang workflow **chạy thủ công**:

```text
GitHub Actions: tests -> build Linux amd64 -> non-root import probe
              -> export image + Compose + checksum thành artifact
Người vận hành: tải artifact -> SCP VPS -> docker load -> Compose up -> smoke test
```

Push code không còn tự restart VPS bằng workflow này. Workflow chỉ tạo artifact khi
tests và build đạt; không SSH tới VPS, không đọc secrets VPS, không cần registry công khai.
Image gắn commit SHA; artifact giữ 7 ngày, hãy tải và giữ bản rollback. Dependency
còn có khoảng phiên bản mở; build lại cùng SHA ở ngày khác có thể khác dependency.
Giữ artifact/checksum/image ID thực tế, không chỉ ghi SHA source.

Image build trên runner, VPS chỉ giải nén/load/chạy. Quota RAM/CPU container không
giới hạn RAM và đĩa của `docker load`; cần đủ headroom và dung lượng cho hai bản image.

## 3. Xác định đường vào production trước cutover

Trong Vercel (hoặc nền tảng frontend), xem Environment Variables của deployment thật:
`NEXT_PUBLIC_API_URL`. Không dùng giá trị file `.env.local` trên máy để suy ra production.
Trên SSH VPS, chạy chỉ đọc:

```bash
uname -m
cat /etc/os-release
free -m
df -h
docker version
docker compose version
ss -ltnp | grep -E ':80|:443|:8000|:8001'
```

Nếu dùng Nginx:

```bash
sudo nginx -T
```

Chỉ chia sẻ domain, listen/proxy_pass cần thiết, không gửi cấu hình chứa secret.
Image workflow hiện dành cho `x86_64`/amd64. Nếu VPS là ARM, cần đổi target build trước.
Nếu chưa có Docker Engine/Compose plugin, cài theo distro đã xác định, hướng dẫn chính
thức: https://docs.docker.com/engine/install/ . Không cài Docker Desktop trên Linux VPS.
Sau khi cài, xác nhận tài khoản SSH có quyền chạy Docker; quyền này tương đương quyền root.

Production Compose mặc định publish `127.0.0.1:8000`:

- Có Nginx/proxy trên host: proxy HTTPS tới `http://127.0.0.1:8000`, giữ MCP private.
- Đang dùng trực tiếp IP:8000: cần chủ động chọn `API_BIND_ADDRESS=0.0.0.0` cùng firewall
  phù hợp. HTTP public không tương đương HTTPS production (cookie Secure, mixed content
  từ frontend HTTPS); thiết lập domain/HTTPS trước khi coi rollout hoàn tất.
- Chưa xác định proxy: giữ loopback và chưa cắt hệ thống đang host.

API hiện dùng `--no-proxy-headers` để không tin header giả từ client. URL/client IP từ
proxy chưa được chuẩn hóa; kiểm tra redirect và rate-limit hành vi qua proxy. Nếu cần
trusted proxy headers, cấu hình chính xác địa chỉ proxy/Docker gateway sau khi kiểm tra;
không tin toàn bộ `*` trên cổng mở public. CORS phải là origin frontend thật, JSON list.

## 4. Tạo và tải release

Sau khi code đã lên GitHub:

1. Actions -> **Build tested Docker release (manual VPS rollout)** -> Run workflow.
2. Chọn branch/commit muốn triển khai; chỉ dùng commit đã review.
3. Chờ tất cả bước thành công; tải artifact `steam-backend-<SHA>` và giải nén vào một
   thư mục riêng, ví dụ `$HOME\Downloads\steam-release`.
4. Artifact gồm `backend-image.tar.gz`, `compose.production.yml`, `production.env.example`,
   `image-tag.txt`, `SHA256SUMS`, README này. Không có `.env` thật.

Trên SSH tạo thư mục release mới (thay `<SHA>` bằng SHA thực, không nhập dấu ngoặc):

```bash
mkdir -p ~/steam-releases/<SHA>
```

Trên PowerShell local, thay `<VPS_IP>` bằng IP thật và `<SHA>` bằng mã release:

```powershell
scp "$HOME\Downloads\steam-release\*" thinhthinhhay2002@<VPS_IP>:~/steam-releases/<SHA>/
```

`scp` cần kết nối SSH/key phù hợp. Nếu dùng đường dẫn key riêng, thêm `-i <path-to-key>`;
không upload private key. Có thể dùng upload file của giao diện SSH rồi đặt file vào
đúng thư mục. Không ghi đè thư mục bản đang chạy hoặc bản rollback.

## 5. Chuẩn bị env VPS và preflight

Trên SSH:

```bash
cd ~/steam-releases/<SHA>
sha256sum -c SHA256SUMS
docker load -i backend-image.tar.gz
cat image-tag.txt
umask 077
cp production.env.example .env.production
chmod 600 .env.production
nano .env.production
```

Chỉ `cp` khi file `.env.production` chưa tồn tại; không ghi đè secret đã điền. Cập nhật:

- `BACKEND_IMAGE`: đúng nội dung `image-tag.txt`.
- Hai URL Supabase session pooler đã xác minh, hai role đúng; Upstash URL TLS.
- JWT settings và secret VPS còn an toàn; secret đã lộ phải rotate, sẽ cần đăng nhập lại.
- `MCP_SHARED_SECRET` mạnh, chung cho API/MCP của cùng deployment.
- `CORS_ORIGINS`: domain frontend thật; OpenRouter/E2B của production.
- Bind address/proxy theo mục 3. Compose ép DEBUG=false, DB_SSL_VERIFY=true và MCP DNS nội bộ.
- Không bootstrap admin ngoài ý muốn; để email notification tắt cho tới khi cấu hình riêng.

Chạy preflight trước khi dừng backend cũ:

```bash
docker compose --env-file .env.production -f compose.production.yml config --quiet
docker compose --env-file .env.production -f compose.production.yml run --rm --no-deps -T api python -c 'from app.core.config import settings; print("SETTINGS OK")'
```

Lệnh chỉ import Settings, không mở database hoặc khởi động scheduler.
Không in Settings ra terminal. Preflight này chỉ validate cấu hình, chưa chứng minh DB
hay provider hoạt động. Log có thể chứa thông tin nhạy cảm nếu lỗi; che trước khi chia sẻ.

## 6. Chuyển từ native VPS sang Docker

1. Dừng local sau khi run test hoàn tất:

```powershell
./scripts/backend_docker.ps1 down
```

2. Trên VPS, ghi lại thư mục/command của bản native để rollback. Không `git reset`,
   sửa `.env` cũ hoặc xóa venv. Kiểm tra lại PID hiện tại:

```bash
ps -eo pid,ppid,args | grep -E '[u]vicorn|[g]unicorn|[a]pp\.main|[a]pp\.mcp_server'
```

3. Khi không có tác vụ cần giữ, gửi `kill -TERM <PID_API>`; chờ process API dừng,
   rồi `kill -TERM <PID_MCP>`. Chỉ dùng PID vừa xác minh, không PID trong chat cũ.
   Nếu process do systemd/timer quản lý, dừng manager đó trước để tránh tự bật lại.
4. Xác nhận port 8000/8001 đã rảnh rồi chạy trong thư mục release:

```bash
docker compose --env-file .env.production -f compose.production.yml up -d --no-build --pull never --wait --wait-timeout 300
docker compose --env-file .env.production -f compose.production.yml ps -a
docker compose --env-file .env.production -f compose.production.yml exec -T mcp python -m app.healthcheck http://127.0.0.1:8001/health
docker compose --env-file .env.production -f compose.production.yml exec -T api python -m app.healthcheck http://127.0.0.1:8000/health
curl --fail --silent --show-error http://127.0.0.1:8000/health
```

MCP không publish port; API host port giữ 8000. Quota giữ như local: 384/256 MiB,
0.12/0.08 CPU; restart `unless-stopped`, log tối đa 2 file x 5 MB/service.
Health check unhealthy không tự restart process; restart policy xử lý process exit.

5. Test từ URL HTTPS backend thật và frontend đã host: login, refresh/logout, games,
   chat, chart, history. Kiểm tra CORS/cookie, không chỉ localhost health. Theo dõi:

```bash
docker compose --env-file .env.production -f compose.production.yml logs --since 5m --tail 80
docker stats steam-backend-production-api-1 steam-backend-production-mcp-1
free -m
```

Chỉ xác nhận chuyển đổi hoàn tất khi đường public, chức năng và tài nguyên ổn. Đánh dấu
release directory đang chạy. Không khởi động local hoặc native song song với Docker VPS.

## 7. Rollback và lần cập nhật sau

Nếu lần chuyển đầu thất bại:

```bash
docker compose --env-file .env.production -f compose.production.yml down
```

Xác nhận container đã dừng trước khi chạy native cũ; dùng lệnh/venv/env đã ghi lại,
MCP trước API. Xem phần khôi phục trong `docs/guides/local-operations-runbook.md` của
repository. Nếu secret đã rotate, bản native cũng cần secret mới tương ứng.
Rollback process/image không rollback dữ liệu đã ghi và không undo migration.

Lần cập nhật Docker sau: chuẩn bị/load release mới trước; giữ image và thư mục release
cũ. Dừng stack cũ (`down`) rồi `up --no-build --pull never --wait` từ release mới.
Project name cố định nên chỉ có một cặp API/MCP. Có downtime; không blue/green trên
database dùng chung vì agent scheduler chưa hỗ trợ hai API song song.
Nếu lỗi, `down` bản mới, quay thư mục cũ và `up` với `.env.production` cũ đã cập nhật
credential nếu cần. Không `docker system prune -a` vì có thể mất image rollback.
Không có data volume local cho app hiện tại; dữ liệu bền ở Supabase, thư mục temp trong
container là tạm. Chức năng mới ghi file bền phải thiết kế volume/backup trước triển khai.

## 8. Trạng thái kiểm chứng của thay đổi

- Local frontend/login/chat/chart: người dùng xác nhận ngày 03/11/2026.
- Production Compose và workflow: chuẩn bị để review; chưa chạy trên VPS/GitHub.
- URL/proxy production: người dùng chưa nhớ, cần kiểm tra mục 3.
- Git conflict và rotation credential: còn cần người dùng thực hiện trước publish.
- Unit suite đầy đủ: workflow sẽ chạy và chặn artifact nếu fail; không coi test UI
  local là thay thế unit/regression hoặc kiểm tra release image.

Tài liệu Docker: https://docs.docker.com/reference/cli/docker/compose/up/
