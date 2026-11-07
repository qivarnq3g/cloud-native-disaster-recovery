# Biên bản diễn tập official-D5-1

- Mã lần: `official-D5-1`
- Tình huống: D5, mất cả nhóm tài nguyên `rg-dr-primary` (máy ảo, mạng và kho ảnh chính), chuyển ấm sang cụm dự phòng đang chạy bản sao
- Ngày: 07/11/2026
- Người chạy: qivarnq3g, tác vụ tự động theo lịch, chạy bằng `python -m scripts.dr.azure_drill`
- Người bấm giờ: không có, lần này dùng `--auto-decide` nên bước quyết định gần bằng 0, không phản ánh thời gian người trực quyết định
- Lần báo trước: có, không tính là lần không báo trước ở mục 5.4 thiết kế
- Giờ phá (UTC): 11:26:56
- Phiên bản mã (commit): 850ac35
- Tín dụng CPU lúc bắt đầu (điểm đo gần nhất của Azure): primary 79, standby 69

| Bước | Bắt đầu (UTC) | Kết thúc (UTC) | Thời gian (s) | Giờ bấm tay | Kết quả |
|---|---|---|---|---|---|
| detect - phát hiện | 11:26:56 | 11:27:28 | 31,4 | | ok |
| decide - quyết định | 11:27:28 | 11:27:28 | 0,4 | | ok |
| infra - dựng hạ tầng |  |  |  | | not_needed |
| restore - khôi phục dữ liệu | 11:27:29 | 11:31:08 | 219,1 | | ok |
| switch - chuyển lưu lượng | 11:31:08 | 11:31:22 | 14,1 | | ok |
| verify - kiểm tra | 11:31:22 | 11:32:01 | 38,8 | | ok |

- RTO từ lúc phá tới khi phục vụ lại: 265,7 s, mục tiêu 10 phút, đạt.
- Kết quả kiểm tra: 1105 bài đã xác nhận, còn 1074, thiếu 31 (RPO 19,797 s, mục tiêu 300 s), lỗ hổng 0, mã nội dung khớp, 1100 ảnh kiểm, 0 ảnh hỏng, 0 ảnh mất trong RPO ảnh, đăng bài mới được.
- Kết luận: đạt.
- Sự cố ngoài kế hoạch: Sau lần chạy, lúc dựng lại trạng thái ban đầu, `session-start.sh primary main` dừng ở `deploy-api.sh` vì `terraform output` mất kết nối tới Azure khi đọc trạng thái (`connection may have been reset`). Máy và phần mềm đã cài xong; các bước còn lại của script được chạy tiếp bằng tay, rồi chạy `reset-seed.sh primary`. Không ảnh hưởng kết quả lần này. Lần này chạy `azure_drill` qua lớp bọc ngoài repo, chỉ đọc lại ảnh khi lỗi mạng, không đổi cách chấm; số lần đọc lại: 0.
- Sửa runbook gì sau lần này: Không.
