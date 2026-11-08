# Biên bản diễn tập official-D2-2

- Mã lần: `official-D2-2`
- Tình huống: D2, mất máy `vm-dr-primary`, chuyển lạnh sang `standby`, dùng lại kho ảnh chính
- Ngày: 07/11/2026
- Người chạy: qivarnq3g, tác vụ tự động theo lịch, chạy bằng `python -m scripts.dr.azure_drill`
- Người bấm giờ: không có, lần này dùng `--auto-decide` nên bước quyết định gần bằng 0, không phản ánh thời gian người trực quyết định
- Lần báo trước: có, không tính là lần không báo trước ở mục 5.4 thiết kế
- Tín dụng CPU lúc bắt đầu: không đo được, lệnh đọc số liệu lỗi do Git Bash đổi đường dẫn mã tài nguyên
- Giờ phá (UTC): 03:48:14
- Phiên bản mã (commit): 850ac35

| Bước | Bắt đầu (UTC) | Kết thúc (UTC) | Thời gian (s) | Giờ bấm tay | Kết quả |
|---|---|---|---|---|---|
| detect - phát hiện | 03:48:14 | 03:48:34 | 19,9 | | ok |
| decide - quyết định | 03:48:34 | 03:48:35 | 0,7 | | ok |
| infra - dựng hạ tầng | 03:48:35 | 03:50:59 | 143,9 | | ok |
| restore - khôi phục dữ liệu | 03:50:59 | 03:55:53 | 293,5 | | ok |
| switch - chuyển lưu lượng | 03:55:53 | 03:56:05 | 11,9 | | ok |
| verify - kiểm tra | 03:56:05 | 03:56:43 | 38,2 | | ok |

- RTO từ lúc phá tới khi phục vụ lại: 470,9 s, mục tiêu 60 phút, đạt.
- Kết quả kiểm tra: 1093 bài đã xác nhận, còn 1047, thiếu 46 (RPO 46,334 s, mục tiêu 300 s), lỗ hổng 0, mã nội dung khớp, 1073 ảnh kiểm, 0 ảnh hỏng, 0 ảnh mất trong RPO ảnh, đăng bài mới được.
- Kết luận: đạt.
- Sự cố ngoài kế hoạch: Không có.
- Sửa runbook gì sau lần này: Không.
