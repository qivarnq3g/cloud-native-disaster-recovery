# Kết quả chạy thử trên Azure

Ngày chạy: 24/10/2026. Kế hoạch: `docs/ke-hoach/2026-10-09-chay-thu-azure.md`.

| # | Câu hỏi (mục 8 thiết kế chính) | Kết quả đo | Quyết định |
|---|---|---|---|
| 1 | RAM của một cụm | | |
| 2 | Dung lượng WAL mỗi ngày | | |
| 3 | Thời gian chép ảnh Hàn Quốc sang Nhật | 200 ảnh 200 KB, 1 ảnh/giây: trung vị 52,7 s, p95 128,7 s, lớn nhất 139,2 s, không thiếu ảnh nào | RPO của ảnh đặt không dưới p95: 5 phút là đủ an toàn |
| 4 | Thời gian dựng một cụm mới | Cụm chính: 2 phút 15 giây từ lệnh tạo máy tới Traefik sẵn sàng (máy ảo 71 s, k3s 17 s, nút 8 s, Traefik 39 s). Tín dụng CPU: Azure chưa có số đo cho máy vừa tạo. Cụm dự phòng: 1 phút 57 giây | Dựng lại một cụm mất dưới 3 phút, cộng khoảng 3 phút cài phần mềm (161 s ở cụm chính) |
| 5 | iNET cho ủy quyền `api.dr` sang Azure DNS (bản ghi NS) | | |
| 6 | CNPG dựng cụm bản sao từ kho ở Nhật; đường dẫn WAL riêng mỗi cụm | Được. Bản sao Ready sau 72 s, theo kịp cụm chính sau 61 s (đúng `archive_timeout` 60 s). WAL của cụm chính ở `primary-1024/`, của cụm dự phòng ở `standby-1024/`, không lẫn. Đổi vai thành chính: 7 s, ghi được ngay. Khôi phục lạnh từ kho Nhật: 61 s, dữ liệu mới nhất cũ hơn lúc chạy khoảng 1,5 phút | Giữ thiết kế: cụm bản sao đọc WAL từ Nhật, mỗi cụm một `serverName` |
| 7 | Chứng chỉ khôi phục bằng Velero được dùng lại, không xin mới | | |
| 8 | GitHub gửi email khi workflow lỗi | | |
| 9 | Bản thu nhỏ vừa máy GitHub | | |
| 10 | Ngân sách Azure có tạo được trên tài khoản sinh viên | Được: ngân sách `dr-trial` 25 USD/tháng, cảnh báo email 50/80/100% (API `2023-05-01` trả `amount` 25.0) | Dùng ngân sách có cảnh báo cho cụm thật, không cần xem số dư bằng tay |
| 11 | Thời gian tạo ảnh nhỏ AVIF trên B2als v2 (nếu API đã có) | | |
