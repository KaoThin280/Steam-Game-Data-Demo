# Từ file text đầu tiên đến tìm kiếm trên Pinecone

Hướng dẫn này chia công việc thành bước nhỏ. Hiện đã có [file dữ liệu JSON mẫu](../../knowledge/project-starter.draft.json) gồm 8 đoạn về dự án và cách hiểu chỉ số. Chưa tạo index, chưa kết nối tài khoản, chưa upload và chưa tích hợp chatbot.

## Bước 1 Đọc và duyệt file text

File JSON vẫn chứa text tiếng Việt bình thường, nhưng mỗi đoạn có thêm ID, tiêu đề, loại nội dung và nguồn. Dùng JSON thay vì một file txt dài để dễ kiểm tra từng đoạn và đưa metadata lên Pinecone.

| Trường | Ý nghĩa |
|---|---|
| `_id` | ID ổn định của đoạn |
| `title` | Tiêu đề để người dùng nhận ra nội dung |
| `text` | Phần kiến thức sẽ được embedding và tìm kiếm |
| `category`, `language` | Nhóm nội dung và ngôn ngữ |
| `source` | File nguồn dùng để đối chiếu; không phải URL công khai |
| `version`, `reviewed_at` | Phiên bản và ngày đối chiếu nguồn |
| `status` | draft là chờ bạn duyệt; approved mới được phép ingest |

`reviewed_at` chỉ ngày đối chiếu tài liệu/code, không có nghĩa bạn đã duyệt. Tất cả 8 đoạn đang draft. Đọc và sửa nội dung trước; chỉ sau khi bạn chấp nhận mới đổi status sang approved. File này là bộ mẫu để học quy trình, chưa phải corpus 30 bài trong kế hoạch lớn.

## Bước 2 Chuẩn bị tài khoản

Tạo hoặc đăng nhập tài khoản tại [Pinecone Console](https://app.pinecone.io/). Chọn gói Starter và kiểm tra quota database/embedding đang có trong tài khoản. Không tự chuyển sang gói trả phí khi hết quota.

Tạo API key cho project cần dùng. Lưu key trong biến môi trường local hoặc file .env đã được ignore; không ghi vào JSON, Git hoặc gửi key trong chat. Khi cần hỗ trợ, chỉ cung cấp tên index, model, region hoặc lỗi đã che credential.

## Bước 3 Tạo index đúng loại

Cấu hình mục tiêu:

- Tên: `steam-knowledge`.
- Serverless trên AWS `us-east-1`, trong giới hạn tài khoản Starter.
- Document index có trường `text` kiểu string, bật integrated embedding với `multilingual-e5-large`.
- Giữ text để search trả lại đoạn nội dung; không chọn chế độ chỉ giữ vector.
- Namespace thử nghiệm: `project-starter-v1`.

Index giống nơi chứa tập dữ liệu tìm kiếm; namespace là vùng chia bên trong index. Model embedding biến đoạn text thành vector biểu diễn ý nghĩa. Model tạo embedding khác với model OpenRouter viết câu trả lời.

Nên tạo index qua script Documents API đồng bộ với SDK được chọn. Không tạo index vector thủ công rồi dùng lẫn hướng dẫn Records API. Nếu đã tạo nhầm loại, kiểm tra cấu hình trước; không xóa index có dữ liệu để thử lại.

Nguồn: [Pinecone document schema](https://sdk.pinecone.io/python/how-to/documents/schema-and-upsert.html), [embedding model](https://docs.pinecone.io/models/multilingual-e5-large).

## Bước 4 Kết nối từ Python

Bước lập trình tiếp theo là tạo script local riêng, không sửa chatbot ngay. Script cần đọc `PINECONE_API_KEY` từ môi trường, chọn đúng index và namespace, rồi kiểm tra kết nối/cấu hình. Cài SDK Pinecone trong môi trường Python riêng và cố định phiên bản sau khi kiểm tra tương thích Documents API.

Các thao tác script cần cung cấp:

| Lệnh dự kiến | Việc thực hiện |
|---|---|
| validate | Kiểm tra JSON, trường bắt buộc, ID trùng, nguồn và trạng thái; không gọi mạng |
| dry-run | Liệt kê những đoạn approved sẽ gửi; không upload |
| create-index | Tạo index nếu chưa có, kiểm tra schema/model nếu đã có |
| upload | Gửi những đoạn approved sang namespace thử nghiệm |
| search | Tìm bằng câu hỏi text, in title/text/source/score |

Các lệnh trên là giao diện dự kiến cho script bước sau, chưa phải lệnh có sẵn trong repository. Việc chuẩn bị file text không yêu cầu API key hay cài Pinecone.

## Bước 5 Đưa dữ liệu lên

Script đọc JSON, bỏ qua draft và kiểm tra độ dài theo tokenizer trước khi gửi. Đoạn quá dài cần chia nhỏ; không im lặng cắt mất nội dung. Sau đó dùng `index.documents.upsert` để ghi các document đã duyệt. ID trùng trong namespace sẽ thay thế document cùng ID, nên phải dùng ID có chủ đích.

Pinecone tự embedding trường text đã cấu hình. Không cần tạo vector bằng OpenRouter. Sau upload, chờ dữ liệu nhìn thấy được rồi fetch/đếm ID và chạy tìm kiếm; ghi được request không đồng nghĩa kết quả search xuất hiện ngay.

Nguồn: [Upsert và khả năng nhìn thấy dữ liệu](https://sdk.pinecone.io/python/how-to/documents/schema-and-upsert.html).

## Bước 6 Thử tìm kiếm trước khi nối chatbot

Thử các câu sau, lấy top 3 kết quả:

| Câu hỏi | Nội dung mong tìm thấy |
|---|---|
| Website này dùng để làm gì? | project-overview-v1 |
| Vì sao cộng các genre lại lớn hơn số game? | metric-multiple-genres-v1 |
| Biểu đồ cũ có phải dữ liệu mới nhất không? | project-chart-freshness-v1 |
| Does a sample represent the whole dataset? | metric-sample-versus-total-v1 |

Dùng `index.documents.search` với `EmbedQuery` trên trường text và yêu cầu trả title/text/source. Kết quả là các đoạn gần nghĩa, chưa phải câu trả lời của chatbot. Score không phải xác suất thông tin đúng. Nếu không tìm đúng, kiểm tra namespace, model và cách viết nội dung trước khi bổ sung logic AI.

Nguồn: [Pinecone search documents](https://sdk.pinecone.io/python/how-to/documents/search.html).

## Bước 7 Nối vào chatbot sau khi search đạt

```text
Câu hỏi -> backend tìm đoạn liên quan trong Pinecone
        -> gửi câu hỏi + đoạn có nguồn cho OpenRouter
        -> model trả lời hoặc gọi SQL để lấy số liệu
        -> hiển thị câu trả lời và nguồn
```

Pinecone không tự nối với website chỉ vì đã có dữ liệu. Cần bước tích hợp backend riêng, rồi test nguồn, lỗi dịch vụ và hủy tác vụ. PostgreSQL vẫn giữ dữ liệu game/review và trả số liệu hiện tại; Pinecone chứa kiến thức giải thích.

## Thứ tự làm việc ngay bây giờ

1. Bạn đọc 8 đoạn mẫu và xác nhận nội dung/cách tổ chức phù hợp.
2. Mở rộng thành bộ text đã thống nhất, bổ sung kiến thức Steam có nguồn chính thức.
3. Chuẩn bị tài khoản/index và script kết nối-upload-search.
4. Chạy thử vài đoạn approved, xác minh tìm kiếm.
5. Sau đó mới tích hợp RAG vào chatbot hiện tại.
