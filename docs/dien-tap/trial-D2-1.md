# Biên bản diễn tập trial-D2-1

- Mã lần: `trial-D2-1`
- Tình huống: D2, mất máy ảo cụm chính, chuyển lạnh sang cụm dự phòng dựng mới
- Ngày: 31/10/2026
- Người chạy: qivarnq3g, chạy bằng `python -m scripts.dr.azure_drill`
- Người bấm giờ: không có, vòng thử dùng `--auto-decide` nên bước quyết định gần bằng 0
- Giờ phá (UTC): 09:35:25
- Phiên bản mã (commit): 4431145

| Bước | Bắt đầu (UTC) | Kết thúc (UTC) | Thời gian (s) | Giờ bấm tay | Kết quả |
|---|---|---|---|---|---|
| detect - phát hiện | 09:35:25 | 09:35:45 | 20,3 | | ok |
| decide - quyết định | 09:35:45 | 09:35:46 | 0,8 | | ok |
| infra - dựng hạ tầng | 09:35:46 | 10:17:16 | 2489,6 | | fail |
| restore - khôi phục dữ liệu |  |  |  | | skipped |
| switch - chuyển lưu lượng |  |  |  | | skipped |
| verify - kiểm tra |  |  |  | | skipped |

- RTO từ lúc phá tới khi phục vụ lại: không đo được, runbook dừng giữa chừng.
- Kết quả kiểm tra: không chạy.
- Kết luận: không đạt.
- Sự cố ngoài kế hoạch: Terraform tạo `vm-dr-standby` suốt 41 phút rồi Azure trả `VMStartTimedOut`, máy kẹt ở trạng thái `starting`. Đây là lỗi phía Azure. Khôi phục bằng tay: xóa máy kẹt, xóa ổ đĩa `vm-dr-standby-os` mà `az vm delete` để lại, chạy lại `failover-cold.sh` (6 phút 59 giây). Cụm dự phòng có RPO 43,5 giây, không lỗ hổng, mã nội dung khớp.
- Sửa runbook gì sau lần này: Runbook: nếu máy ảo chưa lên sau 10 phút thì xóa và tạo lại, nhớ xóa ổ đĩa còn sót.
