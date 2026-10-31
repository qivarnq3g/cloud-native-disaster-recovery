# Biên bản diễn tập trial-D1-2

- Mã lần: `trial-D1-2`
- Tình huống: D1, xóa namespace `dr-api` trên cụm chính, khôi phục tại chỗ về 1 giây trước sự cố
- Ngày: 31/10/2026
- Người chạy: qivarnq3g, chạy bằng `python -m scripts.dr.azure_drill`
- Người bấm giờ: không có, vòng thử dùng `--auto-decide` nên bước quyết định gần bằng 0
- Giờ phá (UTC): 09:18:43
- Phiên bản mã (commit): 3efdf59

| Bước | Bắt đầu (UTC) | Kết thúc (UTC) | Thời gian (s) | Giờ bấm tay | Kết quả |
|---|---|---|---|---|---|
| detect - phát hiện | 09:18:43 | 09:18:53 | 9,8 | | ok |
| decide - quyết định | 09:18:53 | 09:18:53 | 0,0 | | ok |
| infra - dựng hạ tầng |  |  |  | | not_needed |
| restore - khôi phục dữ liệu | 09:18:53 | 09:19:02 | 8,4 | | fail |
| switch - chuyển lưu lượng |  |  |  | | skipped |
| verify - kiểm tra |  |  |  | | skipped |

- RTO từ lúc phá tới khi phục vụ lại: không đo được, runbook dừng giữa chừng.
- Kết quả kiểm tra: không chạy.
- Kết luận: không đạt.
- Sự cố ngoài kế hoạch: Bước khôi phục dừng sau 8 giây: câu jsonpath chọn bản Velero bị chèn ký tự xuống dòng thật, kubectl báo `unterminated quoted string`. Test giả không bắt được vì `kubectl` giả không đọc jsonpath. Namespace đã bị xóa, cụm chính được khôi phục bằng tay bằng chính `restore-namespace.sh` đã sửa (66 giây, còn 1117 bài).
- Sửa runbook gì sau lần này: Sửa jsonpath, thêm test kiểm chuỗi `{"\n"}` trong lệnh gọi.
