# Biên bản diễn tập trial-D5-1

- Mã lần: `trial-D5-1`
- Tình huống: D5, mất cả nhóm tài nguyên `rg-dr-primary` (máy ảo, mạng và kho ảnh chính), chuyển ấm sang cụm dự phòng đang chạy bản sao
- Ngày: 04/11/2026
- Người chạy: qivarnq3g, chạy bằng `python -m scripts.dr.azure_drill`
- Người bấm giờ: không có, vòng thử dùng `--auto-decide` nên bước quyết định gần bằng 0
- Giờ phá (UTC): 02:47:19
- Phiên bản mã (commit): ffc8282

| Bước | Bắt đầu (UTC) | Kết thúc (UTC) | Thời gian (s) | Giờ bấm tay | Kết quả |
|---|---|---|---|---|---|
| detect - phát hiện | 02:47:20 | 02:47:50 | 30,1 | | ok |
| decide - quyết định | 02:47:50 | 02:47:52 | 2,1 | | ok |
| infra - dựng hạ tầng |  |  |  | | not_needed |
| restore - khôi phục dữ liệu | 02:47:53 | 02:51:29 | 216,3 | | ok |
| switch - chuyển lưu lượng | 02:51:29 | 02:51:42 | 13,2 | | ok |
| verify - kiểm tra | 02:51:42 | 02:52:32 | 49,2 | | ok |

- RTO từ lúc phá tới khi phục vụ lại: 262,3 s, mục tiêu 10 phút, đạt.
- Kết quả kiểm tra: 1102 bài đã xác nhận, còn 1046, thiếu 56 (RPO 47,001 s, mục tiêu 300 s), lỗ hổng 0, mã nội dung khớp, 1072 ảnh kiểm, 0 ảnh hỏng, 0 ảnh mất trong RPO ảnh, đăng bài mới được.
- Kết luận: đạt.
- Sự cố ngoài kế hoạch: Không có.
- Sửa runbook gì sau lần này: Không.
