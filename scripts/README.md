# scripts

Script dựng, tắt và kiểm tra hệ thống. Người làm: Quang.

| Lệnh | Việc |
|---|---|
| `bash scripts/azure/session-start.sh primary <image_tag>` | Dựng máy ảo, cài phần mềm, khôi phục cơ sở dữ liệu từ phiên trước, chạy API, đổi bản ghi DNS |
| `bash scripts/azure/session-pause.sh primary` | Tắt máy ảo (deallocate), giữ ổ đĩa; chỉ nghỉ dưới 1 giờ |
| `bash scripts/azure/session-resume.sh primary` | Bật lại máy ảo, chờ `/healthz` trả 200 |
| `bash scripts/azure/session-stop.sh primary` | Sao lưu đầy đủ, sao lưu Velero, ghi `session.json`, xóa máy ảo |
| `python -m scripts.dr.dns_switch <ip>` | Đổi bản ghi A của `api.dr.qivarn.id.vn` qua API Cloudflare |
| `python -m scripts.dr.backup_check` | Kiểm tra độ mới của WAL, Velero, bản chép ảnh, hạn SAS (workflow `backup-check` mỗi giờ) |
| `bash scripts/drill/run-daily-drill.sh` | Khôi phục vào cụm kind và so dữ liệu (workflow `daily-drill` mỗi ngày) |
| `bash scripts/kind/run.sh <D1..D6>` | Diễn tập trên bản thu nhỏ hai cụm kind |

Số đo của các lần chạy thật nằm trong `data/azure/`, kết quả tóm tắt trong `docs/trial-results.md`.
