# Biên bản diễn tập trial-D4-1

- Mã lần: `trial-D4-1`
- Tình huống: D4, mất cả nhóm tài nguyên `rg-dr-primary` (máy ảo, mạng và kho ảnh chính), chuyển lạnh sang cụm dự phòng dựng mới, ảnh lấy từ kho bản sao ở Nhật
- Ngày: 03/11/2026
- Người chạy: qivarnq3g, chạy bằng `python -m scripts.dr.azure_drill`
- Người bấm giờ: không có, vòng thử dùng `--auto-decide` nên bước quyết định gần bằng 0
- Giờ phá (UTC): 16:21:37
- Phiên bản mã (commit): 6f84ada

| Bước | Bắt đầu (UTC) | Kết thúc (UTC) | Thời gian (s) | Giờ bấm tay | Kết quả |
|---|---|---|---|---|---|
| detect - phát hiện | 16:21:39 | 16:22:09 | 29,3 | | ok |
| decide - quyết định | 16:22:09 | 16:22:09 | 0,6 | | ok |
| infra - dựng hạ tầng | 16:22:10 | 16:24:27 | 137,7 | | ok |
| restore - khôi phục dữ liệu | 16:24:28 | 16:51:23 | 1615,8 | | fail |
| switch - chuyển lưu lượng |  |  |  | | skipped |
| verify - kiểm tra |  |  |  | | skipped |

- RTO từ lúc phá tới khi phục vụ lại: không đo được, runbook dừng giữa chừng.
- Kết quả kiểm tra: không chạy.
- Kết luận: không đạt.
- Sự cố ngoài kế hoạch: Cài phần mềm, khôi phục cơ sở dữ liệu và chạy API trên cụm dự phòng đều xong trong vài phút, nhưng `copy-images.sh` không bao giờ thoát. Vòng chờ đợi tới khi không còn ảnh nào ở kho đích có trạng thái chép khác `success`. Kho ảnh dự phòng còn 4 ảnh chỉ nó có, tải lên lúc cụm dự phòng phục vụ ngày 31/10. Các ảnh này không được chép nên trạng thái chép là rỗng và vòng chờ không dừng, dù cả 1.897 ảnh chép đều `success`. Dừng tay sau 27 phút.
- Sửa runbook gì sau lần này: Không đổi bước nào. Sửa `copy-images.sh`: chỉ chờ ảnh đang `pending`, rồi báo lỗi nếu có ảnh `failed` hoặc `aborted`.
