# Từ file text đầu tiên đến tìm kiếm trên Pinecone

Hướng dẫn này chia công việc thành bước nhỏ. Hiện đã có [file dữ liệu JSON mẫu](../../knowledge/project-starter.draft.json) gồm 30 bài: 8 kiến thức Steam, 6 hướng dẫn website, 10 định nghĩa chỉ số và 6 mẫu phân tích. Người dùng đã yêu cầu duyệt toàn bộ nội dung ngày 2026-11-09; tất cả bài có status=approved. Người dùng đã tạo index ai-data-knowledge theo ảnh Console, nhưng chưa xác minh cấu hình bằng API, chưa upload corpus này và chưa tích hợp chatbot.

## Bước 1 Đọc và duyệt file text

File JSON vẫn chứa text tiếng Việt bình thường, nhưng mỗi đoạn có thêm ID, tiêu đề, loại nội dung và nguồn. Dùng JSON thay vì một file txt dài để dễ kiểm tra từng đoạn và đưa metadata lên Pinecone.

| Trường | Ý nghĩa |
|---|---|
| `_id` | ID ổn định của đoạn |
| `title` | Tiêu đề để người dùng nhận ra nội dung |
| `text` | Phần kiến thức sẽ được embedding và tìm kiếm |
| `category`, `language` | Nhóm nội dung và ngôn ngữ |
| `source`, `sources` | Nguồn chính và danh sách nguồn: URL Steamworks hoặc đường dẫn file trong repository |
| `version`, `reviewed_at` | Phiên bản và ngày đối chiếu nguồn |
| `status` | draft là chờ bạn duyệt; approved mới được phép ingest |

`reviewed_at` là ngày đối chiếu nguồn; `approved_at` và `approval_basis=user_instruction` ghi nhận yêu cầu duyệt toàn bộ của người dùng. Cả 30 bài hiện là approved. Giữ tên file `project-starter.draft.json` để không làm hỏng liên kết cũ; trạng thái thực tế nằm trong từng bản ghi, không suy ra từ tên file.

`corpus_version=project-starter-v2` và `content_hash` (SHA-256 của text UTF-8) giúp theo dõi phiên bản. Tám ID cũ được giữ nguyên. Sáu mẫu phân tích mang `verification=schema_reviewed_not_executed`: đã đối chiếu schema, chưa chạy trên database; duyệt nội dung không đồng nghĩa kiểm thử truy vấn thành công. Đây là bài nguồn, chưa phải chunk được đo theo tokenizer. Chỉ embedding trường text; các trường còn lại là metadata.

## Bước 2 Chuẩn bị tài khoản

Tạo hoặc đăng nhập tài khoản tại [Pinecone Console](https://app.pinecone.io/). Chọn gói Starter và kiểm tra quota database/embedding đang có trong tài khoản. Không tự chuyển sang gói trả phí khi hết quota.

Tạo API key cho project cần dùng. Lưu key trong biến môi trường local hoặc file .env đã được ignore; không ghi vào JSON, Git hoặc gửi key trong chat. Khi cần hỗ trợ, chỉ cung cấp tên index, model, region hoặc lỗi đã che credential.

## Bước 3 Tạo index đúng loại

Cấu hình mục tiêu:

- Tên: `steam-knowledge`.
- Serverless trên AWS `us-east-1`, trong giới hạn tài khoản Starter.
- Document index có trường `text` kiểu string, bật integrated embedding với `multilingual-e5-large`.
- Giữ text để search trả lại đoạn nội dung; không chọn chế độ chỉ giữ vector.
- Namespace thử nghiệm cho corpus hiện tại: `project-starter-v2`.

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

Script standalone hiện có tại `tools/rag/pinecone_corpus.py`; xem lệnh thực tế ở cuối tài liệu. Script không tạo index, không sửa chatbot và không tự chia bài quá dài; nó dừng nếu bài vượt 450 token để tránh cắt mất nội dung.

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

1. Corpus 30 bài đã được duyệt theo yêu cầu người dùng.
2. Kiểm tra độ dài bằng tokenizer, chia chunk và dry-run trước upload.
3. Chuẩn bị tài khoản/index và script kết nối-upload-search.
4. Chạy thử vài đoạn approved, xác minh tìm kiếm.
5. Sau đó mới tích hợp RAG vào chatbot hiện tại.


## Script local đã bổ sung (2026-11-09)

Chạy PowerShell tại root repository. SDK cố định `pinecone==10.3.0`.

```powershell
python -m venv .venv-rag
.\.venv-rag\Scripts\python.exe -m pip install -r tools/rag/requirements.txt
.\.venv-rag\Scripts\python.exe tools/rag/pinecone_corpus.py validate
.\.venv-rag\Scripts\python.exe tools/rag/pinecone_corpus.py check
.\.venv-rag\Scripts\python.exe tools/rag/pinecone_corpus.py dry-run
```

Script đọc `back_end/.env.docker.local`, hỗ trợ `PINECONE_API_KEY` hoặc alias người dùng đã đặt `PINECORN_API_KEY`. Không in key. Biến môi trường của process được ưu tiên hơn file. Dùng `--index TEN_INDEX` nếu tên khác mặc định `ai-data-knowledge`; dùng `--field chunk_text` nếu schema giữ tên đó. Script không đọc biến tên index/namespace từ env: dùng tham số CLI cho hai giá trị này.

Kiểm tra live ngày 2026-11-09 bằng key local: kết nối thành công; project của key chỉ liệt kê `ai-data-knowledge`, schema `_values` dense 768/cosine và `_sparse_values`. Chưa có string field integrated embedding. Vì vậy index này chưa phù hợp để upload text bằng script. Cần tạo document index có `text` với model `multilingual-e5-large` (hoặc kiểm tra đúng project/API key nếu đã tạo nơi khác). Không xóa index cũ.

Dry-run lần đầu tải tokenizer công khai `intfloat/multilingual-e5-large`, không tải trọng số embedding và không gửi corpus tới Pinecone. Đếm cả tiền tố passage và special tokens; bài trên 450 token làm lệnh dừng. Không tự coi mỗi bài là chunk hợp lệ trước khi kiểm tra.

Sau khi có index phù hợp và đã kiểm tra quota miễn phí trong Console:

```powershell
.\.venv-rag\Scripts\python.exe tools/rag/pinecone_corpus.py upload --index steam-knowledge --free-quota-checked
.\.venv-rag\Scripts\python.exe tools/rag/pinecone_corpus.py verify --index steam-knowledge
.\.venv-rag\Scripts\python.exe tools/rag/pinecone_corpus.py search --index steam-knowledge --query "AppID là gì?"
```

Tên `steam-knowledge` trong ví dụ phải là tên index bạn thực sự tạo. Upload theo lô 10 bài, giữ ID nên chạy lại không nhân bản; nếu lỗi giữa chừng có thể đã ghi một số lô. Namespace mới dùng khi thay đổi/xóa bài; script không xóa bản ghi thừa hoặc kích hoạt corpus trong chatbot. Verify kiểm tra đủ ID và content hash, có thể cần chạy lại sau vài giây vì dữ liệu chưa hiện ngay. Search top 3 có thể dùng quota embedding/read. Không tự nâng gói. Các lỗi provider chỉ hiển thị loại lỗi để tránh lộ credential.

Kiểm thử local 2026-11-09: validate 30 bài thành công; kiểm tra từ chối draft, ID trùng và hash sai đều đạt. Dry-run tokenizer E5: tổng 3.308 token, bài dài nhất 149 token (đã tính passage prefix/special tokens). Chưa kiểm thử upsert/fetch/search provider vì index hiện có chưa phù hợp.
