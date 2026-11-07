# Biên bản diễn tập official-D4-1

- Mã lần: `official-D4-1`
- Tình huống: D4, mất cả nhóm tài nguyên `rg-dr-primary` (máy ảo, mạng và kho ảnh chính), chuyển lạnh, chép ảnh từ bản chép ở Nhật
- Ngày: 07/11/2026
- Người chạy: qivarnq3g, tác vụ tự động theo lịch, chạy bằng `python -m scripts.dr.azure_drill`
- Người bấm giờ: không có, lần này dùng `--auto-decide` nên bước quyết định gần bằng 0, không phản ánh thời gian người trực quyết định
- Lần báo trước: có, không tính là lần không báo trước ở mục 5.4 thiết kế
- Giờ phá (UTC): khoảng 07:10:20, suy từ giờ phát hiện, công cụ không ghi được `runs.csv`
- Phiên bản mã (commit): 850ac35

| Bước | Bắt đầu (UTC) | Kết thúc (UTC) | Thời gian (s) | Giờ bấm tay | Kết quả |
|---|---|---|---|---|---|
| detect - phát hiện | | 07:10:50 | 29,7 | | ok |
| infra - dựng hạ tầng | 07:10:50 | 07:13:12 | 141,8 | | ok |
| restore - khôi phục dữ liệu | 07:13:12 | 07:19:30 | 377,5 | | ok |
| switch - chuyển lưu lượng | 07:19:30 | 07:19:43 | 12,8 | | ok |
| verify - kiểm tra | 07:19:43 | 07:20:49 | | | lỗi |

- RTO từ lúc phá tới khi phục vụ lại: không có số, bước kiểm tra chưa hoàn tất.
- Kết quả kiểm tra: không có. Công cụ dừng với `TimeoutError` khi đọc thân phản hồi một ảnh qua API, hết 30 s, không có thử lại.
- Kết luận: không đạt. Không có số RPO, số bài và số ảnh nên không chấm được; lần này không chấm lại.
- Sự cố ngoài kế hoạch: Có. Nhật ký API cho thấy mọi yêu cầu ảnh đều được trả trong tối đa 217 ms, yêu cầu cuối lúc 07:20:19, lỗi ở phía máy chạy kiểm tra lúc 07:20:49, tức là thân phản hồi bị treo trên đường truyền từ cụm về laptop. Đọc lại 3.312 lần từ laptop với cùng 16 luồng không tái hiện. Nguyên nhân gốc của lần treo chưa xác định. Điểm yếu đã rõ: `image_faults` không thử lại, một lần đọc treo làm hỏng cả lần diễn tập.
- Sửa runbook gì sau lần này: Có, ở bước dựng lại: sau `rebuild-primary-storage.sh` bỏ qua `restore-replication.sh`, vì chạy lại báo lỗi chính sách đã tồn tại. Đề xuất sửa công cụ kiểm tra và `restore-replication.sh` qua PR.
