# Ghi chú khi làm kế hoạch API

Ngày 21/10/2026. Ghi lại các chỗ khác với [kế hoạch API](2026-10-09-api.md) khi làm thật, lý do, và bước nào chưa chạy được. Không chỗ nào đổi thiết kế.

## Môi trường đã dùng

- Rust 1.97.0 (kế hoạch ghi 1.97.1; máy chỉ có sẵn 1.97.0, `rust-version = "1.97"` vẫn khớp).
- Docker 29.9.1, Docker Compose 5.6.0; Postgres 18.6, Azurite 3.37.0, SeaweedFS 4.48 chạy bằng `app/compose.yaml`.
- `az` (Azure CLI 2.91.0) cài vào môi trường Python riêng chỉ để `app/dev/setup.sh` tạo container và mã SAS đọc trên Azurite; không đăng nhập Azure.

## Chỗ sửa so với kế hoạch

### Task 5: `with_client_options` xóa `allow_http`

`AmazonS3Builder::with_client_options` thay toàn bộ `ClientOptions`. Trong kế hoạch:
- `tests/common/mod.rs` gọi `.with_allow_http(true)` rồi mới `.with_client_options(...)`, nên S3 tới SeaweedFS qua `http://` lỗi `BadScheme`;
- `ImageStore::from_config` gọi `from_env()` rồi `.with_client_options(...)`, nên `AWS_ALLOW_HTTP` (và mọi biến cấu hình mạng khác của `object_store`) bị bỏ qua.

Sửa: đặt `with_client_options` và `with_retry` trước; trong `from_config` tạo builder trống, đặt tùy chọn mạng, rồi mới đọc các biến `AZURE_*` hoặc `AWS_*` giống cách `from_env()` làm. Các biến môi trường dùng vẫn đúng như kế hoạch ghi.

### Task 6: `ServedImage` thêm `Debug`

Kiểm thử `missing_original_is_not_found` gọi `unwrap_err()` trên `Result<ServedImage, ApiError>`, cần `ServedImage: Debug`. Thêm `#[derive(Debug)]`.

Kiểm thử `thumbnail` ở bản debug mất khoảng 90 giây vì mã hóa AVIF không tối ưu; không đổi gì.

Số đo ví dụ `bench-thumbnail` trên máy làm (4 nhân, bản release, chưa bật `production`): `n=5 median_ms=958 p95_ms=973 jpeg_bytes=1151764`. Đây chưa phải số đo trên B2als v2 mà mục 7 thiết kế web yêu cầu (ngưỡng phân vị 95 không quá 500 ms); đo lại ở bước chạy thử Azure, nhớ bật `--features production`.

### Task 9: định dạng và gộp `use`

`cargo fmt` định dạng lại mọi tệp (code trong kế hoạch dài hơn 100 cột), tách thành commit riêng. Các dòng `use` mới của `routes/posts.rs` gộp vào khối `use` đầu tệp như kế hoạch dặn.

### Sau Task 10: `clippy -D warnings`

`clippy` 1.97 báo `collapsible_if` ở `ThumbnailService::generate` (code Task 6). Gộp thành `if !self.read_only && let Err(e) = ...`, hành vi không đổi.

## Task 11, Step 2: kiểm thử tải chạy 5 phút theo thiết kế

Mục 5 [thiết kế web](../thiet-ke-web.md) (dòng 189) ghi: "đăng 1 bài mỗi giây **trong 5 phút** với ảnh giống ảnh của script đo: CPU trung bình của API không quá 10% một nhân". Bản đầu của `tests/load.rs` trong kế hoạch chỉ đăng 60 bài (1 phút). Đợt làm dừng ở đây, Quang chọn giữ thiết kế; kế hoạch đã sửa thành 300 bài và đổi tên kiểm thử thành `one_post_per_second_for_five_minutes_uses_under_ten_percent_of_a_core`.

Lưu ý: kiểm thử đo `cpu_time::ProcessTime` của cả tiến trình kiểm thử, gồm cả API, máy khách `reqwest` và việc tạo ảnh PNG, không riêng API. Số đo vì vậy cao hơn CPU thật của API, tức là chặt hơn ngưỡng.

Lần chạy bản 1 phút trước khi sửa (tệp tạm, không commit): `cpu_ratio=0.003`.

Lần chạy bản 5 phút đã commit (`cargo test --release --test load -- --ignored --nocapture`, SeaweedFS): `cpu_ratio=0.003`, PASS sau 300,51 giây.

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
| Dựng image (`--features production`, musl, LTO) | 8 phút 26 giây, thành công | |
| Biên dịch tĩnh musl cùng `ravif` (bật asm) | Tệp `/api` là `static-pie`, chạy được trên `distroless/static`; `--print-openapi` in ra OpenAPI 3.1 | Chạy được trên `distroless/static` |
| Kích thước image, lệnh của kế hoạch (`docker image inspect .Size`) | `image_mb=21.4` | Khoảng 10-15 MB, ghi số thật |
| Kích thước tệp chạy `/api` | 10,8 MB | |
| Kích thước nén khi đẩy lên registry | 5,66 MB | |
| Khởi động, lệnh của kế hoạch (tính cả `docker compose up`) | `startup_ms=1114` | |
| Từ lúc container chạy tới `/healthz` 200 (3 lần `docker start`) | 224, 189, 206 ms | Dưới 1 giây |
| Bộ nhớ lúc nghỉ | 13,4 MiB | |
| Ảnh nhỏ từ JPEG 2560x1920 (898 KB) trong image | AVIF 800x600, 12 KB; lần đầu 0,75 giây (gồm đọc ảnh gốc từ SeaweedFS), lần sau 2 ms từ bộ nhớ đệm | Phân vị 95 không quá 500 ms trên B2als v2 |

Ghi chú về kích thước: Docker trên máy làm dùng containerd snapshotter, `.Size` cộng cả lớp nén lẫn lớp đã giải nén (image nền `distroless/static` báo 5,9 MB). Kích thước thật khi chạy gần với tệp chạy cộng nền, khoảng 13 MB; trên GitHub Actions số `image_mb` có thể khác.

Thời gian tạo ảnh nhỏ 0,75 giây là một lần đo trên máy làm, chưa phải phân vị 95 trên B2als v2; vẫn cần đo ở bước chạy thử Azure.

### Step 5: toàn bộ kiểm tra trước khi commit

Chạy trên máy làm, cùng thứ tự với job `api` trong `ci` (trừ bước dựng và đẩy image):
- `cargo fmt --check`: qua.
- `cargo clippy --all-targets -- -D warnings`: qua, không cảnh báo.
- `cargo sqlx prepare --check -- --all-targets`: qua.
- `cargo run -- --print-openapi` so với `openapi.json` đã commit: khớp.
- `cargo test --all-targets`: 52 kiểm thử qua, 1 bỏ qua có chủ ý (`tai`, chạy riêng ở trên).

Các tệp Task 12 commit trước khi có kết quả này (commit "đang kiểm"); sau khi kiểm không phải sửa gì.

### Rủi ro của `ci` chưa kiểm được

- Chưa chạy trên GitHub Actions: workflow chỉ chạy khi đẩy vào `main` hoặc mở PR, cả hai chưa làm (kế hoạch ghi "chỉ làm khi Quang cho phép").
- Ước lượng theo máy làm: biên dịch kiểm thử khoảng 2 phút, `cargo test --all-targets` khoảng 3,5 phút, bản release cho `tai` khoảng 8 phút cộng 5 phút chạy, dựng image khoảng 8,5 phút. Tổng khoảng 30-35 phút trên máy 4 nhân, sát `timeout-minutes: 45` ở lần chạy đầu chưa có bộ nhớ đệm.
- Vòng `until curl ... /healthz` trong bước đo image không có giới hạn, nếu API không lên thì job treo tới hết 45 phút.

## Việc khác thấy khi đối chiếu thiết kế

- Mục 2.1 thiết kế web ghi "Phiên bản cụ thể của mọi thư viện ghi trong `docs/phien-ban.md`". Kế hoạch API không có bước tạo tệp này, nên chưa làm. Phiên bản thật đang ghim trong `app/api/Cargo.lock` (ví dụ axum 0.8.9, sqlx 0.8.6, object_store 0.12.5, utoipa 5.5.0, image 0.25.10, ravif 0.11.20, fast_image_resize 5.5.0, tokio 1.54.0).

## Đổi tên sang tiếng Anh (21/10)

Quy ước Quang chốt 21/10: mọi tên trong code (tệp, thư mục, module, hàm, biến, hằng, kiểu, kiểm thử, bảng, cột, route, tham số query, trường JSON, mã lỗi, biến môi trường, khóa cấu hình, image, dịch vụ compose) bằng tiếng Anh; chữ hiện cho người dùng vẫn tiếng Việt. Các mục trên của tệp này đã đổi tên cho khớp code.

### Tên chính

| Cũ | Mới |
|---|---|
| bảng `bai`, cột `ma_lan_dang`, `tieu_de`, `mo_ta`, `anh_sha256`, `anh_kieu`, `anh_byte`, `rong`, `cao`, `tao_luc` | bảng `posts`, cột `idempotency_key`, `title`, `description`, `image_sha256`, `image_type`, `image_bytes`, `width`, `height`, `created_at` |
| `GET /v1/bai?truoc=&so=`, trả `{ bai, tiep }` | `GET /v1/posts?before=&limit=`, trả `{ posts, next }` |
| `/v1/bai/{id}/anh`, `/v1/bai/{id}/anh-nho`, `POST /v1/ma/kiem-tra` | `/v1/posts/{id}/image`, `/v1/posts/{id}/thumbnail`, `POST /v1/secret-code/verify` |
| lỗi `{ loi, thong_bao }`; `ma_sai`, `khong_tim_thay`, `anh_qua_lon`, `khong_phai_anh`, `du_lieu_sai`, `thu_qua_nhieu`, `tam_ngung`, `chi_doc` | `{ error, message }`; `invalid_code`, `not_found`, `image_too_large`, `not_an_image`, `invalid_input`, `too_many_attempts`, `unavailable`, `read_only` |
| `/healthz`: `trang_thai` (`on`, `loi`), `cum` (`chinh`, `du-phong`), `vung`, `phien_ban`, `chi_doc`, `hong` (`csdl`, `kho_anh`) | `status` (`ok`, `error`), `cluster` (`primary`, `standby`), `region`, `version`, `read_only`, `failing` (`database`, `image_store`) |
| `KHO_ANH`, `KHO_ANH_CONTAINER`, `KHO_ANH_CHI_DOC`, `MA_BI_MAT`, `CUM`, `VUNG`, `CORS_NGUON`, `PROXY_TIN_CAY`, `CONG`, `PHIEN_BAN`, `AZURITE_SAS_DOC` | `IMAGE_STORE`, `IMAGE_STORE_CONTAINER`, `IMAGE_STORE_READ_ONLY`, `SECRET_CODE`, `CLUSTER`, `REGION`, `CORS_ORIGINS`, `TRUSTED_PROXIES`, `PORT`, `APP_VERSION`, `AZURITE_READ_SAS` |
| kho ảnh: container `anh`, khóa `goc/{id}`, `nho/{id}.avif` | container `images`, khóa `original/{id}`, `thumbnail/{id}.avif` |
| `app/thu/chuan-bi.sh`, dịch vụ `csdl`, feature `phat_hanh`, ví dụ `do-anh-nho`, cờ `--in-openapi` | `app/dev/setup.sh`, dịch vụ `db`, feature `production`, ví dụ `bench-thumbnail`, cờ `--print-openapi` |
| module `cau_hinh`, `loi`, `van_ban`, `anh`, `ma_bi_mat`, `kho_anh`, `anh_nho`, `csdl`, `trang_thai`, `dinh_tuyen` | `config`, `error`, `text`, `image_file`, `secret_code`, `image_store`, `thumbnail`, `db`, `state`, `routes` |

Module ảnh tên `image_file`, không phải `image`, để không trùng tên crate `image`.

### Cố ý giữ tiếng Việt

- Câu trả về cho người dùng trong `ApiError`, `text`, `routes/posts.rs`, mô tả trong OpenAPI, câu báo lỗi cấu hình lúc khởi động.
- Dữ liệu và câu báo trong kiểm thử ("Tiêu đề", "Song song", "Kho chết", "thiếu {missing} phải lỗi"...).
- Tên bước trong `ci.yml` (nhãn hiện trên GitHub).
- Phía trang web (chưa có code trong `app/`): đường dẫn `/xem`, `?bai=`, `?gioi-thieu`, khóa `localStorage`, `san-sang.json`, tên biến TypeScript trong kế hoạch trang web. Kế hoạch trang web chỉ đổi những chỗ gọi API.
- Tên tệp trong `docs/` và tên nhánh: chưa đổi, theo yêu cầu.

Nhật ký (`tracing`) trước đây viết tiếng Việt không dấu, nay đổi sang tiếng Anh vì không hiện cho người dùng.

### Phải làm theo

- Cơ sở dữ liệu thử cục bộ tạo từ migration cũ phải dựng lại (`docker compose down --remove-orphans` rồi `app/dev/setup.sh`): migration `20261009000000` đã sửa nội dung nên `sqlx` báo checksum khác.
- Kế hoạch chạy thử Azure đã đổi container ảnh thành `images`. Nếu trên Azure đã tạo container `anh`, tạo lại container `images` (kèm luật chép sang Nhật) hoặc đặt `IMAGE_STORE_CONTAINER=anh`.
