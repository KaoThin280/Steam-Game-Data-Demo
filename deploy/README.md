# Cấu hình triển khai và script đồng bộ cũ

Hướng dẫn hiện hành nằm ở [deployment](../docs/operations/deployment.md) và [systemd/Compose](../docs/operations/vps-services.md).

## Nội dung thư mục

| File | Vai trò |
|---|---|
| [nginx/steam-api.conf](nginx/steam-api.conf) | Mẫu reverse proxy; thay domain/chứng chỉ và kiểm tra cấu hình trước dùng |
| [vps_sync.sh](vps_sync.sh) | Fetch/reset staging, rsync sang live, restart steam-api |
| [steam-sync.service](steam-sync.service), [steam-sync.timer](steam-sync.timer) | Wrapper systemd/timer cho script đồng bộ cũ |

## Giới hạn của auto-sync cũ

Không dùng timer này như hướng triển khai mặc định của Agent Harness hiện tại:

- Chỉ restart `steam-api`, không quản lý MCP hoặc kiểm tra readiness hai process.
- `rsync --delete` chỉ exclude frontend/db_admin, chưa bảo vệ `.env`, virtualenv và file runtime riêng ở live.
- So sánh requirements sau rsync nên thay đổi đã bị copy đè trước khi kiểm tra; không bảo đảm cài dependency mới.
- Script có fetch/reset và đồng bộ xóa file; cần môi trường staging/live dành riêng, backup và sửa quy trình trước khi sử dụng.

Workflow được check-in ở [.github/workflows/deploy.yml](../.github/workflows/deploy.yml) dùng SSH/nohup, khác với timer này. Không chạy đồng thời các cơ chế trên cùng thư mục/port. Rà soát tài liệu chưa thay đổi hoặc thực thi các script triển khai.
