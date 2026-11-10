# Cập nhật VPS: giữ backend hiện tại và thêm RAG

Phạm vi chốt ngày 2026-11-10: không sửa refresh/login trong bản này; người dùng chấp nhận đăng nhập lại. Không reset/xóa tài khoản, không đổi schema PostgreSQL. RAG chỉ thêm bước tìm kiến thức trước model; SQL/chart/tools hiện tại tiếp tục hoạt động. RAG lỗi/key thiếu/timeout sẽ ghi event rồi tiếp tục luồng cũ.

## Giới hạn tài nguyên

Giả định VPS là GCP e2-micro tiêu chuẩn, khoảng 1 GiB RAM và CPU shared-core. Cần đối chiếu máy thật bằng `free -m` trước rollout. Nguồn: [GCP machine types](https://docs.cloud.google.com/compute/docs/general-purpose-machines), [Free Tier](https://docs.cloud.google.com/free/docs/free-cloud-features).

| Thành phần | RAM cứng | CPU tối đa | Worker |
|---|---:|---:|---:|
| API | 384 MiB | 0.12 vCPU | 1 |
| MCP | 256 MiB | 0.08 vCPU | 1 |

Tổng trần container 640 MiB, chừa khoảng 384 MiB trên máy 1 GiB cho OS/Docker/Nginx. Đây là ngân sách, không bảo đảm tránh OOM nếu có dịch vụ khác dùng RAM. Không chạy PostgreSQL/Redis/frontend/embedding model trên VPS: vẫn dùng Supabase/Redis bên ngoài, frontend ở nơi host hiện tại, embedding tại Pinecone.

Giữ log 2 file × 5 MiB mỗi service, PID 96, mỗi DB engine pool 1 + overflow 1. Có tối đa 2 agent runs thực thi đồng thời trước cả bước load history; tối đa 8 run mới đang chờ/chạy trong process, quá ngưỡng trả HTTP 503 và Retry-After 10 giây. Khi phục hồi lịch sử có nhiều run, chúng vẫn chờ slot, không gọi provider đồng thời hết. Runtime chưa có worker queue phân tán.

Không cài `tools/rag/requirements.txt` hoặc transformers trên VPS. Chỉ image backend chứa Pinecone SDK. Retrieval async một lần/lượt, timeout 5 giây, không retry; context giới hạn nhỏ. Không tự nạp dữ liệu lên Pinecone lúc startup.

## Cấu hình thêm vào .env.production bảo vệ trên VPS

Giữ DATABASE_URL, DATABASE_URL_READONLY, Redis, JWT, OpenRouter, E2B và domain/CORS đang hoạt động. Chỉ thêm:

```dotenv
RAG_ENABLED=True
PINECONE_API_KEY=<key riêng của bạn>
PINECONE_INDEX_NAME=steam-knowledge
PINECONE_NAMESPACE=project-starter-v2
PINECONE_TEXT_FIELD=text
AGENT_RECOVERY_ENABLED=True
```

Không cần đổi secret để buộc reset login. Nếu browser còn phiên cũ, đăng xuất/đăng nhập lại. Không đưa file env vào Git/artifact. Mẫu mới chỉ phục vụ tham khảo, không chép đè toàn bộ env đang chạy.

## Phát hành và xác minh

1. Commit đủ cả file mới/untracked của RAG. Chạy workflow `Build tested Docker release (manual VPS rollout)` trên đúng commit. Workflow chạy tests, build Linux amd64, import app/API/MCP/RAG trong container hạn chế RAM/CPU và xuất artifact; không deploy tự động.
2. Trước thay VPS, dừng gửi chat local dùng chung Supabase và chờ các run đang chạy kết thúc. Dừng stack local bằng `scripts/backend_docker.ps1 -Action down`. Không chạy hai API thực thi run trong lúc VPS restart vì chưa có lease đa instance.
3. Giữ image/tag/Compose cũ để rollback; tải và kiểm tra artifact/checksum theo hướng dẫn Docker VPS hiện có. Build trên CI/local, không build trên VPS 1 GiB.
4. Chuyển BACKEND_IMAGE sang tag mới, nạp image, chạy từ thư mục release với env bảo vệ:

```bash
docker compose --env-file .env.production -f compose.production.yml up -d --wait --wait-timeout 300
docker compose --env-file .env.production -f compose.production.yml ps
docker compose --env-file .env.production -f compose.production.yml stats --no-stream
```

5. Kiểm tra login, một câu kiến thức AppID có retrieval.completed và nguồn, một câu số liệu vẫn gọi SQL, một biểu đồ cũ vẫn hiển thị. Theo dõi OOM/restart và bộ nhớ; health xanh chỉ kiểm tra dependency cơ bản, không chứng minh Pinecone/OpenRouter hoạt động.
6. Frontend source cards cần phát hành frontend riêng theo host hiện tại. Không chuyển frontend sang VPS miễn phí. Không dùng API URL localhost trong build frontend production.

## Rollback

Nếu chỉ RAG có vấn đề, đổi `RAG_ENABLED=False` trong env và recreate API; các endpoint/tool cũ vẫn giữ nguyên. Nếu image lỗi, trở lại tag image và Compose cũ, chạy up lại. Không xóa volume, database, corpus namespace hoặc lịch sử chat để rollback.

## Giới hạn xác nhận

Đây là cấu hình/release đã chuẩn bị, không phải bằng chứng đo tải trên VPS thật. Các smoke local trước dùng corpus thật và dataset fixture; chất lượng truy xuất khi đổi chủ đề còn hạn chế. Bản này có thể thử nghiệm có kiểm soát, không tuyên bố đạt bộ 40 câu hoặc khả năng phục vụ nhiều người dùng.
