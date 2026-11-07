# Biên bản diễn tập official-D6-1

- Mã lần: `official-D6-1`
- Tình huống: D6, thử xóa và ghi đè gói trong két chống xóa `drvaulte307a0/vault`
- Ngày: 07/11/2026
- Người chạy: qivarnq3g, tác vụ tự động theo lịch, chạy bằng `scripts/azure/vault-d6.sh official-D6-1`
- Lần báo trước: có
- Giờ chạy (UTC): khoảng 02:42
- Gói bị thử: `primary-202611040518/20261104T052644Z.tar.age` (410.038.298 byte)
- Chính sách WORM lúc chạy: 7 ngày, đã khóa cứng (Locked)
- Phiên bản mã (commit): 850ac35

| Lần thử | Dùng quyền | Kết quả | Mã HTTP | Mã lỗi Azure |
|---|---|---|---|---|
| Xóa gói | Khóa tài khoản | Bị từ chối | 409 | `BlobImmutableDueToPolicy` |
| Ghi đè gói | Khóa tài khoản | Bị từ chối | 409 | `BlobImmutableDueToPolicy` |
| Xóa gói | SAS `vault-writer` (`cl`) | Bị từ chối | 403 | `AuthorizationPermissionMismatch` |
| Ghi đè gói | SAS `vault-writer` (`cl`) | Bị từ chối | 403 | `UnauthorizedBlobOverwrite` |
| Rút ngắn WORM | Khóa tài khoản | Bị từ chối | | `ContainerImmutabilityPolicyFailure` |

- Kiểm tra sau đó: chính sách vẫn Locked 7 ngày; gói vẫn 410.038.298 byte, giờ sửa lần cuối vẫn 05:28:17 UTC ngày 04/11.
- Kết luận: đạt. Cả bốn cách xóa và ghi đè đều bị từ chối, gói không đổi. Khác lần `d6-1`, chính sách đã khóa cứng nên người có khóa tài khoản cũng không rút ngắn được thời hạn.
- Dữ liệu gốc: `data/azure/drills/official-D6-1/vault-d6.csv`.
- Sự cố ngoài kế hoạch: Không có.
- Sửa runbook gì sau lần này: Không.
