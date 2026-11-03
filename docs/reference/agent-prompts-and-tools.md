# Prompt và tool của agent

Tài liệu chỉ mô tả Agent Harness đang được frontend sử dụng. Sửa `services/ai_service.py` không thay đổi system prompt của luồng này.

## Nguồn quyết định hành vi

| Nguồn | Vai trò |
|---|---|
| [runtime.py](../../back_end/app/agent_harness/runtime.py) | `SYSTEM_PROMPT`, chọn ngôn ngữ, vòng lặp và xử lý tool |
| [provider.py](../../back_end/app/agent_harness/provider.py) | Chuyển tool schemas sang function calling và gọi OpenRouter |
| [mcp.py](../../back_end/app/agent_harness/mcp.py) | Catalog, input schema, validation, query, chart và Python handlers |
| [agent_rpc.py](../../back_end/app/api/v1/agent_rpc.py) | History từ completed runs và context user/session/run |
| [config.py](../../back_end/app/core/config.py) | Model, giới hạn bước, timeout, history và kích thước event |

## System prompt

Agent được yêu cầu phân tích dữ liệu Steam; làm rõ metric/khoảng thời gian, dùng SQL aggregate cho thông tin thực tế, kiểm tra schema khi cần và không bịa số liệu. Khi được phép dùng cache, tìm chart đã lưu trước khi tạo mới. Prompt mô tả schema rút gọn và cấm dữ liệu auth/RBAC; quyền DB vẫn phải được cấu hình riêng.

Ngôn ngữ được suy ra từ câu hỏi hiện tại: có ký tự tiếng Việt trong tập kiểm tra thì chọn Vietnamese, còn lại English. Đây là heuristic; tiếng Việt không dấu có thể bị nhận là English. History chỉ gồm input/output của các run completed trước đó trong cùng phiên.

## Catalog hiện tại

| Tool | Input chính | Kết quả / giới hạn |
|---|---|---|
| `steam_catalog_overview` | Không cần tham số | Số đếm game/review |
| `describe_steam_table` | `table`, `sample_size` | Schema, thống kê, 1–10 dòng mẫu |
| `query_steam_data` | `sql` | SELECT/WITH, mẫu hoặc aggregate có giới hạn |
| `analyze_with_python` | `sql`, `code` | Truy vấn tối đa 5.000 dòng/5 MiB; Python dùng `df`, gán `result` với summary/statistics/chart/notes |
| `monthly_game_releases` | `start_month`, `end_month`, `chart_type`, `force_refresh` | Chuỗi theo tháng và chart lưu lại |
| `create_chart` | `source_query`, `chart_type`, `title`; tùy chọn trục và mô tả | Tối đa 1.200 điểm; hỗ trợ `bar`, `line`, `scatter`, `area` |
| `search_saved_charts` | `query`, `chart_type`, `limit` | Tìm trong chart của user hiện tại |
| `get_saved_chart` | `chart_id` | Lấy chart theo quyền sở hữu |
| `simulate_failure` | Thông điệp lỗi | Lỗi có chủ ý |
| `simulate_slow_tool` | `seconds` | Trì hoãn để kiểm thử timeout/hủy |
| `simulate_disconnect` | Không cần tham số | Mô phỏng mất kết nối |

Ba tool mô phỏng vẫn nằm trong catalog thực tế. Không mô tả chúng là đã bị vô hiệu hóa ở production. Đọc schema trong `list_tools()` trước khi thêm client mới; không suy ra định dạng tool từ khả năng hiển thị của Plotly.

## Tham số model và vòng lặp

Provider dùng `settings.OPENROUTER_MODEL`, `tool_choice="auto"`, `temperature=0.1`, `max_tokens=1800`; timeout SDK theo `LLM_TIMEOUT=120`, `max_retries=1`. Cấu hình có `OPENROUTER_FALLBACK_MODEL`, nhưng `OpenRouterProvider` không thực hiện chuyển sang model này.

Tool result được nối vào messages của run hiện tại, để model sửa SQL hoặc giải thích lỗi. History/event/chart lưu trong PostgreSQL; không có vector retrieval hay tự huấn luyện model từ hội thoại.

## Kiểm tra khi thay đổi

Sửa prompt, schema và handler đồng bộ; kiểm tra unit tests rồi smoke test các câu hỏi tiếng Việt/Anh, số đếm, biểu đồ đúng loại, khoảng thời gian, lookup chart và lỗi tool. Thay đổi prompt không tự bảo đảm model tuân thủ; cần kiểm tra event và kết quả thực tế.
