# Thiết kế triển khai RAG theo giai đoạn

> Cập nhật 2026-11-09: retrieval Pinecone, events và hiển thị nguồn đã tích hợp; xem [trạng thái triển khai và kiểm thử local](../guides/rag-local.md). Các mục bên dưới là thiết kế gốc, không phải tất cả đều đã hoàn tất.
**Trạng thái: triển khai một phần V1; xem hướng dẫn local để biết các phần đã kiểm thử.** Tài liệu này bổ sung [định hướng RAG](rag.md) thành các hạng mục có thể phát triển và kiểm thử. Tên module, contract và cấu hình bên dưới là thiết kế dự kiến, không phải file/API đã tồn tại. Nhà cung cấp embedding, kho index và ngân sách vẫn cần được chọn khi bắt đầu milestone liên quan.

## Phạm vi phiên bản đầu

Bắt đầu với tài liệu schema, định nghĩa metric và ví dụ SQL do người phát triển kiểm duyệt, có bản tiếng Việt/Anh nếu cần. Chưa ingest toàn bộ review, chat history hoặc chart riêng của user. Mục tiêu là giúp agent hiểu câu hỏi và chọn query đúng, không thay database bằng một kho số liệu cũ.

| Câu hỏi | Nguồn trả lời chính |
|---|---|
| Có bao nhiêu game hiện có trong dataset? | SQL tool trên database hiện tại |
| Trong dự án, một game nhiều genre được đếm thế nào? | Định nghĩa metric có nguồn; SQL kiểm tra khi cần số liệu |
| Gợi ý mẫu query game theo tháng | Ví dụ SQL được kiểm duyệt, xác minh theo schema hiện tại |
| Vì sao một xu hướng xảy ra? | Chỉ giải thích nguyên nhân nếu có nguồn phù hợp; biểu đồ tương quan không đủ |

## Luồng ingest và vòng đời tài liệu

```text
nguồn được chọn -> đọc/chuẩn hóa -> chia chunk theo mục
               -> gắn provenance/quyền/version -> index phiên bản mới
               -> kiểm tra -> kích hoạt phiên bản
nguồn sửa/xóa -> reindex/tombstone -> vô hiệu cache liên quan
```

Chỉ đọc danh sách nguồn cho phép. Loại `.env`, credential, log, token, bảng tài khoản và event trace khỏi corpus mặc định. Giữ ranh giới heading, bảng và code SQL khi chia chunk; không tách mất điều kiện áp dụng của một metric. Kích thước chunk/overlap phải thử với câu hỏi thật, không coi một con số là phù hợp mọi loại tài liệu.

Ingest cần idempotent theo nguồn, phiên bản và content hash: chạy lại cùng nội dung không nhân bản chunk. Tạo index mới ở trạng thái staging, chỉ kích hoạt sau kiểm tra để query không đọc bản cập nhật nửa chừng. Giữ bản index trước đủ để rollback; xóa nguồn phải làm nội dung hết khả năng truy xuất, kể cả trong cache.

## Metadata tối thiểu dự kiến

| Trường | Ý nghĩa |
|---|---|
| document_id, chunk_id | Định danh ổn định để đối chiếu/citation |
| source_uri, heading | Nguồn và vị trí nội dung |
| document_type | schema, metric_definition, sql_example hoặc domain_document |
| content_hash, document_version | Nhận biết nội dung thay đổi và ingest lặp |
| schema_version, dataset_version | Biết ví dụ/insight áp dụng cho phiên bản nào; có thể null nếu không liên quan |
| language | Ngôn ngữ phục vụ truy xuất/đánh giá |
| access_scope, owner_user_id | Phạm vi nội bộ toàn ứng dụng hoặc user; không lấy từ lời model |
| updated_at, indexed_at, deleted_at | Thời điểm nguồn/index và tombstone |
| embedding_model, embedding_version | Chỉ có khi dùng embedding; thay model có thể cần reindex |

Phiên bản đầu có thể chỉ có tài liệu chung cho user đã xác thực. Dù chưa có corpus riêng, interface nên nhận trusted user context để về sau không phải dùng ownership từ query/model. Chính sách quyền có thể đơn giản nhưng phải rõ.

## Contract truy xuất dự kiến

```text
retrieve(query, trusted_context, filters, budget)
  -> status: ok | empty | unavailable
  -> chunks: [{chunk_id, text, source_uri, heading, version, score}]
  -> index_version, duration_ms, truncated
```

`trusted_context` đến từ user/session đã được backend xác thực. Lọc quyền và nội dung đã xóa **trước** chọn top-k; không lấy chunk riêng của người khác rồi mới lọc sau khi gửi model. Nếu cache retrieval, key phải bao gồm phạm vi quyền, phiên bản index và các filter liên quan; quyền thay đổi phải làm cache cũ không còn dùng được.

Budget cần giới hạn số chunk, tổng kích thước/token và timeout. Score chỉ phản ánh thuật toán retrieval, không phải xác suất câu trả lời đúng. `empty` nghĩa không tìm thấy bằng chứng phù hợp; `unavailable` nghĩa dependency lỗi. Không tự chuyển lỗi retrieval thành câu trả lời khẳng định.

## Tích hợp vào Agent Harness

Phương án khởi đầu: retrieval ở application layer trước khi gọi runtime, truyền context qua interface có kiểu rõ ràng. Runtime giữ độc lập với SQL/vector SDK. Vị trí tạo history hiện ở `agent_rpc.py`; khi logic lớn lên có thể tách application service. Phương án tool retrieval theo nhu cầu là lựa chọn khác nếu đo được lợi ích, không bắt buộc triển khai đồng thời cả hai.

```text
user -> REST task -> lưu run -> dựng history
     -> retrieve có quyền -> context có nguồn và budget
     -> AgentRuntime -> OpenRouter -> SQL/chart/E2B tools -> answer
```

Nguồn retrieved phải được đóng khung là dữ liệu tham khảo, không được ghi đè system prompt hoặc cấp thêm quyền tool. Câu trả lời dẫn chunk/source thực sự được cung cấp. Khi nguồn mâu thuẫn, nêu xung đột hoặc ưu tiên theo quy tắc phiên bản được kiểm chứng; không chọn câu nghe hợp lý nhất.

Ghi event retrieval về trạng thái, index version, chunk IDs, thời gian và kích thước context. Không ghi toàn bộ tài liệu riêng vào log theo mặc định. Khi run replay, ghi rõ index version mới hay dùng snapshot cũ; đây là quyết định sản phẩm cần thống nhất, không được tự coi replay là tái lập chính xác.

Có feature flag dự kiến để bật/tắt RAG. Khi tắt, luồng hiện tại giữ nguyên. Khi retrieval lỗi, agent có thể tiếp tục SQL/tool nếu câu hỏi cho phép; nếu câu hỏi cần tài liệu mà không có nguồn, phải nói thiếu căn cứ. Không đưa embedding key vào frontend hoặc chạy ingest nặng trong request chat.

## Chọn storage sau khi đo

Trước hết thử corpus nhỏ với keyword/full-text và retriever giả lập trong unit tests. Nếu không đáp ứng truy vấn đa ngôn ngữ hoặc semantic matching, so sánh embedding/hybrid retrieval. Đánh giá hỗ trợ lọc quyền, vận hành, backup, migration, latency và giới hạn host hiện tại. Chưa cần mặc định thêm ChromaDB, Qdrant hoặc một dịch vụ mới.

Nếu dùng PostgreSQL extension hoặc bảng index mới, kiểm tra khả năng của môi trường, thiết kế migration và quyền riêng; không mở rộng quyền `steam_readonly` tới corpus riêng một cách vô điều kiện. Ingest có thể cần quyền ghi mà runtime retrieval không cần.

## Milestone và điều kiện nghiệm thu

| Giai đoạn | Kết quả phải có | Điều kiện qua |
|---|---|---|
| 0 Baseline | Bộ câu hỏi, đáp án/nguồn đối chiếu, cấu hình model/dataset cố định | Đo luồng không RAG; không bịa chỉ số |
| 1 Ingest | Corpus nhỏ, metadata, index có phiên bản | Re-ingest không trùng; sửa/xóa nguồn phản ánh đúng; không ingest secret |
| 2 Retrieve | Contract có quyền, budget, timeout, provenance | Không trả chunk trái quyền; xác định empty/unavailable; không vượt budget |
| 3 Integrate | Feature flag, context/citation, events, fallback | Tắt flag giữ luồng cũ; lỗi retrieval không treo run; số liệu hiện tại vẫn dùng SQL |
| 4 Evaluate | So sánh có/không RAG và báo cáo lỗi | Đạt mục tiêu đã chọn trên cùng bộ câu hỏi; kiểm tra bảo mật đạt |
| 5 Operate | Reindex, invalidation, rollback, theo dõi tài nguyên | Có thể đổi/xóa corpus và quay lại index trước bằng quy trình kiểm tra được |

Trước giai đoạn 4, chốt mục tiêu đo cụ thể theo baseline và ngân sách: retrieval recall@k nếu có nhãn chunk, độ đúng metric/query, citation có hỗ trợ kết luận, latency p50/p95, token/chi phí, tỷ lệ tool thất bại. Không đặt một mức cải thiện phần trăm chưa có dữ liệu. Yêu cầu không rò chunk trái quyền là điều kiện bắt buộc, không đánh đổi lấy recall.

## Bộ tình huống kiểm thử tối thiểu

- Câu Việt/Anh cùng ý tìm được tài liệu đúng; phân biệt game count và review count.
- Không có nguồn, nguồn mâu thuẫn hoặc schema cũ: không bịa nguồn/kết luận.
- Chunk chứa câu lệnh “bỏ qua hướng dẫn” không thay quyền hoặc quy tắc agent.
- Hai user có corpus riêng: retrieval, cache và citation không vượt quyền.
- Xóa nguồn/thu hồi quyền: cả query mới lẫn cache không trả nội dung cũ.
- Re-ingest cùng nguồn không sinh bản trùng; ingest gián đoạn không kích hoạt index chưa hoàn tất.
- Embedding/index timeout: có event lỗi phù hợp và kết thúc/fallback theo contract.
- Tắt RAG, cancel và restart/replay: giữ trạng thái run đúng, ghi rõ phiên bản context.

Các tình huống này là yêu cầu test cho phần triển khai sau, chưa phải test đã chạy. Xem [skill phát triển](../guides/development-skills.md) để dùng hướng dẫn phù hợp khi bắt đầu.
