# Cơ sở lý thuyết

Người viết: Huong-19. Nguồn chính: Bài giảng Chương 4; NIST SP 800-34 Rev. 1, "Contingency Planning Guide for Federal Information Systems" (2010); tài liệu Velero (https://velero.io/docs/).

Đề tài yêu cầu báo cáo các nội dung sau.

## 1. Đánh giá ảnh hưởng và mục tiêu phục hồi

- Business impact analysis (đánh giá ảnh hưởng nghiệp vụ)
- RPO: lượng dữ liệu tối đa được phép mất
- RTO: thời gian ngừng tối đa được phép
- Thời hạn giữ bản sao lưu (retention)
- Quy tắc sao lưu 3-2-1

## 2. Các chiến lược dự phòng và chi phí

- Pilot light
- Warm standby
- Active-passive
- Active-active
- So sánh chi phí để duy trì mỗi mức sẵn sàng

## 3. Sao lưu đúng cách

- Sao lưu nhất quán ở mức ứng dụng
- Snapshot nhất quán của cơ sở dữ liệu
- Bản sao lưu không thể sửa, xóa (immutability)
- Mã hóa bản sao lưu

## 4. Quy trình khi có thảm họa

- Runbook (hướng dẫn khôi phục từng bước)
- Ai có quyền tuyên bố thảm họa và kích hoạt khôi phục
- Truyền thông trong lúc sự cố
- Kiểm thử định kỳ kế hoạch phục hồi
