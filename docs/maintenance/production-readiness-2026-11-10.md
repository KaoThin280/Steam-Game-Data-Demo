# Rà soát production ngày 2026-11-10

Kết luận cập nhật: đã chuẩn bị code và cấu hình cho bản cập nhật backend hiện tại + RAG trên VPS nhỏ. Backend đạt 49 tests; vẫn cần build artifact qua CI và smoke trên VPS trước khi xác nhận chạy ổn định. Chưa deploy hoặc sửa VPS trong lần rà soát này.

> Phạm vi sau phản hồi người dùng: chấp nhận đăng nhập lại, không xử lý refresh trong bản cập nhật này; ưu tiên backend cũ + RAG trên VPS miễn phí. Đã bổ sung cấu hình production RAG, giới hạn run và application import probe trong workflow. Xem [bản cập nhật VPS](../operations/rag-vps-release.md). Danh sách dưới ghi lại phát hiện tại thời điểm rà soát ban đầu; refresh/benchmark đầy đủ là việc tiếp theo, không phải điều kiện người dùng yêu cầu cho bản thử nghiệm có kiểm soát.

## Các phát hiện và trạng thái xử lý

1. **Đóng gói thiếu file nếu chỉ commit các file đã tracked.** `knowledge.py`, `knowledge_retrieval.py`, test RAG và thư mục `tools/` đang untracked. Runtime/router đã import các module mới. Cần commit đầy đủ, chạy workflow release trên đúng commit và kiểm tra import application trong image; workflow đã bổ sung import app/API/MCP/RAG với giới hạn RAM/CPU, nhưng chưa có kết quả chạy workflow mới.
2. **Chưa bảo đảm một nơi thực thi một run khi chung Supabase.** Local tắt recovery, nhưng VPS mặc định vẫn quét mọi queued/running run mà không có owner/lease. VPS restart có thể replay run local còn hoạt động. Trước rollout phải dừng nhận chat local và chờ run kết thúc, hoặc triển khai ownership/lease ở cả hai phía. Cờ local không giải quyết toàn bộ bài toán nhiều instance.
3. **Refresh token frontend chưa khớp backend.** Backend trả access token trong JSON và refresh token qua httpOnly cookie; frontend vẫn yêu cầu refreshToken trong store và gửi JSON refresh_token. Khi hết hạn access token, phiên có thể bị xóa hoặc refresh thất bại. Refresh dùng cùng interceptor còn có nguy cơ lặp nếu refresh endpoint trả 401. Để lại cho đợt sau theo phạm vi người dùng chốt; trong bản này có thể cần đăng nhập lại khi phiên hết hạn.
4. **Đã bổ sung cấu hình RAG production.** `.env.production.example` có flag/key/index/namespace/text field; Settings vẫn mặc định RAG_ENABLED=False để tương thích luồng cũ. Khi rollout chỉ thêm cấu hình cần thiết vào env VPS đang chạy, kiểm tra key và dùng false để rollback RAG.
5. **Chưa hoàn tất nghiệm thu chất lượng RAG.** Mới có 3 smoke turns trên fixture; câu đổi chủ đề vẫn truy xuất nguồn AppID/top genre khi hỏi game miễn phí. Budget hiện là 1.600 byte JSON + dự phòng, không phải budget 1.800 token theo model. Chưa có kết quả 40 câu, Recall@5, đánh giá hỗ trợ citation hay p50/p95. Smoke SQL hiện chỉ kiểm tra câu trả lời chứa ký tự '2', chưa đối chiếu cấu trúc kết quả số đầy đủ.

## Bằng chứng và giới hạn

- Chạy lại backend tests: **49 passed** (gồm giới hạn chạy đồng thời, hủy khi chờ slot và từ chối khi đầy hàng chờ), database giả, không sử dụng credential production.
- Frontend `npm run build` đạt: compile, lint/type validation và tạo 9 trang. Đây là build local, không phải artifact đã phát hành với API URL production.
- `git diff --check` đạt, có cảnh báo chuyển LF/CRLF.
- Lịch sử phiên này có smoke thật qua REST/Pinecone/OpenRouter trên database fixture: Việt/Anh, SQL và persistence đạt. Không coi đó là smoke trên Supabase production.
- Lần kiểm tra hiện tại: Docker Engine không chạy; API local `/health` không truy cập được. Chưa xác nhận chuyển stack local sang Supabase thành công sau lần chạy trước bị gián đoạn.
- Chưa đọc trạng thái/config VPS trực tiếp, chưa kiểm tra quota tài khoản hay ngân sách thực tế.
- Release workflow hiện build image Linux amd64 sau tests và xuất artifact theo commit; triển khai VPS là thao tác thủ công. Frontend hiển thị nguồn cần phát hành riêng theo nơi frontend đang được host.

## Thứ tự đề nghị

Theo phạm vi đã chốt: commit đầy đủ → CI/release image → ngừng chat local dùng chung Supabase và chờ run kết thúc → bổ sung env RAG trên VPS → chạy image với giới hạn tài nguyên → kiểm tra login/chat/sources/SQL/chart và tài nguyên. Giữ image cũ để rollback; có thể tắt riêng RAG bằng flag. Sửa refresh và bộ đánh giá 40 câu là công việc tiếp theo, không chặn bản thử nghiệm này.

