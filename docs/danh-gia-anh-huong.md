# Đánh giá ảnh hưởng khi web ngừng hoạt động

Người viết: Huong-19. Mục tiêu RPO/RTO do Quang đưa.

Đề tài yêu cầu một bản đánh giá ảnh hưởng ngắn, bảng RPO/RTO cho từng thành phần và chiến lược phục hồi có lý do lựa chọn.

| Thành phần | Nếu mất hoặc ngừng thì ảnh hưởng gì | RPO | RTO | Lý do |
|---|---|---|---|---|
| Cơ sở dữ liệu bài viết |Người dùng không thể đọc hay đăng bài viết mới, sẽ mất dự liệu hoặc bài viết gần đây nhất. |5 phút |15 phút (lạnh)
2 phút (ấm) | |
| Kho ảnh | Các hình ảnh đính kèm trong bài viết hoặc tài nguyên giao diện bị lỗi hiển thị, không tải được ảnh.|5 phút | 15 phút (lạnh)
2 phút (ấm)| |
| Cấu hình triển khai |Không thể dừng lại các pod/service, dịch vụ nhưng hoàn toàn, không thể điều phối ứng dụng trên Kubernetes |1 giờ |15 phút (lạnh)
0 (sẵn ở cụm dự phòng) | |
|Web |Toàn bộ hệ thống website ngừng cung cấp dịch vụ cho người dùng | |60 phút (lạnh)
10 phút (ấm) | |
## Chiến lược phục hồi được chọn và lý do
2.Các lý do đạt mục tiêu RPO
Bài viết (Postgres): RPO đạt 5 phút nhờ vào cơ chế nhật ký thay đổi (WAL - 
Write-Ahead Logging) được truyền đi với độ trễ chậm nhất mỗi 1 phút
Ảnh: RPO đạt 5 phút dựa trên cơ chế tự sao chép của Azure (dù không cam kết độ trễ cố định, thực tế đo đạc ngày 24/10 ghi nhận mức p95 là 129 giây).
Cấu hình Kubernetes: RPO đạt 1 giờ do công cụ Velero thực hiện việc sao lưu định kỳ mỗi giờ, kết hợp với các file cấu hình gốc đã được quản lý và lưu trữ trực tiếp trong hệ thống Git

3.Các chiến lược phục hồi RTO
Cách lạnh (Cold Standby): Thời gian khôi phục lâu hơn (RTO của web lên tới 60 phút) do cần thời gian phát hiện sự cố, đưa ra quyết định, tiến hành dựng lại hạ tầng từ đầu và thực hiện cấu hình đổi tên miền (DNS)
Cách ấm (Warm Standby): Thời gian khôi phục được rút ngắn đáng kể (RTO của web giảm xuống còn 10 phút, cấu hình Kubernetes sẵn sàng ở cụm dự phòng) nhờ vào hạ tầng dự phòng đã được chuẩn bị sẵn sàng từ trước
