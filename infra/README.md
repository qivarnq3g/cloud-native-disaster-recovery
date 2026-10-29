# infra

Hạ tầng thật trên Azure for Students và bản thu nhỏ trên kind. Người làm: Quang.

| Thư mục | Nội dung |
|---|---|
| `bootstrap/` | Tạo nhóm `rg-dr-backup` và tài khoản lưu state Terraform, chạy một lần |
| `terraform/storage/` | Kho sao lưu ở `japanwest`, két không xóa được (WORM), kho ảnh chính và bản chép, ngân sách |
| `terraform/cluster/` | Một máy ảo B2als v2 chạy k3s cho mỗi cụm (`primary` hoặc `standby`) ở `koreacentral` |
| `k8s/platform/` | CloudNativePG, kho đối tượng cho Barman, lịch sao lưu CNPG và Velero, cert-manager |
| `k8s/overlays/azure/` | API trên cụm thật, có Ingress và chứng chỉ Let's Encrypt |
| `k8s/drill/` | Cụm kind và mẫu khôi phục cho diễn tập hằng ngày trên máy GitHub |
| `kind/` | Bản thu nhỏ hai cụm kind (diễn tập D1, D2, D3, D6) |
| `trial/` | Bằng chứng của buổi chạy thử 24/10, giữ nguyên |

Bật và tắt cụm bằng script trong `scripts/azure/`, xem `scripts/README.md`.
