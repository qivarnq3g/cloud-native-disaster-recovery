# Biên bản diễn tập trial-D2-4

- Mã lần: `trial-D2-4`
- Tình huống: D2, mất máy ảo cụm chính, chuyển lạnh sang cụm dự phòng dựng mới
- Ngày: 31/10/2026
- Người chạy: qivarnq3g, chạy bằng `python -m scripts.dr.azure_drill`
- Người bấm giờ: không có, vòng thử dùng `--auto-decide` nên bước quyết định gần bằng 0
- Giờ phá (UTC): 11:46:03
- Phiên bản mã (commit): 4ac4eed

| Bước | Bắt đầu (UTC) | Kết thúc (UTC) | Thời gian (s) | Giờ bấm tay | Kết quả |
|---|---|---|---|---|---|
| detect - phát hiện | 11:46:03 | 11:46:23 | 20,2 | | ok |
| decide - quyết định | 11:46:23 | 11:46:24 | 0,7 | | ok |
| infra - dựng hạ tầng | 11:46:24 | 11:48:42 | 137,7 | | ok |
| restore - khôi phục dữ liệu | 11:48:42 | 11:53:18 | 275,8 | | ok |
| switch - chuyển lưu lượng | 11:53:18 | 11:53:34 | 16,5 | | ok |
| verify - kiểm tra | 11:53:34 | 11:54:13 | 38,7 | | ok |

- RTO từ lúc phá tới khi phục vụ lại: 451,5 s, mục tiêu 60 phút, đạt.
- Kết quả kiểm tra: 1092 bài đã xác nhận, còn 1051, thiếu 41 (RPO 41,636 s, mục tiêu 300 s), lỗ hổng 0, mã nội dung khớp, 1077 ảnh kiểm, 0 ảnh hỏng, đăng bài mới được.
- Kết luận: đạt.
- Sự cố ngoài kế hoạch: Không có.
- Sửa runbook gì sau lần này: Không.
