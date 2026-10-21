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

## Task 11, Step 2: kiểm thử tải chạy 5 phút theo thiết kế

Mục 5 [thiết kế web](../thiet-ke-web.md) (dòng 189) ghi: "đăng 1 bài mỗi giây **trong 5 phút** với ảnh giống ảnh của script đo: CPU trung bình của API không quá 10% một nhân". Bản đầu của `tests/tai.rs` trong kế hoạch chỉ đăng 60 bài (1 phút). Đợt làm dừng ở đây, Quang chọn giữ thiết kế; kế hoạch đã sửa thành 300 bài và đổi tên kiểm thử thành `dang_mot_bai_moi_giay_trong_nam_phut_ton_duoi_10_phan_tram_mot_nhan`.

Lưu ý: kiểm thử đo `cpu_time::ProcessTime` của cả tiến trình kiểm thử, gồm cả API, máy khách `reqwest` và việc tạo ảnh PNG, không riêng API. Số đo vì vậy cao hơn CPU thật của API, tức là chặt hơn ngưỡng.

Lần chạy bản 1 phút trước khi sửa (tệp tạm, không commit): `cpu_tren_thoi_gian=0.003`.

Lần chạy bản 5 phút đã commit (`cargo test --release --test tai -- --ignored --nocapture`, SeaweedFS): `cpu_tren_thoi_gian=0.003`, PASS sau 300,51 giây.

## Task 12: image và `ci`

`Dockerfile`, `.dockerignore`, dịch vụ `api` trong `app/compose.yaml`, `.github/workflows/ci.yml` và phần thêm vào `app/README.md` đúng như kế hoạch, không sửa gì.

### Dựng image trên máy làm

Máy làm đi ra mạng qua proxy có CA riêng, nên bản dựng trong Docker không tải được crate nếu dùng thẳng `docker compose build`. Để không phải sửa `Dockerfile` (GitHub Actions không cần proxy), chỉ ở máy làm đã:
- dựng một image nền cục bộ từ `rust:1.97.1-alpine` có thêm CA của proxy và `CARGO_HTTP_CAINFO`;
- dựng bằng `docker buildx build --network host --build-context rust:1.97.1-alpine=docker-image://<image nền cục bộ> --build-arg HTTPS_PROXY=... -t dr-app-api app/api`.

Image cuối dựng từ `distroless/static-debian12:nonroot`, chỉ chép tệp `/api` sang, nên không mang CA hay biến proxy nào.

### Số đo (máy làm, 4 nhân)

| Việc | Kết quả | Ngưỡng ở mục 7 thiết kế web |
|---|---|---|
| Dựng image (`--features phat_hanh`, musl, LTO) | 8 phút 26 giây, thành công | |
| Biên dịch tĩnh musl cùng `ravif` (bật asm) | Tệp `/api` là `static-pie`, chạy được trên `distroless/static`; `--in-openapi` in ra OpenAPI 3.1 | Chạy được trên `distroless/static` |
| Kích thước image, lệnh của kế hoạch (`docker image inspect .Size`) | `image_mb=21.4` | Khoảng 10-15 MB, ghi số thật |
| Kích thước tệp chạy `/api` | 10,8 MB | |
| Kích thước nén khi đẩy lên registry | 5,66 MB | |
| Khởi động, lệnh của kế hoạch (tính cả `docker compose up`) | `khoi_dong_ms=1114` | |
| Từ lúc container chạy tới `/healthz` 200 (3 lần `docker start`) | 224, 189, 206 ms | Dưới 1 giây |
| Bộ nhớ lúc nghỉ | 13,4 MiB | |
| Ảnh nhỏ từ JPEG 2560x1920 (898 KB) trong image | AVIF 800x600, 12 KB; lần đầu 0,75 giây (gồm đọc ảnh gốc từ SeaweedFS), lần sau 2 ms từ bộ nhớ đệm | Phân vị 95 không quá 500 ms trên B2als v2 |

Ghi chú về kích thước: Docker trên máy làm dùng containerd snapshotter, `.Size` cộng cả lớp nén lẫn lớp đã giải nén (image nền `distroless/static` báo 5,9 MB). Kích thước thật khi chạy gần với tệp chạy cộng nền, khoảng 13 MB; trên GitHub Actions số `image_mb` có thể khác.

Thời gian tạo ảnh nhỏ 0,75 giây là một lần đo trên máy làm, chưa phải phân vị 95 trên B2als v2; vẫn cần đo ở bước chạy thử Azure.

### Rủi ro của `ci` chưa kiểm được

- Chưa chạy trên GitHub Actions: workflow chỉ chạy khi đẩy vào `main` hoặc mở PR, cả hai chưa làm (kế hoạch ghi "chỉ làm khi Quang cho phép").
- Ước lượng theo máy làm: biên dịch kiểm thử khoảng 2 phút, `cargo test --all-targets` khoảng 3,5 phút, bản release cho `tai` khoảng 8 phút cộng 5 phút chạy, dựng image khoảng 8,5 phút. Tổng khoảng 30-35 phút trên máy 4 nhân, sát `timeout-minutes: 45` ở lần chạy đầu chưa có bộ nhớ đệm.
- Vòng `until curl ... /healthz` trong bước đo image không có giới hạn, nếu API không lên thì job treo tới hết 45 phút.

## Việc khác thấy khi đối chiếu thiết kế

- Mục 2.1 thiết kế web ghi "Phiên bản cụ thể của mọi thư viện ghi trong `docs/phien-ban.md`". Kế hoạch API không có bước tạo tệp này, nên chưa làm. Phiên bản thật đang ghim trong `app/api/Cargo.lock` (ví dụ axum 0.8.9, sqlx 0.8.6, object_store 0.12.5, utoipa 5.5.0, image 0.25.10, ravif 0.11.20, fast_image_resize 5.5.0, tokio 1.54.0).
