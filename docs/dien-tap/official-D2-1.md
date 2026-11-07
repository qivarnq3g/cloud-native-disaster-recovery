# Biên bản diễn tập official-D2-1

- Mã lần: `official-D2-1`
- Tình huống: D2, mất máy `vm-dr-primary`, chuyển lạnh sang `standby`, dùng lại kho ảnh chính
- Ngày: 07/11/2026
- Người chạy: qivarnq3g, tác vụ tự động theo lịch, chạy bằng `python -m scripts.dr.azure_drill`
- Người bấm giờ: không có, lần này dùng `--auto-decide` nên bước quyết định gần bằng 0, không phản ánh thời gian người trực quyết định
- Lần báo trước: có, không tính là lần không báo trước ở mục 5.4 thiết kế
- Tín dụng CPU lúc bắt đầu: không đo được, lệnh đọc số liệu lỗi do Git Bash đổi đường dẫn mã tài nguyên
- Giờ phá (UTC): 03:19:05
- Phiên bản mã (commit): 850ac35

| Bước | Bắt đầu (UTC) | Kết thúc (UTC) | Thời gian (s) | Giờ bấm tay | Kết quả |
|---|---|---|---|---|---|
| detect - phát hiện | 03:19:05 | 03:19:25 | 20,7 | | ok |
| decide - quyết định | 03:19:25 | 03:19:26 | 0,1 | | ok |
| infra - dựng hạ tầng | 03:19:26 | 03:21:48 | 141,8 | | ok |
| restore - khôi phục dữ liệu | 03:21:48 | 03:26:53 | 304,7 | | ok |
| switch - chuyển lưu lượng | 03:26:53 | 03:27:06 | 12,9 | | ok |
| verify - kiểm tra | 03:27:06 | 03:27:46 | 40,2 | | ok |

- RTO từ lúc phá tới khi phục vụ lại: 481,1 s, mục tiêu 60 phút, đạt.
- Kết quả kiểm tra: 1092 bài đã xác nhận, còn 1088, thiếu 4 (RPO 4,785 s, mục tiêu 300 s), lỗ hổng 0, mã nội dung khớp, 1114 ảnh kiểm, 0 ảnh hỏng, 0 ảnh mất trong RPO ảnh, đăng bài mới được.
- Kết luận: đạt.
- Sự cố ngoài kế hoạch: Không có.
- Sửa runbook gì sau lần này: Không.
