# Ghi chú khi làm kế hoạch API

Ngày 21/10/2026. Ghi lại các chỗ khác với [kế hoạch API](2026-10-09-api.md) khi làm thật, lý do, và bước nào chưa chạy được. Không chỗ nào đổi thiết kế.

## Môi trường đã dùng

- Rust 1.97.0 (kế hoạch ghi 1.97.1; máy chỉ có sẵn 1.97.0, `rust-version = "1.97"` vẫn khớp).
- Docker 29.9.1, Docker Compose 5.6.0; Postgres 18.6, Azurite 3.37.0, SeaweedFS 4.48 chạy bằng `app/compose.yaml`.
- `az` (Azure CLI 2.91.0) cài vào môi trường Python riêng chỉ để `app/thu/chuan-bi.sh` tạo container và mã SAS đọc trên Azurite; không đăng nhập Azure.

## Chỗ sửa so với kế hoạch

### Task 5: `with_client_options` xóa `allow_http`

`AmazonS3Builder::with_client_options` thay toàn bộ `ClientOptions`. Trong kế hoạch:
- `tests/chung/mod.rs` gọi `.with_allow_http(true)` rồi mới `.with_client_options(...)`, nên S3 tới SeaweedFS qua `http://` lỗi `BadScheme`;
- `KhoAnh::tu_cau_hinh` gọi `from_env()` rồi `.with_client_options(...)`, nên `AWS_ALLOW_HTTP` (và mọi biến cấu hình mạng khác của `object_store`) bị bỏ qua.

Sửa: đặt `with_client_options` và `with_retry` trước; trong `tu_cau_hinh` tạo builder trống, đặt tùy chọn mạng, rồi mới đọc các biến `AZURE_*` hoặc `AWS_*` giống cách `from_env()` làm. Các biến môi trường dùng vẫn đúng như kế hoạch ghi.

### Task 6: `AnhTraVe` thêm `Debug`

Kiểm thử `thieu_anh_goc_thi_khong_tim_thay` gọi `unwrap_err()` trên `Result<AnhTraVe, ApiLoi>`, cần `AnhTraVe: Debug`. Thêm `#[derive(Debug)]`.

Kiểm thử `anh_nho` ở bản debug mất khoảng 90 giây vì mã hóa AVIF không tối ưu; không đổi gì.

Số đo ví dụ `do-anh-nho` trên máy làm (4 nhân, bản release, chưa bật `phat_hanh`): `n=5 trung_vi_ms=958 p95_ms=973 jpeg_byte=1151764`. Đây chưa phải số đo trên B2als v2 mà mục 7 thiết kế web yêu cầu (ngưỡng phân vị 95 không quá 500 ms); đo lại ở bước chạy thử Azure, nhớ bật `--features phat_hanh`.
