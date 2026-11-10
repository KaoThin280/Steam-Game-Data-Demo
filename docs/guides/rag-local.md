# Chạy RAG trên local


## Local dùng chung Supabase với VPS (cấu hình đang sử dụng)

Người dùng đã cho phép local đọc/ghi chung Supabase với VPS. Stack đang dùng là `steam-backend-local`, cấu hình `back_end/compose.local.yml` và `.env.docker.local`. Stack `steam-rag-local` ở phần dưới chỉ còn là lựa chọn kiểm thử dữ liệu giả lập.

```powershell
# Từ root repository, khi Docker Desktop đã chạy:
.\scripts\backend_docker.ps1 -Action up
.\scripts\backend_docker.ps1 -Action verify
```

API vẫn ở `http://127.0.0.1:8000`, frontend ở `http://127.0.0.1:3000`. Đăng xuất tài khoản fixture và đăng nhập bằng tài khoản Supabase/VPS của bạn; không dùng `rag-local@example.com`. Frontend giữ nguyên API URL. Nếu có cookie/token cũ gây lỗi, xóa site data của 127.0.0.1 hoặc mở cửa sổ riêng tư rồi đăng nhập lại.

```powershell
cd front_end
$env:NEXT_PUBLIC_API_URL="http://127.0.0.1:8000/api/v1"
node .\node_modules\next\dist\bin\next dev --hostname 127.0.0.1 --port 3000
```

Compose local bật RAG và đặt `AGENT_RECOVERY_ENABLED=false`; startup không đọc/cập nhật/schedule run đang dở của VPS. Shutdown bình thường đánh dấu các run đang thực thi tại local là cancelled thay vì queued. Không tạo tài khoản bootstrap, seed hoặc chạy migration lên Supabase. Game/review, tài khoản, session/run/event/chart là dữ liệu dùng chung; thao tác của bạn tại local có thể thay đổi dữ liệu VPS đang nhìn thấy. SQL AI vẫn dùng kết nối read-only riêng.

**Giới hạn chạy song song:** đây chưa phải cơ chế phân quyền/lease run giữa nhiều máy. Nếu VPS restart trong lúc local đang chạy run, VPS phiên bản cũ vẫn có thể replay run đó. Local bị kill/mất điện cũng có thể để lại run active. Tránh restart/deploy VPS trong lúc local đang xử lý chat; chờ run kết thúc trước khi dừng local. Cần triển khai lease/instance ownership đồng bộ cả hai phía trước khi vận hành nhiều worker lâu dài.

Để dừng local: `.\scripts\backend_docker.ps1 -Action down`. Không bật cả hai stack local cùng cổng 8000. Script `tools/rag/smoke_local.py` chỉ dành cho fixture, không chạy nó trên stack Supabase (tài khoản và số liệu mong đợi khác).

## Phạm vi đã tích hợp

```text
Frontend → REST xác thực/lưu run → lịch sử cùng phiên
  → Pinecone tìm text một lần → context có nhãn [S1], [S2]
  → OpenRouter → trả lời hoặc SQL/chart tools
  → PostgreSQL lưu câu trả lời + retrieval events → frontend hiển thị nguồn
```

`RAG_ENABLED=False` mặc định giữ luồng cũ. Khi bật, router inject `KnowledgeRetriever` vào runtime; adapter Pinecone nằm ở `app/services/knowledge_retrieval.py`. Không tạo thêm tool hoặc migration database. Key chỉ ở backend, hỗ trợ cả `PINECONE_API_KEY` và alias `PINECORN_API_KEY`.

Query gồm câu hỏi hiện tại trước, tối đa hai câu user trước, giới hạn 2.000 ký tự. Tìm top 5 trong namespace active, filter approved và corpus_version. Loại trùng text, bỏ nguồn không hợp lệ. Budget bảo thủ: tối đa 1.600 byte UTF-8 cho các chunk JSON và 200 byte dự phòng envelope, thường chỉ giữ 1–2 bài; đây là giới hạn byte bảo thủ thay vì tokenizer runtime của model OpenRouter. Không tải model/tokenizer trên API. Giữ nguyên bài, không cắt giữa nội dung. Vì vậy có thể trả empty dù Pinecone có match quá dài. Chưa có reranker, ngưỡng similarity hoặc cache retrieval.

Timeout toàn retrieval 5 giây, SDK không retry. Lỗi/key thiếu/quota hết tạo retrieval.failed rồi tiếp tục model/tools. Không lưu nội dung exception provider vào event. Cancellation ngắt coroutine đang chờ; shutdown requeue theo vòng đời cũ. Recovery truy xuất corpus đang active lại, không bảo đảm tái lập câu trả lời.

Nguồn là dữ liệu không đáng tin cậy về mặt chỉ dẫn: system prompt yêu cầu bỏ qua lệnh trong chunk, không thay quyền tools và vẫn dùng SQL cho số liệu hiện tại. Đây không phải bảo đảm model miễn nhiễm prompt injection. Source cards lấy từ event, không từ URL do model tự viết. Mở lại phiên đọc lại nguồn đã lưu. Nguồn đã truy xuất không đồng nghĩa tất cả đã được dùng.

## Stack thử nghiệm cô lập

File `back_end/compose.rag-local.yml` tạo PostgreSQL/Redis riêng, MCP và API trên máy. Không dùng database/Redis từ `.env.docker.local`. Dữ liệu là **3 game giả lập, 2 miễn phí**, không phải số liệu Steam thật. Pinecone và OpenRouter vẫn là dịch vụ bên ngoài; chat thử sử dụng quota.

Trong PowerShell tại root repository:

```powershell
.\.venv-rag\Scripts\python.exe tools/rag/prepare_local.py
docker compose -f back_end/compose.rag-local.yml up -d --build --wait --wait-timeout 240
.\.venv-rag\Scripts\python.exe -X utf8 tools/rag/smoke_local.py
```

Nếu chưa có `.venv-rag`, tạo bằng Python 3.12 rồi cài `tools/rag/requirements.txt`. Script prepare chỉ sao chép key Pinecone/OpenRouter (và model nếu có), tạo secret/tài khoản test riêng, không in key và không ghi đè env đã tồn tại. File `.env.rag-test.local` được Git/Docker build bỏ qua. Seed kiểm tra hostname/database trước khi tạo fixture; đây không phải migration production.

API: `http://127.0.0.1:8000/docs`. Chạy frontend trong terminal riêng:

```powershell
cd front_end
$env:NEXT_PUBLIC_API_URL="http://127.0.0.1:8000/api/v1"
node .\node_modules\next\dist\bin\next dev --hostname 127.0.0.1 --port 3000
```

Mở `http://127.0.0.1:3000`. Tài khoản test là `rag-local@example.com`; mật khẩu nằm ở `BOOTSTRAP_ADMIN_PASSWORD` trong `back_end/.env.rag-test.local`. Nếu trình duyệt còn tài khoản môi trường khác, đăng xuất rồi đăng nhập tài khoản test. Đặt câu hỏi AppID, mở “Tài liệu tham khảo đã truy xuất”, rồi hỏi số game miễn phí. Không khởi động hai API cùng port 8000.

Kiểm tra/dừng:

```powershell
docker compose -f back_end/compose.rag-local.yml ps
docker compose -f back_end/compose.rag-local.yml down
```

`down` giữ volume và lịch sử chat test. Không thêm `-v` nếu muốn giữ dữ liệu. Dừng frontend bằng Ctrl+C trong terminal chạy dev server. TLS PostgreSQL/Redis chỉ tắt cho mạng Docker cô lập; mặc định ứng dụng vẫn bật TLS.

## Kết quả kiểm thử ngày 2026-11-09

- Backend: 44 unit tests đạt; gồm retrieval timeout/failure/empty, hủy/shutdown, replay phiên bản, tắt RAG, budget/filter và tools còn hoạt động.
- Frontend: `npm run type-check` đạt. Chưa kiểm tra trực quan đầy đủ trên browser.
- Docker: API/MCP/PostgreSQL healthy; Redis chạy local.
- Smoke thật qua REST login/session/task/events: 3 lượt đạt; AppID tiếng Việt/Anh trả đúng nguồn và nhãn citation; câu số game gọi `query_steam_data`, kết quả 2 game miễn phí trên 3 game giả lập. Mở lại session/events vẫn giữ câu trả lời và nguồn.
- Retrieval ba lượt lần lượt 3295, 2586, 2188 ms. Đây là ba mẫu, không phải benchmark p50/p95 hay đánh giá 40 câu.
- Chưa thử quota exhaustion thật, kill/restart trong lúc provider đang chạy hoặc đánh giá prompt injection với provider thật; các contract lỗi/hủy/replay mới có unit evidence.

Đặc biệt: câu hỏi thứ ba bị ảnh hưởng bởi hai câu AppID trước đó và trả nguồn chưa sát câu hỏi miễn phí; SQL vẫn trả đúng. Cần benchmark retrieval trên hội thoại nhiều chủ đề trước khi bật production.

## Bật trong môi trường sử dụng dữ liệu riêng

Sau khi xác nhận môi trường/credential mong muốn, đặt trong env backend:

```dotenv
RAG_ENABLED=True
PINECONE_INDEX_NAME=steam-knowledge
PINECONE_NAMESPACE=project-starter-v2
PINECONE_TEXT_FIELD=text
```

Giữ key đã cấu hình. Rebuild image có dependency `pinecone==10.3.0`, recreate API để nạp env. Không dùng lệnh này với database production chỉ để thử local. Rollback hành vi bằng `RAG_ENABLED=False` rồi recreate API; nguồn trong event cũ vẫn đọc được. Cập nhật corpus dùng namespace mới đã verify rồi đổi `PINECONE_NAMESPACE`; không xóa namespace cũ khi chưa cần.
