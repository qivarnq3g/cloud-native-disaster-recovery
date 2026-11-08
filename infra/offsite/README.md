# Bản sao ngoài Azure

Tầng thứ ba ở mục 4.3 của `docs/thiet-ke.md`. Server `quang-service` nằm ngoài Azure và nối qua Tailscale. Mỗi đêm lúc 02:30 giờ Việt Nam, server tự kéo các gói mới trong két về bằng mã SAS chỉ đọc, rồi lưu vào kho restic.

- `scripts/vault/offsite.py` chỉ giữ chuỗi gói của server mới nhất trong thư mục `mirror`, tức gói đầy đủ cùng các gói nối tiếp. File đang tải dở có đuôi `.part` và bị xóa nếu lỗi, nên không làm hỏng bản cũ.
- `offsite-backup.sh` chụp `mirror` bằng restic, giữ 7 bản theo ngày, rồi bỏ dần bản cũ nhất cho tới khi kho dưới 3 GiB.
- Gói đã được mã hóa bằng `age` từ trong cụm. Server không có khóa giải mã, nên người có quyền trên server cũng không đọc được dữ liệu.
- Dịch vụ chạy bằng user hệ thống `dr-offsite`. Nó chỉ ghi được vào `/var/lib/dr-offsite`, không đụng các dịch vụ khác trên server.

## Cài đặt

1. Trên laptop, cấp mã chỉ đọc và liệt kê cho container `vault`: `DR_SAS_DAYS=30 bash scripts/azure/issue-sas.sh offsite-read`. Mã hết hạn sau 30 ngày, phải cấp lại trước hạn.
2. Trên server, cài `restic`, tạo user `dr-offsite`, chép `scripts/vault/{__init__,blob,pack,offsite}.py` và `infra/offsite/` vào `/opt/dr-offsite`.
3. Tạo `/etc/dr-offsite/env` từ `env.example`, ghi mã SAS vào `/etc/dr-offsite/sas` và một mật khẩu ngẫu nhiên vào `/etc/dr-offsite/restic-pass`. Ba file thuộc `root:dr-offsite`, quyền 640.
4. Chạy `restic init` bằng user `dr-offsite`, chép hai unit vào `/etc/systemd/system/`, rồi `systemctl enable --now dr-offsite.timer`.

## Khôi phục (D7, phần server)

Trên server, lấy bản mới nhất ra một thư mục tạm:

```bash
set -a; . /etc/dr-offsite/env; set +a
restic restore latest --target /tmp/d7-offsite
```

restic giữ nguyên đường dẫn gốc, nên các gói nằm ở `/tmp/d7-offsite/var/lib/dr-offsite/mirror/`. Chép thư mục đó về laptop (`scp -r`). Sau đó khôi phục mà không cần Azure, bằng khóa `age` của Quang:

```bash
python -m scripts.vault.restore_test --from-dir <thư mục mirror> --key <khóa age> --age <đường dẫn age> --psql "..." --pg-restore "..."
```

Nếu gói được đóng sau một lần chuyển sang cụm dự phòng, thêm `--incident-at <giờ sự cố ISO 8601>`. Khi đó, ảnh mất của bài tạo trong 300 s trước sự cố được tính là mất trong RPO ảnh, giống bước kiểm tra của D1-D5. Giờ tạo bài lấy từ mã UUIDv7 của bài. Xóa `/tmp/d7-offsite` trên server sau khi chép xong.
