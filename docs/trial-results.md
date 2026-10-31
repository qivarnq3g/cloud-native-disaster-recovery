# Kết quả chạy thử trên Azure

Ngày chạy: 24/10/2026. Kế hoạch: `docs/ke-hoach/2026-10-09-chay-thu-azure.md`.

| # | Câu hỏi (mục 8 thiết kế chính) | Kết quả đo | Quyết định |
|---|---|---|---|
| 1 | RAM của một cụm | Máy 3906 MB. Lúc rảnh (đủ phần mềm và cơ sở dữ liệu): 1772 MB dùng. Trong 1 giờ tải 1 bài/giây, 12 lần đo cách 5 phút: 1721-1797 MB, đỉnh 1797 MB (46%) | Dưới ngưỡng 80% (3200 MB): giữ B2als v2 |
| 2 | Dung lượng WAL mỗi ngày | Khoảng 1 giờ (06:05-07:05 UTC): 63 tệp WAL, 4 622 357 byte sau nén gzip, tức khoảng 111 MB/ngày trong kho. Số tệp gần bằng số phút vì `archive_timeout` 60 s ép đổi tệp mỗi phút | Dưới ngưỡng 2 GB/ngày: giữ cỡ tệp WAL mặc định |
| 3 | Thời gian chép ảnh Hàn Quốc sang Nhật | 200 ảnh 200 KB, 1 ảnh/giây: trung vị 52,7 s, p95 128,7 s, lớn nhất 139,2 s, không thiếu ảnh nào | RPO của ảnh đặt không dưới p95: 5 phút là đủ an toàn |
| 4 | Thời gian dựng một cụm mới | Cụm chính: 2 phút 15 giây từ lệnh tạo máy tới Traefik sẵn sàng (máy ảo 71 s, k3s 17 s, nút 8 s, Traefik 39 s). Tín dụng CPU: Azure chưa có số đo cho máy vừa tạo; khoảng 35 phút sau còn 69-73 (cụm chính) và 62-66 (cụm dự phòng). Cụm dự phòng: 1 phút 57 giây | Dựng lại một cụm mất dưới 3 phút, cộng khoảng 3 phút cài phần mềm (161 s ở cụm chính) |
| 5 | iNET cho ủy quyền `api.dr` sang Azure DNS (bản ghi NS) | Câu hỏi đã đổi: từ 09/10 DNS của `qivarn.id.vn` nằm ở Cloudflare Free (`nslookup` 24/10 trả `alexandra`, `bryce.ns.cloudflare.com`). Tài liệu Cloudflare (đọc 24/10): gói Free cho tạo bản ghi NS để ủy quyền tên con, tối đa 10 máy chủ tên; tên con ủy quyền không đi qua proxy của Cloudflare. Chưa tạo bản ghi nào | Chốt 24/10 (Quang chọn): giữ ở Cloudflare, đổi bản ghi A qua API Cloudflare khi chuyển cụm; bỏ vùng Azure DNS khỏi thiết kế |
| 6 | CNPG dựng cụm bản sao từ kho ở Nhật; đường dẫn WAL riêng mỗi cụm | Được. Bản sao Ready sau 72 s, theo kịp cụm chính sau 61 s (đúng `archive_timeout` 60 s). WAL của cụm chính ở `primary-1024/`, của cụm dự phòng ở `standby-1024/`, không lẫn. Đổi vai thành chính: 7 s, ghi được ngay. Khôi phục lạnh từ kho Nhật: 61 s, dữ liệu mới nhất cũ hơn lúc chạy khoảng 1,5 phút | Giữ thiết kế: cụm bản sao đọc WAL từ Nhật, mỗi cụm một `serverName` |
| 7 | Chứng chỉ khôi phục bằng Velero được dùng lại, không xin mới | Được. Serial ở cụm dự phòng sau khôi phục trùng hệt serial cụm chính (`2C8D…5E20`, Let's Encrypt STAGING); sau 10 phút chỉ có 1 CertificateRequest, là bản do Velero khôi phục (người tạo `velero-server`), không có yêu cầu mới; Certificate `True` | Không cần tắt cert-manager khi khôi phục, miễn là Velero khôi phục Secret cùng lúc với Certificate |
| 8 | GitHub gửi email khi workflow lỗi | Có. Workflow `fail-test` lỗi lúc 13:22 (giờ Việt Nam), thư "Run failed: fail-test - trial/fail-email" tới `qivarnq3g@gmail.com` lúc 13:23, nằm ở tab Cập nhật của Gmail (Quang xác nhận bằng ảnh chụp). Theo tài liệu GitHub (chưa kiểm ở đây), thư chỉ gửi cho người kích hoạt workflow | Dùng email của GitHub để báo khi `kiem-tra-sao-luu` hoặc `dien-tap-hang-ngay` lỗi; hai bạn trong nhóm sẽ không nhận được, nên cần báo thêm qua kênh khác nếu muốn cả nhóm biết |
| 9 | Bản thu nhỏ vừa máy GitHub | Vừa. Máy GitHub của kho riêng (2 CPU, 8 GB) dựng xong hai cụm kind, mỗi cụm có cert-manager, CNPG, Barman, Velero và một cơ sở dữ liệu, cộng SeaweedFS: RAM dùng 3,45 GB, còn trống 4,48 GB; ổ đĩa còn 6,5 GB | Giữ bản thu nhỏ hai cụm kind trên GitHub Actions |
| 10 | Ngân sách Azure có tạo được trên tài khoản sinh viên | Được: ngân sách `dr-trial` 25 USD/tháng, cảnh báo email 50/80/100% (API `2023-05-01` trả `amount` 25.0) | Dùng ngân sách có cảnh báo cho cụm thật, không cần xem số dư bằng tay |
| 11 | Thời gian tạo ảnh nhỏ AVIF trên B2als v2 (nếu API đã có) | `bench-thumbnail 50` (bản `production`, musl) trên máy cụm dự phòng đang rảnh, còn 62-66 tín dụng CPU nên không bị giới hạn: trung vị 1275 ms, p95 1340 ms | Vượt ngưỡng 500 ms: đổi ảnh nhỏ sang WebP (mục 7 thiết kế web). Đo ở cụm dự phòng thay vì cụm chính vì cụm chính đang chạy tải giả lập |

## Phiên thật đầu tiên

Ngày chạy: 29/10/2026, cụm chính ở `koreacentral`, ảnh API `e10ae45`. Kế hoạch: Task 10 bước 5 của `docs/ke-hoach/2026-10-24-azure-infrastructure.md`. Mốc thời gian nằm trong `data/azure/session.csv` và `data/azure/dns-switch.csv`.

| Bước | Thời gian | Ghi chú |
|---|---|---|
| Tiếp phiên (`session-resume.sh`) | 69 s | Từ lệnh bật máy tới `/healthz` trả 200 |
| Tắt phiên (`session-stop.sh`) | 2 phút 41 s | Bản đầy đủ CNPG 12 s, bản Velero 8 s, xóa máy bằng Terraform 2 phút 21 s |
| Bật phiên (`session-start.sh`) | 7 phút 9 s | Máy ảo và k3s 2 phút 21 s, phần mềm và khôi phục cơ sở dữ liệu 3 phút 48 s, API 49 s, đổi DNS 9 s |
| Đổi bản ghi A | 7 s | Từ lúc gọi API Cloudflare tới khi DoH thấy IP mới 6 s sau khi bản ghi đổi |

Kết quả:

- Trước khi tắt có 25 bài (5 bài cũ và 20 bài thử mới). Sau khi bật lại vẫn 25 bài, mã băm nội dung giữ nguyên `d8acda86d97314800b17eef5668007ef`.
- Chứng chỉ Let's Encrypt giữ nguyên serial `05652BF0…88B3`: Velero khôi phục từ bản `stop-202610290519`, không xin chứng chỉ mới.
- `session.json` có `server_name` mới `primary-202610290522`, nên WAL của cụm mới không ghi đè lên WAL cũ.
- Xóa máy ảo thì mất luôn IP tĩnh: IP đổi từ `4.218.8.39` sang `20.200.223.12`, `dns_switch.py` đổi bản ghi A tự động. Máy nào còn nhớ IP cũ thì chờ hết TTL 60 s.
- IP nhà đổi giữa hai lần làm việc nên `kubectl` bị chặn ở cổng 6443 trong khi API công khai vẫn chạy. Đã sửa: `session-resume.sh` và `session-stop.sh` cập nhật quy tắc `admin` sang IP hiện tại trước khi dùng cụm.

### Kiểm tra sao lưu mỗi giờ chạy thật

Ngày 29/10, workflow `backup-check` chạy tay trên `main` ba lần:

| Lúc | Trạng thái phiên | Kết quả |
|---|---|---|
| 06:03 UTC | Đang chạy nhưng máy đã nghỉ 30 phút | Đỏ đúng như mong đợi: `wal_age` báo WAL cũ 1787 s, ngưỡng 300 s |
| 06:07 UTC | Đang chạy | Xanh: WAL cũ 59 s, bản Velero cũ 128 s, 26 ảnh đủ ở bản chép |
| 06:14 UTC | Đã tắt | Xanh: chỉ kiểm `session_file`, `sas_expiry`, `stop_backups` |

Lần chạy đầu sau khi tắt phiên báo đỏ ở `stop_backups`. Nguyên nhân: plugin Barman Cloud đặt tên thư mục bản đầy đủ theo mã của nó (`20261029T060730`) và ghi `backup_name=backup-20261029060729` trong `backup.info`, cả hai đều khác tên đối tượng `Backup` của CNPG (`stop-202610290607`) mà `session-stop.sh` lưu vào `session.json`. Đã sửa: `session-stop.sh` lưu `.status.backupId` của đối tượng `Backup`, thiếu thì giữ máy và thoát 1. Từ 06:15 UTC biến `BACKUP_CHECK_ENABLED=true`, kiểm tra chạy mỗi giờ.

### Diễn tập lạnh mỗi ngày chạy thật

Ngày 29/10, workflow `daily-drill` (run 40837880242) trên máy GitHub, khôi phục từ phiên đã tắt `primary-202610290522` và bản Velero `stop-202610290607`:

| Bước | Thời gian |
|---|---|
| Dựng cụm kind | 43 s |
| Cài cert-manager, CNPG, plugin Barman, Velero | 1 phút 25 s |
| Velero khôi phục secret, configmap, deployment, service | 43 s |
| CNPG khôi phục cơ sở dữ liệu từ kho Nhật | 1 phút 13 s |
| API chạy, đọc ảnh ở bản chép | 7 s |
| Kiểm tra | 7 s |
| Tổng | 4 phút 18 s |

Kết quả: 25 bài đúng bằng `post_count`, mã băm nội dung khớp, ảnh không hỏng, container `cnpg` không có tệp mới. API trong cụm diễn tập báo `"cluster":"standby"`, `"read_only":true`.

Ba lần chạy trước đó đỏ, đều do script, không do sao lưu:

- Velero khôi phục các service `db-r`, `db-rw`, `db-ro` của CNPG. Velero gỡ `ownerReferences` khi khôi phục, nên CNPG coi chúng là của người khác và không bao giờ tạo pod. Sửa: khôi phục với `--selector 'app.kubernetes.io/managed-by notin (cloudnative-pg)'`.
- Velero CLI không nhận toán tử `!=` trong bộ chọn nhãn, phải dùng `notin`.

Rủi ro ghi vào báo cáo: diễn tập dùng khóa tài khoản kho sao lưu (`DRILL_VELERO_KEY`, có quyền ghi) vì plugin Velero cho Azure v1.14.4 chưa nhận SAS. Velero đặt kho ở chế độ `ReadOnly`, và kiểm tra cuối xác nhận kho không có tệp mới.

### Trang dùng và phiên thứ hai

Ngày 29/10:

- Repo chuyển sang công khai lúc khoảng 09:20 UTC: GitHub Actions của repo riêng tư đã hết phút miễn phí trong tháng, job mới bị từ chối và không chạy. Trước khi công khai, lịch sử được viết lại để họ tên và email riêng của hai thành viên được thay bằng tên GitHub.
- `API_READY=true`, job `deploy` của `ci` chạy xong: `https://dr.qivarn.id.vn/ready.json` trả `{"ready":true}`, nút "Vào xem" dẫn tới `/view/`. Trang `/view/` hiện nhãn "Cụm chính · Hàn Quốc" và đủ 25 bài.
- Bật phiên lần hai dừng ở bước đổi DNS: `dns_switch` kiểm tra `/healthz` ngay sau khi API rollout, lúc Ingress chưa định tuyến, nên trả lỗi. Ba bước còn lại làm bằng tay; `dns_switch` giờ thử lại tới 120 s.
- Tắt phiên lần hai: `session.json` ghi `full_backup=20261029T094102`, đúng mã của Barman, và `backup-check` xanh với `stop_backups` (sửa ở PR #10 đã đúng trên cụm thật).
- Năm bài thử tạo sáng 29/10 có tiêu đề hỏng dấu ("B?i th? 5") vì được gửi lên với sai bảng mã. Lỗi nằm ở dữ liệu thử, không ở API; API không có lệnh xóa bài nên chúng còn lại.
- Chi phí Azure của ngày 29/10: chưa xem, Cost Management cập nhật chậm khoảng một ngày.

### Cụm dự phòng ấm

Ngày 31/10, cụm chính `primary-202610310410` đang chạy, ảnh API `cf4a692`:

- Lần dựng đầu hỏng: cơ sở dữ liệu bản sao không Ready sau 15 phút, mọi job `db-1-full-recovery` báo `no target backup found`. Cụm chính vừa bật lại dưới tên server mới, mà bản đầy đủ theo lịch 6 giờ chưa chạy, nên kho Nhật chưa có bản đầy đủ nào của tên đó. `standby-up.sh` giờ tạo một bản đầy đủ trên cụm chính và chờ nó xong rồi mới dựng máy.
- Lần dựng thứ hai (`standby-202610310442`), mốc trong `data/azure/standby.csv`: bản đầy đủ 15 s, dựng máy 2 phút 20 s, bản sao Ready 3 phút 22 s, API chạy 34 s; tổng 6 phút 31 s. Xóa cụm hỏng bằng `standby-down.sh` mất 2 phút 10 s.
- Cụm dự phòng báo `Cluster in healthy state`, `pg_is_in_recovery()` trả `t`, `/healthz` qua IP dự phòng trả `"read_only":true`.
- Độ trễ bản sao: một bài đăng ở cụm chính xuất hiện ở cụm dự phòng sau 13 s (đo một lần, kiểm tra 5 s một lần; trước đó 25 bài, sau đó 26 bài ở cả hai cụm). Với `archive_timeout` 60 s, độ trễ có thể lên gần 60 s cộng thời gian đọc WAL nếu bài rơi vào đầu một đoạn WAL; một lần đo chưa đủ để nêu giới hạn.
