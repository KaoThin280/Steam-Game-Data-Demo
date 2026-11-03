# Luồng thực thi Agent Harness

Phạm vi là luồng chat mặc định qua `/api/v1/agent-rpc`. Từ “RPC” trong URL chỉ cách đặt tên API; request từ frontend là REST JSON, không có envelope JSON-RPC.

## Từ câu chat đến câu trả lời

1. [useAgentHarness.ts](../../front_end/src/hooks/useAgentHarness.ts) gửi câu hỏi vào phiên đã chọn.
2. [agent_rpc.py](../../back_end/app/api/v1/agent_rpc.py) kiểm tra user, sở hữu session và rate limit; lưu `AgentRun(status="queued")`, trả `202` cùng `run_id`.
3. `_schedule_run` dùng `asyncio.create_task` trong process API. `_execute` lấy tối đa `AGENT_HISTORY_RUNS` run completed của cùng phiên, ghép `input_text`/`output_text`, rồi thêm câu hỏi mới. Event/tool trace cũ không tự được đưa lại vào history.
4. [runtime.py](../../back_end/app/agent_harness/runtime.py) thêm system prompt, lấy danh sách tool, gọi provider. [provider.py](../../back_end/app/agent_harness/provider.py) gửi messages và function schemas tới OpenRouter.
5. Nếu model trả tool calls, runtime ghi event, gọi gateway, thêm kết quả thành message `tool` rồi gọi model tiếp. Nếu model không yêu cầu tool nữa, lưu câu trả lời và trạng thái completed.
6. [store.py](../../back_end/app/agent_harness/store.py) lưu run/event vào PostgreSQL; frontend poll trạng thái và event. Backend cũng có SSE phát event đã lưu, không phải token streaming từ model.

Các interface `ModelProvider`, `ToolGateway`, `RunStore` nằm ở [types.py](../../back_end/app/agent_harness/types.py). Chúng giúp thay provider/transport/storage mà vẫn giữ vòng lặp; phần scheduling và dựng history hiện còn nằm trong router.

## Ranh giới MCP

`HTTPMCPGateway` gọi `POST /mcp` trên tool server, thêm Bearer service secret và chèn `__agent_context` từ API. Model không được tự chọn user sở hữu chart.

Ví dụ envelope minh họa, không phải kết quả gọi thật:

```json
{"jsonrpc":"2.0","id":"example-1","method":"tools/call","params":{"name":"steam_catalog_overview","arguments":{}}}
```

Server hỗ trợ `tools/list` và `tools/call`. Chưa có `initialize`, thương lượng capability hay đầy đủ Streamable HTTP. Tên class `MockSteamMCPServer` không có nghĩa mọi dữ liệu là giả: handler truy cập PostgreSQL và E2B thật khi được cấu hình.

## Trạng thái và phục hồi

```text
queued -> running -> completed | failed | cancelled
shutdown/restart -> requeue/recover -> chạy lại run
```

Database có partial unique index cho một run queued/running trên mỗi session. Hủy run ghi `cancel_requested` và trạng thái cancelled, rồi hủy task cục bộ nếu còn tồn tại. Việc hủy task API không chứng minh tác vụ bên ngoài đã dừng tức thì.

Startup tìm run queued/running, xử lý yêu cầu hủy hoặc ghi `run.recovered` và lập lịch lại. Đây là **replay từ đầu**, không phải checkpoint tại một tool step. Chống lặp tool trong runtime chỉ tồn tại trong lần thực thi đó. Cache chart có thể tái sử dụng nhưng không phải bảo đảm exactly-once cho mọi ghi dữ liệu; replay có thể phát sinh thêm lần gọi model, E2B hoặc ghi chart.

Event là nhật ký được ứng dụng thêm theo sequence; không phải audit log bất biến ở mức database. Xóa session không có run active sẽ cascade xóa run/event. Multi-worker cần lease/heartbeat và idempotency trước khi mở rộng.

## Giới hạn và lỗi

| Cơ chế | Hiện trạng trong code |
|---|---|
| Bước model | `AGENT_MAX_STEPS=8`, cấu hình cho phép 1–30 |
| History | Tối đa 20 run completed theo mặc định |
| Timeout tool | 12 giây mặc định; Python dùng tối thiểu `E2B_TIMEOUT + 10` tại gateway |
| Query cho model | Tối đa 10 sample rows; aggregate tối đa 1.200 điểm |
| Python input | Tối đa 5.000 dòng và 5 MiB, cấp sẵn DataFrame `df` |
| Event payload | `AGENT_EVENT_MAX_BYTES=65536` mặc định |
| Tool mô phỏng | `simulate_failure`, `simulate_slow_tool`, `simulate_disconnect` được công bố cùng catalog, chưa có cờ chỉ bật khi test |

Gateway chuyển một số lỗi tool/HTTP timeout/kết nối thành lỗi cấu trúc để model có thể sửa yêu cầu. Tuy nhiên runtime còn bọc lời gọi bằng `asyncio.wait_for`; timeout ở lớp ngoài hoặc exception không được gateway xử lý có thể làm run failed với `RUNTIME_ERROR`. Chống gọi lặp ghi nhớ mọi call đã trả về, kể cả kết quả `ok=false`, nên lặp nguyên tham số lỗi cũng có thể bị chặn.

Runtime hiện lưu `str(exc)` vào lỗi run/event; không có bước redaction tổng quát cho trace này. Ngưỡng event 65.536 byte kích hoạt cắt preview, không phải giới hạn tuyệt đối kích thước JSON sau khi thêm wrapper. SQL validator và bộ lọc Python là lớp kiểm tra đầu vào; quyền database thực tế và E2B mới là những ranh giới cần được kiểm chứng.

Xem [prompt và tools](../reference/agent-prompts-and-tools.md), [API contract](../reference/api.md) và [testing](../guides/testing.md).
