# Đồng bộ bản hiện tại: GitHub Desktop -> GitHub Actions -> Docker VPS

Ngày: 03/11/2026. Chỉ hướng dẫn file hiện tại; không xử lý lịch sử Git.
Người dùng tự commit/push và chạy lệnh VPS.

## 1. File nào lên GitHub?

Đã cập nhật `.gitignore` để bỏ qua:

- `.env`, `.env.local`, `.env.docker.local`, `.env.production` và các biến thể riêng;
- Python venv/cache, node_modules, Next.js build/cache, tsbuildinfo;
- log/test_logs, scripts/output, temp_data, test-results, playwright-report;
- thư mục release tải về, image tar/gzip và ZIP artifact tên steam-backend-* ở root;
- private key `.key`/`.pem`/`.p12`/`.pfx`, id_rsa/id_ed25519, credentials.local.json.

Giữ trên GitHub: source backend/frontend, requirements/lockfile, Dockerfile,
Compose local/production, scripts vận hành, tests, docs, knowledge/skills của dự án,
`.gitattributes`, `.gitignore`, `.dockerignore`, các file `.env*.example` đã khai báo.
Giữ cả `back_end/certs/supabase-ca.crt`: đây là CA công khai và Dockerfile đang COPY nó.
Không ignore toàn bộ `certs/`, `.github/`, `docs/` hoặc lockfile.

`.gitignore` không tự loại file đã tracked/staged. Hiện không cần xóa source để giảm
số file trong Changes. Tài liệu cũ trong docs/archive được giữ vì có link tham chiếu;
chúng không phải dependency runtime nhưng là tài liệu dự án, không phải cache.

## 2. GitHub Actions hiện làm gì?

| File | Khi nào chạy? | Kết quả | Có đụng VPS không? |
|---|---|---|---|
| `.github/workflows/backend-agent-tests.yml` | Push/PR có thay đổi backend hoặc chính workflow; cũng chạy tay được | Unit tests Python 3.12 | Không |
| `.github/workflows/deploy.yml` | Chỉ khi chọn Run workflow | Tests -> build image amd64 -> import probe -> artifact release | Không; người dùng tự triển khai artifact |
| `.github/workflows/ci.yml` | File local đang ignore, không tracked | Không đưa thêm workflow cũ này lên trong đợt push | Không có hiệu lực từ file local này |

Tên workflow release: **Build tested Docker release (manual VPS rollout)**.
File vẫn tên deploy.yml nhưng không còn lệnh SSH, git reset, fuser, nohup hay pip install
trên VPS. Push bản mới sẽ không tự chuyển VPS sang Docker. Giữ cả hai workflow tracked
trong commit để thay thế đúng pipeline cũ và không bỏ sót bước kiểm thử.

## 3. Resolve conflict hiện có, giữ nội dung local

Git hiện có conflict modify/delete ở `Instruction4Agent.md`. Đây không phải file rác;
không đưa nó vào gitignore để che conflict. Nội dung working tree là bản hướng dẫn
hiện tại cần giữ.

Trong GitHub Desktop chọn đúng repository Steam-Game-Data-Demo, branch main.
Nếu Desktop hiển thị hộp conflict có lựa chọn giữ file đã sửa, chọn giữ bản đang có
trên máy, không chọn xóa. Nếu không có lựa chọn rõ ràng, dùng Repository -> Open in
Terminal (hoặc mở PowerShell tại thư mục dự án) và chạy đúng hai lệnh:

```powershell
git add -- Instruction4Agent.md
git diff --name-only --diff-filter=U
```

Lệnh thứ nhất đánh dấu bản hiện tại là kết quả giải quyết; không commit hoặc push.
Lệnh thứ hai cần không còn in tên file. Trở lại GitHub Desktop để commit toàn bộ.
Nếu Desktop còn yêu cầu hoàn tất merge, làm theo trạng thái hiển thị; không discard
changes, không force push và không reset repository để xử lý conflict này.

## 4. Commit và push bằng GitHub Desktop

1. Current Repository: Steam-Game-Data-Demo; Current Branch: main.
2. Tab Changes: chọn toàn bộ file dự án cần đồng bộ sau khi ignore đã có hiệu lực.
3. Xác nhận có `.github/workflows/deploy.yml`, `backend-agent-tests.yml` nếu thay đổi,
   Dockerfile, Compose, CA `.crt`, `.env.production.example`, và docs mới.
4. Xác nhận không có `.env` thật, private key, image tar, node_modules hoặc venv.
   Các file có hậu tố `.example` phải chỉ chứa mẫu, không dùng credential thật.
5. Summary gợi ý: `Prepare Docker local and VPS release workflow`.
6. Bấm **Commit to main**, sau đó **Push origin**. Nếu yêu cầu Fetch/Pull vì remote
   mới hơn, đọc diff và resolve conflict trước; không dùng force push.
7. Mở repository trên GitHub và kiểm tra commit mới cùng các file quan trọng.

Kiểm tra thêm bằng PowerShell nếu muốn:

```powershell
git status --short
git ls-files -- '*.env' '*.env.local' '*.env.production'
git ls-files -- .github/workflows/deploy.yml back_end/certs/supabase-ca.crt back_end/compose.production.yml
```

Sau commit/push, status cần sạch nếu không sửa tiếp. Lệnh liệt kê env thật cần không
in file. GitHub Desktop có thể hiển thị việc stage khác nhau, nhưng commit cuối phải
chứa phiên bản mới nhất của tất cả file đã chọn.

Tham khảo UI: https://docs.github.com/en/desktop/making-changes-in-a-branch/committing-and-reviewing-changes-to-your-project-in-github-desktop

## 5. Tạo image từ chính commit đã push

1. GitHub -> repository -> **Actions**.
2. Kiểm tra workflow **Backend agent tests** của commit mới. Nếu đỏ, đọc lỗi, sửa
   local và commit/push lại; không dùng artifact của commit khác để gọi là bản mới.
3. Chọn **Build tested Docker release (manual VPS rollout)** -> **Run workflow** -> main.
4. Workflow release chạy tests lại và chỉ xuất artifact khi mọi bước đạt.
5. Mở run xanh, kiểm tra SHA commit đúng; ở Artifacts tải `steam-backend-<SHA>`.
6. Giải nén ZIP vào thư mục riêng, ví dụ `$HOME\Downloads\steam-release`.

Trong thư mục giải nén phải có:

```text
backend-image.tar.gz
compose.production.yml
production.env.example
image-tag.txt
SHA256SUMS
README.md
```

GitHub Actions không cần DB/Redis production hoặc SSH secrets để build release.
Artifact không chứa env thật. Thời gian giữ artifact: 7 ngày, nên giữ bản đã tải để rollback.
Không upload tar này vào Git repository. VPS không cần build source bằng pip trên RAM 1 GB.

## 6. Đồng bộ sang VPS

Ở cơ chế này, đồng bộ VPS nghĩa là đưa **image của commit mới và Compose** lên VPS.
Không cần git pull trên VPS để chạy image, và không chạy script deploy native cũ.

### A. Kiểm tra VPS và đường public (SSH Linux)

```bash
uname -m
docker version
docker compose version
free -m
df -h
ss -ltnp | grep -E ':80|:443|:8000|:8001'
```

Cần Linux amd64/x86_64, Docker Engine và Compose plugin; đủ đĩa/RAM để load image.
Nếu chưa cài, dừng ở bước này và cài đúng distro, không Docker Desktop trên VPS.
URL backend public hiện chưa được xác nhận. Kiểm tra NEXT_PUBLIC_API_URL trong cấu
hình frontend đã deploy. Nếu dùng Nginx trên host, proxy phải trỏ 127.0.0.1:8000.
File Nginx mẫu trong repo có upstream Unix socket, không copy nguyên mẫu đó cho Compose
TCP mà không chỉnh. Mặc định Compose chỉ bind loopback, không tự public backend.

### B. Chuyển artifact

Thay `<SHA>` và `<VPS_IP>` bằng giá trị thật, bỏ dấu ngoặc. SSH:

```bash
mkdir -p ~/steam-releases/<SHA>
```

PowerShell Windows:

```powershell
scp "$HOME\Downloads\steam-release\*" thinhthinhhay2002@<VPS_IP>:~/steam-releases/<SHA>/
```

SCP cần SSH credential phù hợp; thêm `-i <key-path>` nếu dùng key riêng. Nếu dùng nút
upload trong SSH browser, upload các file giải nén vào cùng thư mục release.

### C. Load image và điền cấu hình production (SSH)

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

Chỉ copy mẫu khi chưa có `.env.production`; không ghi đè file đã điền.
Điền BACKEND_IMAGE đúng image-tag.txt, URL Supabase/Upstash và keys của VPS,
CORS_ORIGINS là origin frontend production. Hai URL Supabase dùng session pooler;
read-only giữ đúng role riêng. Không dùng origin localhost thay domain frontend thật.
CA Supabase đã có trong image, không cần tải lại để start artifact này.

`API_BIND_ADDRESS=127.0.0.1` dành cho reverse proxy trên host. Chỉ chọn 0.0.0.0 nếu
đã xác nhận mô hình mở port, firewall và HTTPS. Local Healthy chưa đủ để xác nhận
website public hoạt động.

```bash
docker compose --env-file .env.production -f compose.production.yml config --quiet
docker compose --env-file .env.production -f compose.production.yml run --rm --no-deps -T api python -c 'from app.core.config import settings; print("SETTINGS OK")'
```

### D. Chuyển backend đang chạy sang Docker

Trước hết, PowerShell local:

```powershell
./scripts/backend_docker.ps1 down
```

Trên VPS, kiểm tra PID mới bằng `ps -eo pid,ppid,args | grep -E '[u]vicorn|[g]unicorn'`.
Nếu native API/MCP còn chạy: dừng API bằng `kill -TERM <PID_API>`, chờ dừng rồi dừng MCP.
Không dùng PID trong hội thoại cũ; không dừng process chưa xác định. Kiểm tra không có
timer/systemd tự bật native lại. Giữ venv và env cũ để rollback; không git reset/pip upgrade.

Trong thư mục release VPS:

```bash
docker compose --env-file .env.production -f compose.production.yml up -d --no-build --pull never --wait --wait-timeout 300
docker compose --env-file .env.production -f compose.production.yml ps -a
docker compose --env-file .env.production -f compose.production.yml exec -T mcp python -m app.healthcheck http://127.0.0.1:8001/health
docker compose --env-file .env.production -f compose.production.yml exec -T api python -m app.healthcheck http://127.0.0.1:8000/health
curl --fail --silent --show-error http://127.0.0.1:8000/health
```

Cần hai service healthy và JSON API database/redis connected. Tiếp theo mở frontend
production, thử login, refresh/logout, chat và chart qua URL public; xem log/stats:

```bash
docker compose --env-file .env.production -f compose.production.yml logs --since 5m --tail 80
docker stats steam-backend-production-api-1 steam-backend-production-mcp-1
```

Nếu thất bại, `docker compose --env-file .env.production -f compose.production.yml down`
trước khi khôi phục native cũ. Không chạy API local/native/Docker VPS cùng lúc trên
database chung. Bản sau cũng tạo release directory riêng, giữ image cũ để rollback.
Chi tiết cutover/rollback: [Docker VPS migration](../operations/docker-vps-migration.md).

## 7. Các mốc hoàn thành khác nhau

- Push thành công: file/commit đã có trên GitHub.
- Actions xanh: tests/build cho commit đó đạt và có artifact.
- VPS Healthy: container và các dependency health đã đạt.
- Website hoạt động: URL public, frontend, auth/chat/chart đã được kiểm thử trên VPS.

Đừng coi mốc đầu tiên là đã deploy xong. Trợ lý chỉ chuẩn bị file/hướng dẫn, chưa
thực hiện commit, push, workflow run hoặc chuyển đổi VPS.
