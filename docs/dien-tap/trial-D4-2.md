# Biên bản diễn tập trial-D4-2

- Mã lần: `trial-D4-2`
- Tình huống: D4, mất cả nhóm tài nguyên `rg-dr-primary` (máy ảo, mạng và kho ảnh chính), chuyển lạnh sang cụm dự phòng dựng mới, ảnh lấy từ kho bản sao ở Nhật
- Ngày: 03/11/2026
- Người chạy: qivarnq3g, chạy bằng `python -m scripts.dr.azure_drill`
- Người bấm giờ: không có, vòng thử dùng `--auto-decide` nên bước quyết định gần bằng 0
- Giờ phá (UTC): 17:25:49
- Phiên bản mã (commit): bab1bff

| Bước | Bắt đầu (UTC) | Kết thúc (UTC) | Thời gian (s) | Giờ bấm tay | Kết quả |
|---|---|---|---|---|---|
| detect - phát hiện | 17:25:51 | 17:26:15 | 24,5 | | ok |
| decide - quyết định | 17:26:15 | 17:26:20 | 4,8 | | ok |
| infra - dựng hạ tầng | 17:26:20 | 17:28:44 | 143,7 | | ok |
| restore - khôi phục dữ liệu | 17:28:44 | 17:33:45 | 300,5 | | fail |
| switch - chuyển lưu lượng |  |  |  | | skipped |
| verify - kiểm tra |  |  |  | | skipped |

- RTO từ lúc phá tới khi phục vụ lại: không đo được, runbook dừng giữa chừng.
- Kết quả kiểm tra: không chạy.
- Kết luận: không đạt.
- Sự cố ngoài kế hoạch: Azure từ chối lệnh chép ảnh sang kho dự phòng với mã `OrsPolicyConflict`. Kho dự phòng vẫn là đích của chính sách chép ảnh từ kho chính, dù kho chính đã mất cùng nhóm `rg-dr-primary`, và kho đích của một chính sách không nhận ghi từ nguồn khác. `failover-cold.sh` chỉ gỡ chính sách này ở cuối bước restore, sau khi chép. Lần trial-D4-1 không gặp vì tối 31/10 hệ thống được tắt khi chưa dựng lại chính sách, nên lúc đó kho dự phòng không là đích của chính sách nào.
- Sửa runbook gì sau lần này: Không đổi bước nào. Sửa `failover-cold.sh`: khi chép ảnh từ kho bản sao, gỡ chính sách chép ảnh của kho dự phòng và chờ kho nhận ghi trước khi chép.
