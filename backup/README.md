# backup

Sao lưu cơ sở dữ liệu, ảnh và tài nguyên Kubernetes. Người làm: Quang.

| Phần | Cách làm | Cấu hình |
|---|---|---|
| Cơ sở dữ liệu | CloudNativePG đẩy WAL mỗi phút và bản đầy đủ theo lịch vào kho ở Nhật qua plugin Barman Cloud | `infra/k8s/platform/object-store.yaml.tpl`, `scheduled-backup.yaml` |
| Tài nguyên Kubernetes và chứng chỉ | Velero sao lưu mỗi giờ, giữ 72 giờ; bản lúc tắt phiên giữ 7 ngày | `infra/k8s/platform/velero-schedule.yaml` |
| Ảnh | Object replication từ kho ảnh chính sang bản chép ở vùng khác | `infra/terraform/storage/` |
| Bản không xóa được | Két có chính sách WORM | `infra/terraform/storage/` |

Kiểm tra mỗi giờ bằng workflow `backup-check`, khôi phục thử mỗi ngày bằng workflow `daily-drill`. Chưa làm: mã hóa bản sao lưu bằng `age`.
