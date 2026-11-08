# Biên bản diễn tập official-D7-1

- Mã lần: `official-D7-1`
- Tình huống: D7, khôi phục từ két (`drvault`) trên laptop, không cần kho ở Nhật và không cần cụm Azure
- Ngày: 07/11/2026
- Người chạy: qivarnq3g, bằng `python -m scripts.vault.restore_test`, khóa `age` của Quang, Postgres 18.6 trong Docker trên laptop
- Lần báo trước: có
- Giờ bắt đầu (UTC): 14:19:22, kết thúc 14:39:23
- Phiên bản mã (commit): 850ac35
- Gói khôi phục: `standby-202611071335/20261107T134904Z.tar.age`, đóng lúc dừng cụm dự phòng ngay sau official-D5-3

## Kết quả

- Tải, giải mã và khôi phục: 1.201 s (lần thử ngày 04/11 mất 328 s; chưa rõ vì sao chậm hơn).
- Bài viết: 1.113 bài, số bài khớp `manifest.json`, mã băm nội dung khớp.
- Ảnh: 3.182 ảnh trong gói; `restore_test.py` báo thiếu 86 ảnh gốc (`original/`), nên lệnh trả về `ok: false`.
- Cả 86 ảnh thiếu có mã UUIDv7 ứng với giờ tạo 13:42:04 tới 13:43:30 UTC, nằm trong 90 s đăng bài trước giờ phá official-D5-3 (13:43:34). official-D5-3 đã tính đúng 86 ảnh này là mất trong RPO ảnh (300 s). Cụm dự phòng giữ các bài nhưng không có ảnh, và gói trong két chép lại đúng trạng thái đó.
- Chấm theo luật RPO ảnh ở mục 5.3 thiết kế (ảnh của bài đăng trong 300 s trước sự cố được tính là mất trong RPO): 0 ảnh thiếu ngoài RPO. Kết luận chấm lại: đạt phần két.
- Phần khôi phục từ bản ở máy chủ ngoài Azure: chạy lúc 20:05:47 UTC ngày 07/11 (03:05 ngày 08/11 giờ Việt Nam), đạt, xem mục dưới.

## Phần 2: khôi phục từ bản ở máy chủ ngoài Azure

- Tầng thứ ba được dựng ngày 07/11 (`infra/offsite/`, nhánh `offsite-restic-copy`): server `quang-service` ngoài Azure kéo gói mới nhất trong két bằng mã SAS chỉ đọc, giữ bằng restic.
- Trên server, `restic restore latest` lấy ra gói `primary-202611071412/20261107T144834Z.tar.age` (628.285.482 byte) trong 4 s, rồi chép về laptop qua Tailscale trong 221 s.
- Trên laptop chạy `restore_test --from-dir`, không có biến `DRILL_READ_SAS_JSON` và không gọi Azure: giải mã và khôi phục 59 s, 1.026 bài, số bài và mã băm nội dung khớp `manifest.json`, 3.182 ảnh trong gói, 0 ảnh thiếu. Kết quả: đạt.
- Gói này đóng lúc tắt phiên sau khi dựng lại cụm chính, không sau một lần chuyển sang cụm dự phòng, nên không có ảnh mất trong RPO ảnh.

## Ghi chú

- `restore_test.py` lúc chạy phần 1 chưa áp luật RPO ảnh như `azure_drill.py`, nên báo thiếu cả ảnh đã được tính là mất trong RPO. Nhánh `offsite-restic-copy` thêm `--incident-at`, dùng giờ tạo bài lấy từ mã UUIDv7, đúng cách đã chấm lại bằng tay ở trên.
- Phần 1 chậm (1.201 s) so với phần 2 (59 s) cho thấy phần lớn thời gian phần 1 là tải gói từ két ở Nhật; lần này chưa đo riêng bước tải.
- Sửa runbook gì sau lần này: Không.
