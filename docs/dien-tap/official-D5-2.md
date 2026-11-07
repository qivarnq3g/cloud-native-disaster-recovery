# Biên bản diễn tập official-D5-2

- Mã lần: `official-D5-2`
- Tình huống: D5, mất cả nhóm tài nguyên `rg-dr-primary` (máy ảo, mạng và kho ảnh chính), chuyển ấm sang cụm dự phòng đang chạy bản sao
- Ngày: 07/11/2026
- Người chạy: qivarnq3g, chạy tự động theo đợt, bằng `python -m scripts.dr.azure_drill`
- Người bấm giờ: không có, lần này dùng `--auto-decide` nên bước quyết định gần bằng 0, không phản ánh thời gian người trực quyết định
- Lần báo trước: có, không tính là lần không báo trước ở mục 5.4 thiết kế
- Giờ phá (UTC): 12:53:03
- Phiên bản mã (commit): 850ac35
- Tín dụng CPU lúc bắt đầu (điểm đo gần nhất của Azure): primary 101, standby không có điểm đo

| Bước | Bắt đầu (UTC) | Kết thúc (UTC) | Thời gian (s) | Giờ bấm tay | Kết quả |
|---|---|---|---|---|---|
| detect - phát hiện | 12:53:03 | 12:53:28 | 25,3 | | ok |
| decide - quyết định | 12:53:28 | 12:53:34 | 5,5 | | ok |
| infra - dựng hạ tầng |  |  |  | | not_needed |
| restore - khôi phục dữ liệu | 12:53:34 | 12:57:09 | 214,8 | | ok |
| switch - chuyển lưu lượng | 12:57:09 | 12:57:22 | 12,2 | | ok |
| verify - kiểm tra | 12:57:22 | 12:58:01 | 38,9 | | ok |

- RTO từ lúc phá tới khi phục vụ lại: 258,4 s, mục tiêu 10 phút, đạt.
- Kết quả kiểm tra: 1100 bài đã xác nhận, còn 1048, thiếu 52 (RPO 45,205 s, mục tiêu 300 s), lỗ hổng 0, mã nội dung khớp, 1074 ảnh kiểm, 0 ảnh hỏng, 48 ảnh mất trong RPO ảnh, đăng bài mới được.
- Kết luận: đạt.
- Sự cố ngoài kế hoạch: Hai lần dựng cụm dự phòng trước lần này hỏng vì lỗi mạng tạm thời tới Azure (cổng 6443 của máy mới dựng, rồi `terraform init` khi lấy khóa tài khoản lưu trữ trạng thái), trước khi phá nên không tính là lần chạy. Sau lần này, lần dừng phiên đầu tiên lỗi vì job két hết thời gian chờ mạng (`urlopen error timed out`), lần thử lại sau 6 phút qua. Không ảnh hưởng kết quả lần này. Lần này chạy `azure_drill` qua lớp bọc ngoài repo, chỉ đọc lại ảnh khi lỗi mạng, không đổi cách chấm; số lần đọc lại: 0.
- Sửa runbook gì sau lần này: Không.
