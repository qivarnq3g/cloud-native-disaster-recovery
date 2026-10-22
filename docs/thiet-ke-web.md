# Thiết kế web: API và trang dùng

Ngày 09/10/2026. Quang duyệt từng phần trong buổi thiết kế cùng ngày. Tài liệu này chi tiết hóa mục 2 của [thiết kế chính](thiet-ke.md); chỗ nào hai tài liệu khác nhau thì sửa cả hai cho khớp trước khi làm.

## 0. Mục đích và tiêu chí thành công

Web là đối tượng để diễn tập khôi phục: script đo gọi thẳng API, còn trang dùng để người xem, giảng viên và video demo thấy hệ thống hoạt động và thấy lúc chuyển cụm.

Thành công khi:
- người xem xem được danh sách ảnh, mở từng bài; người có mã bí mật đăng được bài, kể cả ảnh chụp điện thoại vài MB;
- khi cụm chính mất, trang không vỡ mà báo đang khôi phục, tự thử lại, và khi chạy lại thì cho biết đang ở cụm nào;
- API nhỏ, bật nhanh, ít tốn bộ nhớ, để không làm chậm việc khôi phục trên máy ảo 4 GB;
- trang dùng đạt điểm hiệu năng Lighthouse từ 95 trở lên trên điện thoại;
- mọi bước kiểm tra chạy tự động trên GitHub Actions.

Ưu tiên của Quang: tối ưu hơn đơn giản, miễn khả thi.

## 1. Các khối và vị trí code

| Khối | Thư mục | Công nghệ | Chạy ở đâu |
|---|---|---|---|
| API | `app/api` | Rust | Trong cụm k3s, sau Traefik, tên `api.dr.qivarn.id.vn` |
| Trang web | `app/web` | Astro (xuất trang tĩnh) + Svelte | GitHub Pages của kho `dr-preview`, tên `dr.qivarn.id.vn` |
| Môi trường chạy thử | `app/compose.yaml` | Docker Compose | Máy cá nhân và GitHub Actions |

**Vì sao code nằm trong kho đồ án mà trang lại đăng từ `dr-preview`:** GitHub Pages miễn phí chỉ đăng từ kho công khai, còn kho đồ án đang riêng tư. Để code ở một chỗ giúp API và trang luôn khớp nhau; GitHub Actions dựng trang rồi chép bản đã dựng sang `dr-preview`. Khi kho đồ án chuyển công khai vẫn giữ cách này, không phải đổi gì.

**Đường đi của dữ liệu:** trình duyệt → `api.dr.qivarn.id.vn` (DNS trỏ tới cụm đang phục vụ, đổi khi chuyển cụm theo mục 6.1 của thiết kế chính) → API → Postgres (CNPG) và kho ảnh. Trang web không bao giờ gọi thẳng kho ảnh.

## 2. API

### 2.1 Công nghệ

- Rust bản ổn định, khung web `axum` trên `tokio`.
- Postgres qua `sqlx`, câu truy vấn được kiểm tra lúc biên dịch (chế độ offline để CI không cần cơ sở dữ liệu lúc biên dịch). Cấu trúc bảng tạo bằng `sqlx migrate` khi API khởi động; `sqlx` giữ khóa nên chạy lại nhiều lần vẫn an toàn.
- Kho ảnh qua `object_store`: một giao diện cho hai nơi cất.
  - Azure Blob trên Azure, xác thực bằng mã SAS đọc và ghi (mục 4.4 thiết kế chính).
  - SeaweedFS qua giao thức S3 ở bản thu nhỏ trên kind (mục 6.4 thiết kế chính).
  - Chọn nơi cất bằng cấu hình lúc chạy, không biên dịch hai bản.
  - Thư viện chính thức của Azure cho Rust còn ở giai đoạn thử nghiệm nên không dùng.
- Mô tả lệnh OpenAPI 3.1 sinh từ code bằng `utoipa`, xuất ở `/openapi.json`.
- Xử lý ảnh: `image` để đọc, `fast_image_resize` để thu nhỏ, `ravif` để ghi ảnh nhỏ dạng AVIF.
- Image container: biên dịch tĩnh (musl, TLS bằng `rustls`), chạy trên nền `distroless/static` bằng người dùng không phải root. Kích thước mục tiêu khoảng 10–15 MB, đo thật ở bước làm thử.
- Phiên bản cụ thể của mọi thư viện ghi trong `docs/phien-ban.md`.

### 2.2 Dữ liệu

Bảng `posts` trong Postgres:

| Cột | Kiểu | Ghi chú |
|---|---|---|
| `id` | UUID v7 | API tạo; tăng theo thời gian nên dùng luôn để phân trang |
| `idempotency_key` | UUID, duy nhất | Trình duyệt tạo cho mỗi lần đăng; gửi lại cùng mã thì trả về bài đã có |
| `title` | text | 1–100 ký tự sau khi bỏ khoảng trắng hai đầu |
| `description` | text | 0–1000 ký tự |
| `image_sha256` | 32 byte | Mã băm của đúng các byte ảnh gốc đã cất |
| `image_type` | text | `image/jpeg`, `image/png` hoặc `image/webp` |
| `image_bytes` | int | Kích thước ảnh gốc |
| `width`, `height` | int | Kích thước ảnh, để trang xếp lưới trước khi ảnh tải xong |
| `created_at` | timestamptz | Giờ đăng |

Văn bản được chuẩn hóa Unicode NFC; ký tự điều khiển bị từ chối.

Kho ảnh, một container tên `images`:
- `original/{id}`: ảnh gốc, đúng các byte nhận được.
- `thumbnail/{id}.avif`: ảnh nhỏ, cạnh dài nhất 800 px, tạo lần đầu có người xem (mục 2.7). Ảnh gốc không quá 800 px mỗi cạnh thì không có ảnh nhỏ, dùng luôn ảnh gốc. Đây là dữ liệu dẫn xuất: mất thì API tạo lại từ ảnh gốc, không tính là mất dữ liệu.

Bước kiểm tra sau khôi phục (mục 5.3 thiết kế chính) đối chiếu từng dòng `posts` với `original/{id}` và mã SHA-256. Ảnh gốc không có dòng `posts` tương ứng (do lần đăng hỏng giữa chừng) được báo riêng, không tính là mất dữ liệu.

### 2.3 Các lệnh

Tất cả nằm dưới `/v1`, trừ ba lệnh vận hành ở cuối bảng.

| Lệnh | Việc làm | Trả về |
|---|---|---|
| `GET /v1/posts?before={id}&limit={n}` | Danh sách, mới nhất trước. `limit` mặc định 24, tối đa 60. `before` là `id` cuối của trang trước | `{ posts: [...], next: id hoặc null }` |
| `GET /v1/posts/{id}` | Một bài | Bài, gồm `width`, `height`, `image_sha256`, `created_at` |
| `GET /v1/posts/{id}/image` | Ảnh gốc | Byte ảnh; `ETag` là mã SHA-256; `Cache-Control: public, max-age=31536000, immutable` |
| `GET /v1/posts/{id}/thumbnail` | Ảnh nhỏ, theo mục 2.7 | Như trên |
| `POST /v1/secret-code/verify` | Kiểm tra mã bí mật, gửi trong `Authorization: Bearer` | 204 hoặc lỗi |
| `POST /v1/posts` | Đăng bài. `multipart/form-data`: `idempotency_key`, `title`, `description`, `image`; mã bí mật trong `Authorization: Bearer` | 201 kèm bài; 200 kèm bài cũ nếu `idempotency_key` đã có |
| `GET /healthz` | Sẵn sàng phục vụ thật | Xem 2.5 |
| `GET /livez` | Tiến trình còn chạy, không kiểm tra gì thêm | 204 |
| `GET /openapi.json` | Mô tả lệnh | OpenAPI 3.1 |

Không có lệnh sửa hay xóa bài: đồ án không cần, và thêm vào làm khó việc đếm dữ liệu sau khôi phục. Bài thử trong bước kiểm tra sau khôi phục (mục 5.3 thiết kế chính) cũng không xóa; trạng thái được dựng lại sau mỗi lần diễn tập.

**Thứ tự khi đăng:**
1. Kiểm tra mã bí mật, rồi `idempotency_key`: đã có thì trả bài cũ ngay.
2. Kiểm tra ảnh: tối đa 1 MiB (1 048 576 byte); nhận dạng kiểu bằng các byte đầu tệp, không tin tên đuôi hay `Content-Type`; đọc được thật; tối đa 50 triệu điểm ảnh để chặn ảnh nén bất thường.
3. Tính SHA-256, cất `original/{id}`.
4. Ghi dòng `posts`. Trùng `idempotency_key` do hai yêu cầu chạy song song thì trả bài của yêu cầu thắng.

Nhờ cất ảnh trước rồi mới ghi bài, không bao giờ có bài trỏ tới ảnh chưa có.

Lúc đăng không tạo ảnh nhỏ: mỗi lần đăng chỉ tốn công tính mã băm và cất ảnh. Script đo đăng 1 bài mỗi giây suốt buổi diễn tập (mục 5.1 và 5.4 thiết kế chính), nên mọi việc nặng hơn ở bước này sẽ chiếm CPU của máy ảo B-series và làm lệch chính thời gian khôi phục đang đo. Kho ảnh ở chế độ chỉ đọc (mục 2.7) thì lệnh đăng trả 503 `read_only` ngay từ đầu.

### 2.4 Mã bí mật

- Lưu trong Kubernetes Secret, nằm trong danh sách chìa khóa khôi phục của Quang (mục 4.4 thiết kế chính).
- So sánh bằng phép so thời gian hằng định.
- Sai quá 10 lần trong 10 phút từ cùng một địa chỉ IP thì trả 429 kèm `Retry-After`. Bộ đếm nằm trong bộ nhớ của API (mỗi cụm một bản chạy). Địa chỉ IP lấy từ `X-Forwarded-For` chỉ khi yêu cầu đến từ Traefik.

### 2.5 Kiểm tra còn sống

`/healthz` trả 200 khi trong 2 giây làm được cả hai việc:
- chạy `SELECT 1` trên Postgres;
- đọc một khóa cố định không tồn tại trong kho ảnh và nhận về "không có". Cách này chứng minh kho ảnh trả lời và mã SAS còn đọc được, mà không cần quyền liệt kê hay ghi gì vào kho.

Nội dung: `{ "status": "ok", "cluster": "primary", "region": "koreacentral", "version": "<git sha>", "read_only": false }`. Hỏng thì trả 503 với `status: "error"` và phần hỏng (`database` hoặc `image_store`).

`cluster` và `region` lấy từ biến môi trường do cấu hình từng cụm đặt (`primary` hoặc `standby`). `/healthz` cũng là readiness probe; `/livez` là liveness probe, để Kubernetes không khởi động lại API chỉ vì cơ sở dữ liệu đang được khôi phục.

### 2.6 Lỗi, CORS và nhật ký

- Lỗi có dạng `{ "error": "<mã>", "message": "<câu tiếng Việt>" }`. Các mã: `invalid_code` (401), `not_found` (404), `image_too_large` (413), `not_an_image` (415), `invalid_input` (422), `too_many_attempts` (429), `unavailable` (503), `read_only` (503).
- CORS chỉ cho phép `https://dr.qivarn.id.vn`; khi chạy thử thêm địa chỉ máy cá nhân qua cấu hình. Chỉ `GET`, `POST`, các header `Authorization` và `Content-Type`.
- Giới hạn thân yêu cầu 1,2 MiB. Mọi phản hồi có `X-Content-Type-Options: nosniff`.
- Nhật ký dạng JSON qua `tracing`, mỗi yêu cầu một dòng. Không thu thập số liệu theo dõi riêng: script đo đo từ bên ngoài.

### 2.7 Ảnh nhỏ và chế độ chỉ đọc

**Ảnh nhỏ tạo khi có người xem.** Khi có `GET /v1/posts/{id}/thumbnail`, API làm theo thứ tự:
1. Ảnh gốc không quá 800 px mỗi cạnh: trả luôn ảnh gốc.
2. Có `thumbnail/{id}.avif` trong kho: trả nó.
3. Có trong bộ nhớ đệm của API (tối đa 64 MB, bỏ ảnh lâu không dùng trước): trả nó.
4. Còn lại thì tạo:
   - mỗi `id` chỉ tạo một lần dù nhiều yêu cầu đến cùng lúc; các yêu cầu sau chờ kết quả của lần đó;
   - cả API chỉ tạo một ảnh nhỏ tại một thời điểm, trên luồng riêng ngoài luồng phục vụ yêu cầu, nên nhiều người xem cùng lúc cũng không chiếm hết hai nhân của máy và không làm chậm các lệnh khác;
   - tạo xong thì đưa vào bộ nhớ đệm, rồi cất vào kho nếu kho cho ghi. Cất lỗi chỉ ghi cảnh báo vào nhật ký, vẫn trả ảnh cho người xem.

**Chế độ chỉ đọc.** Bật bằng biến môi trường `IMAGE_STORE_READ_ONLY=true` khi API chạy với mã chỉ đọc, như lúc diễn tập lạnh mỗi ngày đọc thẳng bản chép ảnh ở Nhật (mục 4.6 thiết kế chính). Khi đó:
- API không gửi lệnh ghi nào tới kho; ảnh nhỏ chỉ nằm trong bộ nhớ đệm;
- `POST /v1/posts` trả 503 `read_only` với câu "Hệ thống đang ở chế độ chỉ đọc.";
- `/healthz` trả `read_only: true` và vẫn chỉ cần quyền đọc (mục 2.5).

Hai lớp này độc lập: quên bật chế độ chỉ đọc khi dùng mã chỉ đọc thì việc xem vẫn chạy, chỉ có cảnh báo trong nhật ký.

## 3. Trang web

### 3.1 Công nghệ và các trang

- Astro xuất trang tĩnh; trang dùng là một đảo Svelte. TanStack Svelte Query lo tải, lưu đệm và thử lại.
- Code gọi API sinh từ `/openapi.json` bằng `openapi-typescript`, gọi bằng `openapi-fetch`.
- Phông Be Vietnam Pro, nền đen, các nút và thanh bằng kính lỏng giống trang giới thiệu (dùng lại `glass.js`). Trang dùng không tải Three.js.
- `/` là trang giới thiệu, giữ nguyên bản đang chạy ở `dr-preview`, thêm hai việc:
  - một đoạn script nhỏ đặt đầu trang: ai đã bấm "Vào xem" thì chuyển ngay sang `/view` trước khi cảnh 3D bắt đầu tải, trừ khi địa chỉ có `?intro`;
  - nút "Vào xem" mở `/view` và ghi nhớ lựa chọn.
- `/view` là trang dùng. Một bài mở bằng `/view?post={id}`: GitHub Pages không có định tuyến phía máy chủ, nên dùng tham số thay cho đường dẫn con.
- Mọi đọc ghi `localStorage` đều bọc `try/catch`; không có `localStorage` thì trang vẫn chạy, chỉ không nhớ được.

### 3.2 Trang dùng

- **Thanh trên** bằng kính: tên trang, nhãn trạng thái, nút "Đăng ảnh" (ẩn khi `/healthz` báo `read_only: true`), đường dẫn "Giới thiệu" (`/?intro`).
- **Lưới ảnh:** xếp hàng đều theo tỉ lệ thật của ảnh, không cắt; chiều cao hàng khoảng 240 px trên máy tính, khoảng 2 ảnh mỗi hàng trên điện thoại. Dùng `width` và `height` để dựng khung xám đúng kích thước trước khi ảnh tải, nên trang không nhảy. Tiêu đề màu xám dưới ảnh. Ảnh nhỏ tải dần khi cuộn tới; cuộn gần cuối thì tải trang tiếp theo.
- **Xem một bài:** hộp thoại `<dialog>` toàn màn hình với ảnh gốc, tiêu đề, mô tả, giờ đăng. Phím mũi tên hoặc vuốt để sang bài khác; ảnh gốc của bài kề bên được tải trước. Esc hoặc nút Quay lại của trình duyệt để đóng; địa chỉ đổi theo bài nên gửi được cho người khác.
- **Đăng ảnh:**
  1. Chưa có mã trên máy thì hỏi mã, kiểm tra bằng `POST /v1/secret-code/verify`, đúng thì nhớ mã trong `localStorage`. Có nút "Quên mã".
  2. Kéo thả hoặc chọn ảnh, xem trước, nhập tiêu đề và mô tả.
  3. Trình duyệt luôn mã hóa lại ảnh trước khi gửi: xoay đúng chiều, cạnh dài nhất tối đa 2560 px, ghi WebP chất lượng 0,85 rồi giảm dần tới khi không quá 1 MiB; trình duyệt không ghi được WebP thì dùng JPEG. Việc mã hóa lại cũng xóa thông tin vị trí trong ảnh chụp điện thoại.
  4. `idempotency_key` tạo bằng `crypto.randomUUID()` một lần cho mỗi lần bấm Đăng và giữ nguyên khi thử lại.
  5. Gửi bằng `XMLHttpRequest` để có thanh tiến độ. Xong thì bài mới hiện ngay đầu lưới.
- **Nhãn trạng thái:**
  - Gọi `/healthz` mỗi 5 giây khi tab đang mở, dừng khi tab bị ẩn, chờ tối đa 3 giây mỗi lần.
  - Hai lần lỗi liên tiếp thì chuyển sang trạng thái sự cố, để một lần chập chờn không làm nhãn nháy. Lúc sự cố gọi mỗi 2 giây.
  - Bình thường: chấm xanh, "Cụm chính · Hàn Quốc" hoặc "Cụm dự phòng · Hàn Quốc", theo `cluster` và `region`.
  - Sự cố: chấm vàng, "Đang khôi phục…", dải thông báo ngắn; ảnh đã tải vẫn xem được.
  - Chạy lại: chấm xanh với tên cụm mới, thông báo "Đã chạy lại sau X phút Y giây" tính từ lần lỗi đầu tiên tới lần thành công đầu tiên theo đồng hồ của trình duyệt, rồi tải lại danh sách. Con số này chỉ để minh họa trong video, không thay số đo chính thức của script đo.
  - Thay đổi trạng thái được đọc cho trình đọc màn hình qua `aria-live`.
- **Dễ dùng cho mọi người:** dùng được hoàn toàn bằng bàn phím, ảnh có chữ thay thế là tiêu đề, độ tương phản đạt WCAG AA, chế độ giảm chuyển động tắt hiệu ứng.

## 4. Đưa lên mạng

- **API:** `ci` biên dịch image và đẩy lên GitHub Container Registry (mục 9 thiết kế chính). Cụm kéo image bằng mã kéo riêng, nằm trong danh sách chìa khóa khôi phục.
- **Trang web:** khi nhánh `main` qua hết kiểm tra, GitHub Actions dựng `app/web` rồi đẩy bản đã dựng thành một commit mới lên nhánh `main` của `dr-preview`, ghi mã commit nguồn trong lời commit. Quyền ghi vào `dr-preview` là một deploy key chỉ cho kho đó; khóa riêng lưu trong secret của kho đồ án. Tệp `CNAME` nằm trong bản dựng để tên miền không bị mất.
- **Bật trang dùng:** khi API trên Azure chưa chạy, biến dựng `PUBLIC_API_READY` để `false`: nút "Vào xem" vẫn ghi "sắp có" và `/view` chỉ hiện "Sắp có". Bật thành `true` khi API trên Azure chạy (tuần 3 theo lịch).

## 5. Kiểm tra

Tất cả chạy trong `ci` mỗi lần đẩy code; trang web chỉ được đăng khi qua hết.

**API:**
- Kiểm thử đơn vị: nhận dạng ảnh (tệp đổi đuôi, ảnh hỏng, ảnh vượt 1 MiB, ảnh quá nhiều điểm ảnh), độ dài và ký tự của tiêu đề và mô tả, so mã, bộ đếm chặn đoán mã, phân trang.
- Kiểm thử chạy thật với Postgres, Azurite (giả lập Azure Blob) và SeaweedFS trong Docker, chạy cùng bộ kiểm thử cho cả hai loại kho:
  - đăng, xem, lấy ảnh gốc và so SHA-256 với ảnh đã gửi;
  - gửi lại cùng `idempotency_key`, kể cả hai yêu cầu song song, chỉ ra một bài;
  - ảnh nhỏ: ảnh gốc không quá 800 px thì trả ảnh gốc; xóa ảnh nhỏ thì lần xem sau tạo lại; 20 yêu cầu cùng lúc cho cùng một ảnh chỉ tạo một lần;
  - chế độ chỉ đọc, chạy với mã chỉ đọc của Azurite và của SeaweedFS: xem bài và ảnh nhỏ vẫn chạy, không lệnh ghi nào tới kho, đăng bài trả 503 `read_only`; bật ghi nhầm với mã chỉ đọc thì việc xem vẫn chạy, lỗi cất ảnh nhỏ chỉ nằm trong nhật ký;
  - đăng 1 bài mỗi giây trong 5 phút với ảnh giống ảnh của script đo: CPU trung bình của API không quá 10% một nhân;
  - dừng kho ảnh hoặc Postgres: `/healthz` trả 503 đúng phần hỏng, `/livez` vẫn 204, lần đăng thất bại không để lại dòng `posts` nào thiếu ảnh.
- Đo kích thước image và thời gian từ lúc container chạy tới lúc `/healthz` trả 200; ghi vào báo cáo của `ci`.

**Trang web:**
- Kiểm thử đơn vị cho phần logic: xếp lưới, mã hóa lại ảnh, máy trạng thái của nhãn.
- Playwright chạy với API thật trong Docker, ở cỡ màn hình máy tính và điện thoại: xem lưới, mở và chuyển bài, đăng ảnh với mã, quên mã; dừng API thì nhãn chuyển vàng, chạy lại thì nhãn xanh và ảnh hiện lại; mở `/` sau khi đã vào xem thì tới `/view`.
- axe-core trong Playwright: không có lỗi trợ năng mức nghiêm trọng.
- Lighthouse CI trên `/view`, cấu hình điện thoại: hiệu năng từ 95 trở lên.

**Khớp nhau:** `ci` xuất `/openapi.json` từ API vừa biên dịch, so với bản đã commit, rồi sinh lại code gọi và kiểm tra kiểu của trang (`astro check`). Lệch là lỗi.

Chuyển cụm đầy đủ được kiểm ở bản thu nhỏ trên kind (tuần 2). Phần web chỉ cần chứng minh trang phản ứng đúng khi API mất rồi có lại.

## 6. Ngoài phạm vi

Sửa và xóa bài, tài khoản người dùng, bình luận, tìm kiếm, nhiều cỡ ảnh, CDN, theo dõi số liệu bên trong API.

## 7. Phải đo hoặc kiểm ở bước làm thử

| Việc | Ngưỡng | Nếu không đạt |
|---|---|---|
| Thời gian tạo ảnh nhỏ AVIF trên B2als v2 | Phân vị 95 không quá 500 ms | Đổi ảnh nhỏ sang WebP |
| `object_store` xác thực Azure Blob bằng mã SAS và chạy với SeaweedFS | Kiểm thử chạy thật qua | Viết lớp kho ảnh riêng cho từng nơi cất |
| Biên dịch tĩnh musl cùng `ravif` | Image chạy được trên `distroless/static` | Dùng `distroless/cc` và liên kết động |
| Kích thước image API | Khoảng 10–15 MB | Ghi số thật, không chặn |
| Thời gian từ lúc container chạy tới `/healthz` 200 | Dưới 1 giây khi Postgres và kho ảnh sẵn sàng | Tìm bước khởi động chậm |
| Hiệu năng Lighthouse của `/view` trên điện thoại | Từ 95 | Cắt bớt mã JavaScript tải ban đầu |
