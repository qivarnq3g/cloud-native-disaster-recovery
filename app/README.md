# app

Web đăng ảnh kèm mô tả: cơ sở dữ liệu lưu bài viết, kho object lưu ảnh. Người làm: Quang.

## Chạy API trên máy

Cần Docker, Rust 1.97.1 và Azure CLI (để tạo container trong Azurite).

```bash
app/thu/chuan-bi.sh            # Postgres, Azurite, SeaweedFS; in AZURITE_SAS_DOC
export AZURITE_SAS_DOC='<giá trị in ra>'
cd app/api
cargo test --all-targets       # kiểm thử, cần các dịch vụ trên
cd .. && docker compose --profile api up --build api   # API ở http://127.0.0.1:8080
```

Thiết kế: `docs/thiet-ke-web.md`. Kế hoạch: `docs/ke-hoach/2026-10-09-api.md`.
