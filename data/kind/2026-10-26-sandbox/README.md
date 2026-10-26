# Lần chạy trong sandbox ngày 26/10/2026

Lần chạy đầu tiên của bản thu nhỏ, mỗi tình huống một lần, trên máy ảo Linux 4 CPU, 16 GB RAM, Docker 29.9.2 dùng cgroup v1 (nên có hai chỉnh sửa ở `infra/kind/cluster.yaml.tpl`). Bộ mẫu 1000 bài, đăng 1 bài/giây trong 90 giây trước lúc phá.

- D3 chạy trên môi trường `up.sh` đầy đủ; D1 dựng lại bằng `run.sh D1 --iterations 1 --keep`; D2 chạy ngay sau D1 trên cùng môi trường (bộ mẫu lúc đó 1096 bài cộng bài của D1); D6 dựng lại bằng `run.sh D6 --iterations 1`.
- `up.csv` gồm ba lần dựng: hồ sơ full (dòng `manual`), rồi hồ sơ primary cho D1 và D6. Dòng `standby` mang `run_id` của D2 là bước dựng hạ tầng của D2.
