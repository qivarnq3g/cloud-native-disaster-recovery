# Biên bản diễn tập official-D2-3

- Mã lần: `official-D2-3`
- Tình huống: D2, mất máy `vm-dr-primary`, chuyển lạnh sang `standby`, dùng lại kho ảnh chính
- Ngày: 07/11/2026
- Người chạy: qivarnq3g, tác vụ tự động theo lịch, chạy bằng `python -m scripts.dr.azure_drill`
- Người bấm giờ: không có, lần này dùng `--auto-decide` nên bước quyết định gần bằng 0, không phản ánh thời gian người trực quyết định
- Lần báo trước: có, không tính là lần không báo trước ở mục 5.4 thiết kế
- Tín dụng CPU lúc bắt đầu: không đo được, lệnh đọc số liệu lỗi do Git Bash đổi đường dẫn mã tài nguyên
- Giờ phá (UTC): 04:16:36
- Phiên bản mã (commit): 850ac35

| Bước | Bắt đầu (UTC) | Kết thúc (UTC) | Thời gian (s) | Giờ bấm tay | Kết quả |
|---|---|---|---|---|---|
| detect - phát hiện | 04:16:36 | 04:16:57 | 21,0 | | ok |
| decide - quyết định | 04:16:57 | 04:17:07 | 9,7 | | ok |
| infra - dựng hạ tầng | 04:17:07 | 04:19:17 | 130,1 | | ok |
| restore - khôi phục dữ liệu | 04:19:17 | 04:25:55 | 397,3 | | ok |
| switch - chuyển lưu lượng | 04:25:55 | 04:26:16 | 20,5 | | ok |
| verify - kiểm tra | 04:26:16 | 04:28:42 | 146,3 | | ok |

- RTO từ lúc phá tới khi phục vụ lại: 579,3 s, mục tiêu 60 phút, đạt.
- Kết quả kiểm tra: 1091 bài đã xác nhận, còn 1044, thiếu 47 (RPO 49,075 s, mục tiêu 300 s), lỗ hổng 0, mã nội dung khớp, 1070 ảnh kiểm, 0 ảnh hỏng, 0 ảnh mất trong RPO ảnh, đăng bài mới được.
- Kết luận: đạt.
- Sự cố ngoài kế hoạch: Không có. Khôi phục và kiểm tra chậm hơn hai lần trước (397,3 s so với khoảng 300 s; 146,3 s so với khoảng 40 s), chưa rõ nguyên nhân, vẫn trong mục tiêu.
- Sửa runbook gì sau lần này: Không.
