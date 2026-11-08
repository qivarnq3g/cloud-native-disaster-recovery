# Biên bản diễn tập official-D3-3

- Mã lần: `official-D3-3`
- Tình huống: D3, mất máy `vm-dr-primary`, chuyển ấm sang cụm dự phòng đang chạy bản sao
- Ngày: 07/11/2026
- Người chạy: qivarnq3g, tác vụ tự động theo lịch, chạy bằng `python -m scripts.dr.azure_drill`
- Người bấm giờ: không có, lần này dùng `--auto-decide` nên bước quyết định gần bằng 0, không phản ánh thời gian người trực quyết định
- Lần báo trước: có, không tính là lần không báo trước ở mục 5.4 thiết kế
- Giờ phá (UTC): 06:46:19
- Phiên bản mã (commit): 850ac35
- Tín dụng CPU lúc bắt đầu (điểm đo gần nhất của Azure): primary 62, standby 78

| Bước | Bắt đầu (UTC) | Kết thúc (UTC) | Thời gian (s) | Giờ bấm tay | Kết quả |
|---|---|---|---|---|---|
| detect - phát hiện | 06:46:19 | 06:46:39 | 20,4 | | ok |
| decide - quyết định | 06:46:39 | 06:46:39 | 0,3 | | ok |
| infra - dựng hạ tầng |  |  |  | | not_needed |
| restore - khôi phục dữ liệu | 06:46:40 | 06:50:20 | 220,6 | | ok |
| switch - chuyển lưu lượng | 06:50:21 | 06:50:35 | 14,1 | | ok |
| verify - kiểm tra | 06:50:35 | 06:51:14 | 39,5 | | ok |

- RTO từ lúc phá tới khi phục vụ lại: 256,1 s, mục tiêu 10 phút, đạt.
- Kết quả kiểm tra: 1093 bài đã xác nhận, còn 1088, thiếu 5 (RPO 5,847 s, mục tiêu 300 s), lỗ hổng 0, mã nội dung khớp, 1114 ảnh kiểm, 0 ảnh hỏng, 0 ảnh mất trong RPO ảnh, đăng bài mới được.
- Kết luận: đạt.
- Sự cố ngoài kế hoạch: Không có.
- Sửa runbook gì sau lần này: Không.
