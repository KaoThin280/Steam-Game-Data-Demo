# Frontend

Ứng dụng Next.js 14 theo package.json, React 18 và TypeScript. Giao diện gọi Product API, không gọi tool server trực tiếp.

## Trang và thành phần

| Đường dẫn | Nội dung |
|---|---|
| `/login` | Đăng ký/đăng nhập |
| `/games`, `/games/[appid]` | Danh sách game, bộ lọc, phân trang, chi tiết và reviews |
| `/dashboard` | Thống kê và Chart.js, không có chat panel |
| `/chat` | AgentChatWorkspace, session/run/event và biểu đồ Plotly |
| `/admin` | Danh sách người dùng; chưa có đầy đủ UI gán/thu hồi role |

`src/hooks/useAgentHarness.ts` gọi `/agent-rpc` và poll tiến trình. `src/lib/api.ts` cấu hình Axios; `src/store/` quản lý auth/status bằng Zustand. SWR dùng cho truy vấn dữ liệu, Tailwind cho giao diện, react-hook-form/zod cho form. Xem [package.json](package.json) để tra dependency chính xác.

## Chạy local

Từ `front_end/`, chạy `npm ci`, cấu hình `.env.local` theo [.env.local.example](.env.local.example), rồi `npm run dev`. URL API cần đầy đủ prefix:

```dotenv
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

API cần MCP đang chạy. Hướng dẫn khởi động cả stack ở [local development](../docs/guides/local-development.md). Kiểm tra code bằng `npm run type-check`, `npm run lint`, `npm run build`.

## Auth và ranh giới quyền

Axios gửi cookie (`withCredentials`) và Bearer token từ store. Backend login trả access token nhưng chỉ đặt refresh token trong cookie. Logic frontend hiện còn kỳ vọng refreshToken trong store trước khi refresh; đây là khoảng trống tích hợp cần sửa/kiểm thử, không bảo đảm auto-refresh hoạt động sau hết hạn access token.

UI chat cho analyst/scientist/admin, viewer chủ yếu vào games. Route guard và navigation chỉ là kiểm soát UI; Agent API hiện cho user active sở hữu session, dashboard API cho cả bốn role. Xem [API](../docs/reference/api.md).

## Hosting

Khi cấu hình Vercel, dùng root directory `front_end` và biến `NEXT_PUBLIC_API_URL=https://<api-host>/api/v1`. CORS/cookie/domain cần kiểm thử trên môi trường thật. Repository không tự xác nhận deployment hoặc integration tự deploy đã được bật.

Xem [deployment](../docs/operations/deployment.md) và [mục lục](../docs/README.md).
