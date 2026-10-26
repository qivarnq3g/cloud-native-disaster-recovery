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
| Velero | v1.18.4 | CLI trên laptop cùng bản; chart Helm chọn theo `app_version` |
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
| Node.js | 24 |
