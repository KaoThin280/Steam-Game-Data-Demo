# Đề xuất bổ sung RAG cho Agent Harness

**Trạng thái: chưa triển khai.** Đây là đề xuất nghiên cứu, không phải mô tả luồng chat hiện tại. Trong code được rà soát chưa có `rag_service.py`, pipeline embedding hoặc vector store tích hợp vào Agent Harness.

Để chuyển định hướng thành hạng mục phát triển, xem [thiết kế triển khai RAG](rag-implementation.md): contract truy xuất, ingestion, quyền dữ liệu, version/index và điều kiện nghiệm thu theo giai đoạn.

## Nền tảng đã có

Agent hiện nhận schema rút gọn từ system prompt, khám phá bảng bằng `describe_steam_table`, query dữ liệu qua tool, dùng history completed runs trong cùng phiên và tìm chart đã lưu theo user. Lookup chart hiện tại là tìm kiếm catalog, không phải vector retrieval. Xem [kiến trúc agent](../architecture/agent-harness.md).

## Vấn đề cần thử nghiệm

RAG có thể bổ sung định nghĩa metric, tài liệu nghiệp vụ và ví dụ SQL đã được kiểm duyệt. Mục tiêu là cung cấp ngữ cảnh có nguồn gốc, không thay SQL bằng những con số cũ trong hội thoại. Chưa có benchmark để kết luận giảm token, tăng độ chính xác hay giảm latency theo một tỷ lệ cụ thể.

## Thiết kế đề xuất

```text
Question -> retrieval có lọc quyền / phiên bản dữ liệu
         -> context có nguồn và giới hạn kích thước
         -> AgentRuntime -> model / tools như hiện tại
```

Đặt retrieval phía ứng dụng trước khi dựng messages hoặc làm tool riêng qua gateway. Không tích hợp vào `AIService.chat()` của legacy nếu mục tiêu là cải thiện chat hiện hành.

| Loại tài liệu | Quy tắc chuẩn bị |
|---|---|
| Schema và định nghĩa metric | Gắn phiên bản schema; cập nhật khi migration thay đổi |
| Ví dụ SQL | Kiểm duyệt logic, quyền và kết quả; query chạy thành công chưa đủ chứng minh đúng |
| Kiến thức Steam | Ghi nguồn và ngày kiểm tra; không suy diễn nguyên nhân từ biểu đồ đếm game |
| Insight hoặc chart của user | Lọc quyền ngay lúc retrieval; gắn thời điểm/dataset version và kiểm tra độ mới |

## Lộ trình thử nghiệm

1. Tạo tập câu hỏi và đáp án SQL đối chiếu; đo baseline của Agent Harness hiện tại.
2. Bắt đầu bằng tập tài liệu nhỏ và retrieval đơn giản; chỉ chọn embedding/vector store sau khi đo nhu cầu ngôn ngữ, tài nguyên và quyền truy cập.
3. Giới hạn context và số tài liệu; xử lý nội dung truy xuất như dữ liệu không đáng tin, không cho ghi đè system instructions.
4. So sánh có/không retrieval trên cùng dữ liệu, model và câu hỏi: độ đúng metric/SQL, token, latency, lỗi tool và rò rỉ dữ liệu giữa user.
5. Chỉ triển khai khi cải thiện có bằng chứng; thêm cơ chế cập nhật/xóa index và fallback khi retrieval lỗi.

RAG không tự huấn luyện model, không bảo đảm câu trả lời đúng và không tự làm dữ liệu mới hơn. Chưa chọn nhà cung cấp hoặc cam kết ngân sách/thời gian triển khai.
