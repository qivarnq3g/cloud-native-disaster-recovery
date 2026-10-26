# Bản thu nhỏ trên kind

Bản thu nhỏ của mục 6.4 thiết kế ([`docs/thiet-ke.md`](../../docs/thiet-ke.md)): cả thí nghiệm sao lưu và khôi phục chạy trong một máy có Docker, không cần Azure, không tốn tiền. Đây là phạm vi tối thiểu đề yêu cầu: ai trong nhóm cũng dựng lại được trên laptop của mình.

| Thành phần | Trên Azure | Ở bản thu nhỏ |
|---|---|---|
| Cụm chính, cụm dự phòng | Hai máy ảo k3s | Hai cụm kind `primary`, `standby` (Kubernetes 1.37) |
| Kho sao lưu, bản chép ảnh, két | Azure Blob ở Nhật | SeaweedFS 4.48 (S3), các bucket `cnpg`, `velero`, `images-copy`, `vault` |
| Kho ảnh chính, kho ảnh dự phòng | Azure Blob ở Hàn Quốc | Bucket `images`, `images-standby` |
| Object replication | Azure tự chép | Container `dr-image-copy` chạy `rclone copy` mỗi 2 giây, chỉ thêm không xóa |
| Két chống xóa | Chính sách WORM 7 ngày | Bucket `vault` bật Object Lock, mặc định COMPLIANCE 7 ngày |
| Cơ sở dữ liệu | CNPG 1.30.1 + Barman Cloud Plugin v0.15.1 | Như Azure, `archive_timeout` 60 s |
| Cấu hình Kubernetes | Velero v1.18.4, plugin Azure | Velero v1.18.4, plugin AWS v1.14.4 trỏ vào SeaweedFS |
| API | Image trên GitHub Container Registry | Build tại máy từ `app/api`, nạp bằng `kind load` |
| Đổi DNS | Cloudflare | Không có: bước 6 ghi `not_applicable` |

Cấu hình API dùng chung nằm ở `infra/k8s/base/api`, phần riêng của kind (kho ảnh S3, NodePort, image) ở overlay `infra/k8s/overlays/kind`. Bản Azure là một overlay riêng, không nằm ở đây.

## Cần cài trước

- Docker: Docker Desktop (Windows dùng WSL2, macOS) hoặc Docker Engine trên Linux. Cho Docker ít nhất 4 CPU và 8 GB RAM; còn trống ít nhất 15 GB ổ đĩa.
- `kind` v0.33.0, `kubectl` 1.36, Helm 4.3.1, `curl`, `git`.
- Python 3.12 trở lên, rồi trong thư mục gốc của kho: `pip install -r scripts/kind/requirements.txt`.

Cài trên Linux (macOS đổi `linux` thành `darwin`, máy Apple Silicon đổi `amd64` thành `arm64`):

```bash
curl -fsSLo kind https://kind.sigs.k8s.io/dl/v0.33.0/kind-linux-amd64
curl -fsSLo kubectl https://dl.k8s.io/release/v1.36.5/bin/linux/amd64/kubectl
curl -fsSL https://get.helm.sh/helm-v4.3.1-linux-amd64.tar.gz | tar xz && mv linux-amd64/helm .
chmod +x kind kubectl helm && sudo mv kind kubectl helm /usr/local/bin/
```

Trên Windows, chạy mọi lệnh trong terminal của WSL2 (Ubuntu), không chạy trong PowerShell.

## Dựng: một lệnh

```bash
scripts/kind/up.sh
```

Lệnh này dựng SeaweedFS và các bucket, container chép ảnh, hai cụm kind có đủ cert-manager, CNPG, Barman Cloud Plugin, Velero, API, cụm bản sao ở `standby` (cách ấm), rồi đăng bộ dữ liệu mẫu 1000 bài, mỗi bài một ảnh khoảng 200 KB. Xong thì API cụm chính ở `http://127.0.0.1:18080`.

- Lần đầu mất thêm thời gian kéo image (khoảng 2,5 GB) và build image API (5 tới 10 phút). Các lần sau khoảng 4 phút.
- `scripts/kind/up.sh --profile primary` chỉ dựng cụm chính, đủ cho D1, D2, D6.
- Khóa truy cập, mật khẩu cơ sở dữ liệu và mã bí mật đều sinh ngẫu nhiên mỗi lần dựng, nằm trong `~/.dr-kind/` (ngoài kho), `down.sh` xóa đi.

## Diễn tập: mỗi tình huống một lệnh

```bash
scripts/kind/run.sh D1   # xóa nhầm namespace dr-api ở cụm chính, khôi phục ngay trên cụm chính
scripts/kind/run.sh D2   # mất cụm chính, cách lạnh: dựng cụm dự phòng mới, khôi phục từ bản sao lưu
scripts/kind/run.sh D3   # mất cụm chính, cách ấm: cụm bản sao ở standby thành cụm chính
scripts/kind/run.sh D6   # thử xóa và ghi đè két bằng khóa quản trị: phải bị từ chối
```

D2 và D3 phá cụm chính, nên sau đó muốn chạy tình huống khác thì `down.sh` rồi `up.sh` lại. Cách gọn hơn là để script tự dựng lại trước mỗi lần, đúng như mục 6 thiết kế yêu cầu (sau mỗi lần diễn tập dựng lại trạng thái ban đầu, gồm cả bộ dữ liệu mẫu):

```bash
scripts/kind/run.sh D2 --iterations 3   # dựng lại, chạy D2, lặp 3 lần, xong thì dọn
```

Mỗi lần chạy D1, D2, D3:

1. Tạo một bản đầy đủ của cơ sở dữ liệu và một bản Velero (mục 4.1, trước mỗi lần diễn tập).
2. Đăng 1 bài mỗi giây vào cụm chính trong 90 giây (`WARMUP_S`), ghi sổ mọi bài được xác nhận; đồng thời gọi `/healthz` mỗi giây.
3. Phá, rồi đo sáu bước của mục 5.2:

| Bước | D1 | D2 | D3 |
|---|---|---|---|
| `detect` | Từ lúc phá tới lần gọi hỏng thứ 5 liên tiếp | Như D1 | Như D1 |
| `decide` | Tự động, ngay khi phát hiện (khoảng 0 s) | Như D1 | Như D1 |
| `infra` | Chờ namespace cũ xóa xong | Dựng cụm kind `standby` và cài phần mềm | Không cần (`not_needed`) |
| `restore` | CNPG dựng từ bản đầy đủ và WAL, song song Velero khôi phục cấu hình, tới khi `/healthz` trả 200 | Như D1, ở cụm `standby`, API đọc ghi bản chép ảnh `images-copy` | Đổi cụm bản sao thành cụm chính, bật API |
| `verify` | Mục 5.3: đếm bài, so mã nội dung, tải từng ảnh so SHA-256, đăng thử một bài | Như D1 | Như D1 |
| `switch` | `not_applicable` (không có DNS) | Như D1 | Như D1 |

RTO ghi trong `runs.csv` là tổng năm bước đầu. RPO là khoảng từ bài cuối cùng còn lại tới lúc phá; bài thiếu nằm giữa sổ (không phải ở cuối) là lỗi.

## Dọn: một lệnh

```bash
scripts/kind/down.sh
```

Xóa hai cụm, SeaweedFS, container chép ảnh và `~/.dr-kind/`. Giữ số đo trong `data/kind/` và image đã kéo (gói image cho `kind load` nằm ở `~/.cache/dr-kind/`, xóa tay nếu cần chỗ).

## Số đo

Mỗi lần chạy ghi thêm dòng vào các tệp trong `data/kind/` (giờ UTC):

- `steps.csv`: sáu bước của mỗi lần chạy, cột `run_id,scenario,iteration,step,started_at,ended_at,duration_s,result`.
- `runs.csv`: mỗi lần chạy một dòng: RTO, RPO, số bài xác nhận, còn, thiếu, thiếu quá RPO, lỗ hổng, ngoài sổ, mã nội dung, số ảnh kiểm và ảnh hỏng, kết quả `pass` hoặc `fail`, cùng số CPU và RAM của máy.
- `d6.csv`: từng lần thử với két: danh tính dùng, có bị từ chối không, mã lỗi, bản gốc còn nguyên không.
- `up.csv`: thời gian dựng từng phần (cụm kind, nạp image, cài phần mềm, ứng dụng, dữ liệu mẫu).
- `logs/<run_id>/`: trạng thái cụm và log pod khi một lần chạy lỗi.

Các tệp CSV ở ngay `data/kind/` không được commit (xem `data/kind/.gitignore`); muốn giữ thì chép sang một thư mục con có ngày, như `data/kind/2026-10-26-sandbox/`. Bảng trung vị và khoảng tứ phân vị:

```bash
python3 -m scripts.kind.results summary data/kind
```

## Trên GitHub Actions

Workflow `kind-mini` (`.github/workflows/kind-mini.yml`) chạy tay ở tab Actions với ba tham số: các tình huống, số lần lặp mỗi tình huống (mặc định 30) và số lần mỗi job (mặc định 5). Mỗi job chạy trên một máy riêng, đo RAM và ổ đĩa mỗi 5 giây; job cuối gom CSV của mọi job thành artifact `kind-mini-results` và in bảng tổng hợp vào trang tóm tắt của lần chạy. Khi pull request đổi tệp của bản thu nhỏ, workflow tự chạy mỗi tình huống một lần.

Kho đang riêng tư nên máy GitHub là loại 2 CPU, 8 GB RAM và mỗi phút chạy trừ vào hạn mức miễn phí của tài khoản (2000 phút mỗi tháng với gói Free). 30 lần cho cả bốn tình huống tốn khoảng 800 tới 1000 phút; khi kho chuyển công khai thì máy thành 4 CPU, 16 GB và không tính phút.

## Biến môi trường

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `PRIMARY_PORT`, `STANDBY_PORT` | 18080, 28080 | Cổng trên máy tới API của từng cụm |
| `SEED_POSTS` | 1000 | Số bài của bộ dữ liệu mẫu |
| `WARMUP_S` | 90 | Số giây đăng bài trước lúc phá |
| `DR_KIND_STATE` | `~/.dr-kind` | Thư mục khóa và trạng thái |
| `API_IMAGE` | `dr-api:kind` | Image API; đã có sẵn thì `up.sh` không build lại |

SeaweedFS luôn ở cổng 18333 của máy.

## Khác với thiết kế và điều đã biết

- **API không chạy được trên cụm bản sao.** Lúc khởi động API chạy `sqlx migrate`, mà cơ sở dữ liệu bản sao chỉ đọc, nên API không bao giờ sẵn sàng. Ở cách ấm, Deployment `api` của cụm dự phòng để 0 bản chạy và chỉ bật lúc chuyển. Bản Azure dùng cách ấm cũng gặp đúng điều này.
- **D1 không đặt thời điểm khôi phục.** CNPG đọc hết WAL có trong kho; cụm cũ đã bị xóa nên WAL cuối luôn có trước lúc sự cố. Đặt thời điểm đích sau đoạn WAL đã gửi thì Postgres dừng với lỗi.
- **D2 lấy ảnh từ bản chép** (`images-copy`), không dùng lại kho ảnh chính như mục 6 thiết kế, để kiểm luôn bản chép.
- **D6 khác Azure ở chỗ ghi đè.** S3 cho ghi đè và xóa không kèm phiên bản: hai việc này chỉ tạo phiên bản mới hay dấu xóa, bản gốc vẫn còn nguyên; Azure WORM thì từ chối hẳn. Xóa đúng phiên bản, rút ngắn thời hạn giữ và vượt khóa đều bị từ chối, kể cả với khóa quản trị. Xóa bucket bị từ chối vì bucket còn dữ liệu.
- **Máy dùng cgroup v1** (một số máy Linux cũ, máy ảo hay sandbox) vẫn chạy được: `infra/kind/cluster.yaml.tpl` có sẵn hai chỉnh sửa cho trường hợp này, trên máy thường chúng không đổi gì.
- `kind load docker-image` lỗi với kho image containerd của Docker 29 khi image có nhiều nền tảng, nên script gói image bằng `docker save --platform` rồi `kind load image-archive`.
