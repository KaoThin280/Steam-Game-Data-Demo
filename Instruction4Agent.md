Đây là dự án về trang web mà nhiều người dùng có thể đăng nhập và sử dụng để theo dõi dữ liệu về meta data và review của ~ 10000 game với hơn 169000 review trên steam, có chức năng xem biểu đồ, AI hỗ trợ query và phân tích dữ liệu. Bên cạnh đó còn có admin role dùng để quản lý cơ sở dữ liệu.
Dự án được chia làm nhiều phần:
- Front end - FE: xử lý giao diện, giúp người dùng tương tác với hệ thống, sẽ được deploy trên Vercel;
- Back end - BE: là máy VPS cung cấp bởi Google Cloud Platform xử lý logic, kết nối với database lưu trữ dữ liệu chính (PostgreSQL-supabase) và redis (Uptash);
- Model AI được cung cấp bởi Openrouter thông qua API.
Mọi cấu hình của các nền tảng đều ở mức miễn phí: storage: 1GB (5GB với GCP, 0.25GB với Uptash Redis), RAM: 1GB.
Code ngôn ngữ trong code là tiếng Anh và không sử dụng các ký tự emotion.
Hướng dẫn, định nghĩa về cấu trúc database chứa trong SCHEMA_DOCUMENTATION.md