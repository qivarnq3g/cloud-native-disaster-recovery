# Hướng dẫn tái lập, dọn tài nguyên và chi phí

Tài liệu này trả lời bốn việc đề yêu cầu: dựng lại hệ thống, chạy lại diễn tập, dọn sạch tài nguyên, ước tính chi phí. Cuối tài liệu là danh mục rủi ro bảo mật còn lại.

Có hai cách tái lập:

| Cách | Cần gì | Tốn tiền | Chạy được |
|---|---|---|---|
| Bản thu nhỏ trên kind | Một máy có Docker, 4 CPU, 8 GB RAM | Không | D1, D2, D3, D6 |
| Hệ thống thật trên Azure | Tài khoản Azure, tên miền trên Cloudflare | Có, xem mục 4 | D1 đến D7 |

Phiên bản của mọi công cụ nằm ở [versions.md](versions.md). Thiết kế đầy đủ ở [thiet-ke.md](thiet-ke.md), các bước khôi phục ở [runbook.md](runbook.md).

## 1. Bản thu nhỏ trên kind

Cài đặt và lệnh chi tiết ở [scripts/kind/README.md](../scripts/kind/README.md). Tóm tắt:

```bash
pip install -r scripts/kind/requirements.txt
scripts/kind/up.sh
scripts/kind/run.sh D1
scripts/kind/down.sh
```

`up.sh` dựng hai cụm, kho S3 và bộ dữ liệu mẫu 1.000 bài, khoảng 4 phút từ lần thứ hai. Mỗi lần chạy ghi kết quả vào thư mục dữ liệu của bản thu nhỏ; lặp nhiều lần thì dùng `run.sh D2 --iterations 3` hoặc workflow `kind-mini` trên GitHub Actions. Kết quả 119 lần chạy của nhóm nằm ở `data/kind/2026-11-08-gh42434189591/`.

## 2. Hệ thống thật trên Azure

Chạy trong Git Bash hoặc WSL. Cần `az`, `terraform`, `kubectl`, `helm`, Python 3.12 và `pip install -r scripts/requirements.txt`. Mọi khóa và mã bí mật được script ghi vào `~/.dr/` (ngoài kho), không in ra màn hình.

### 2.1 Dựng lần đầu

1. Đăng nhập: `az login`.
2. Tạo nhóm `rg-dr-backup` ở `japanwest` và tài khoản lưu trạng thái Terraform (có khóa chống xóa):

```bash
bash infra/bootstrap/bootstrap.sh
```

3. Dựng phần lưu trữ sống suốt đồ án: kho sao lưu và két ở Nhật, kho ảnh chính và dự phòng ở Hàn Quốc, chính sách chép ảnh, ngân sách 25 USD có cảnh báo email.

```bash
source scripts/azure/env.sh
tf_init infra/terraform/storage storage.tfstate
terraform -chdir=infra/terraform/storage apply -var suffix=$SFX -var budget_email=<email nhận cảnh báo>
```

`vault_locked` mặc định là `true`: chính sách WORM 7 ngày của két bị khóa cứng, không gỡ được, chỉ kéo dài được. Muốn thử trước mà không khóa thì thêm `-var vault_locked=false`.

4. Cấp các mã SAS (mã truy cập có hạn) cho từng việc:

```bash
bash scripts/azure/issue-sas.sh cnpg-backup
bash scripts/azure/issue-sas.sh api-images-primary
bash scripts/azure/issue-sas.sh api-images-standby
bash scripts/azure/issue-sas.sh vault-writer
bash scripts/azure/issue-sas.sh check-read
bash scripts/azure/issue-sas.sh drill-read
```

`check-read` và `drill-read` còn ghi secret `BACKUP_CHECK_SAS_JSON`, `DRILL_READ_SAS_JSON` lên GitHub bằng `gh secret set`, cho hai workflow `backup-check` (mỗi giờ) và `daily-drill` (mỗi ngày).

5. DNS: ghi token Cloudflare chỉ có quyền sửa DNS của tên miền vào `~/.dr/cloudflare-token` và mã vùng vào `~/.dr/cloudflare-zone-id` (hoặc biến môi trường `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ZONE_ID`). Tên miền `api.dr.qivarn.id.vn` của nhóm được ghi trong `scripts/dr/dns_switch.py`, `infra/k8s/overlays/azure/` và `app/api/src/config.rs`; người tái lập với tên miền khác phải đổi ở các chỗ đó.

### 2.2 Bật, tắt một phiên làm việc

```bash
bash scripts/azure/session-start.sh primary main
bash scripts/azure/standby-up.sh main
bash scripts/azure/session-stop.sh primary
bash scripts/azure/standby-down.sh
```

`session-start.sh` dựng máy ảo, cài k3s và phần mềm, khôi phục cơ sở dữ liệu từ phiên trước, chạy API và đổi DNS. `standby-up.sh` chỉ cần cho cách ấm (D3, D5). `session-stop.sh` lấy bản sao lưu đầy đủ, bản Velero, gói két, rồi xóa máy ảo. Danh sách đầy đủ các script ở [scripts/README.md](../scripts/README.md).

### 2.3 Chạy lại diễn tập

```bash
python -m scripts.dr.azure_drill D2 --run-id official-D2-4
```

Script phá cụm theo tình huống (D1 đến D5), đo sáu bước, kiểm tra dữ liệu và ghi `data/azure/drills/<run_id>/`. Sau mỗi lần, đưa hệ thống về trạng thái ban đầu theo mục "Dựng lại sau diễn tập" của [runbook.md](runbook.md). D6 chạy bằng `bash scripts/azure/vault-d6.sh`. D7 chạy `python -m scripts.vault.restore_test` (tải gói từ két, cần `DRILL_READ_SAS_JSON` và khóa `age`) hoặc `restore_test --from-dir <thư mục gói>` khi gói đã có sẵn ngoài Azure; cách chạy và kết quả mẫu ở [dien-tap/official-D7-1.md](dien-tap/official-D7-1.md). Bảng và biểu đồ trong báo cáo được vẽ lại từ dữ liệu thô bằng:

```bash
python -m scripts.report.charts
```

### 2.4 Tầng thứ ba ngoài Azure

Cách dựng server tự kéo gói từ két mỗi đêm ở [infra/offsite/README.md](../infra/offsite/README.md). Mã SAS của nó cấp bằng `issue-sas.sh offsite-read` và phải cấp lại trước khi hết hạn.

## 3. Dọn tài nguyên

### 3.1 Cuối mỗi buổi

```bash
bash scripts/azure/session-stop.sh <cụm đang phục vụ>
bash scripts/azure/standby-down.sh
az vm list -o table
```

Lệnh cuối không được còn máy `vm-dr-*`. Chỉ tắt máy (`session-pause.sh`) thì vẫn trả tiền ổ đĩa và địa chỉ IP, nên chỉ dùng khi nghỉ dưới một giờ. Bản thu nhỏ dọn bằng `scripts/kind/down.sh`.

### 3.2 Dọn hẳn khi kết thúc đồ án

1. Dọn như mục 3.1 cho cả hai cụm.
2. Két khóa cứng không xóa được trước khi gói cuối cùng hết hạn giữ (7 ngày sau lần ghi cuối). Đợi qua ngày đó.
3. Xóa phần lưu trữ:

```bash
source scripts/azure/env.sh
tf_init infra/terraform/storage storage.tfstate
terraform -chdir=infra/terraform/storage destroy -var suffix=$SFX -var budget_email=<email>
```

4. Gỡ khóa chống xóa của tài khoản trạng thái rồi xóa nhóm cuối cùng:

```bash
az lock delete -g rg-dr-backup -n protect-state --resource-type Microsoft.Storage/storageAccounts --resource "$STATE_ACCOUNT"
az group delete -n rg-dr-backup --yes
```

5. Trên server ngoài Azure: `systemctl disable --now dr-offsite.timer`, xóa `/opt/dr-offsite`, `/var/lib/dr-offsite`, `/etc/dr-offsite` và user `dr-offsite`.
6. Xóa secret GitHub `BACKUP_CHECK_SAS_JSON`, `DRILL_READ_SAS_JSON`, token Cloudflare, rồi xóa thư mục `~/.dr/`.

## 4. Chi phí

Chi phí thật của toàn bộ thử nghiệm và diễn tập, lấy từ Azure Cost Management, từ 25/09 đến hết 07/11/2026: 5,70 USD. Số liệu thô: `data/azure/cost-2026-11-08.csv`.

| Hạng mục | Chi phí thật (USD) |
|---|---|
| Máy ảo B2als v2, tổng 31,2 giờ | 1,46 |
| Truyền dữ liệu giữa hai vùng | 1,08 |
| Thao tác đọc, ghi trên kho lưu trữ | khoảng 2,14 |
| Địa chỉ IP tĩnh, 136,5 giờ | 0,68 |
| Ổ đĩa P4 | 0,34 |
| Tổng | 5,70 |

Ước tính trước khi làm (giá bán lẻ ngày 07/10/2026, 120 giờ-cụm) là khoảng 10 USD; thực tế thấp hơn vì máy ảo chỉ tồn tại trong lúc chạy phiên. Bảng ước tính chi tiết ở mục 7 của [thiet-ke.md](thiet-ke.md).

Để tự ước tính cho một lần tái lập:

- Mỗi giờ một cụm chạy tốn khoảng 0,059 USD (máy 0,0468, ổ đĩa khoảng 0,0072, IP 0,005).
- Ví dụ: một buổi một giờ có cả cụm chính và cụm dự phòng tốn khoảng 0,12 USD tiền máy, chưa tính truyền dữ liệu và thao tác lưu trữ.
- Nếu chạy thật cả tháng: cách lạnh chỉ trả tiền lưu trữ, khoảng 1 USD mỗi tháng; cách ấm thêm một cụm dự phòng chạy suốt, khoảng 44 USD mỗi tháng.

## 5. Rủi ro bảo mật còn lại

- Bản Velero trong kho ở Nhật có chứa Secret của cụm và chỉ được Azure mã hóa phía máy chủ. Bản trong két thì được mã hóa thêm bằng `age`.
- Mã bí mật để đăng bài nằm trong `~/.dr/` trên laptop chạy diễn tập. Lộ mã thì người ngoài đăng được bài; phải sinh mã mới và triển khai lại API.
- Cả ba tầng bản sao trên Azure dùng chung một tài khoản và một tenant. Chỉ tầng thứ ba nằm ngoài Azure.
- Mã chỉ đọc két và khóa `age` dùng cho GitHub nằm trong GitHub Secrets, nên ai có quyền quản trị kho GitHub thì đọc được bản trong két. Dữ liệu là dữ liệu giả nên nhóm chấp nhận.
- Khóa giải mã `age` của người vận hành chỉ có một bản trên laptop. Mất laptop thì không giải mã được két; cần một bản sao cất ngoài máy.
- Hai thành viên còn lại làm theo runbook trên máy của người vận hành, không có tài khoản Azure riêng. Ít người giữ quyền hơn, nhưng vắng người vận hành thì vẫn cần máy đó.
- Máy chủ ngoài Azure do một cá nhân ngoài nhóm cho mượn, nhóm không kiểm soát. Gói ở đó đã được mã hóa và máy không giữ khóa giải mã.
