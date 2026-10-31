# Biên bản diễn tập trial-D3-1

- Mã lần: `trial-D3-1`
- Tình huống: D3, mất máy ảo cụm chính, chuyển ấm sang cụm dự phòng đang chạy bản sao
- Ngày: 31/10/2026
- Người chạy: qivarnq3g, chạy bằng `python -m scripts.dr.azure_drill`
- Người bấm giờ: không có, vòng thử dùng `--auto-decide` nên bước quyết định gần bằng 0
- Giờ phá (UTC): 12:17:20
- Phiên bản mã (commit): 4ac4eed

| Bước | Bắt đầu (UTC) | Kết thúc (UTC) | Thời gian (s) | Giờ bấm tay | Kết quả |
|---|---|---|---|---|---|
| detect - phát hiện | 12:17:20 | 12:17:41 | 20,8 | | ok |
| decide - quyết định | 12:17:41 | 12:17:41 | 0,0 | | ok |
| infra - dựng hạ tầng |  |  |  | | not_needed |
| restore - khôi phục dữ liệu | 12:17:41 | 12:21:16 | 214,6 | | ok |
| switch - chuyển lưu lượng | 12:21:16 | 12:21:27 | 11,2 | | ok |
| verify - kiểm tra | 12:21:27 | 12:22:05 | 37,4 | | ok |

- RTO từ lúc phá tới khi phục vụ lại: 247,2 s, mục tiêu 10 phút, đạt.
- Kết quả kiểm tra: 1092 bài đã xác nhận, còn 1073, thiếu 19 (RPO 19,54 s, mục tiêu 300 s), lỗ hổng 0, mã nội dung khớp, 1099 ảnh kiểm, 0 ảnh hỏng, đăng bài mới được.
- Kết luận: đạt.
- Sự cố ngoài kế hoạch: Không có. Bước khôi phục ấm mất 215 giây, vượt mục tiêu 2 phút của từng thành phần ở mục 3 thiết kế, dù RTO cả web vẫn trong 10 phút.
- Sửa runbook gì sau lần này: Khi tắt phiên sau lần này mới thấy cụm vừa nâng không có lịch backup đầy đủ và lịch Velero (`install-software.sh` ở chế độ bản sao không tạo). `failover-warm.sh` giờ tạo hai lịch ngay khi nâng cụm. Cần đo lại bước khôi phục ấm, tách thời gian nâng cụm, khởi động lại API và chờ kho ảnh nhận ghi.
