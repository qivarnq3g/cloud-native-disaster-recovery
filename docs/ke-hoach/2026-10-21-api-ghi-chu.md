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

### Task 9: định dạng và gộp `use`

`cargo fmt` định dạng lại mọi tệp (code trong kế hoạch dài hơn 100 cột), tách thành commit riêng. Các dòng `use` mới của `dinh_tuyen/bai.rs` gộp vào khối `use` đầu tệp như kế hoạch dặn.

### Sau Task 10: `clippy -D warnings`

`clippy` 1.97 báo `collapsible_if` ở `DichVuAnhNho::tao` (code Task 6). Gộp thành `if !self.chi_doc && let Err(e) = ...`, hành vi không đổi.

## Dừng ở Task 11, Step 2: kiểm thử tải lệch thiết kế

Mục 5 [thiết kế web](../thiet-ke-web.md) ghi: "đăng 1 bài mỗi giây **trong 5 phút** với ảnh giống ảnh của script đo: CPU trung bình của API không quá 10% một nhân". `tests/tai.rs` trong kế hoạch chỉ đăng 60 bài (1 phút), tên kiểm thử cũng là `..._trong_mot_phut_...`. Theo quy ước của đợt làm này (kế hoạch mâu thuẫn thiết kế thì dừng, không tự sửa), `tests/tai.rs` **chưa được commit** và Task 12 chưa làm, vì job `api` trong `ci` chạy `cargo test --release --test tai`.

Một điểm nữa để Quang cân nhắc cùng lúc: kiểm thử đo `cpu_time::ProcessTime` của cả tiến trình kiểm thử, gồm cả API, máy khách `reqwest` và việc tạo ảnh PNG, không riêng API. Số đo vì vậy cao hơn CPU thật của API, tức là chặt hơn ngưỡng.

Để có số liệu, đã chạy bản 1 phút đúng như kế hoạch một lần từ tệp tạm (đã xóa, không commit), với SeaweedFS:

```
cargo test --release --test tai -- --ignored --nocapture
cpu_tren_thoi_gian=0.003
test dang_mot_bai_moi_giay_trong_mot_phut_ton_duoi_10_phan_tram_mot_nhan ... ok
```

Cần Quang chọn một trong hai:
1. Sửa kế hoạch cho khớp thiết kế: vòng lặp 300 lần (5 phút), đổi tên kiểm thử; job `ci` dài thêm khoảng 4 phút.
2. Sửa thiết kế mục 5 thành 1 phút nếu 1 phút là đủ.

Sau khi chọn thì làm tiếp: commit `tests/tai.rs`, rồi Task 12 (Dockerfile, đo image và thời gian khởi động, workflow `ci`, hướng dẫn trong `app/README.md`).

## Việc khác thấy khi đối chiếu thiết kế

- Mục 2.1 thiết kế web ghi "Phiên bản cụ thể của mọi thư viện ghi trong `docs/phien-ban.md`". Kế hoạch API không có bước tạo tệp này, nên chưa làm. Phiên bản thật đang ghim trong `app/api/Cargo.lock` (ví dụ axum 0.8.9, sqlx 0.8.6, object_store 0.12.5, utoipa 5.5.0, image 0.25.10, ravif 0.11.20, fast_image_resize 5.5.0, tokio 1.54.0).
