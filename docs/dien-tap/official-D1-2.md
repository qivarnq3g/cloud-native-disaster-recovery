# Biên bản diễn tập official-D1-2

- Mã lần: `official-D1-2`
- Tình huống: D1, xóa namespace `dr-api` trên cụm chính, khôi phục tại chỗ về 1 giây trước sự cố
- Ngày: 07/11/2026
- Người chạy: qivarnq3g, tác vụ tự động theo lịch, chạy bằng `python -m scripts.dr.azure_drill`
- Người bấm giờ: không có, lần này dùng `--auto-decide` nên bước quyết định gần bằng 0, không phản ánh thời gian người trực quyết định
- Lần báo trước: có, không tính là lần không báo trước ở mục 5.4 thiết kế
- Tín dụng CPU lúc bắt đầu: không đo được, lệnh đọc số liệu lỗi do Git Bash đổi đường dẫn mã tài nguyên
- Giờ phá (UTC): 03:03:18
- Phiên bản mã (commit): 850ac35

| Bước | Bắt đầu (UTC) | Kết thúc (UTC) | Thời gian (s) | Giờ bấm tay | Kết quả |
|---|---|---|---|---|---|
| detect - phát hiện | 03:03:18 | 03:03:28 | 9,4 | | ok |
| decide - quyết định | 03:03:28 | 03:03:28 | 0,0 | | ok |
| infra - dựng hạ tầng |  |  |  | | not_needed |
| restore - khôi phục dữ liệu | 03:03:28 | 03:04:32 | 64,4 | | ok |
| switch - chuyển lưu lượng |  |  |  | | not_needed |
| verify - kiểm tra | 03:04:33 | 03:05:11 | 38,9 | | ok |

- RTO từ lúc phá tới khi phục vụ lại: 74,1 s, mục tiêu 60 phút, đạt.
- Kết quả kiểm tra: 1100 bài đã xác nhận, còn 1092, thiếu 8 (RPO 3,491 s, mục tiêu 300 s), lỗ hổng 0, mã nội dung khớp, 1118 ảnh kiểm, 0 ảnh hỏng, 0 ảnh mất trong RPO ảnh, đăng bài mới được.
- Kết luận: đạt.
- Sự cố ngoài kế hoạch: Không có.
- Sửa runbook gì sau lần này: Không.
