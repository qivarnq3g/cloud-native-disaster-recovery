# Biên bản diễn tập official-D4-5

- Mã lần: `official-D4-5`
- Tình huống: D4, mất cả nhóm tài nguyên `rg-dr-primary` (máy ảo, mạng và kho ảnh chính), chuyển lạnh, chép ảnh từ bản chép ở Nhật
- Ngày: 07/11/2026
- Người chạy: qivarnq3g, tác vụ tự động theo lịch, chạy bằng `python -m scripts.dr.azure_drill`
- Người bấm giờ: không có, lần này dùng `--auto-decide` nên bước quyết định gần bằng 0, không phản ánh thời gian người trực quyết định
- Lần báo trước: có, không tính là lần không báo trước ở mục 5.4 thiết kế
- Giờ phá (UTC): 10:36:30
- Phiên bản mã (commit): 850ac35
- Tín dụng CPU lúc bắt đầu (điểm đo gần nhất của Azure): primary 76

| Bước | Bắt đầu (UTC) | Kết thúc (UTC) | Thời gian (s) | Giờ bấm tay | Kết quả |
|---|---|---|---|---|---|
| detect - phát hiện | 10:36:30 | 10:36:58 | 27,7 | | ok |
| decide - quyết định | 10:36:58 | 10:37:01 | 3,4 | | ok |
| infra - dựng hạ tầng | 10:37:01 | 10:39:37 | 155,8 | | ok |
| restore - khôi phục dữ liệu | 10:39:37 | 10:46:13 | 395,7 | | ok |
| switch - chuyển lưu lượng | 10:46:14 | 10:46:26 | 12,5 | | ok |
| verify - kiểm tra | 10:46:26 | 10:47:04 | 37,6 | | ok |

- RTO từ lúc phá tới khi phục vụ lại: 596,1 s, mục tiêu 60 phút, đạt.
- Kết quả kiểm tra: 1102 bài đã xác nhận, còn 1043, thiếu 59 (RPO 50,937 s, mục tiêu 300 s), lỗ hổng 0, mã nội dung khớp, 1069 ảnh kiểm, 0 ảnh hỏng, 0 ảnh mất trong RPO ảnh, đăng bài mới được.
- Kết luận: đạt.
- Sự cố ngoài kế hoạch: Không có. Lần này chạy `azure_drill` qua lớp bọc ngoài repo, chỉ đọc lại ảnh khi lỗi mạng, không đổi cách chấm; số lần đọc lại: 0.
- Sửa runbook gì sau lần này: Không.
