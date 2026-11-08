# Biên bản diễn tập official-D4-3

- Mã lần: `official-D4-3`
- Tình huống: D4, mất cả nhóm tài nguyên `rg-dr-primary` (máy ảo, mạng và kho ảnh chính), chuyển lạnh, chép ảnh từ bản chép ở Nhật
- Ngày: 07/11/2026
- Người chạy: qivarnq3g, tác vụ tự động theo lịch, chạy bằng `python -m scripts.dr.azure_drill`
- Người bấm giờ: không có, lần này dùng `--auto-decide` nên bước quyết định gần bằng 0, không phản ánh thời gian người trực quyết định
- Lần báo trước: có, không tính là lần không báo trước ở mục 5.4 thiết kế
- Giờ phá (UTC): 09:08:35
- Phiên bản mã (commit): 850ac35
- Tín dụng CPU lúc bắt đầu (điểm đo gần nhất của Azure): primary 89

| Bước | Bắt đầu (UTC) | Kết thúc (UTC) | Thời gian (s) | Giờ bấm tay | Kết quả |
|---|---|---|---|---|---|
| detect - phát hiện | 09:08:35 | 09:09:01 | 25,7 | | ok |
| decide - quyết định | 09:09:01 | 09:09:04 | 3,6 | | ok |
| infra - dựng hạ tầng | 09:09:04 | 09:11:21 | 136,6 | | ok |
| restore - khôi phục dữ liệu | 09:11:21 | 09:18:29 | 427,6 | | ok |
| switch - chuyển lưu lượng | 09:18:29 | 09:18:43 | 13,7 | | ok |
| verify - kiểm tra | 09:18:43 | 09:19:21 | 38,1 | | ok |

- RTO từ lúc phá tới khi phục vụ lại: 608,2 s, mục tiêu 60 phút, đạt.
- Kết quả kiểm tra: 1099 bài đã xác nhận, còn 1046, thiếu 53 (RPO 46,900 s, mục tiêu 300 s), lỗ hổng 0, mã nội dung khớp, 1072 ảnh kiểm, 0 ảnh hỏng, 46 ảnh mất trong RPO ảnh, đăng bài mới được.
- Kết luận: đạt.
- Sự cố ngoài kế hoạch: Không có. Lần này chạy `azure_drill` qua lớp bọc ngoài repo, chỉ đọc lại ảnh khi lỗi mạng, không đổi cách chấm; số lần đọc lại: 0.
- Sửa runbook gì sau lần này: Không.
