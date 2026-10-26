# Kế hoạch hạ tầng Azure thật (tuần 3)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> Chỉ chạy các bước tạo tài nguyên Azure khi Quang đã cho phép. Task 1, 7, 9 và phần code của Task 10, 11 không tốn tiền và làm được trước. Mỗi bước tốn tiền ghi rõ "(tạo tài nguyên Azure)".

**Goal:** dựng hạ tầng Azure thật của đồ án bằng Terraform, cài phần mềm sao lưu vào cụm chính, chạy API trên cụm chính ở `https://api.dr.qivarn.id.vn`, và có hai workflow GitHub theo dõi sao lưu mỗi giờ và diễn tập lạnh mỗi ngày.

**Architecture:** Terraform chia hai phần có vòng đời khác nhau: `infra/terraform/storage` (nhóm tài nguyên, các tài khoản lưu trữ, object replication, két, ngân sách; sống suốt đồ án) và `infra/terraform/cluster` (một máy ảo k3s; mỗi cụm một state riêng, dựng lúc bật phiên và xóa lúc tắt phiên). Tài khoản chứa Terraform state được tạo trước bằng script Azure CLI. Phần mềm trong cụm cài bằng Helm và Kustomize từ script; chìa khóa nằm ngoài kho, trong `~/.dr/` và GitHub Secrets. DNS của API nằm ở Cloudflare, script Python đổi bản ghi A qua API Cloudflare.

**Tech Stack:** Terraform 1.x (bản mới nhất lúc cài, ghim ở Task 1) với provider `azurerm` 4.x (ghim bằng `.terraform.lock.hcl`), Azure CLI 2.89, k3s v1.37.1+k3s1, cert-manager v1.21.2, CloudNativePG 1.30.1, Barman Cloud Plugin v0.15.1, Velero v1.18.4 với plugin Azure v1.14.4, Helm 4.3, kubectl 1.36, Kustomize (có sẵn trong kubectl), Python 3.12+ với `azure-storage-blob==12.*` và `pytest`, Rust 1.97.1 cho API, kind cho diễn tập hằng ngày.

**Spec:** [`docs/thiet-ke.md`](../thiet-ke.md) mục 1, 3, 4, 5, 6, 7, 10; [`docs/thiet-ke-web.md`](../thiet-ke-web.md) mục 2, 7; số đo và quyết định ở [`docs/trial-results.md`](../trial-results.md); script đã chạy được ở [`2026-10-09-chay-thu-azure.md`](2026-10-09-chay-thu-azure.md) và `scripts/trial/`, `infra/trial/`.

## Global Constraints

- Chỉ tạo tài nguyên trong ba nhóm `rg-dr-primary`, `rg-dr-standby` (đều `koreacentral`) và `rg-dr-backup` (`japanwest`). Không bao giờ đụng nhóm nào khác, nhất là `rg-splitbind-prod` (dự án khác). Mọi lệnh `az` ghi rõ `-g`, không dùng nhóm mặc định.
- Không có `rg-dr-dns`, không có Azure DNS: bản ghi A `api.dr.qivarn.id.vn` ở Cloudflare, tắt proxy, TTL 60 giây (chốt 24/10).
- Máy ảo: `Standard_B2als_v2` (giữ theo số đo RAM đỉnh 46%), Ubuntu 24.04, ổ P4 32 GB `Premium_LRS`. Không bao giờ chạy cùng lúc quá hai máy (giới hạn 4 nhân).
- Khu vực và cỡ máy là biến Terraform có giá trị mặc định, không viết cứng trong resource.
- Máy ảo không dùng thì phải tắt hẳn (deallocate) hoặc xóa: nghỉ giữa phiên thì `session-pause.sh` (deallocate), hết phiên thì `session-stop.sh` (xóa máy, theo mục 4.1 thiết kế). Mỗi máy có lịch tự tắt 23:00 giờ Việt Nam để phòng quên.
- Tên mọi thứ bằng tiếng Anh: tệp, thư mục, biến, tài nguyên, workflow, trường JSON. Workflow `kiem-tra-sao-luu` của thiết kế có tệp là `backup-check.yml`, `dien-tap-hang-ngay` là `daily-drill.yml`. Thư mục số liệu của thiết kế `data/hang-ngay/` thành `data/daily-drill/`.
- Đăng ký provider trước lần tạo đầu tiên: `Microsoft.Storage`, `Microsoft.Compute`, `Microsoft.Network`, `Microsoft.Insights`, `Microsoft.Consumption`, `Microsoft.DevTestLab` (lịch tự tắt). Thiếu `Microsoft.Storage` thì Azure báo `SubscriptionNotFound` dù tài khoản vẫn `Enabled`.
- Trong Git Bash, lệnh `az` nhận ID tài nguyên (chuỗi bắt đầu bằng `/subscriptions/`) phải có `MSYS_NO_PATHCONV=1` đứng trước; đường dẫn tệp truyền cho `az` dùng `cygpath -m`.
- Lệnh `kubectl` với đối tượng sao lưu luôn ghi tên đầy đủ: `backups.velero.io`, `restores.velero.io`, `schedules.velero.io`, `backupstoragelocations.velero.io`, `backups.postgresql.cnpg.io`, `scheduledbackups.postgresql.cnpg.io`, `clusters.postgresql.cnpg.io`. Tên ngắn `backup` trỏ nhầm sang CNPG.
- Phiên bản ghim như mục Tech Stack. Chart Helm luôn có `--version`: chart CNPG và Velero được chọn theo `app_version` (1.30.1 và 1.18.4) như `scripts/trial/install-software.sh`.
- Ảnh nhỏ là WebP, không còn AVIF (AVIF p95 1340 ms trên B2als v2, vượt ngưỡng 500 ms).
- RPO của ảnh là 5 phút (p95 chép ảnh đo được 129 s). Thiết kế mục 3 sửa từ 15 phút thành 5 phút ở Task 1.
- WAL: `archive_timeout` 60 s, cỡ tệp WAL mặc định (khoảng 111 MB/ngày). Bản đầy đủ mỗi 6 giờ trong phiên và một bản lúc tắt phiên. Giữ 7 ngày (`retentionPolicy: "7d"`).
- Mỗi lần dựng cụm, `serverName` mới dạng `<cluster>-<yyyymmddHHMM>` (UTC), ví dụ `primary-202610271405`.
- Chứng chỉ thật dùng Let's Encrypt production, nhưng chỉ xin khi không có bản Velero để khôi phục; mọi lần dựng lại phải khôi phục Secret chứng chỉ bằng Velero trước (giới hạn 5 chứng chỉ mỗi 7 ngày cho cùng tên).
- Chìa khóa và khóa truy cập nằm trong `~/.dr/` trên laptop (ngoài kho) và GitHub Secrets. Không bao giờ có trong tệp của kho, trong lệnh có ghi lịch sử của kho, hay trong output của workflow. `.gitignore` chặn thêm `.terraform/`, `*.tfstate*`, `*.tfvars` (trừ `*.tfvars.example`).
- Mã Cloudflare chỉ có quyền `Zone.DNS:Edit` trên vùng `qivarn.id.vn`. Trên laptop đọc từ `~/.dr/cloudflare-token`, trên GitHub là secret `CLOUDFLARE_API_TOKEN`.
- Mọi số đo ghi CSV theo giờ UTC: số đo buổi làm ở `data/azure/`, số liệu workflow ở nhánh `ops-log` (`data/backup-check/`, `data/daily-drill/`).
- Văn bản trong kho viết tiếng Việt có dấu, không dùng gạch dài, gạch ngắn hay `--` làm dấu câu.

## Review Focus

- **Bật phiên khi phiên trước chưa tắt sạch** (máy cũ còn, `status/session.json` vẫn `running`): `session-start.sh` phải dừng và báo, không dựng cụm thứ ba, không ghi WAL vào `serverName` cũ. Test ở Task 10 Step 1.
- **Chứng chỉ bị xin mới mỗi lần dựng lại** vì Certificate được áp trước khi Velero khôi phục Secret: `deploy-api.sh` phải khôi phục Velero trước khi áp Ingress có TLS, và chỉ xin mới khi kho chưa có bản Velero nào. Test ở Task 8 Step 4.
- **Đổi DNS sang IP sai hoặc cụm chưa sống:** `dns_switch.py` phải gọi `https://<ip>/healthz` (đúng tên miền qua SNI) trước khi sửa bản ghi và từ chối khi API chưa trả 200. Test ở Task 9 Step 1.
- **Workflow kiểm tra báo "ổn" khi kho rỗng** (chưa có WAL, chưa có Velero, thiếu tệp trạng thái): phải coi là lỗi, không phải là "không có gì để kiểm". Test ở Task 11 Step 1.
- **Quên tắt máy:** lịch tự tắt 23:00 có trên mọi máy, và `session-pause.sh` kiểm tra trạng thái máy là `VM deallocated` (không chỉ `stopped`, vì `stopped` vẫn tính tiền máy). Test ở Task 4 Step 4 và Task 10 Step 5.

---

## Cấu trúc tệp

| Tệp | Việc |
|---|---|
| `infra/bootstrap/bootstrap.sh` | Đăng ký provider, tạo `rg-dr-backup` và tài khoản Terraform state. Chạy được nhiều lần |
| `infra/terraform/storage/*.tf` | Nhóm tài nguyên chính và dự phòng, năm tài khoản lưu trữ, container, phiên bản, vòng đời, object replication, két, ngân sách |
| `infra/terraform/cluster/*.tf`, `cloud-init.yaml.tftpl` | Một máy ảo k3s với mạng, IP, NSG, lịch tự tắt |
| `infra/k8s/platform/*.yaml.tpl` | ObjectStore của Barman, Cluster CNPG, ScheduledBackup, ClusterIssuer, lịch Velero |
| `infra/k8s/api/` (Kustomize) | Deployment, Service, Ingress của API |
| `infra/k8s/values/velero.yaml.tpl` | Giá trị Helm của Velero |
| `scripts/azure/env.sh` | Biến chung: tên tài nguyên, đường dẫn `~/.dr/` |
| `scripts/azure/issue-sas.sh` | Cấp mã SAS theo quyền tối thiểu, ghi ngày hết hạn, đẩy secret lên GitHub |
| `scripts/azure/install-software.sh` | Cài cert-manager, CNPG, Barman, Velero; tạo cơ sở dữ liệu |
| `scripts/azure/deploy-api.sh` | Khôi phục Velero (nếu có), triển khai API, chờ chứng chỉ |
| `scripts/azure/session-start.sh`, `session-pause.sh`, `session-resume.sh`, `session-stop.sh` | Vòng đời phiên |
| `scripts/dr/session_state.py` | Đọc, ghi `status/session.json` và `status/sas-expiry.json` |
| `scripts/dr/dns_switch.py` | Đổi bản ghi A qua API Cloudflare |
| `scripts/dr/backup_check.py` | Lõi kiểm tra của workflow mỗi giờ |
| `scripts/dr/verify_restore.py` | Đếm bài, so mã băm sau khôi phục (dùng cho diễn tập hằng ngày) |
| `tests/scripts/test_*.py` | Kiểm thử cho `scripts/dr/` |
| `.github/workflows/backup-check.yml`, `daily-drill.yml` | Hai workflow theo lịch |
| `docs/versions.md` | Phiên bản cụ thể của mọi công cụ (mục 9 thiết kế gọi là `phien-ban.md`) |

**Tên tài nguyên** (`SFX` là 6 ký tự hex ngẫu nhiên, sinh một lần, lưu ở `~/.dr/suffix`; khác với hậu tố của buổi chạy thử):

| Thứ | Tên |
|---|---|
| Tài khoản Terraform state (`rg-dr-backup`) | `drtfstate${SFX}`, container `tfstate`, khóa state `storage.tfstate`, `cluster-primary.tfstate`, `cluster-standby.tfstate` |
| Kho sao lưu (`rg-dr-backup`) | `drbackup${SFX}`, container `cnpg`, `velero`, `status` |
| Bản chép ảnh ở Nhật (`rg-dr-backup`) | `drimgcopy${SFX}`, container `images` |
| Két (`rg-dr-backup`) | `drvault${SFX}`, container `vault` |
| Kho ảnh chính (`rg-dr-primary`) | `drimgpri${SFX}`, container `images` |
| Kho ảnh dự phòng (`rg-dr-standby`) | `drimgstb${SFX}`, container `images` |
| Máy ảo | `vm-dr-primary`, `vm-dr-standby`; tên DNS Azure `dr-primary-${SFX}.koreacentral.cloudapp.azure.com` |
| Namespace | `dr-api` (API và Cluster CNPG `db`, để D1 xóa cả hai), `cert-manager`, `cnpg-system`, `velero` |
| Ngân sách | `dr-budget`, 25 USD/tháng, cảnh báo 50/80/100% tới `qivarnq3g@gmail.com` |

**Tệp trong `~/.dr/`:** `suffix`, `ssh_ed25519`(`.pub`), `kubeconfig-<cluster>`, `key-<account>`, `sas-<name>.txt`, `cloudflare-token`, `cloudflare-zone-id`, `ghcr-token`, `secret-code`, `age-public.txt` (tuần 4).

**Hai tệp trạng thái** trong container `status` của kho sao lưu, mọi script đều đọc ghi qua `scripts/dr/session_state.py`:

```json
// status/session.json
{"state": "running", "cluster": "primary", "server_name": "primary-202610271405",
 "started_at": "2026-10-27T14:05:12Z", "stopped_at": null,
 "full_backup": null, "velero_backup": null, "post_count": null, "content_digest": null}
// status/sas-expiry.json
{"api-images-primary": "2026-11-26T00:00:00Z", "cnpg-backup": "...", "check-read": "...", "drill-read": "..."}
```

`content_digest` là `md5(string_agg(id::text || ':' || encode(image_sha256, 'hex'), ',' ORDER BY id))` trên bảng `posts`.

---

### Task 1: Công cụ, `.gitignore`, kiểm tra trong `ci`, sửa thiết kế theo buổi chạy thử

**Files:**
- Create: `docs/versions.md`, `scripts/requirements.txt`, `scripts/dr/__init__.py`, `tests/scripts/conftest.py`
- Modify: `.gitignore`, `.github/workflows/ci.yml`, `docs/thiet-ke.md` (mục 3 bảng RPO, mục 9 tên tệp), `docs/thiet-ke-web.md` (mục 2 dòng xử lý ảnh, mục 7)

**Interfaces:**
- Produces: job `infra` trong `ci` chạy `terraform fmt -check -recursive infra/terraform`, rồi với từng thư mục `terraform init -backend=false`, `terraform validate`, `terraform test` (provider giả, không gọi Azure), rồi `python -m pytest tests/scripts -q`. Các task sau chỉ cần thêm tệp, job tự chạy.

- [ ] Step 1: Cài Terraform và ghi phiên bản

Run: `winget install --id Hashicorp.Terraform -e` rồi mở shell mới, `terraform version`.
Expected: in ra `Terraform v1.<x>.<y>` với `x` từ 7 trở lên (cần `mock_provider` cho `terraform test`). Ghi đúng số đó vào `docs/versions.md` cùng mọi phiên bản ở mục Tech Stack. Trong `ci`, `hashicorp/setup-terraform@v3` dùng đúng số này. Cài thêm Velero CLI v1.18.4 (tệp `velero-v1.18.4-windows-amd64.tar.gz` từ trang release của `vmware-tanzu/velero`) vào `~/bin`, `velero version --client-only` in `v1.18.4`.

- [ ] Step 2: `.gitignore`, `scripts/requirements.txt` (`azure-storage-blob==12.*`, `pytest==8.*`), `conftest.py` thêm thư mục gốc kho vào `sys.path` để test nhập được `scripts.dr`

- [ ] Step 3: Thêm job `infra` vào `.github/workflows/ci.yml`, chạy trên `ubuntu-latest`, Python 3.12, cài `scripts/requirements.txt`. Job phải xanh khi `infra/terraform/*` chưa có tệp `.tf` nào (bỏ qua thư mục rỗng) và khi `tests/scripts` chỉ có `conftest.py`.

- [ ] Step 4: Sửa thiết kế: `thiet-ke.md` mục 3 dòng "Ảnh" RPO 15 phút thành 5 phút, câu "Ảnh: Azure tự chép, không cam kết độ trễ, nên phải đo" thêm "đo 24/10: p95 129 s"; mục 9 đổi `docs/phien-ban.md` thành `docs/versions.md`, và hai tên workflow kèm tên tệp tiếng Anh. `thiet-ke-web.md` mục 2: "`ravif` để ghi ảnh nhỏ dạng AVIF" thành "`webp` để ghi ảnh nhỏ dạng WebP (AVIF đo p95 1340 ms trên B2als v2, vượt 500 ms)"; mục 7 dòng AVIF ghi kết quả.

- [ ] Step 5: Kiểm tra

Run: `git push` nhánh rồi xem `ci` trên PR.
Expected: job `infra` xanh, job `api` và `web` không đổi.

- [ ] Step 6: Commit

```bash
git add .gitignore .github/workflows/ci.yml docs/versions.md docs/thiet-ke.md docs/thiet-ke-web.md scripts/requirements.txt scripts/dr/__init__.py tests/scripts/conftest.py
git commit -m "Hạ tầng: công cụ, kiểm tra Terraform trong ci, sửa thiết kế theo buổi chạy thử"
```

---

### Task 2: Khởi tạo ngoài Terraform: provider và tài khoản state

**Files:**
- Create: `scripts/azure/env.sh`, `infra/bootstrap/bootstrap.sh`

**Interfaces:**
- Produces: `scripts/azure/env.sh` export `SFX`, `RG_PRIMARY=rg-dr-primary`, `RG_STANDBY=rg-dr-standby`, `RG_BACKUP=rg-dr-backup`, `CLUSTER_REGION=koreacentral`, `STORAGE_REGION=japanwest`, tên sáu tài khoản lưu trữ theo bảng trên (`STATE_ACCOUNT`, `BACKUP_ACCOUNT`, `IMAGE_COPY_ACCOUNT`, `VAULT_ACCOUNT`, `IMAGE_PRIMARY_ACCOUNT`, `IMAGE_STANDBY_ACCOUNT`), `PRIVATE_DIR=~/.dr`, `SSH_KEY=~/.dr/ssh_ed25519`, `REPO_ROOT`, `DATA_DIR=$REPO_ROOT/data/azure`, và hàm `tf_init <dir> <state-key>` chạy `terraform -chdir=<dir> init -reconfigure` với `-backend-config` cho `resource_group_name`, `storage_account_name`, `container_name=tfstate`, `key`. Sinh `~/.dr/suffix` và khóa SSH nếu chưa có (như `scripts/trial/env.sh`).

- [ ] Step 1: Viết `bootstrap.sh`, làm theo thứ tự, mỗi bước bỏ qua nếu đã xong:
  1. Với từng provider ở Global Constraints: đọc `registrationState`, khác `Registered` thì `az provider register -n <p> --wait`.
  2. `az group create -n rg-dr-backup -l japanwest`.
  3. Tài khoản `$STATE_ACCOUNT`: `Standard_LRS`, `StorageV2`, TLS 1.2, cấm truy cập công khai, bật lưu phiên bản blob và xóa mềm 7 ngày (state hỏng thì lấy lại bản cũ). Container `tfstate`.
  4. Gắn khóa `CanNotDelete` tên `protect-state` lên tài khoản state.

- [ ] Step 2: Chạy (tạo tài nguyên Azure)

Run: `bash infra/bootstrap/bootstrap.sh && bash infra/bootstrap/bootstrap.sh`
Expected: lần hai không tạo gì mới và thoát 0. `az provider show -n Microsoft.DevTestLab --query registrationState -o tsv` in `Registered`. `az storage account show -g rg-dr-backup -n $STATE_ACCOUNT --query provisioningState -o tsv` in `Succeeded`.

- [ ] Step 3: Commit

```bash
git add scripts/azure/env.sh infra/bootstrap/bootstrap.sh
git commit -m "Hạ tầng: script khởi tạo provider và kho Terraform state"
```

---

### Task 3: Terraform `storage`: nhóm tài nguyên, kho lưu trữ, object replication, két, ngân sách

**Files:**
- Create: `infra/terraform/storage/versions.tf`, `variables.tf`, `main.tf`, `replication.tf`, `outputs.tf`, `terraform.tfvars.example`, `.terraform.lock.hcl`

**Interfaces:**
- Consumes: `tf_init`, tên tài khoản trong `env.sh` (Task 2).
- Produces (output): `backup_account`, `image_copy_account`, `vault_account`, `image_primary_account`, `image_standby_account`, `resource_group_primary`, `resource_group_standby`. Biến: `suffix` (string, bắt buộc), `cluster_region` (mặc định `koreacentral`), `storage_region` (mặc định `japanwest`), `budget_amount` (mặc định 25), `budget_email` (bắt buộc), `vault_locked` (bool, mặc định `false`).

- [ ] Step 1: `versions.tf`: `required_version = "~> 1.<x>"` theo Task 1, `azurerm` `~> 4.0`, backend `azurerm` để trống (điền bằng `-backend-config`), `provider "azurerm" { features {}; resource_provider_registrations = "none" }` (provider đã đăng ký ở Task 2, không để Terraform tự đăng ký cả loạt).

- [ ] Step 2: `main.tf`:
  - `azurerm_resource_group` cho `rg-dr-primary` và `rg-dr-standby` ở `cluster_region`; `rg-dr-backup` là `data`, vì bootstrap đã tạo.
  - Năm tài khoản (`azurerm_storage_account`), cùng thiết lập như tài khoản state, mỗi tài khoản một container như bảng tên. `shared_access_key_enabled = true` (Velero cần khóa tài khoản).
  - Kho ảnh chính và kho ảnh dự phòng: bật `versioning_enabled` và `change_feed_enabled` (nguồn của object replication). Bản chép ảnh: bật `versioning_enabled`, và `azurerm_storage_management_policy` xóa phiên bản cũ sau 7 ngày. Kho sao lưu không bật lưu phiên bản (mục 1 thiết kế).
  - Két: `azurerm_storage_container_immutability_policy` trên container `vault`, `immutability_period_in_days = 7`, `locked = var.vault_locked`, `protected_append_writes_enabled = false`.
  - `azurerm_consumption_budget_subscription` tên `dr-budget`, lọc theo ba nhóm `rg-dr-*`, ba cảnh báo `Actual` ở 50, 80, 100.

- [ ] Step 3: `replication.tf`: hai `azurerm_storage_object_replication`, nguồn đều là kho ảnh chính, container `images`: một tới bản chép ảnh ở Nhật, một tới kho ảnh dự phòng (thiết kế mục 6.1: một nguồn chép được tới hai đích). `copy_blobs_created_after = "Everything"`.

- [ ] Step 4: Test Terraform không tốn tiền (`infra/terraform/storage/tests/storage.tftest.hcl`, `mock_provider "azurerm" {}`, `command = plan`, biến `suffix = "abc123"`, `budget_email = "x@example.com"`). Các `run`:
  - `vault_is_worm_7_days`: `azurerm_storage_container_immutability_policy.vault.immutability_period_in_days == 7` và `locked == false`.
  - `image_accounts_versioned`: kho ảnh chính, kho dự phòng, bản chép đều `blob_properties[0].versioning_enabled == true`; kho sao lưu `false`.
  - `replication_two_destinations`: đúng hai `azurerm_storage_object_replication`, cùng nguồn.
  - `names_fit_storage_rules`: mọi tên tài khoản dài từ 3 tới 24 ký tự, chỉ chữ thường và số (`can(regex("^[a-z0-9]{3,24}$", ...))`).
  - `budget_alerts`: ba `notification` với ngưỡng 50, 80, 100.

Run: `terraform -chdir=infra/terraform/storage fmt -check && terraform -chdir=infra/terraform/storage init -backend=false && terraform -chdir=infra/terraform/storage validate && terraform -chdir=infra/terraform/storage test`
Expected: viết test trước thì `test` FAIL; viết xong `main.tf`, `replication.tf` thì `Success! 5 passed, 0 failed.`

- [ ] Step 5: Dựng (tạo tài nguyên Azure)

Run: `source scripts/azure/env.sh && tf_init infra/terraform/storage storage.tfstate && terraform -chdir=infra/terraform/storage apply -var suffix=$SFX -var budget_email=qivarnq3g@gmail.com`
Expected: `Apply complete!`, rồi `terraform plan` lần nữa in `No changes.` Kiểm tra replication: `az storage account or-policy list -g rg-dr-primary -n $IMAGE_PRIMARY_ACCOUNT --query "length(@)"` in `2`. Thử chép: tải một ảnh 200 KB vào `images` của kho chính, chờ tối đa 5 phút, `az storage blob exists` trên bản chép và kho dự phòng đều `true`.

- [ ] Step 6: Thử két từ chối xóa (D6 rút gọn)

Run: tải `probe.txt` vào container `vault`, rồi `az storage blob delete` bằng khóa tài khoản.
Expected: lỗi có mã `BlobImmutableDueToPolicy`. Ghi nguyên văn vào `data/azure/vault-probe.txt`.

- [ ] Step 7: Commit (gồm `.terraform.lock.hcl`, không gồm `.terraform/`)

```bash
git add infra/terraform/storage
git commit -m "Hạ tầng: Terraform cho kho lưu trữ, chép ảnh, két và ngân sách"
```

---

### Task 4: Terraform `cluster`: một máy ảo k3s

**Files:**
- Create: `infra/terraform/cluster/versions.tf`, `variables.tf`, `main.tf`, `outputs.tf`, `cloud-init.yaml.tftpl`, `.terraform.lock.hcl`

**Interfaces:**
- Consumes: `rg-dr-primary`, `rg-dr-standby` (Task 3, đọc bằng `data`).
- Produces: biến `cluster` (chỉ nhận `primary` hoặc `standby`, có `validation`), `suffix`, `vm_size` (mặc định `Standard_B2als_v2`), `cluster_region` (mặc định `koreacentral`), `admin_cidrs` (list, bắt buộc), `ssh_public_key` (string), `k3s_version` (mặc định `v1.37.1+k3s1`), `auto_shutdown_time` (mặc định `"2300"`), `auto_shutdown_timezone` (mặc định `"SE Asia Standard Time"`). Output: `public_ip`, `fqdn`, `vm_name`, `resource_group`.

- [ ] Step 1: `cloud-init.yaml.tftpl` lấy từ `infra/trial/cloud-init-k3s.yaml.tpl`, thay `__FQDN__` bằng `${fqdn}`, phiên bản bằng `${k3s_version}`, thêm `--tls-san=${public_ip}`.

- [ ] Step 2: `main.tf` cho máy `vm-dr-${var.cluster}` trong `rg-dr-${var.cluster}`: VNet `10.${cluster == "primary" ? 10 : 20}.0.0/16` và một subnet; IP công khai `Standard`, `Static`, `domain_name_label = "dr-${cluster}-${suffix}"`; NSG với hai luật như `scripts/trial/create-cluster.sh` (22 và 6443 chỉ từ `admin_cidrs`, 80 và 443 từ `Internet`); `azurerm_linux_virtual_machine` Ubuntu 24.04 (`Canonical` `ubuntu-24_04-lts` `server`), người dùng `dr`, chỉ đăng nhập bằng khóa, `custom_data = base64encode(templatefile(...))`, ổ `Premium_LRS` 32 GB; `azurerm_dev_test_global_vm_shutdown_schedule` theo giờ trong biến, không gửi thông báo.

- [ ] Step 3: Test Terraform không tốn tiền (`infra/terraform/cluster/tests/cluster.tftest.hcl`, `mock_provider "azurerm" {}`, `command = plan`, biến `suffix = "abc123"`, `admin_cidrs = ["1.2.3.4/32"]`, `ssh_public_key = "ssh-ed25519 AAAA test"`). Các `run`:
  - `rejects_unknown_cluster`: `cluster = "backup"`, `expect_failures = [var.cluster]`.
  - `primary_defaults`: `cluster = "primary"`; máy `size == "Standard_B2als_v2"`, ổ `disk_size_gb == 32` và `storage_account_type == "Premium_LRS"`, `disable_password_authentication == true`, `resource_group_name == "rg-dr-primary"`.
  - `admin_ports_only_from_admin_cidrs`: luật có cổng 22 và 6443 có `source_address_prefixes == ["1.2.3.4/32"]`; luật 80, 443 có nguồn `Internet`.
  - `auto_shutdown_at_23`: `daily_recurrence_time == "2300"`, `timezone == "SE Asia Standard Time"`, `enabled == true`.
  - `cloud_init_pins_k3s`: `strcontains(base64decode(azurerm_linux_virtual_machine.k3s.custom_data), "v1.37.1+k3s1")`.

Run: `terraform -chdir=infra/terraform/cluster init -backend=false && terraform -chdir=infra/terraform/cluster validate && terraform -chdir=infra/terraform/cluster test`
Expected: trước khi viết `main.tf` thì FAIL; sau đó `Success! 5 passed, 0 failed.`

- [ ] Step 4: Dựng cụm chính và đo (tạo tài nguyên Azure)

Run: `tf_init infra/terraform/cluster cluster-primary.tfstate`, rồi `terraform apply` với `cluster=primary`, `admin_cidrs=["$(curl -s https://api.ipify.org)/32"]`, `ssh_public_key="$(cat ~/.dr/ssh_ed25519.pub)"`. Lấy kubeconfig như `create-cluster.sh` vào `~/.dr/kubeconfig-primary`, ghi các mốc `start`, `vm_created`, `k3s_installed`, `node_ready`, `traefik_ready` vào `data/azure/cluster-build.csv` (cột `cluster,mark,time_utc`).
Expected: `kubectl get nodes` một nút `Ready`; tổng thời gian cỡ 2 phút 15 giây như buổi thử. `az resource list -g rg-dr-primary --resource-type Microsoft.DevTestLab/schedules --query "[0].name" -o tsv` in `shutdown-computevm-vm-dr-primary`.

- [ ] Step 5: Commit

```bash
git add infra/terraform/cluster
git commit -m "Hạ tầng: Terraform cho máy ảo k3s, có lịch tự tắt"
```

---

### Task 5: Mã SAS theo quyền tối thiểu và secret trên GitHub

**Files:**
- Create: `scripts/azure/issue-sas.sh`, `scripts/dr/session_state.py`, `tests/scripts/test_session_state.py`

**Interfaces:**
- Consumes: tên tài khoản (Task 2), container (Task 3).
- Produces:
  - `session_state.py`: `@dataclass Session` với đúng các trường của `status/session.json`; `read_session(client: ContainerClient) -> Session | None`; `write_session(client: ContainerClient, s: Session) -> None`; `read_sas_expiry(client) -> dict[str, datetime]`; `merge_sas_expiry(client, name: str, expiry: datetime) -> None`. Dòng lệnh: `python -m scripts.dr.session_state get <field>`, `set <field>=<value>...`, `sas-expiry <name> <iso>`; xác thực bằng biến `BACKUP_ACCOUNT` và `BACKUP_ACCOUNT_KEY`.
  - `issue-sas.sh <name>` cấp một mã SAS cấp container, hạn 30 ngày, chỉ HTTPS, ghi vào `~/.dr/sas-<name>.txt` và `status/sas-expiry.json`, và với mã dùng trên GitHub thì `gh secret set`. Bảng mã:

| `name` | Tài khoản / container | Quyền | Dùng ở | Secret GitHub |
|---|---|---|---|---|
| `api-images-primary` | kho ảnh chính / `images` | `racwl` | API ở cụm chính | |
| `cnpg-backup` | kho sao lưu / `cnpg` | `racwdl` (Barman cần xóa để giữ 7 ngày) | CNPG | |
| `check-read` | kho sao lưu / `cnpg`, `velero`, `status`; kho ảnh chính và bản chép / `images` | `rl` | `backup-check` | `BACKUP_CHECK_SAS_JSON` (một JSON `{container_url: sas}`) |
| `drill-read` | kho sao lưu / `cnpg`, `velero`, `status`; bản chép / `images` | `rl` | `daily-drill` | `DRILL_READ_SAS_JSON` |

  Velero dùng khóa tài khoản kho sao lưu, như buổi thử (cách duy nhất đã kiểm); lệch với bảng quyền tối thiểu ở mục 4.4 thiết kế, ghi vào phần rủi ro của báo cáo.

- [ ] Step 1: Test trước (`tests/scripts/test_session_state.py`, dùng một `ContainerClient` giả lưu blob trong `dict`)

```python
def test_session_round_trip(fake_container):
    s = Session(state="running", cluster="primary", server_name="primary-202610271405",
                started_at="2026-10-27T14:05:12Z")
    write_session(fake_container, s)
    assert read_session(fake_container) == s

def test_missing_session_is_none(fake_container):
    assert read_session(fake_container) is None

def test_sas_expiry_merge_keeps_other_names(fake_container):
    merge_sas_expiry(fake_container, "cnpg-backup", datetime(2026, 11, 26, tzinfo=UTC))
    merge_sas_expiry(fake_container, "check-read", datetime(2026, 11, 27, tzinfo=UTC))
    assert set(read_sas_expiry(fake_container)) == {"cnpg-backup", "check-read"}

def test_rejects_unknown_state(fake_container):
    with pytest.raises(ValueError):
        Session(state="paused", cluster="primary", server_name="x", started_at="x")
```

- [ ] Step 2: `python -m pytest tests/scripts/test_session_state.py -q` báo FAIL vì chưa có module.

- [ ] Step 3: Viết `session_state.py` và `issue-sas.sh`. SAS sinh bằng `az storage container generate-sas --auth-mode key --https-only --expiry`; khóa đọc từ `~/.dr/key-<account>` (lấy bằng `az storage account keys list` nếu chưa có).

- [ ] Step 4: test PASS.

- [ ] Step 5: Cấp mã thật (tạo tài nguyên Azure: chỉ ghi blob)

Run: `for n in api-images-primary cnpg-backup check-read drill-read; do bash scripts/azure/issue-sas.sh $n; done && gh secret list`
Expected: `gh secret list` có `BACKUP_CHECK_SAS_JSON`, `DRILL_READ_SAS_JSON`; `python -m scripts.dr.session_state` đọc `status/sas-expiry.json` có đủ bốn tên. Thử quyền: dùng `sas-check-read` để `az storage blob upload` vào `status` thì bị `AuthorizationPermissionMismatch`.

- [ ] Step 6: Commit

```bash
git add scripts/azure/issue-sas.sh scripts/dr/session_state.py tests/scripts/test_session_state.py
git commit -m "Hạ tầng: mã SAS quyền tối thiểu và tệp trạng thái phiên"
```

---

### Task 6: Cài phần mềm sao lưu vào cụm và tạo cơ sở dữ liệu

**Files:**
- Create: `scripts/azure/install-software.sh`, `infra/k8s/values/velero.yaml.tpl`, `infra/k8s/platform/object-store.yaml.tpl`, `infra/k8s/platform/db-new.yaml.tpl`, `infra/k8s/platform/db-recover.yaml.tpl`, `infra/k8s/platform/scheduled-backup.yaml`, `infra/k8s/platform/velero-schedule.yaml`

**Interfaces:**
- Consumes: kubeconfig `~/.dr/kubeconfig-<cluster>` (Task 4), `sas-cnpg-backup.txt` (Task 5), `session_state` (Task 5).
- Produces: `install-software.sh <cluster> <server_name> [<recover_from_server>]`. Sau khi chạy: Helm release `cert-manager`, `cnpg`, `velero`; Deployment `barman-cloud` trong `cnpg-system`; ObjectStore `japan-store` và Cluster `db` (1 bản, 5 Gi, Postgres 18, `archive_timeout: "60s"`, `serverName: <server_name>`) trong `dr-api`; Secret `db-app` do CNPG tạo (khóa `uri`); ScheduledBackup `db-every-6h` (`schedule: "0 0 */6 * * *"`, `method: plugin`); Velero Schedule `hourly` (`0 * * * *`, TTL `72h0m0s`, `includedNamespaces: [dr-api, cert-manager]`, loại trừ `clusters.postgresql.cnpg.io`, `backups.postgresql.cnpg.io`, `persistentvolumeclaims`, `persistentvolumes`, `pods`).

- [ ] Step 1: Mẫu cấu hình chép từ `infra/trial/` và sửa:
  - `object-store.yaml.tpl`: `azureCredentials.storageSasToken` đọc Secret `japan-store-sas` (khóa `SAS`) thay cho khóa tài khoản; `retentionPolicy: "7d"`; `wal.compression: gzip`; `data.compression: gzip`.
  - `db-new.yaml.tpl`: `bootstrap.initdb` với cơ sở dữ liệu `dr`, chủ `dr`.
  - `db-recover.yaml.tpl`: `bootstrap.recovery.source: previous` với `externalClusters[0]` dùng plugin Barman, `barmanObjectName: japan-store`, `serverName: <recover_from_server>`. Plugin WAL archiver vẫn ghi vào `<server_name>` mới.
  - `velero.yaml.tpl`: như `infra/trial/velero-values.yaml.tpl`, `resourceGroup: rg-dr-backup`.

- [ ] Step 2: Viết `install-software.sh` theo `scripts/trial/install-software.sh` (thứ tự cert-manager, CNPG, Barman, Velero, có `--wait`), cộng: tạo namespace `dr-api`, Secret `japan-store-sas`, áp `db-recover` khi có đối số thứ ba, ngược lại `db-new`; chờ `kubectl -n dr-api wait --for=condition=Ready clusters.postgresql.cnpg.io/db --timeout=900s`; áp ScheduledBackup và Velero Schedule. Ghi mốc vào `data/azure/install.csv`.

- [ ] Step 3: Chạy trên cụm chính (tạo tài nguyên Azure)

Run: `bash scripts/azure/install-software.sh primary primary-$(date -u +%Y%m%d%H%M)`
Expected: `kubectl -n velero get backupstoragelocations.velero.io default -o jsonpath='{.status.phase}'` in `Available`. Sau 2 phút, `az storage blob list ... -c cnpg --prefix <server_name>/wals/ --query "length(@)"` lớn hơn 0.

- [ ] Step 4: Thử khôi phục sang `serverName` mới

Run: `kubectl -n dr-api delete clusters.postgresql.cnpg.io/db`, tạo một bản đầy đủ trước đó bằng `kubectl apply` một `backups.postgresql.cnpg.io/manual-1` (`method: plugin`) và chờ `completed`; rồi chạy lại `install-software.sh primary primary-<giờ mới> primary-<giờ cũ>`.
Expected: Cluster `Ready`; bảng `posts` có đủ số dòng đã chèn thử trước khi xóa; WAL mới nằm dưới `<giờ mới>/wals/`, thư mục `<giờ cũ>/` không có tệp nào mới hơn lúc xóa.

- [ ] Step 5: Commit

```bash
git add scripts/azure/install-software.sh infra/k8s/values infra/k8s/platform
git commit -m "Hạ tầng: cài CNPG, Barman, Velero, cert-manager và lịch sao lưu"
```

---

### Task 7: Ảnh nhỏ WebP thay cho AVIF

**Files:**
- Modify: `app/api/Cargo.toml` (bỏ `ravif`, bỏ `ravif/asm` khỏi feature `production`, thêm `webp = "0.3"` hoặc bản 0.x mới nhất có `Encoder::from_rgba(...).encode(quality)`; ghi bản cụ thể vào `docs/versions.md`), `app/api/src/thumbnail.rs`, `app/api/src/image_store.rs:75`, `app/api/src/routes/posts.rs:106`, `app/api/tests/http.rs:61-71`, `app/api/tests/read_only.rs:23`, `app/api/examples/bench-thumbnail.rs`, `app/api/Dockerfile` (bỏ `nasm` nếu không còn cần), `app/api/openapi.json`, `app/web/src/lib/api/schema.d.ts` (sinh lại)

**Interfaces:**
- Produces: `make_thumbnail(original: &[u8], kind: ImageType) -> anyhow::Result<Vec<u8>>` trả WebP có mất mát, chất lượng 75; khóa blob `thumbnail/{id}.webp`; `content_type` `"image/webp"`. Hàm `avif(data)` đổi tên thành `webp(data)`. Ảnh nhỏ AVIF cũ trong kho không cần chuyển: cụm thật chưa có bài nào.

- [ ] Step 1: Sửa test trước: `produces_avif` thành `produces_webp` với `assert_eq!(&out[0..4], b"RIFF"); assert_eq!(&out[8..12], b"WEBP");`; `thumbnail_is_avif_for_large_and_original_for_small` thành `thumbnail_is_webp_...` với `content-type` `image/webp`; `read_only.rs` cũng vậy; test ở `thumbnail.rs:306` cũng vậy. Thêm `webp_thumbnail_is_smaller_than_original` cho ảnh JPEG 2560x1920 của test: kết quả nhỏ hơn 25% cỡ ảnh gốc (chặn lỡ tay dùng WebP không mất mát).

- [ ] Step 2: `cargo test --all-targets` (cần `app/dev/setup.sh` như `ci`) báo FAIL ở các test trên.

- [ ] Step 3: Sửa code theo Interfaces.

- [ ] Step 4: Kiểm tra

Run: `cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test --all-targets && cargo run --quiet -- --print-openapi > openapi.json`, rồi trong `app/web`: `npm run gen-types`.
Expected: test PASS; `git diff` của `openapi.json` chỉ đổi chữ AVIF thành WebP.

- [ ] Step 5: Đo trên B2als v2 khi cụm chính đang chạy (Task 4)

Run: build `bench-thumbnail` bằng lệnh Docker musl ở Task 10 của kế hoạch chạy thử (có `MSYS_NO_PATHCONV=1`), `scp` lên `vm-dr-primary`, chạy `./bench-thumbnail 50`.
Expected: p95 không quá 500 ms. Ghi trung vị, p95 và số tín dụng CPU còn lại vào dòng 11 của `docs/trial-results.md` (thêm "Đo lại với WebP").

- [ ] Step 6: Commit

```bash
git add app/api app/web/src/lib/api/schema.d.ts docs/versions.md docs/trial-results.md
git commit -m "API: ảnh nhỏ WebP thay cho AVIF (AVIF p95 1340 ms trên B2als v2)"
```

---

### Task 8: Chạy API trên cụm chính

**Files:**
- Create: `infra/k8s/api/kustomization.yaml`, `deployment.yaml`, `service.yaml`, `ingress.yaml`, `certificate.yaml`, `infra/k8s/platform/cluster-issuers.yaml`, `scripts/azure/deploy-api.sh`

**Interfaces:**
- Consumes: Secret `db-app` (Task 6), `sas-api-images-primary.txt` (Task 5), image `ghcr.io/qivarnq3g/dr-api:<sha>` do `ci` đẩy khi merge vào `main` (cần Task 7 đã merge).
- Produces: `deploy-api.sh <cluster> <image_tag>`. Deployment `api` (1 bản) trong `dr-api`, Service `api` cổng 80 tới 8080, Ingress `api` host `api.dr.qivarn.id.vn` dùng TLS Secret `api-tls` (không có chú thích `cert-manager.io/cluster-issuer`, để cert-manager không tự sinh Certificate thứ hai); Certificate `api-tls` riêng ở `certificate.yaml`, `issuerRef` `letsencrypt-production`, nhãn `app.kubernetes.io/part-of: dr-api-tls` trên chính nó và trên Secret (`spec.secretTemplate.labels`). ClusterIssuer `letsencrypt-staging` và `letsencrypt-production` (HTTP-01 qua Traefik).
- Biến môi trường của API (đúng tên trong `app/api/src/config.rs`): `DATABASE_URL` từ `db-app`/`uri`; `IMAGE_STORE=azure`; `IMAGE_STORE_CONTAINER=images`; `AZURE_STORAGE_ACCOUNT_NAME` và `AZURE_STORAGE_SAS_KEY` từ Secret `image-store`; `SECRET_CODE` từ Secret `api-secret-code` (đọc `~/.dr/secret-code`, ít nhất 16 ký tự); `CLUSTER=<cluster>`; `REGION=koreacentral`; `TRUSTED_PROXIES=10.42.0.0/16` (dải pod của k3s, nơi Traefik chạy); `CORS_ORIGINS` để mặc định. `readinessProbe` và `livenessProbe` là `GET /healthz`. `imagePullSecrets: [ghcr-pull]` tạo từ `~/.dr/ghcr-token` (mã GitHub cổ điển chỉ có `read:packages`, Quang tạo).

- [ ] Step 1: Manifest Kustomize và hai ClusterIssuer theo Interfaces. `kubectl kustomize infra/k8s/api` chạy được mà không cần cụm.

- [ ] Step 2: Viết `deploy-api.sh`, thứ tự cố định:
  1. Tạo hoặc cập nhật Secret `image-store`, `api-secret-code`, `ghcr-pull` (bằng `kubectl create secret ... --dry-run=client -o yaml | kubectl apply -f -`).
  2. Áp ClusterIssuer.
  3. Nếu `velero backup get` có bản `Completed` mới nhất: `velero restore create --from-backup <tên> --include-resources secrets,certificates.cert-manager.io --selector app.kubernetes.io/part-of=dr-api-tls --wait` (Secret và Certificate `api-tls` mang nhãn này, xem `certificate.yaml`), chờ `restores.velero.io/<tên>` `Completed`.
  4. `kubectl apply -k infra/k8s/api` với `kustomize edit set image` theo `<image_tag>`.
  5. `kubectl -n dr-api rollout status deploy/api --timeout=300s`.
  Không đổi DNS ở đây; chứng chỉ chỉ cấp được sau khi Task 9 trỏ DNS.

- [ ] Step 3: Chạy lần đầu (tạo tài nguyên Azure)

Run: `bash scripts/azure/deploy-api.sh primary <sha>`; rồi `curl -fsS --resolve api.dr.qivarn.id.vn:80:<public_ip> http://api.dr.qivarn.id.vn/healthz`.
Expected: JSON có `"cluster":"primary"` và trạng thái 200.

- [ ] Step 4: Thử dựng lại không xin chứng chỉ mới (sau Task 9 đã trỏ DNS và chứng chỉ đã `Ready`)

Run: chờ một bản Velero `hourly` (hoặc `velero backup create pre-redeploy --from-schedule hourly --wait`), `kubectl delete namespace dr-api`, rồi `install-software.sh` phần cơ sở dữ liệu và `deploy-api.sh` lại.
Expected: serial chứng chỉ (`kubectl -n dr-api get secret api-tls -o jsonpath='{.data.tls\.crt}' | base64 -d | openssl x509 -noout -serial`) giống trước khi xóa; `kubectl -n dr-api get certificaterequests.cert-manager.io` chỉ có bản do Velero khôi phục.

- [ ] Step 5: Commit

```bash
git add infra/k8s/api infra/k8s/platform/cluster-issuers.yaml scripts/azure/deploy-api.sh
git commit -m "Hạ tầng: triển khai API trên cụm chính, khôi phục chứng chỉ bằng Velero"
```

---

### Task 9: Đổi bản ghi DNS của API qua Cloudflare

**Files:**
- Create: `scripts/dr/dns_switch.py`, `tests/scripts/test_dns_switch.py`

**Interfaces:**
- Produces:
  - `class CloudflareDns(token: str, zone_id: str, http: Callable[[Request], tuple[int, dict]] = urlopen_json)` với `get_a_record(name: str) -> dict` (trả `{"id", "content", "ttl", "proxied"}`, lỗi nếu không có hoặc có hơn một bản ghi A) và `set_a_record(record_id: str, ip: str) -> None` (PATCH `content=ip`, `ttl=60`, `proxied=false`). Chỉ dùng thư viện chuẩn (`urllib.request`), endpoint `https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records`.
  - `switch(dns: CloudflareDns, name: str, ip: str, health: Callable[[str, str], bool], resolve: Callable[[str], set[str]], timeout_s: int = 300) -> SwitchResult` với `SwitchResult(changed: bool, started_at: datetime, record_updated_at: datetime, resolved_at: datetime | None)`. Thứ tự: `health(name, ip)` phải `True` (gọi `https://{ip}/healthz` với SNI và Host là `name`, chấp nhận chứng chỉ staging khi có `--insecure`), không thì `HealthCheckFailed`; nếu bản ghi đã là `ip` thì `changed=False`; ngược lại PATCH rồi chờ `resolve(name)` (hỏi DoH `https://cloudflare-dns.com/dns-query` và `https://dns.google/resolve`) trả đúng `{ip}`.
  - Dòng lệnh: `python -m scripts.dr.dns_switch <ip> [--name api.dr.qivarn.id.vn] [--insecure] [--csv data/azure/dns-switch.csv]`; mã lấy từ biến `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ZONE_ID`, không có thì đọc `~/.dr/cloudflare-token`, `~/.dr/cloudflare-zone-id`. Ghi một dòng CSV `started_at,record_updated_at,resolved_at,old_ip,new_ip` (bước 6 của mục 5.2 thiết kế). Không bao giờ in mã.

- [ ] Step 1: Test trước (giả `http`, `health`, `resolve`)

```python
def test_refuses_when_target_not_healthy(fake_dns):
    with pytest.raises(HealthCheckFailed):
        switch(fake_dns, NAME, "20.0.0.2", health=lambda n, ip: False, resolve=lambda n: set())
    assert fake_dns.patches == []

def test_noop_when_record_already_points_to_ip(fake_dns):  # bản ghi đang là 20.0.0.1
    r = switch(fake_dns, NAME, "20.0.0.1", health=ok, resolve=lambda n: {"20.0.0.1"})
    assert r.changed is False and fake_dns.patches == []

def test_patches_content_ttl_and_proxy_off(fake_dns):
    switch(fake_dns, NAME, "20.0.0.2", health=ok, resolve=lambda n: {"20.0.0.2"})
    assert fake_dns.patches == [{"content": "20.0.0.2", "ttl": 60, "proxied": False}]

def test_times_out_if_resolvers_never_agree(fake_dns):
    r = switch(fake_dns, NAME, "20.0.0.2", health=ok, resolve=lambda n: {"20.0.0.1"}, timeout_s=0)
    assert r.changed is True and r.resolved_at is None

def test_rejects_non_ipv4(fake_dns):
    with pytest.raises(ValueError):
        switch(fake_dns, NAME, "dr-primary.koreacentral.cloudapp.azure.com", health=ok, resolve=lambda n: set())

def test_two_a_records_is_an_error(fake_dns_two_records):
    with pytest.raises(LookupError):
        fake_dns_two_records.get_a_record(NAME)

def test_token_never_printed(capsys, fake_dns):
    switch(fake_dns, NAME, "20.0.0.2", health=ok, resolve=lambda n: {"20.0.0.2"})
    assert fake_dns.token not in capsys.readouterr().out
```

Khi `resolved_at is None`, dòng lệnh thoát mã 2 (bản ghi đã đổi nhưng chưa thấy lan ra) để runbook biết mà chờ thêm.

- [ ] Step 2: test FAIL. Step 3: viết `dns_switch.py`. Step 4: test PASS.

- [ ] Step 5: Mã Cloudflare (Quang làm trên trang Cloudflare)

Quang tạo API token mẫu "Edit zone DNS", chỉ vùng `qivarn.id.vn`, lưu vào trình quản lý mật khẩu, rồi `~/.dr/cloudflare-token` và `~/.dr/cloudflare-zone-id`, và `gh secret set CLOUDFLARE_API_TOKEN < ~/.dr/cloudflare-token`, `gh secret set CLOUDFLARE_ZONE_ID < ~/.dr/cloudflare-zone-id`. Nếu chưa có bản ghi A `api.dr` thì tạo một bản trỏ tạm vào IP cụm chính, proxy tắt, TTL 60.

- [ ] Step 6: Trỏ API vào cụm chính thật

Run: `python -m scripts.dr.dns_switch <public_ip của cụm chính> --insecure --csv data/azure/dns-switch.csv` (lần đầu chứng chỉ chưa có nên cần `--insecure`), rồi chờ `kubectl -n dr-api wait --for=condition=Ready certificates.cert-manager.io/api-tls --timeout=600s`, rồi `curl -fsS https://api.dr.qivarn.id.vn/healthz`.
Expected: 200, `"cluster":"primary"`. Lệnh thoát 0, CSV có một dòng.

- [ ] Step 7: Commit

```bash
git add scripts/dr/dns_switch.py tests/scripts/test_dns_switch.py data/azure/dns-switch.csv
git commit -m "DR: đổi bản ghi A của api.dr qua API Cloudflare, có kiểm tra cụm đích"
```

---

### Task 10: Vòng đời phiên: bật, nghỉ, tiếp, tắt

**Files:**
- Create: `scripts/azure/session-start.sh`, `session-pause.sh`, `session-resume.sh`, `session-stop.sh`, `scripts/azure/lib.sh`, `tests/scripts/test_session_scripts.py`

**Interfaces:**
- Consumes: mọi script ở Task 2 đến 9, `session_state` (Task 5).
- Produces:
  - `session-start.sh <cluster> <image_tag>`: dừng với mã 3 nếu `session.json` là `running` hoặc máy `vm-dr-<cluster>` đang tồn tại; dừng với mã 4 nếu đang có hai máy `vm-dr-*` (giới hạn nhân). Rồi: Terraform `cluster` apply; `install-software.sh <cluster> <cluster>-<giờ> <server_name cũ nếu có>`; `deploy-api.sh`; `dns_switch.py`; ghi `session.json` (`state=running`, `server_name` mới, `started_at`, các trường còn lại `null`). Ghi mốc vào `data/azure/session.csv`.
  - `session-pause.sh <cluster>`: `az vm deallocate`, rồi kiểm tra `az vm get-instance-view ... --query "instanceView.statuses[?starts_with(code,'PowerState/')].code" -o tsv` là `PowerState/deallocated`, khác thì thoát 1. Không đổi `session.json`. Trong lúc nghỉ không có WAL mới, nên `backup-check` sẽ báo lỗi WAL cũ: ghi rõ trong runbook là chỉ nghỉ dưới 1 giờ, lâu hơn thì `session-stop.sh`.
  - `session-resume.sh <cluster>`: `az vm start`, chờ `/healthz` trên IP của máy trả 200.
  - `session-stop.sh <cluster>` (thứ tự của mục 4.1 thiết kế, chưa có job két vì két làm ở tuần 4): bản đầy đủ `backups.postgresql.cnpg.io/stop-<giờ>` chờ `completed`; `velero backup create stop-<giờ> --from-schedule hourly --ttl 168h0m0s --wait`, chờ `backups.velero.io/stop-<giờ>` `Completed`; tính `post_count` và `content_digest` bằng `kubectl exec` vào `db-1` chạy `psql`; ghi `session.json` (`state=stopped`, `stopped_at`, `full_backup`, `velero_backup`, `post_count`, `content_digest`); `terraform destroy` stack `cluster` của `<cluster>`; kiểm tra `az vm list -g rg-dr-<cluster>` rỗng. Bất kỳ bước sao lưu nào lỗi thì dừng trước khi xóa máy, thoát 1.
  - `lib.sh`: `vm_exists <cluster>`, `vm_count`, `power_state <cluster>`, `mark <file> <cluster> <mark>`.

- [ ] Step 1: Test trước cho phần chặn (`tests/scripts/test_session_scripts.py` chạy script bằng `bash` với `PATH` trỏ tới một thư mục có `az`, `terraform`, `kubectl` giả ghi lại lệnh được gọi; `session_state` giả bằng biến môi trường `DR_FAKE_SESSION`)

```python
def test_start_refuses_when_session_running(fake_tools):
    fake_tools.session = {"state": "running", "cluster": "primary"}
    r = fake_tools.run("session-start.sh", "primary", "abc")
    assert r.returncode == 3 and "terraform" not in fake_tools.calls

def test_start_refuses_third_vm(fake_tools):
    fake_tools.vms = ["vm-dr-primary", "vm-dr-standby"]
    assert fake_tools.run("session-start.sh", "primary", "abc").returncode == 4

def test_stop_keeps_vm_when_backup_fails(fake_tools):
    fake_tools.fail_on = "backups.postgresql.cnpg.io"
    r = fake_tools.run("session-stop.sh", "primary")
    assert r.returncode == 1 and not any("destroy" in c for c in fake_tools.calls)

def test_pause_fails_if_only_stopped(fake_tools):
    fake_tools.power_state = "PowerState/stopped"
    assert fake_tools.run("session-pause.sh", "primary").returncode == 1
```

- [ ] Step 2: test FAIL. Step 3: viết bốn script và `lib.sh`. Step 4: test PASS.

- [ ] Step 5: Chạy thật một vòng (tạo tài nguyên Azure)

Run: `session-pause.sh primary`, kiểm tra `PowerState/deallocated`; `session-resume.sh primary`; đăng 20 bài thử; `session-stop.sh primary`; `session-start.sh primary <sha>`.
Expected: sau lần bật lại, `curl https://api.dr.qivarn.id.vn/v1/posts` đủ 20 bài; `session.json` có `server_name` mới; serial chứng chỉ không đổi; thời gian từng bước nằm trong `data/azure/session.csv`. Ghi tổng thời gian bật phiên vào `docs/trial-results.md` mục mới "Phiên thật đầu tiên".

- [ ] Step 6: Commit

```bash
git add scripts/azure/session-*.sh scripts/azure/lib.sh tests/scripts/test_session_scripts.py data/azure
git commit -m "Hạ tầng: script bật, nghỉ, tiếp và tắt phiên"
```

---

### Task 11: Workflow kiểm tra sao lưu mỗi giờ (`backup-check`)

**Files:**
- Create: `scripts/dr/backup_check.py`, `tests/scripts/test_backup_check.py`, `.github/workflows/backup-check.yml`

**Interfaces:**
- Consumes: `session_state` (Task 5), secret `BACKUP_CHECK_SAS_JSON` (Task 5).
- Produces:
  - `@dataclass Snapshot(session: Session | None, sas_expiry: dict[str, datetime], newest_wal: datetime | None, newest_velero: datetime | None, velero_names: set[str], full_backup_names: set[str], primary_images: dict[str, datetime], copied_images: set[str])`.
  - `evaluate(s: Snapshot, now: datetime) -> list[CheckResult]`, `CheckResult(name: str, ok: bool, detail: str)`. Tên kiểm tra cố định: `session_file`, `wal_age`, `velero_age`, `image_replication`, `sas_expiry`, `stop_backups`.
  - `collect(sas: dict[str, str]) -> Snapshot` đọc kho bằng `azure-storage-blob`: WAL mới nhất dưới `cnpg/<server_name>/wals/`, `velero/backups/*/velero-backup.json` mới nhất, tên bản đầy đủ dưới `cnpg/<server_name>/base/`.
  - Dòng lệnh: `python -m scripts.dr.backup_check --csv <file>` in bảng kết quả, thêm một dòng CSV `checked_at,state,<tên kiểm tra>...` (giá trị `ok`/`fail`/`skip`), thoát 1 nếu có `fail`.
- Ngưỡng (mục 4.5 thiết kế và quyết định 24/10): WAL cũ hơn 5 phút; Velero cũ hơn 2 giờ; ảnh trong kho chính cũ hơn 5 phút mà chưa có ở bản chép; SAS còn dưới 7 ngày. Khi `state=stopped`: chỉ `session_file`, `sas_expiry`, `stop_backups` (`full_backup` có trong `full_backup_names` và `velero_backup` có trong `velero_names`); ba kiểm tra kia là `skip`.

- [ ] Step 1: Test trước (dựng `Snapshot` bằng tay, `NOW = datetime(2026, 10, 27, 15, 0, tzinfo=UTC)`)

```python
def test_running_all_fresh_is_ok():
    assert all(r.ok for r in evaluate(running(wal=NOW - timedelta(minutes=2), velero=NOW - timedelta(minutes=50)), NOW))

def test_wal_older_than_5_minutes_fails():
    assert failed(evaluate(running(wal=NOW - timedelta(minutes=5, seconds=1)), NOW)) == {"wal_age"}

def test_velero_older_than_2_hours_fails():
    assert failed(evaluate(running(velero=NOW - timedelta(hours=2, seconds=1)), NOW)) == {"velero_age"}

def test_image_not_copied_after_5_minutes_fails():
    s = running(primary_images={"a.jpg": NOW - timedelta(minutes=6)}, copied_images=set())
    assert failed(evaluate(s, NOW)) == {"image_replication"}

def test_image_not_copied_yet_but_young_is_ok():
    s = running(primary_images={"a.jpg": NOW - timedelta(minutes=4)}, copied_images=set())
    assert failed(evaluate(s, NOW)) == set()

def test_sas_expiring_within_7_days_fails():
    assert failed(evaluate(running(sas={"check-read": NOW + timedelta(days=6, hours=23)}), NOW)) == {"sas_expiry"}

def test_empty_store_fails_not_skips():
    s = Snapshot(session=None, sas_expiry={}, newest_wal=None, newest_velero=None, velero_names=set(),
                 full_backup_names=set(), primary_images={}, copied_images=set())
    assert {"session_file", "sas_expiry"} <= failed(evaluate(s, NOW))

def test_running_without_any_wal_fails():
    assert "wal_age" in failed(evaluate(running(wal=None), NOW))

def test_stopped_checks_only_stop_backups_and_sas():
    s = stopped(full_backup="stop-202610271700", velero_backup="stop-202610271700",
                full_backup_names={"stop-202610271700"}, velero_names=set())
    results = {r.name: r for r in evaluate(s, NOW)}
    assert not results["stop_backups"].ok and results["wal_age"].detail == "skip"
```

`running(...)` và `stopped(...)` là hàm dựng trong file test, mặc định mọi thứ đều mới và SAS còn 30 ngày.

- [ ] Step 2: test FAIL. Step 3: viết `backup_check.py`. Step 4: test PASS.

- [ ] Step 5: Workflow `.github/workflows/backup-check.yml`
  - `on: schedule: [{cron: "17 * * * *"}]` và `workflow_dispatch`. `permissions: contents: write` (chỉ để ghi nhánh `ops-log`). `concurrency: backup-check`.
  - Bước: checkout; Python 3.12; cài `scripts/requirements.txt`; `python -m scripts.dr.backup_check --csv ops/data/backup-check/$(date -u +%Y-%m).csv` với `BACKUP_CHECK_SAS_JSON` từ secret; bước ghi CSV chạy `if: always()`: checkout nhánh `ops-log` vào `ops/` (tạo nhánh mồ côi nếu chưa có), commit `backup-check <giờ UTC>`, push. Thử push lại tối đa 3 lần nếu bị từ chối vì `daily-drill` cũng ghi nhánh này.
  - Lỗi kiểm tra làm job lỗi, nên GitHub gửi email cho Quang (đã kiểm 24/10). Thư chỉ tới người kích hoạt, tức tài khoản sửa cron gần nhất: luôn để Quang là người commit tệp workflow này.

- [ ] Step 6: Kiểm tra trên GitHub

Run: merge vào `main` (workflow theo lịch chỉ chạy từ nhánh mặc định), rồi `gh workflow run backup-check.yml` lúc cụm chính đang chạy và lúc phiên đã tắt.
Expected: cả hai lần xanh; nhánh `ops-log` có hai dòng CSV, lần sau có `skip` ở `wal_age`. Thử một lần đỏ: chạy khi đã `session-pause.sh` hơn 5 phút, thấy `wal_age` `fail` và có email.

- [ ] Step 7: Commit

```bash
git add scripts/dr/backup_check.py tests/scripts/test_backup_check.py .github/workflows/backup-check.yml
git commit -m "DR: workflow kiểm tra sao lưu mỗi giờ"
```

---

### Task 12: Workflow diễn tập lạnh mỗi ngày (`daily-drill`)

**Files:**
- Create: `scripts/dr/verify_restore.py`, `tests/scripts/test_verify_restore.py`, `scripts/drill/run-daily-drill.sh`, `infra/k8s/drill/kind-config.yaml`, `infra/k8s/drill/db-recover.yaml.tpl`, `infra/k8s/values/velero-drill.yaml.tpl`, `.github/workflows/daily-drill.yml`

**Interfaces:**
- Consumes: `session_state` (Task 5), secret `DRILL_READ_SAS_JSON`, Velero Schedule và ObjectStore (Task 6), `content_digest` (Task 10).
- Produces:
  - `verify_restore.py`: `compare(expected: Session, actual_count: int, actual_digest: str, image_checks: list[ImageCheck]) -> VerifyReport`, `ImageCheck(post_id: str, expected_sha256: str, actual_sha256: str | None)`, `VerifyReport(ok: bool, missing_posts: int, extra_posts: int, digest_match: bool, bad_images: list[str])`. Dòng lệnh: `python -m scripts.dr.verify_restore --api http://127.0.0.1:8080 --psql "<lệnh psql>" --sample 50` lấy 50 bài ngẫu nhiên qua `GET /v1/posts`, tải ảnh gốc, so SHA-256 với `image_sha256` trong cơ sở dữ liệu; thoát 1 nếu `ok` là `False`.
  - `run-daily-drill.sh` ghi `data/daily-drill/<yyyy-mm-dd>.csv` với cột `step,started_at,ended_at,result` cho các bước `kind_up`, `install`, `db_restore`, `velero_restore`, `api_up`, `verify`.
- Velero trong kind dùng BackupStorageLocation `accessMode: ReadOnly`; nó cần khóa tài khoản (Task 5), nên với diễn tập hằng ngày dùng một secret riêng `DRILL_VELERO_KEY`. Đây là khóa tài khoản kho sao lưu, có quyền ghi: ghi vào phần rủi ro của báo cáo cùng điểm ở Task 5. Nếu khi làm thấy plugin Azure v1.14.4 nhận SAS (`AZURE_STORAGE_SAS_TOKEN` hoặc tương đương trong tài liệu của plugin) thì dùng SAS của `drill-read` và bỏ secret này.

- [ ] Step 1: Test trước cho `compare`

```python
def test_all_match_is_ok():
    r = compare(session(post_count=1000, digest="d1"), 1000, "d1", [ImageCheck("p1", "aa", "aa")])
    assert r.ok and r.missing_posts == 0

def test_missing_posts_counted():
    r = compare(session(post_count=1000, digest="d1"), 998, "d2", [])
    assert not r.ok and r.missing_posts == 2 and not r.digest_match

def test_more_posts_than_recorded_is_not_ok():  # dữ liệu sau lúc tắt phiên không được có trong bản khôi phục lúc phiên đã tắt
    r = compare(session(post_count=10, digest="d1"), 11, "d3", [])
    assert not r.ok and r.extra_posts == 1

def test_missing_image_is_bad():
    r = compare(session(post_count=1, digest="d1"), 1, "d1", [ImageCheck("p1", "aa", None)])
    assert not r.ok and r.bad_images == ["p1"]

def test_running_session_checks_images_only():
    # phiên đang chạy: session.json chưa có post_count, chỉ kiểm mã băm ảnh
    r = compare(session(state="running", post_count=None, digest=None), 5, "dx", [ImageCheck("p1", "aa", "aa")])
    assert r.ok
```

- [ ] Step 2: test FAIL. Step 3: viết `verify_restore.py`. Step 4: test PASS.

- [ ] Step 5: Viết `run-daily-drill.sh`: `kind create cluster --config infra/k8s/drill/kind-config.yaml`; cài CNPG, Barman, Velero cùng phiên bản với Task 6 (không cần cert-manager); ObjectStore `japan-store` dùng SAS `drill-read` (chỉ `rl`) và Cluster `db` khôi phục từ `server_name` trong `session.json`, không bật plugin WAL archiver (diễn tập không được ghi vào kho); Velero restore từ `velero_backup` (phiên đã tắt) hoặc bản `hourly` mới nhất (phiên đang chạy), loại trừ `clusters.postgresql.cnpg.io`, `persistentvolumeclaims`, `persistentvolumes`, `ingresses.networking.k8s.io`, `certificates.cert-manager.io`; `kubectl -n dr-api set env deploy/api IMAGE_STORE_READ_ONLY=true AZURE_STORAGE_ACCOUNT_NAME=<bản chép> AZURE_STORAGE_SAS_KEY=<SAS drill-read của bản chép> CLUSTER=standby`; `kubectl port-forward svc/api 8080:80`; `verify_restore.py`.

- [ ] Step 6: Workflow `.github/workflows/daily-drill.yml`: `on: schedule: [{cron: "40 20 * * *"}]` (03:40 giờ Việt Nam) và `workflow_dispatch`; `timeout-minutes: 60`; `permissions: contents: write, packages: read` (kéo image API của chính kho bằng `GITHUB_TOKEN`); cài `kind` v0.x bản ghim trong `docs/versions.md`, kubectl 1.36, Helm 4.3.1, Velero CLI v1.18.4; chạy `run-daily-drill.sh`; ghi CSV vào `ops-log` như Task 11 (`if: always()`); tải lên log của các pod khi lỗi.

- [ ] Step 7: Kiểm tra trên GitHub

Run: sau khi `session-stop.sh primary` ở Task 10, merge vào `main`, `gh workflow run daily-drill.yml`.
Expected: xanh trong dưới 30 phút; CSV có đủ sáu bước `ok`; `verify` báo số bài đúng bằng `post_count`, `digest_match` đúng, không ảnh hỏng. Trong kho sao lưu không có tệp nào mới dưới `cnpg/` trong lúc chạy (so `az storage blob list` trước và sau).

- [ ] Step 8: Commit

```bash
git add scripts/dr/verify_restore.py tests/scripts/test_verify_restore.py scripts/drill infra/k8s/drill infra/k8s/values/velero-drill.yaml.tpl .github/workflows/daily-drill.yml
git commit -m "DR: diễn tập lạnh mỗi ngày trên máy GitHub"
```

---

### Task 13: Bật trang dùng, ghi kết quả, dọn

**Files:**
- Modify: `docs/trial-results.md`, `docs/versions.md`, `infra/README.md`, `scripts/README.md`, `backup/README.md`, `docs/thiet-ke.md` (mục 10, đánh dấu tuần 3)

- [ ] Step 1: Bật nút "Vào xem" khi `https://api.dr.qivarn.id.vn/healthz` trả 200 từ cụm chính: `gh variable set API_READY --body true`, chạy lại job `deploy` của `ci` trên `main`.
Expected: `curl -fsS https://dr.qivarn.id.vn/ready.json` có `"ready":true`; trang `/view/` hiện bài từ cụm chính. Khi phiên tắt, trang dùng hiện băng báo sự cố, đó là hành vi đúng của thiết kế web, không đặt lại `API_READY=false`.

- [ ] Step 2: README của `infra/`, `scripts/`, `backup/` thay câu "trên máy cá nhân" bằng mô tả thật và lệnh bật, tắt phiên. `infra/trial/` và `scripts/trial/` giữ nguyên làm bằng chứng của buổi thử.

- [ ] Step 3: Tắt phiên và kiểm tra không còn máy

Run: `bash scripts/azure/session-stop.sh primary && az vm list -g rg-dr-primary -o tsv | wc -l && az vm list -g rg-dr-standby -o tsv | wc -l`
Expected: `0` và `0`. Tài khoản lưu trữ vẫn còn (chúng là sao lưu).

- [ ] Step 4: Chi phí: ngày hôm sau xem Cost Management của ba nhóm `rg-dr-*`, ghi vào `docs/trial-results.md` mục "Phiên thật đầu tiên".

- [ ] Step 5: Commit

```bash
git add docs infra/README.md scripts/README.md backup/README.md
git commit -m "Hạ tầng tuần 3: ghi kết quả, bật trang dùng"
```

---

## Ngoài kế hoạch này (tuần 4 trở đi)

Cụm dự phòng chạy thật và cách ấm, job két với `age`, server bạn, script đo của mục 5.1, bản thu nhỏ trên kind, nút kích hoạt khôi phục trên GitHub. Kho ảnh dự phòng, replication tới nó và két đã được tạo ở Task 3 để tuần 4 chỉ còn phần trong cụm.

### Đề còn đòi mà kế hoạch này chưa làm (so ngày 26/10)

So với đề 23 (trang 23) và yêu cầu chung (trang 2) trong file đề. Mỗi mục cần một kế hoạch riêng ở tuần 4, viết theo đúng mục thiết kế đã có.

- [ ] Mã hóa bản sao lưu. Đề: "Backup được mã hóa, có chính sách retention và bằng chứng khôi phục thành công". Azure tự mã hóa lúc lưu chưa đủ làm bằng chứng của nhóm; job két mã hóa bằng `age` cho hai khóa như thiết kế mục 4.3 và 4.4, kèm một lần giải mã và khôi phục thử có log.
- [ ] Diễn tập mất cụm và giả lập mất vùng, đo từng bước. Đề: xóa có kiểm soát namespace hoặc cụm, kích hoạt runbook trên môi trường dự phòng, đo phát hiện, quyết định, cấp phát, phục hồi dữ liệu, kiểm thử, chuyển lưu lượng. Cần cụm dự phòng, script đo mục 5.1 và 5.2, các lượt D1 tới D6 theo mục 6, biên bản trong `docs/dien-tap/`.
- [ ] Runbook sửa sau diễn tập và kế hoạch kiểm thử lại. Đề yêu cầu bản đã chỉnh sau diễn tập, không phải bản viết trước. Theo mục 6.1 và 6.3.
- [ ] Bản chạy trên máy cá nhân. Đề: phạm vi tối thiểu phải chạy được trên máy cá nhân, phòng máy hoặc gói miễn phí. Bản thu nhỏ hai cụm kind với SeaweedFS theo mục 6.4, có hướng dẫn tái lập.
- [ ] Cả ba thành viên tham gia. Đề: mỗi người hiểu toàn bộ kiến trúc, mã nguồn và kết quả đo; kho có lịch sử đóng góp của ba người. Lan Hương và Minh Thư mỗi người ngồi cùng ít nhất một phiên Azure, tự commit phần của mình (BIA, checklist, biên bản, script biểu đồ), và ít nhất một lượt diễn tập do một trong hai người tự chạy theo runbook (mục 6 và 8).
- [ ] Sản phẩm bàn giao còn lại. Bộ số đo CSV kèm script tạo lại bảng và biểu đồ, hướng dẫn dọn tài nguyên và ước tính chi phí, danh mục rủi ro bảo mật còn lại (có điểm Velero dùng khóa tài khoản ở Task 5), thẻ phiên bản cho bản nghiệm thu, video hoặc buổi demo có cả luồng bình thường và một tình huống lỗi.
