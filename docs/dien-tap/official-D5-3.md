# Biên bản diễn tập official-D5-3

- Mã lần: `official-D5-3`
- Tình huống: D5, mất cả nhóm tài nguyên `rg-dr-primary` (máy ảo, mạng và kho ảnh chính), chuyển ấm sang cụm dự phòng đang chạy bản sao
- Ngày: 07/11/2026
- Người chạy: qivarnq3g, chạy tự động theo đợt, bằng `python -m scripts.dr.azure_drill`
- Người bấm giờ: không có, lần này dùng `--auto-decide` nên bước quyết định gần bằng 0, không phản ánh thời gian người trực quyết định
- Lần báo trước: có, không tính là lần không báo trước ở mục 5.4 thiết kế
- Giờ phá (UTC): 13:43:34
- Phiên bản mã (commit): 850ac35
- Tín dụng CPU lúc bắt đầu (điểm đo gần nhất của Azure): primary 85, standby 67

| Bước | Bắt đầu (UTC) | Kết thúc (UTC) | Thời gian (s) | Giờ bấm tay | Kết quả |
|---|---|---|---|---|---|
| detect - phát hiện | 13:43:34 | 13:44:05 | 31,4 | | ok |
| decide - quyết định | 13:44:05 | 13:44:06 | 1,1 | | ok |
| infra - dựng hạ tầng |  |  |  | | not_needed |
| restore - khôi phục dữ liệu | 13:44:07 | 13:47:40 | 213,3 | | ok |
| switch - chuyển lưu lượng | 13:47:40 | 13:47:52 | 11,8 | | ok |
| verify - kiểm tra | 13:47:52 | 13:48:29 | 37,0 | | ok |

- RTO từ lúc phá tới khi phục vụ lại: 258,1 s, mục tiêu 10 phút, đạt.
- Kết quả kiểm tra: 1102 bài đã xác nhận, còn 1086, thiếu 16 (RPO 6,467 s, mục tiêu 300 s), lỗ hổng 0, mã nội dung khớp, 1112 ảnh kiểm, 0 ảnh hỏng, 86 ảnh mất trong RPO ảnh, đăng bài mới được.
- Kết luận: đạt.
- Sự cố ngoài kế hoạch: Không. Lần này chạy `azure_drill` qua lớp bọc ngoài repo, chỉ đọc lại ảnh khi lỗi mạng, không đổi cách chấm; số lần đọc lại: 0.
- Sửa runbook gì sau lần này: Không.
