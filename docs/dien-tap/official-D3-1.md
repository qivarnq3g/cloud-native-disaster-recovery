# Biên bản diễn tập official-D3-1

- Mã lần: `official-D3-1`
- Tình huống: D3, mất máy `vm-dr-primary`, chuyển ấm sang cụm dự phòng đang chạy bản sao
- Ngày: 07/11/2026
- Người chạy: qivarnq3g, tác vụ tự động theo lịch, chạy bằng `python -m scripts.dr.azure_drill`
- Người bấm giờ: không có, lần này dùng `--auto-decide` nên bước quyết định gần bằng 0, không phản ánh thời gian người trực quyết định
- Lần báo trước: có, không tính là lần không báo trước ở mục 5.4 thiết kế
- Giờ phá (UTC): 04:56:21
- Phiên bản mã (commit): 850ac35
- Tín dụng CPU lúc bắt đầu (điểm đo gần nhất của Azure): primary 64

| Bước | Bắt đầu (UTC) | Kết thúc (UTC) | Thời gian (s) | Giờ bấm tay | Kết quả |
|---|---|---|---|---|---|
| detect - phát hiện | 04:56:21 | 04:56:44 | 23,5 | | ok |
| decide - quyết định | 04:56:44 | 04:56:52 | 7,7 | | ok |
| infra - dựng hạ tầng |  |  |  | | not_needed |
| restore - khôi phục dữ liệu | 04:56:52 | 05:00:27 | 215,2 | | ok |
| switch - chuyển lưu lượng | 05:00:28 | 05:00:46 | 18,1 | | ok |
| verify - kiểm tra | 05:00:46 | 05:01:26 | 40,2 | | ok |

- RTO từ lúc phá tới khi phục vụ lại: 265,2 s, mục tiêu 10 phút, đạt.
- Kết quả kiểm tra: 1093 bài đã xác nhận, còn 1085, thiếu 8 (RPO 8,438 s, mục tiêu 300 s), lỗ hổng 0, mã nội dung khớp, 1111 ảnh kiểm, 0 ảnh hỏng, 0 ảnh mất trong RPO ảnh, đăng bài mới được.
- Kết luận: đạt.
- Sự cố ngoài kế hoạch: Không có.
- Sửa runbook gì sau lần này: Không.
