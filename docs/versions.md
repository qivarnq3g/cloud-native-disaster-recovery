# Phiên bản công cụ

Phiên bản cụ thể của mọi công cụ dùng trong đồ án (mục 9 thiết kế). Đổi phiên bản thì sửa tệp này trong cùng commit.

## Hạ tầng

| Công cụ | Phiên bản | Ghi chú |
|---|---|---|
| Terraform | 1.16.6 | `ci` dùng đúng bản này qua `hashicorp/setup-terraform@v3` |
| Provider `azurerm` | 4.x | Ghim bằng `.terraform.lock.hcl` |
| Azure CLI | 2.89 | |
| k3s | v1.37.1+k3s1 | |
| cert-manager | v1.21.2 | |
| CloudNativePG | 1.30.1 | Chart Helm chọn theo `app_version` |
| Barman Cloud Plugin | v0.15.1 | |
| Velero | v1.18.4 | CLI trên laptop cùng bản; chart Helm `12.2.1` (ghi `app_version` 1.18.2, chưa có chart cho 1.18.4) với `image.tag=v1.18.4` |
| Plugin Velero cho Azure | v1.14.4 | |
| Helm | 4.3.1 | |
| kubectl | 1.36 | Kustomize có sẵn trong kubectl |
| kind | | Dùng cho diễn tập hằng ngày |

## Script và kiểm thử

| Công cụ | Phiên bản |
|---|---|
| Python | 3.12 trong `ci` |
| `azure-storage-blob` | 12.x |
| `pytest` | 8.x |

## Ứng dụng

| Công cụ | Phiên bản |
|---|---|
| Rust | 1.97.1 |
| `webp` (ảnh nhỏ, bọc libwebp) | 0.3.1 |
| Node.js | 24 |

## Bản thu nhỏ trên kind

Dùng cho `scripts/kind/` và workflow `kind-mini` (mục 6.4 thiết kế). Phiên bản CNPG, Barman Cloud Plugin, Velero và cert-manager giống bảng Hạ tầng ở trên.

| Công cụ hoặc image | Phiên bản | Ghi chú |
|---|---|---|
| kind | v0.33.0 | Image nút `kindest/node:v1.37.0` (ghim bằng digest trong `infra/kind/cluster.yaml.tpl`) |
| kubectl | v1.36.5 | |
| Helm | v4.3.1 | |
| Chart `jetstack/cert-manager` | v1.21.2 | |
| Chart `cnpg/cloudnative-pg` | 0.29.1 | Chart có `app_version` 1.30.1 |
| Barman Cloud Plugin | v0.15.1 | Manifest chép vào `infra/kind/vendor/` |
| Chart `vmware-tanzu/velero` | 12.2.1 | Chart mới nhất chỉ có `app_version` 1.18.2, nên ghi đè image thành `velero/velero:v1.18.4` |
| Plugin Velero cho AWS (S3) | v1.14.4 | Trỏ vào SeaweedFS |
| Postgres | `ghcr.io/cloudnative-pg/postgresql:18.6-minimal-trixie` | |
| SeaweedFS | 4.48 (28/09/2026) | Có các sửa lỗi Object Lock của tháng 9/2026; cùng bản với `app/compose.yaml` |
| rclone | 1.75.2 | Chép ảnh thay object replication |
| Python | 3.12 trong workflow | |
| `boto3` | 1.40.x | |
