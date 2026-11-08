# Bản thu nhỏ lặp 30 lần, ngày 08/11/2026

Lượt chạy `kind-mini` số 42434189591 trên `main` (commit `38bfddd`), tình huống D1, D2, D3, D6, mỗi tình huống 30 lần, chia thành 6 job, mỗi job 5 lần. Máy GitHub Actions `ubuntu-latest`: 4 CPU, khoảng 16 GB RAM (cột `cpus`, `mem_total_mb`). Bộ mẫu 1.000 bài, đăng 1 bài/giây trước lúc phá.

- `runs.csv`: 119 dòng, mỗi dòng một lần chạy, đều đạt. D2 có 29 dòng: lần D2 thứ 2 của job thứ 2 hỏng ở bước dựng cụm, trước lúc phá, nên không có dòng nào. Pod `barman-cloud` kẹt ở ContainerCreating 5,5 phút, `rollout status` hết giờ chờ. Ảnh chụp đối tượng của cụm lúc hỏng nằm trong `logs/`; chẩn đoán lúc đó không lưu sự kiện Kubernetes, nên chưa biết nguyên nhân.
- `steps.csv`: thời gian từng bước khôi phục; `up.csv`: thời gian dựng môi trường; `resources.csv`: CPU và RAM lấy mẫu trong lúc chạy.
- Các tệp được gộp từ artifact `kind-<tình huống>-<job>` của lượt chạy, bỏ dòng trùng, sắp theo `run_id`.

Tóm tắt (nhỏ nhất / tứ phân vị 1 / trung vị / tứ phân vị 3 / lớn nhất, giây):

| Tình huống | Số lần đạt | RTO | RPO |
|---|---|---|---|
| D1 | 30/30 | 51,4 / 54,1 / 56,9 / 58,4 / 63,8 | 0 |
| D2 | 29/29 (một lần hỏng lúc dựng cụm) | 142,1 / 149,1 / 152,3 / 154,5 / 156,2 | 34,0 / 34,0 / 35,0 / 35,0 / 36,0 |
| D3 | 30/30 | 11,1 / 12,1 / 13,7 / 14,1 / 15,0 | 34,0 / 35,0 / 35,0 / 35,0 / 37,0 |
| D6 | 30/30 | | |

Mọi lần: mã băm nội dung khớp, không ảnh hỏng, không bài mất ngoài RPO. Không so trực tiếp với số đo trên Azure vì phần cứng, mạng và cách đổi DNS khác nhau.
