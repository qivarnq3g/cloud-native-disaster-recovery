# Biên bản diễn tập official-D4-2

- Mã lần: `official-D4-2`
- Tình huống: D4, mất cả nhóm tài nguyên `rg-dr-primary` (máy ảo, mạng và kho ảnh chính), chuyển lạnh, chép ảnh từ bản chép ở Nhật
- Ngày: 07/11/2026
- Người chạy: qivarnq3g, tác vụ tự động theo lịch, chạy bằng `python -m scripts.dr.azure_drill`
- Người bấm giờ: không có, lần này dùng `--auto-decide` nên bước quyết định gần bằng 0, không phản ánh thời gian người trực quyết định
- Lần báo trước: có, không tính là lần không báo trước ở mục 5.4 thiết kế
- Giờ phá (UTC): khoảng 08:06:25, suy từ giờ phát hiện, công cụ không ghi được `runs.csv`
- Phiên bản mã (commit): 850ac35

| Bước | Bắt đầu (UTC) | Kết thúc (UTC) | Thời gian (s) | Giờ bấm tay | Kết quả |
|---|---|---|---|---|---|
| detect - phát hiện | | 08:06:52 | 27,1 | | ok |
| infra - dựng hạ tầng | 08:06:52 | 08:08:52 | 120,1 | | ok |
| restore - khôi phục dữ liệu | 08:08:53 | 08:15:41 | 408,0 | | ok |
| switch - chuyển lưu lượng | 08:15:41 | 08:15:56 | 14,8 | | ok |
| verify - kiểm tra | 08:15:56 | 08:16:47 | | | lỗi |

- RTO từ lúc phá tới khi phục vụ lại: không có số, bước kiểm tra chưa hoàn tất.
- Kết quả kiểm tra: không có. Công cụ dừng với `ConnectionResetError` khi đọc một ảnh qua API, không có thử lại.
- Kết luận: không đạt. Không có số RPO, số bài và số ảnh nên không chấm được; lần này không chấm lại.
- Sự cố ngoài kế hoạch: Có. Cùng lỗi với `official-D4-1`, nhật ký API không có yêu cầu nào lỗi. Đọc lại bằng đúng đường của công cụ kiểm tra (HTTP thẳng tới IP máy ảo, 16 luồng) tái hiện được: 3 lần treo 30 s trong 4.504 lần đọc; qua tên miền HTTPS trước đó 0 lần trong 3.312 lần. Lỗi nằm trên đường từ laptop tới cụm, nguyên nhân gốc chưa xác định. Từ lần sau chạy qua lớp bọc ngoài repo chỉ đọc lại ảnh khi lỗi mạng, không đổi cách chấm.
- Sửa runbook gì sau lần này: Không. Đề xuất sửa công cụ kiểm tra qua PR.
