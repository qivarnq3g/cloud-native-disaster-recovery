# Biên bản diễn tập official-D3-2

- Mã lần: `official-D3-2`
- Tình huống: D3, mất máy `vm-dr-primary`, chuyển ấm sang cụm dự phòng đang chạy bản sao
- Ngày: 07/11/2026
- Người chạy: qivarnq3g, tác vụ tự động theo lịch, chạy bằng `python -m scripts.dr.azure_drill`
- Người bấm giờ: không có, lần này dùng `--auto-decide` nên bước quyết định gần bằng 0, không phản ánh thời gian người trực quyết định
- Lần báo trước: có, không tính là lần không báo trước ở mục 5.4 thiết kế
- Giờ phá (UTC): 05:28:26
- Phiên bản mã (commit): 850ac35
- Tín dụng CPU lúc bắt đầu (điểm đo gần nhất của Azure): primary 63, standby 80

| Bước | Bắt đầu (UTC) | Kết thúc (UTC) | Thời gian (s) | Giờ bấm tay | Kết quả |
|---|---|---|---|---|---|
| detect - phát hiện | 05:28:26 | 05:28:49 | 23,5 | | ok |
| decide - quyết định | 05:28:49 | 05:28:56 | 7,1 | | ok |
| infra - dựng hạ tầng |  |  |  | | not_needed |
| restore - khôi phục dữ liệu | 05:28:57 | 05:32:36 | 219,0 | | ok |
| switch - chuyển lưu lượng | 05:32:36 | 05:32:51 | 15,3 | | ok |
| verify - kiểm tra | 05:32:51 | 05:33:33 | 41,9 | | ok |

- RTO từ lúc phá tới khi phục vụ lại: 265,7 s, mục tiêu 10 phút, đạt.
- Kết quả kiểm tra: 1092 bài đã xác nhận, còn 1074, thiếu 18 (RPO 18,489 s, mục tiêu 300 s), lỗ hổng 0, mã nội dung khớp, 1100 ảnh kiểm, 0 ảnh hỏng, 0 ảnh mất trong RPO ảnh, đăng bài mới được.
- Kết luận: đạt.
- Sự cố ngoài kế hoạch: Sau khi lần này đạt, bước tắt phiên `session-stop.sh standby` lúc dựng lại bị lỗi: job két `vault-202611070533` hết giờ (120 s) khi nối tới kho ảnh `standby`. Kết quả lần diễn tập không đổi. lỗi lặp lại ở lần chạy lại thứ nhất và tái hiện được khi cụm mở nhiều kết nối ngắn tới kho, nghi do cổng nguồn NAT bị dùng lại, chưa chứng minh trọn vẹn. Xử lý: chờ 6 phút rồi chạy lại bước tắt phiên, đề xuất sửa mã qua PR.
- Sửa runbook gì sau lần này: Không.
