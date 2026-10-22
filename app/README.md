# app

Web đăng ảnh kèm mô tả: cơ sở dữ liệu lưu bài viết, kho object lưu ảnh. Người làm: Quang.

## Chạy API trên máy

Cần Docker, Rust 1.97.1 và Azure CLI (để tạo container trong Azurite).

```bash
app/dev/setup.sh               # Postgres, Azurite, SeaweedFS; in AZURITE_READ_SAS
export AZURITE_READ_SAS='<giá trị in ra>'
cd app/api
cargo test --all-targets       # kiểm thử, cần các dịch vụ trên
cd .. && docker compose --profile api up --build api   # API ở http://127.0.0.1:8080
```

Thiết kế: `docs/thiet-ke-web.md`. Kế hoạch: `docs/ke-hoach/2026-10-09-api.md`.

## Chạy trang web trên máy

Cần Node 24 và API đang chạy (`docker compose --profile api up -d api` trong `app/`).

```bash
cd app/web
npm ci
PUBLIC_API_URL=http://127.0.0.1:8080 PUBLIC_API_READY=true npm run dev    # http://127.0.0.1:4321/view/
npm test && npm run e2e
```

Khi `main` qua hết kiểm tra, `ci` đẩy bản dựng sang kho `dr-preview` (GitHub Pages, `dr.qivarn.id.vn`). Việc đẩy chỉ chạy khi biến `DEPLOY_ENABLED` của kho là `true` (hiện chưa đặt, nên chưa đăng gì). Trang dùng chỉ mở khi biến `API_READY` của kho là `true`; đặt bằng `gh variable set API_READY --body true` khi API trên Azure đã chạy.
