# Biên bản diễn tập official-D4-4

- Mã lần: `official-D4-4`
- Tình huống: D4, mất cả nhóm tài nguyên `rg-dr-primary` (máy ảo, mạng và kho ảnh chính), chuyển lạnh, chép ảnh từ bản chép ở Nhật
- Ngày: 07/11/2026
- Người chạy: qivarnq3g, tác vụ tự động theo lịch, chạy bằng `python -m scripts.dr.azure_drill`
- Người bấm giờ: không có, lần này dùng `--auto-decide` nên bước quyết định gần bằng 0, không phản ánh thời gian người trực quyết định
- Lần báo trước: có, không tính là lần không báo trước ở mục 5.4 thiết kế
- Giờ phá (UTC): 09:56:57
- Phiên bản mã (commit): 850ac35
- Tín dụng CPU lúc bắt đầu (điểm đo gần nhất của Azure): primary 82

| Bước | Bắt đầu (UTC) | Kết thúc (UTC) | Thời gian (s) | Giờ bấm tay | Kết quả |
|---|---|---|---|---|---|
| detect - phát hiện | 09:56:57 | 09:57:25 | 28,5 | | ok |
| decide - quyết định | 09:57:25 | 09:57:29 | 3,5 | | ok |
| infra - dựng hạ tầng | 09:57:29 | 10:00:08 | 158,8 | | ok |
| restore - khôi phục dữ liệu | 10:00:08 | 10:07:17 | 428,8 | | ok |
| switch - chuyển lưu lượng | 10:07:18 | 10:07:42 | 24,7 | | ok |
| verify - kiểm tra | 10:07:42 | 10:08:21 | 38,3 | | ok |

- RTO từ lúc phá tới khi phục vụ lại: 645,5 s, mục tiêu 60 phút, đạt.
- Kết quả kiểm tra: 1102 bài đã xác nhận, còn 1046, thiếu 56 (RPO 47,271 s, mục tiêu 300 s), lỗ hổng 0, mã nội dung khớp, 1072 ảnh kiểm, 0 ảnh hỏng, 0 ảnh mất trong RPO ảnh, đăng bài mới được.
- Kết luận: đạt.
- Sự cố ngoài kế hoạch: Không có. Lần này chạy `azure_drill` qua lớp bọc ngoài repo, chỉ đọc lại ảnh khi lỗi mạng, không đổi cách chấm; số lần đọc lại: 0.
- Sửa runbook gì sau lần này: Không.
