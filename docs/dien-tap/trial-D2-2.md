# Biên bản diễn tập trial-D2-2

- Mã lần: `trial-D2-2`
- Tình huống: D2, mất máy ảo cụm chính, chuyển lạnh sang cụm dự phòng dựng mới
- Ngày: 31/10/2026
- Người chạy: qivarnq3g, chạy bằng `python -m scripts.dr.azure_drill`
- Người bấm giờ: không có, vòng thử dùng `--auto-decide` nên bước quyết định gần bằng 0
- Giờ phá (UTC): 10:44:52
- Phiên bản mã (commit): 4431145

| Bước | Bắt đầu (UTC) | Kết thúc (UTC) | Thời gian (s) | Giờ bấm tay | Kết quả |
|---|---|---|---|---|---|
| detect - phát hiện | 10:44:52 | 10:45:11 | 18,9 | | ok |
| decide - quyết định | 10:45:11 | 10:45:12 | 1,2 | | ok |
| infra - dựng hạ tầng | 10:45:12 | 10:47:05 | 112,9 | | ok |
| restore - khôi phục dữ liệu | 10:47:05 | 10:51:32 | 266,4 | | ok |
| switch - chuyển lưu lượng | 10:51:32 | 10:51:48 | 16,4 | | ok |
| verify - kiểm tra | 10:51:48 | 10:52:24 | 35,2 | | fail |

- RTO từ lúc phá tới khi phục vụ lại: 416,5 s, mục tiêu 60 phút, đạt.
- Kết quả kiểm tra: 1092 bài đã xác nhận, còn 1087, thiếu 5 (RPO 6,396 s, mục tiêu 300 s), lỗ hổng 0, mã nội dung khớp, 1113 ảnh kiểm, 0 ảnh hỏng, đăng bài mới không được.
- Kết luận: không đạt.
- Sự cố ngoài kế hoạch: Dữ liệu đạt nhưng đăng bài mới trả 503: Azure từ chối ghi ảnh với `OrsPolicyConflict`. Hàm gỡ chính sách chép ảnh so `destinationAccount` với tên kho, trong khi Azure trả ID đầy đủ, nên không gỡ gì. Sau khi gỡ đúng, Azure còn từ chối ghi thêm 1 đến 3 phút.
- Sửa runbook gì sau lần này: So phần cuối của ID, bỏ ký tự `\r` do `az` trên Windows xuất ra, và ghi thử một blob tới khi kho dự phòng nhận ghi rồi mới cho API ghi.
