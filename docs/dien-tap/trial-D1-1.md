# Biên bản diễn tập trial-D1-1

- Mã lần: `trial-D1-1`
- Tình huống: D1, xóa namespace `dr-api` trên cụm chính, khôi phục tại chỗ về 1 giây trước sự cố
- Ngày: 31/10/2026
- Người chạy: qivarnq3g, chạy bằng `python -m scripts.dr.azure_drill`
- Người bấm giờ: không có, vòng thử dùng `--auto-decide` nên bước quyết định gần bằng 0
- Giờ phá (UTC): 08:45:57
- Phiên bản mã (commit): b9babf8 (bản sửa `shutil.which` chưa commit)

| Bước | Bắt đầu (UTC) | Kết thúc (UTC) | Thời gian (s) | Giờ bấm tay | Kết quả |
|---|---|---|---|---|---|
| detect - phát hiện | 08:45:57 | 08:46:06 | 9,0 | | ok |
| decide - quyết định | 08:46:06 | 08:46:06 | 0,0 | | ok |
| infra - dựng hạ tầng |  |  |  | | not_needed |
| restore - khôi phục dữ liệu | 08:46:06 | 09:01:17 | 910,4 | | fail |
| switch - chuyển lưu lượng |  |  |  | | skipped |
| verify - kiểm tra |  |  |  | | skipped |

- RTO từ lúc phá tới khi phục vụ lại: không đo được, runbook dừng giữa chừng.
- Kết quả kiểm tra: không chạy.
- Kết luận: không đạt.
- Sự cố ngoài kế hoạch: Bước khôi phục chờ 15 phút rồi dừng. Cơ sở dữ liệu báo `no target backup found`: phiên vừa bật tạo server Postgres mới `primary-202610310831`, kho ở Nhật mới có 8 tệp WAL và chưa có bản đầy đủ nào của server này, nên không khôi phục về một thời điểm được. Velero còn lấy nhầm bản `hourly` của phiên ngày 29/10 (lịch của phiên mới chưa chạy lần nào), nên API chạy image cũ mà ghcr từ chối tải. Trước đó có hai lần chạy dừng ngay khi chuẩn bị, chưa phá gì: Python không tìm thấy `az.cmd`, rồi gọi nhầm bash của WSL.
- Sửa runbook gì sau lần này: Mọi script tạo server mới đều lấy ngay một bản đầy đủ (`take_base_backup`). Bật phiên lấy thêm một bản Velero. `restore-namespace.sh` chỉ dùng bản Velero mới nhất kể từ lúc bật phiên, không có thì dừng.
