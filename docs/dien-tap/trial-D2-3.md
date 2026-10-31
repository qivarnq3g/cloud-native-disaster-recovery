# Biên bản diễn tập trial-D2-3

- Mã lần: `trial-D2-3`
- Tình huống: D2, mất máy ảo cụm chính, chuyển lạnh sang cụm dự phòng dựng mới
- Ngày: 31/10/2026
- Người chạy: qivarnq3g, chạy bằng `python -m scripts.dr.azure_drill`
- Người bấm giờ: không có, vòng thử dùng `--auto-decide` nên bước quyết định gần bằng 0
- Giờ phá (UTC): 11:14:53
- Phiên bản mã (commit): 13fb7b1

| Bước | Bắt đầu (UTC) | Kết thúc (UTC) | Thời gian (s) | Giờ bấm tay | Kết quả |
|---|---|---|---|---|---|
| detect - phát hiện | 11:14:53 | 11:15:15 | 21,6 | | ok |
| decide - quyết định | 11:15:15 | 11:15:24 | 9,2 | | ok |
| infra - dựng hạ tầng | 11:15:24 | 11:17:17 | 113,1 | | ok |
| restore - khôi phục dữ liệu | 11:17:17 | 11:21:55 | 277,3 | | ok |
| switch - chuyển lưu lượng | 11:21:55 | 11:22:07 | 11,6 | | ok |
| verify - kiểm tra | 11:22:07 | 11:22:42 | 35,6 | | fail |

- RTO từ lúc phá tới khi phục vụ lại: 433,6 s, mục tiêu 60 phút, đạt.
- Kết quả kiểm tra: 1092 bài đã xác nhận, còn 1050, thiếu 42 (RPO 42,75 s, mục tiêu 300 s), lỗ hổng 0, mã nội dung khớp, 1076 ảnh kiểm, 50 ảnh hỏng, đăng bài mới được.
- Kết luận: không đạt.
- Sự cố ngoài kế hoạch: Đăng bài được nhưng 50 bài mất ảnh. Cả 50 ảnh đều có ở kho chính và kho bản sao ở Nhật, chỉ thiếu ở kho dự phòng: lần sửa D2-2 đã gỡ nửa chính sách ở kho dự phòng và không có bước nào dựng lại khi quay về cụm chính, nên suốt phiên này không có ảnh nào được chép sang dự phòng.
- Sửa runbook gì sau lần này: Thêm `restore-replication.sh` (gỡ nửa còn sót ở kho chính rồi áp dụng lại stack `storage`) vào bước dựng lại sau mỗi lần chuyển sang dự phòng.
