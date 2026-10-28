# Danh sách kiểm tra sau khôi phục

Người soạn: minhthw1605. Dùng sau mỗi lần khôi phục để xác nhận web và dữ liệu đã trở lại đúng.

| # | Mục kiểm tra | Cách kiểm tra | Kết quả mong đợi | Đạt? |
|---|---|---|---|---|
| 1 | Web mở được | Mở trình duyệt, truy cập vào đường dẫn/IP của cụm dự phòng Azure | Trang web hiển thị giao diện bình thường, không báo lỗi 502/504 hay timeout | Đạt |
| 2 | Số bài viết bằng trước khi phá | So sánh tổng số bài viết trên giao diện hoặc truy vấn trực tiếp CSDL Postgres (`SELECT COUNT(*) FROM posts`) với số liệu trước sự cố | Tổng số bài viết trùng khớp hoàn toàn với số lượng ghi nhận tại mốc sao lưu | Đạt |
| 3 | Ảnh mở được và giống bản gốc (so mã băm) | Click mở xem các ảnh cũ trên bài viết và chạy script so sánh mã băm (SHA-256) của file ảnh | Ảnh hiển thị rõ nét, không bị lỗi link (404), mã băm khớp 100% với bản gốc | Đạt |
| 4 | Đăng bài mới được | Thao tác tạo một bài viết mới kèm ảnh tải lên trên cụm dự phòng | Bài viết và ảnh mới được đăng thành công, hiển thị ngay trên danh sách | Đạt |
| 5 | Dữ liệu tạo sau lần sao lưu cuối (nằm ngoài RPO) được ghi nhận | Kiểm tra các bài viết/thao tác được tạo trong khoảng thời gian giữa lần sao lưu cuối và thời điểm xảy ra sự cố | Xác định rõ các dữ liệu bị mất nằm trong khoảng RPO cho phép và hệ thống không bị sai lệch CSDL | Đạt |
