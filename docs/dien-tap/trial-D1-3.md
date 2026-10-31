# Biên bản diễn tập trial-D1-3

- Mã lần: `trial-D1-3`
- Tình huống: D1, xóa namespace `dr-api` trên cụm chính, khôi phục tại chỗ về 1 giây trước sự cố
- Ngày: 31/10/2026
- Người chạy: qivarnq3g, chạy bằng `python -m scripts.dr.azure_drill`
- Người bấm giờ: không có, vòng thử dùng `--auto-decide` nên bước quyết định gần bằng 0
- Giờ phá (UTC): 09:27:17
- Phiên bản mã (commit): 4431145

| Bước | Bắt đầu (UTC) | Kết thúc (UTC) | Thời gian (s) | Giờ bấm tay | Kết quả |
|---|---|---|---|---|---|
| detect - phát hiện | 09:27:17 | 09:27:27 | 9,7 | | ok |
| decide - quyết định | 09:27:27 | 09:27:27 | 0,0 | | ok |
| infra - dựng hạ tầng |  |  |  | | not_needed |
| restore - khôi phục dữ liệu | 09:27:27 | 09:28:31 | 64,1 | | ok |
| switch - chuyển lưu lượng |  |  |  | | not_needed |
| verify - kiểm tra | 09:28:31 | 09:29:10 | 38,4 | | ok |

- RTO từ lúc phá tới khi phục vụ lại: 74,0 s, mục tiêu 60 phút, đạt.
- Kết quả kiểm tra: 1101 bài đã xác nhận, còn 1092, thiếu 9 (RPO 4,158 s, mục tiêu 300 s), lỗ hổng 0, mã nội dung khớp, 1118 ảnh kiểm, 0 ảnh hỏng, đăng bài mới được.
- Kết luận: đạt.
- Sự cố ngoài kế hoạch: Không có.
- Sửa runbook gì sau lần này: Không.
