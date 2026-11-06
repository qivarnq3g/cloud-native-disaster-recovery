# Đánh giá ảnh hưởng khi web ngừng hoạt động

Người viết: Huong-19. Mục tiêu RPO/RTO do Quang đưa.

Đề tài yêu cầu một bản đánh giá ảnh hưởng ngắn, bảng RPO/RTO cho từng thành phần và chiến lược phục hồi có lý do lựa chọn.

| Thành phần | Nếu mất hoặc ngừng thì ảnh hưởng gì | RPO | RTO | Lý do |
|---|---|---|---|---|
| Cơ sở dữ liệu bài viết |Người dùng không thể đọc hay đăng bài viết mới, sẽ mất dự liệu hoặc bài viết gần đây nhất. |5 phút |15 phút (lạnh)/2 phút (ấm) |RPO đạt 5 phút nhờ vào cơ chế nhật ký thay đổi (WAL - Write-Ahead Logging) được truyền đi với độ trễ chậm nhất mỗi 1 phút |
| Kho ảnh | Các hình ảnh đính kèm trong bài viết hoặc tài nguyên giao diện bị lỗi hiển thị, không tải được ảnh.|5 phút | 15 phút (lạnh)/2 phút (ấm)|RPO đạt 5 phút dựa trên cơ chế tự sao chép của Azure (dù không cam kết độ trễ cố định, thực tế đo đạc ngày 24/10 ghi nhận mức p95 là 129 giây) |
| Cấu hình triển khai |Không thể dừng lại các pod/service, dịch vụ nhưng hoàn toàn, không thể điều phối ứng dụng trên Kubernetes |1 giờ |15 phút (lạnh)/0 (sẵn ở cụm dự phòng) |RPO đạt 1 giờ do công cụ Velero thực hiện việc sao lưu định kỳ mỗi giờ, kết hợp với các file cấu hình gốc đã được quản lý và lưu trữ trực tiếp trong hệ thống Git |
|Web |Toàn bộ hệ thống website ngừng cung cấp dịch vụ cho người dùng |1 giờ |60 phút (lạnh)/10 phút (ấm) |Mức độ mất dữ liệu tối đa của website phụ thuộc vào thành phần có chu kỳ sao lưu lâu nhất là Cấu hình Kubernetes (1 giờ), kết hợp cùng Cơ sở dữ liệu bài viết và Kho ảnh có RPO là 5 phút. |
## Chiến lược phục hồi được chọn và lý do

Cách lạnh (Cold Standby): Thời gian khôi phục lâu hơn (RTO của web lên tới 60 phút) do cần thời gian phát hiện sự cố, đưa ra quyết định, tiến hành dựng lại hạ tầng từ đầu và thực hiện cấu hình đổi tên miền (DNS)
Cách ấm (Warm Standby): Thời gian khôi phục được rút ngắn đáng kể (RTO của web giảm xuống còn 10 phút, cấu hình Kubernetes sẵn sàng ở cụm dự phòng) nhờ vào hạ tầng dự phòng đã được chuẩn bị sẵn sàng từ trước.
Hệ thống thiết lập hai chiến lược phục hồi mô hình dự phòng cách lạnh và cách ấm cho các thành phần chính:
Cơ sở dữ liệu bài viết Sử dụng chiến lược sao lưu nhật ký thay đổi (WAL - Write-Ahead Logging). Nhật ký WAL được gửi đi liên tục với độ trễ tối đa chỉ 1 phút, đảm bảo dữ liệu giao dịch/bài viết không bị thất thoát đáng kể khi gặp sự cố
Kho ảnh sử dụng chiến lược tự sao chép sẵn có của đám mây Azure. 
Cấu hình triển khai (Kubernetes) Sử dụng chiến lược sao lưu tự động bằng Velero kết hợp quản lý mã nguồn qua Git (GitOps). Velero thực hiện sao lưu định kỳ theo chu kỳ mỗi giờ. Các file cấu hình gốc (manifests/helm charts) đều đã được lưu trữ an toàn trong Git, cho phép khôi phục nhanh hoặc triển khai lại lên cụm dự phòng gần như tức thì (RTO = 0 đối với cách ấm)
Nên chọn cách âm thay vì cách lạnh cho cả web, Phương án cách ấm giảm RTO của toàn website từ 60 phút xuống còn 10 phút. Do thời gian phục hồi website bắt buộc phải cộng thêm các bước thực tế (phát hiện sự cố, ra quyết định, dựng hạ tầng và đổi DNS), việc chuẩn bị sẵn cụm dự phòng (cách ấm) giúp tối ưu hóa tối đa thời gian gián đoạn dịch vụ đối với người dùng.
